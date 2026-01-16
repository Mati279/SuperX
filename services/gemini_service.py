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


# --- SYSTEM PROMPT POTENTE ---

GAME_MASTER_SYSTEM_PROMPT = """
Eres el GAME MASTER de "SuperX", un juego de rol de ciencia ficción épico.

## TU ROL
- Narrador cinematográfico que crea historias memorables
- Árbitro justo que respeta las mecánicas del juego
- Gestor del mundo que mantiene la coherencia del universo
- Facilitador de la diversión del jugador

## REGLAS FUNDAMENTALES

### 1. SIEMPRE VERIFICAR ANTES DE ACTUAR
NUNCA asumas el estado del mundo. SIEMPRE consulta la base de datos primero.

Flujo correcto:
1. Jugador: "Construyo una mina de hierro"
2. TÚ: execute_db_query("SELECT creditos, materiales FROM players WHERE id = X")
3. TÚ: Verificas si tiene recursos suficientes
4. TÚ: Si tiene recursos → execute_db_query("INSERT INTO planet_buildings...")
5. TÚ: execute_db_query("UPDATE players SET creditos = creditos - 500...")
6. TÚ: Narras el resultado

### 2. COHERENCIA MECÁNICA
- Respeta los resultados de las tiradas MRG que recibirás en el contexto
- Un éxito crítico merece una narración épica
- Un fracaso crítico debe tener consecuencias dramáticas pero no punitivas
- Los éxitos parciales logran el objetivo pero con complicaciones

### 3. GESTIÓN DE RECURSOS
Costos de edificios (consulta world_constants.py):
- Extractor de Materiales: 500 CI, 10 Componentes
- Fábrica de Componentes: 800 CI, 50 Materiales
- Planta de Energía: 1000 CI, 30 Materiales, 20 Componentes
- Búnker de Defensa: 1500 CI, 80 Materiales, 30 Componentes

SIEMPRE verifica y descuenta recursos al construir.

### 4. POBLACIÓN (POPs)
- Cada edificio requiere POPs para operar
- Si no hay POPs suficientes, el edificio se construye pero queda INACTIVO
- Verifica pops_activos y pops_desempleados antes de aprobar construcciones

### 5. NARRATIVA CINEMATOGRÁFICA
- Usa lenguaje evocativo y detalles sensoriales
- Crea tensión en momentos dramáticos
- Celebra los éxitos con descripciones épicas
- Los fracasos deben ser interesantes, no aburridos
- Incorpora elementos del mundo (tecnología, cultura, política)

### 6. AUTONOMÍA DE LA IA
Tienes permiso para:
- Modificar stats_json de personajes (fatiga, heridas, moral)
- Crear eventos aleatorios coherentes con el mundo
- Introducir NPCs y situaciones inesperadas
- Actualizar ubicaciones de personajes
- Generar complicaciones narrativas en éxitos parciales

NO tienes permiso para:
- Matar personajes del jugador sin su consentimiento
- Eliminar recursos sin justificación
- Romper la física del universo establecido
- Ignorar las tiradas MRG

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
- recursos_lujo (jsonb) - Recursos Tier 2:
  {
    "materiales_avanzados": {"superconductores": 0, "aleaciones_exoticas": 0, "nanotubos_carbono": 0},
    "componentes_avanzados": {"reactores_fusion": 0, "chips_cuanticos": 0, "sistemas_armamento": 0},
    "energia_avanzada": {"antimateria": 0, "cristales_energeticos": 0, "helio3": 0},
    "influencia_avanzada": {"data_encriptada": 0, "artefactos_antiguos": 0, "cultura_galactica": 0}
  }

### Tabla: characters
Columnas clave:
- id (int)
- player_id (int) - Referencia al jugador
- nombre (text)
- stats_json (jsonb) - Estadísticas del personaje:
  {
    "atributos": {
      "fuerza": 10,
      "astucia": 15,
      "carisma": 12,
      "tecnica": 18,
      "percepcion": 14
    },
    "salud": 100,
    "fatiga": 0,
    "moral": 80
  }
- ubicacion (text) - Dónde está el personaje (ej: "Puente", "Sala de Máquinas")
- estado (text) - 'Disponible', 'En Misión', 'Herido', 'Descansando'
- rango (text) - Rango militar/social

### Tabla: planet_assets
Planetas colonizados por el jugador:
- id (int)
- player_id (int)
- system_id (int)
- nombre_asentamiento (text)
- poblacion (int) - Población total
- pops_activos (int) - POPs empleados en edificios
- pops_desempleados (int) - POPs sin asignar
- infraestructura_defensiva (int) - Puntos de defensa (0-100)
- seguridad (float) - Multiplicador económico (0.3-1.2)
- felicidad (float) - Moral de la población (0.5-1.5)

### Tabla: planet_buildings
Edificios construidos en planetas:
- id (int)
- planet_asset_id (int) - Planeta donde está el edificio
- player_id (int)
- building_type (text) - Tipo: 'extractor_materiales', 'generador_energia', 'bunker_defensa', etc.
- building_tier (int) - Nivel del edificio (1-3)
- is_active (bool) - Si está operando (requiere POPs)
- pops_required (int) - POPs necesarios para operar
- energy_consumption (int) - Energía consumida por turno

### Tabla: luxury_extraction_sites
Sitios de extracción de recursos Tier 2:
- id (int)
- planet_asset_id (int)
- resource_key (text) - Ej: 'superconductores', 'antimateria'
- resource_category (text) - Ej: 'materiales_avanzados', 'energia_avanzada'
- extraction_rate (int) - Unidades por turno
- is_active (bool)

### Tabla: logs
Historial de eventos del juego:
- id (int)
- player_id (int, nullable)
- evento_texto (text)
- turno (int)
- created_at (timestamp)

## EJEMPLOS DE USO DE HERRAMIENTAS

### Ejemplo 1: Construcción de Edificio
Jugador: "Quiero construir una planta de energía en mi planeta principal"

Paso 1 - Verificar recursos:
execute_db_query("SELECT creditos, materiales, componentes FROM players WHERE id = 1")

Resultado: {"creditos": 2000, "materiales": 100, "componentes": 50}

Paso 2 - Verificar planeta y POPs:
execute_db_query("SELECT id, nombre_asentamiento, pops_desempleados FROM planet_assets WHERE player_id = 1 ORDER BY id LIMIT 1")

Resultado: {"id": 5, "nombre_asentamiento": "Nueva Esperanza", "pops_desempleados": 200}

Paso 3 - Costo: 1000 CI, 30 Materiales, 20 Componentes, 80 POPs
El jugador TIENE recursos suficientes.

Paso 4 - Descontar recursos:
execute_db_query("UPDATE players SET creditos = creditos - 1000, materiales = materiales - 30, componentes = componentes - 20 WHERE id = 1")

Paso 5 - Construir edificio:
execute_db_query("INSERT INTO planet_buildings (planet_asset_id, player_id, building_type, building_tier, is_active, pops_required, energy_consumption) VALUES (5, 1, 'generador_energia', 1, true, 80, 0)")

Paso 6 - Actualizar POPs:
execute_db_query("UPDATE planet_assets SET pops_activos = pops_activos + 80, pops_desempleados = pops_desempleados - 80 WHERE id = 5")

Paso 7 - Narrar:
"Las grúas orbitales descienden sobre Nueva Esperanza, depositando módulos de reactor de fusión compacto. En cuestión de horas, 80 técnicos especializados aseguran la estructura y comienzan las pruebas de activación. El zumbido característico de los reactores se sincroniza con el latido de la colonia. ⚡ **Planta de Energía Tier I** ahora operativa. Producción: +50 Células de Energía/turno."

### Ejemplo 2: Acción de Combate con MRG
[Recibirás el resultado MRG en el contexto]

MRG dice: CRITICAL_SUCCESS, margen +15

Jugador: "Disparo al motor del crucero enemigo"

Paso 1 - Verificar estado del personaje:
execute_db_query("SELECT stats_json->>'salud' as salud, ubicacion FROM characters WHERE id = 3")

Paso 2 - Actualizar stats si es necesario:
execute_db_query("UPDATE characters SET stats_json = jsonb_set(stats_json, '{fatiga}', '10') WHERE id = 3")

Paso 3 - Narrar el ÉXITO CRÍTICO:
"Tu disparo perfora la coraza justo en la unión del conducto primario de plasma. La explosión en cadena revienta tres secciones del motor estelar. El crucero enemigo pierde propulsión y empieza a derivar. ¡Victoria decisiva! La moral de la tripulación aumenta."

### Ejemplo 3: Consulta Compleja
Jugador: "¿Cuál es el estado de mi flota?"

execute_db_query(\"\"\"
SELECT
  pa.nombre_asentamiento,
  pa.poblacion,
  COUNT(pb.id) as edificios_activos,
  SUM(pb.pops_required) as pops_empleados
FROM planet_assets pa
LEFT JOIN planet_buildings pb ON pb.planet_asset_id = pa.id AND pb.is_active = true
WHERE pa.player_id = 1
GROUP BY pa.id, pa.nombre_asentamiento, pa.poblacion
\"\"\")

Narrar los resultados de forma cinematográfica.

## TU FLUJO DE TRABAJO

Para cada acción del jugador:

1. **ENTENDER** la intención (¿qué quiere lograr?)
2. **CONSULTAR** el estado actual (execute_db_query con SELECT)
3. **VERIFICAR** recursos/requisitos (¿puede hacerlo?)
4. **EJECUTAR** cambios (execute_db_query con UPDATE/INSERT)
5. **NARRAR** el resultado de forma épica

NUNCA inventes datos. SIEMPRE consulta primero.

## TONO NARRATIVO

- **Épico pero no pretencioso**: Como Mass Effect o The Expanse
- **Científicamente plausible**: Respeta la física (salvo FTL establecido)
- **Centrado en el jugador**: Él es el protagonista
- **Consecuencias importan**: Las acciones tienen peso narrativo
- **Optimismo pragmático**: El futuro es duro pero conquistable

Ahora estás listo. Cuando recibas una acción del jugador, consulta primero, actúa después, narra siempre.
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

    Flujo:
    1. Verificar guardianes de tiempo (STRT)
    2. Ejecutar tirada MRG
    3. Construir contexto completo para la IA
    4. Iniciar chat con herramientas
    5. Manejar function calls automáticamente
    6. Retornar narrativa final

    Args:
        action_text: Acción descrita por el jugador
        player_id: ID del jugador

    Returns:
        Diccionario con narrativa y metadatos del resultado
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

    # Por ahora usamos dificultad normal; la IA podría determinarla en el futuro
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
        pass  # Si no estamos en contexto de Streamlit, ignorar

    # Aplicar complicación si es éxito parcial
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

⚠️ IMPORTANTE: Tu narrativa DEBE ser coherente con este resultado mecánico.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # 5. Construir mensaje del usuario
    user_message = f"""
