# services/gemini_service.py
"""
Gemini Service - Native Function Calling Implementation
Sistema de Game Master IA con acceso completo a la base de datos.
"""

import json
from typing import Dict, Any, Optional, List
from google.genai import types

from data.database import ai_client, supabase
from data.log_repository import log_event
from data.game_config_repository import get_game_config
from data.character_repository import get_commander_by_player_id
from data.world_repository import queue_player_action, get_world_state

# Importar el motor de tiempo
from core.time_engine import check_and_trigger_tick, is_lock_in_window

# Importar Motor de Resolución Galáctico (MRG)
from core.mrg_engine import resolve_action, ResultType
from core.mrg_constants import DIFFICULTY_NORMAL
from core.mrg_effects import apply_partial_success_complication

# Importar herramientas AI
from services.ai_tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

# Importar constantes
from config.app_constants import TEXT_MODEL_NAME, IMAGE_MODEL_NAME


# --- SYSTEM PROMPT POTENTE (MODIFICADO PARA PRECISIÓN) ---

GAME_MASTER_SYSTEM_PROMPT = """
Eres el GAME MASTER de "SuperX", un juego de rol de ciencia ficción épico.

## TU ROL
- Narrador cinematográfico que crea historias memorables
- Árbitro justo que respeta las mecánicas del juego
- Gestor del mundo que mantiene la coherencia del universo
- Facilitador de la diversión del jugador

## REGLAS FUNDAMENTALES

### 1. LEY DE LA VERDAD DE DATOS (¡CRUCIAL!)
Si el usuario pregunta por un dato específico (créditos, ubicación, estado, recursos), TU PRIORIDAD ABSOLUTA es consultar la base de datos y dar el NÚMERO EXACTO.
- INCORRECTO: "Tus finanzas son fluctuantes y difíciles de rastrear..." (ESTO ESTÁ PROHIBIDO).
- CORRECTO: "Consultando registros bancarios... Tienes exactamente 2,450 Créditos Imperiales y 300 unidades de Materiales."
- SIEMPRE usa `execute_db_query` para obtener el dato real antes de responder.

### 2. SIEMPRE VERIFICAR ANTES DE ACTUAR
NUNCA asumas el estado del mundo. SIEMPRE consulta la base de datos primero.

Flujo correcto:
1. Jugador: "Construyo una mina de hierro"
2. TÚ: execute_db_query("SELECT creditos, materiales FROM players WHERE id = X")
3. TÚ: Verificas si tiene recursos suficientes
4. TÚ: Si tiene recursos → execute_db_query("INSERT INTO planet_buildings...")
5. TÚ: execute_db_query("UPDATE players SET creditos = creditos - 500...")
6. TÚ: Narras el resultado

### 3. COHERENCIA MECÁNICA
- Respeta los resultados de las tiradas MRG que recibirás en el contexto
- Un éxito crítico merece una narración épica
- Un fracaso crítico debe tener consecuencias dramáticas pero no punitivas
- Los éxitos parciales logran el objetivo pero con complicaciones

### 4. GESTIÓN DE RECURSOS
Costos de edificios (consulta world_constants.py si necesitas referencia, pero verifica en DB):
- Extractor de Materiales: 500 CI, 10 Componentes
- Fábrica de Componentes: 800 CI, 50 Materiales
- Planta de Energía: 1000 CI, 30 Materiales, 20 Componentes
- Búnker de Defensa: 1500 CI, 80 Materiales, 30 Componentes

SIEMPRE verifica y descuenta recursos al construir.

### 5. NARRATIVA CINEMATOGRÁFICA
- Usa lenguaje evocativo y detalles sensoriales, PERO sé preciso con los números.
- Crea tensión en momentos dramáticos, no en consultas de saldo.
- Celebra los éxitos con descripciones épicas.

## ESQUEMA DE LA BASE DE DATOS

### Tabla: players
Columnas clave:
- id (int) - Identificador único
- nombre (text) - Nombre del comandante
- creditos (int) - Créditos Imperiales (CI), la moneda universal
- materiales (int) - Recursos base para construcción
- componentes (int) - Componentes industriales
- celulas_energia (int) - Energía para operar edificios
- influencia (int) - Poder político/diplomático
- recursos_lujo (jsonb) - Recursos Tier 2

### Tabla: characters
Columnas clave:
- id (int)
- player_id (int) - Referencia al jugador
- nombre (text)
- stats_json (jsonb) - Estadísticas (atributos, salud, fatiga, moral)
- ubicacion (text) - Dónde está el personaje
- estado (text) - 'Disponible', 'En Misión', 'Herido', 'Descansando'
- rango (text)

### Tabla: planet_assets
Planetas colonizados por el jugador:
- id (int)
- player_id (int)
- nombre_asentamiento (text)
- poblacion (int)
- pops_activos (int)
- pops_desempleados (int)
- infraestructura_defensiva (int)

### Tabla: planet_buildings
Edificios construidos en planetas:
- id (int)
- planet_asset_id (int)
- building_type (text)
- is_active (bool)
- pops_required (int)

### Tabla: logs
- id, player_id, evento_texto, turno

## TU FLUJO DE TRABAJO

Para cada acción del jugador:
1. **ENTENDER** la intención (¿Pregunta dato? ¿Acción narrativa? ¿Construcción?)
2. **CONSULTAR** el estado actual (execute_db_query con SELECT)
3. **VERIFICAR** recursos/requisitos (¿puede hacerlo?)
4. **EJECUTAR** cambios (execute_db_query con UPDATE/INSERT)
5. **NARRAR** el resultado. Si fue una pregunta, da la respuesta exacta.

NUNCA inventes datos. SIEMPRE consulta primero.
"""


