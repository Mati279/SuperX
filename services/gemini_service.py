# services/gemini_service.py
"""
Gemini Service - Native Function Calling Implementation
Sistema de Game Master IA con acceso completo a la base de datos.
"""

import json
from typing import Dict, Any, Optional, List
from google.genai import types

from data.database import ai_client
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
- Si recibes un resultado MRG, respétalo.
- Si NO hay resultado MRG (porque fue una consulta simple), responde directamente sin inventar tiradas.

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

    # --- 3. DETECTOR DE CONSULTAS VS ACCIONES (NUEVO) ---
    # Si es una pregunta simple, NO tiramos dados MRG para evitar "Complicaciones" injustas.
    query_keywords = ["cuantos", "cuántos", "que", "qué", "como", "cómo", "donde", "dónde", "quien", "quién", "estado", "listar", "ver", "info", "ayuda", "tengo"]
    is_informational_query = any(action_text.lstrip().lower().startswith(k) for k in query_keywords) or "?" in action_text

    mrg_result = None
    mrg_context = ""

    if is_informational_query:
        # Es una consulta: Simulamos un éxito total automático (sin tirar dados)
        # Esto evita que apply_partial_success_complication reste recursos por preguntar la hora.
        class DummyRoll:
            total = 0
            die_1 = 0
            die_2 = 0
        
        class DummyResult:
            result_type = ResultType.TOTAL_SUCCESS # Éxito limpio
            roll = DummyRoll()
            bonus_applied = 0
            merit_points = 0
            difficulty = 0
            margin = 0
        
        mrg_result = DummyResult()
        mrg_context = "\nℹ️ TIPO DE ACCIÓN: Consulta de Datos (Resolución Automática: Éxito). Responde con precisión usando la DB.\n"
    
    else:
        # Es una acción real: Usamos el MRG
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

        # Si es éxito parcial, aplicamos complicación (SOLO si no era consulta)
        if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
            apply_partial_success_complication(mrg_result, player_id)

        # Construir contexto MRG real
        mrg_context = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESULTADO DE TIRADA MRG (Motor de Resolución Galáctico)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎲 Resultado: {mrg_result.result_type.value}
📖 Guía: {_get_narrative_guidance(mrg_result.result_type)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # Guardar resultado en sesión para la UI (si aplica)
    try:
        import streamlit as st
        st.session_state.pending_mrg_result = mrg_result
    except:
        pass

    # 4. Construir mensaje del usuario
    user_message = f"""
!!! INSTRUCCIÓN PRIORITARIA:
SI ES UNA PREGUNTA DE DATOS, RESPONDE CON PRECISIÓN USANDO 'execute_db_query'. NO INVENTES.

**ACCIÓN/PREGUNTA DEL JUGADOR**: "{action_text}"

--- Contexto del Sistema ---
**Comandante**: {commander['nombre']}
{mrg_context}
---------------------------

Procede a usar las herramientas necesarias.
"""

    try:
        # 5. Iniciar chat con herramientas (CORREGIDO PARA NUEVO SDK)
        # Usamos ai_client.chats.create en lugar de models.get().start_chat()
        chat = ai_client.chats.create(
            model=TEXT_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=GAME_MASTER_SYSTEM_PROMPT,
                tools=TOOL_DECLARATIONS,
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO"
                    )
                ),
                temperature=0.4 if is_informational_query else 0.8, # Más preciso si es consulta, más creativo si es acción
                top_p=0.95
            )
        )

        # 6. Enviar mensaje del usuario
        response = chat.send_message(user_message)

        # 7. Manejar function calls en un loop (ReAct Loop)
        max_iterations = 10
        iteration = 0
        function_calls_made = []

        while iteration < max_iterations:
            iteration += 1

            # Verificar si hay function calls (Estructura nuevo SDK)
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                has_function_call = False

                for part in parts:
                    if part.function_call:
                        has_function_call = True
                        function_call = part.function_call
                        
                        fname = function_call.name
                        fargs = function_call.args

                        # Log
                        log_event(f"[AI] Tool: {fname}", player_id)
                        function_calls_made.append({"function": fname, "args": fargs})

                        # Ejecutar
                        if fname in TOOL_FUNCTIONS:
                            try:
                                # Convertir args a dict python estándar
                                args_dict = {k: v for k, v in fargs.items()}
                                result_str = TOOL_FUNCTIONS[fname](**args_dict)
                            except Exception as e:
                                result_str = json.dumps({"error": str(e)})
                        else:
                            result_str = json.dumps({"error": "Función no encontrada"})

                        # Responder a la IA con el resultado
                        response = chat.send_message(
                            types.Part.from_function_response(
                                name=fname,
                                response={"result": result_str}
                            )
                        )
                        break # Procesar una llamada a la vez

                if not has_function_call:
                    break
            else:
                break

        # 8. Extraer narrativa final
        if response.candidates and response.candidates[0].content.parts:
            final_text = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    final_text += part.text
            
            narrative = final_text.strip()
            log_event(f"[GM] {narrative[:100]}...", player_id)
            
            return {
                "narrative": narrative,
                "mrg_result": mrg_result,
                "function_calls_made": function_calls_made
            }

        return {"narrative": "...", "mrg_result": mrg_result}

    except Exception as e:
        log_event(f"Error AI: {e}", player_id, is_error=True)
        return {"narrative": f"⚠️ Error de sistema: {e}", "mrg_result": None}


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