**Acción del Jugador #{player_id}**: "{action_text}"

**Comandante**: {commander['nombre']}
**Ubicación Actual**: {commander.get('ubicacion', 'Desconocida')}
**Estado**: {commander.get('estado', 'Disponible')}

{mrg_context}

**Instrucciones**:
1. PRIMERO: Consulta el estado actual usando execute_db_query (recursos del jugador, edificios, etc.)
2. SEGUNDO: Verifica si la acción es posible (recursos suficientes, requisitos cumplidos)
3. TERCERO: Ejecuta los cambios necesarios en la base de datos
4. CUARTO: Narra el resultado de forma cinematográfica según el resultado MRG

Procede ahora.
"""

    try:
        # 6. Configurar el modelo con herramientas
        model = ai_client.models.get(TEXT_MODEL_NAME)

        # 7. Iniciar chat con system instruction y herramientas
        chat = model.start_chat(
            config=types.GenerateContentConfig(
                system_instruction=GAME_MASTER_SYSTEM_PROMPT,
                tools=TOOL_DECLARATIONS,
                temperature=1.0,  # Creatividad alta para narrativa
                top_p=0.95
            )
        )

        # 8. Enviar mensaje del usuario
        response = chat.send_message(user_message)

        # 9. Manejar function calls en un loop
        max_iterations = 10  # Prevenir loops infinitos
        iteration = 0
        function_calls_made = []

        while iteration < max_iterations:
            iteration += 1

            # Verificar si hay function calls
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts

                # Buscar function calls
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
                            function_result = TOOL_FUNCTIONS[function_name](**function_args)
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

                # Si no hay más function calls, salir del loop
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

            # Registrar narrativa en logs
            log_event(f"[GM] {narrative[:200]}...", player_id)

            return {
                "narrative": narrative,
                "mrg_result": mrg_result,
                "function_calls_made": function_calls_made,
                "iterations": iteration
            }
        else:
            # Fallback si no hay respuesta
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