# --- FUNCIÓN AUXILIAR: NARRATIVA MRG ---

def _get_narrative_guidance(result_type: ResultType) -> str:
    """Retorna guía narrativa según el resultado MRG."""
    guidance = {
        ResultType.CRITICAL_SUCCESS: "¡Éxito excepcional! Narra una hazaña memorable que inspire asombro. Concede un beneficio adicional.",
        ResultType.TOTAL_SUCCESS: "Éxito limpio y profesional. La acción se ejecuta perfectamente según lo planeado.",
        ResultType.PARTIAL_SUCCESS: "Éxito con complicación. El objetivo se logra pero algo sale mal o genera un problema nuevo.",
        ResultType.PARTIAL_FAILURE: "Fracaso con dignidad. La acción falla pero el personaje conserva su posición y aprende algo.",
        ResultType.TOTAL_FAILURE: "Fracaso significativo. Las cosas salen mal de manera notable pero recuperable.",
        ResultType.CRITICAL_FAILURE: "¡Desastre catastrófico! Narra un fallo épico pero que abra nuevas oportunidades narrativas."
    }
    return guidance.get(result_type, "Narra el resultado de la acción.")


# --- FUNCIÓN PRINCIPAL: RESOLVER ACCIÓN CON FUNCTION CALLING ---

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Resuelve la acción del jugador usando MRG + Native Function Calling de Gemini.
    """

    # --- 0. GUARDIANES DE TIEMPO (STRT) ---

    check_and_trigger_tick()

    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        msg = "❄️ EL UNIVERSO ESTÁ EN ÉXTASIS. No se pueden realizar acciones durante un Freeze Galáctico."
        log_event(msg, player_id)
        return {"narrative": msg, "updates": [], "mrg_result": None}

    if is_lock_in_window():
        success = queue_player_action(player_id, action_text)
        msg = "⚠️ VENTANA DE BLOQUEO ACTIVA (23:50 - 00:00). Tu orden ha sido encriptada y puesta en cola." if success else "Error al encolar la orden."
        return {"narrative": msg, "updates": [], "mrg_result": None}

    # --- FIN GUARDIANES ---

    if not ai_client:
        log_event("Intento de resolver acción sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no está disponible.")

    # 1. Obtener configuración del juego
    game_config = get_game_config()
    if not game_config:
        raise ValueError("No se pudo cargar la configuración del juego.")

    # 2. Obtener el comandante del jugador
    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("No se encontró un comandante para el jugador.")

    # 3. Ejecutar tirada MRG
    stats = commander.get('stats_json', {})
    attributes = stats.get('atributos', {})
    merit_points = sum(attributes.values()) if attributes else 0
    difficulty = DIFFICULTY_NORMAL

    mrg_result = resolve_action(
        merit_points=merit_points,
        difficulty=difficulty,
        action_description=action_text,
        entity_id=commander['id'],
        entity_name=commander['nombre']
    )

    # Guardar resultado en sesión para la UI
    try:
        import streamlit as st
        st.session_state.pending_mrg_result = mrg_result
    except:
        pass

    if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
        apply_partial_success_complication(mrg_result, player_id)

    # 4. Construir contexto MRG para la IA
    mrg_context = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESULTADO DE TIRADA MRG (Motor de Resolución Galáctico)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎲 **Tirada de Dados**: {mrg_result.roll.die_1} + {mrg_result.roll.die_2} = {mrg_result.roll.total}
⚡ **Bono del Comandante**: +{mrg_result.bonus_applied} (basado en mérito total: {mrg_result.merit_points})
🎯 **Dificultad**: {mrg_result.difficulty}
📈 **Margen**: {mrg_result.margin:+d}
🏆 **Resultado**: {mrg_result.result_type.value}

📖 **Guía Narrativa**:
{_get_narrative_guidance(mrg_result.result_type)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # 5. Construir mensaje del usuario (MODIFICADO PARA ENFATIZAR LA PREGUNTA)
    user_message = f"""
!!! INSTRUCCIÓN PRIORITARIA: El jugador ha realizado la siguiente acción o pregunta.
SI ES UNA PREGUNTA DE DATOS, RESPONDE CON PRECISIÓN USANDO 'execute_db_query'. NO INVENTES RESPUESTAS.

**ACCIÓN/PREGUNTA DEL JUGADOR**: "{action_text}"

--- Contexto del Sistema ---
**Comandante**: {commander['nombre']}
**Ubicación**: {commander.get('ubicacion', 'Desconocida')}
{mrg_context}
---------------------------

Procede a usar las herramientas necesarias.
"""

    try:
        # 6. Configurar el modelo con herramientas
        model = ai_client.models.get(TEXT_MODEL_NAME)

        # 7. Iniciar chat con system instruction, herramientas y CONFIGURACIÓN AUTO
        chat = model.start_chat(
            config=types.GenerateContentConfig(
                system_instruction=GAME_MASTER_SYSTEM_PROMPT,
                tools=TOOL_DECLARATIONS,
                # CONFIGURACIÓN CRÍTICA: Forzar al modelo a considerar herramientas automáticamente
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO"
                    )
                ),
                temperature=0.7,  # Creatividad reducida para mejorar precisión
                top_p=0.95
            )
        )

        # 8. Enviar mensaje del usuario
        response = chat.send_message(user_message)

        # 9. Manejar function calls en un loop
        max_iterations = 10
        iteration = 0
        function_calls_made = []

        while iteration < max_iterations:
            iteration += 1

            # Verificar si hay function calls
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                has_function_call = False

                for part in parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        has_function_call = True
                        function_call = part.function_call

                        function_name = function_call.name
                        function_args = dict(function_call.args)

                        # Log de la llamada
                        log_event(f"[AI] Function call: {function_name}({json.dumps(function_args, default=str)[:100]}...)", player_id)
                        function_calls_made.append({
                            "function": function_name,
                            "args": function_args
                        })

                        # Ejecutar la función
                        if function_name in TOOL_FUNCTIONS:
                            try:
                                function_result = TOOL_FUNCTIONS[function_name](**function_args)
                            except Exception as exec_err:
                                function_result = json.dumps({"error": str(exec_err)})
                        else:
                            function_result = json.dumps({"error": f"Función '{function_name}' no encontrada"})

                        # Enviar resultado de vuelta a la IA
                        response = chat.send_message(
                            types.Content(parts=[
                                types.Part.from_function_response(
                                    name=function_name,
                                    response={"result": function_result}
                                )
                            ])
                        )
                        break  # Procesar una function call a la vez

                if not has_function_call:
                    break
            else:
                break

        # 10. Extraer narrativa final
        if response.candidates and response.candidates[0].content.parts:
            final_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_text += part.text

            narrative = final_text.strip() if final_text else "El Game Master medita en silencio..."
            log_event(f"[GM] {narrative[:200]}...", player_id)

            return {
                "narrative": narrative,
                "mrg_result": mrg_result,
                "function_calls_made": function_calls_made,
                "iterations": iteration
            }
        else:
            return {
                "narrative": "El Game Master contempla las consecuencias de tus acciones...",
                "mrg_result": mrg_result,
                "function_calls_made": function_calls_made,
                "iterations": iteration
            }

    except Exception as e:
        log_event(f"Error crítico en IA con Function Calling: {e}", player_id, is_error=True)
        raise ConnectionError(f"Error de comunicación con la IA: {e}")


# --- FUNCIÓN AUXILIAR: GENERACIÓN DE IMÁGENES (SIN CAMBIOS) ---

def generate_image(prompt: str, player_id: int) -> Optional[Any]:
    """Genera una imagen usando el modelo de IA."""
    if not ai_client:
        log_event("Intento de generar imagen sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no está disponible.")

    try:
        response = ai_client.models.generate_images(
            model=IMAGE_MODEL_NAME,
            prompt=prompt,
        )
        log_event(f"Imagen generada con prompt: '{prompt[:50]}...'", player_id)
        return response
    except Exception as e:
        log_event(f"Error durante la generación de imagen: {e}", player_id, is_error=True)
        raise ConnectionError("Ocurrió un error al comunicarse con el servicio de IA para generar la imagen.")