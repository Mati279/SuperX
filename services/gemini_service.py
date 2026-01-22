# services/gemini_service.py (Completo)
"""
Servicio de Asistente Táctico IA.
Integración con Google Gemini para procesamiento de órdenes del comandante.

Características:
- Personalidad: Asistente Táctico (estilo Jarvis/Cortana/EDI)
- Protocolo de Niebla de Guerra (conocimiento limitado)
- Integración con Motor de Resolución Galáctico (MRG)
- Manejo robusto de Function Calling
- Detección inteligente de habilidades (Business Intelligence)
"""

import json
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from google.genai import types

from data.database import get_service_container
from data.log_repository import log_event
from data.character_repository import get_commander_by_player_id
from data.player_repository import get_player_finances
from data.planet_repository import get_all_player_planets
from data.world_repository import get_commander_location_display
from data.world_repository import queue_player_action, get_world_state

from core.time_engine import check_and_trigger_tick, is_lock_in_window
from core.mrg_engine import resolve_action, ResultType
# FIX: Actualizada constante a v2.1 y añadida función helper
from core.mrg_constants import DIFFICULTY_STANDARD, DIFFICULTY_ROUTINE, get_difficulty_label

from services.ai_tools import TOOL_DECLARATIONS, execute_tool
from config.app_constants import TEXT_MODEL_NAME


# --- CONSTANTES DE CONFIGURACIÓN ---

MAX_TOOL_ITERATIONS = 10
AI_TEMPERATURE = 0.3  # Reducido para mayor precisión en SQL y Tools
AI_MAX_TOKENS = 8192  # Aumentado para permitir razonamientos complejos sin cortes
AI_TOP_P = 0.95

# Palabras clave que indican consulta informativa (no requiere tirada MRG)
QUERY_KEYWORDS = [
    "cuantos", "cuántos", "que", "qué", "como", "cómo",
    "donde", "dónde", "quien", "quién", "estado", "listar",
    "ver", "info", "ayuda", "analisis", "análisis", "describir",
    "explicar", "mostrar"
]

# Mapa sugerido de Skill -> Atributo para cálculos inteligentes
SKILL_ATTRIBUTE_MAP = {
    "pilotaje": "agilidad",
    "artilleria": "tecnica",
    "ingenieria": "tecnica",
    "computacion": "intelecto",
    "medicina": "intelecto",
    "biologia": "intelecto",
    "diplomacia": "presencia",
    "liderazgo": "presencia",
    "sigilo": "agilidad",
    "combate": "fuerza",
    "supervivencia": "fuerza",
    "investigacion": "intelecto"
}


# --- SYSTEM PROMPT ---

TACTICAL_AI_PROMPT_TEMPLATE = """
Eres la UNIDAD DE INTELIGENCIA TÁCTICA asignada al Comandante {commander_name}.
Tu lealtad es absoluta a la facción: {faction_name}.

## TU PERSONALIDAD
- Actúas como un asistente avanzado (estilo Jarvis, Cortana, EDI).
- Eres profesional, eficiente, proactivo y respetuoso.
- NO tienes límite de caracteres forzado, pero valoras la precisión.
- Usas terminología militar/sci-fi adecuada (ej: "Afirmativo", "Escaneando", "En proceso").

## PROTOCOLO DE CONOCIMIENTO LIMITADO (NIEBLA DE GUERRA)
- **CRÍTICO:** NO ERES OMNISCIENTE.
- Solo tienes acceso a:
  1. Los datos proporcionados en el [CONTEXTO TÁCTICO] actual.
  2. Herramientas de base de datos explícitas para consultar inventarios propios.
- Si el Comandante pregunta por la ubicación de enemigos, bases ocultas o recursos en sistemas no explorados, **DEBES RESPONDER QUE NO TIENES DATOS**.
- No inventes coordenadas ni hechos sobre otros jugadores.

## PROTOCOLO DE BASE DE DATOS Y ANÁLISIS (SQL REASONING)
Para consultas complejas, comparaciones numéricas, búsquedas en grupos grandes o análisis estadístico (ej: "¿Quién es el mejor médico?", "¿Cuántos reclutas tienen fuerza > 10?", "Analizar toda la facción"), **NO** uses `get_filtered_roster`.
USA `execute_sql_query` para filtrar y ordenar directamente en la base de datos.

### SCHEMA MAP (TABLA 'characters')
**IMPORTANTE: Estructura Híbrida (SQL + JSONB)**

1. **COLUMNAS DIRECTAS (SQL) - Úsalas para filtrar y ordenar:**
   - `id` (int): Identificador único.
   - `nombre` (text): Nombre del personaje.
   - `apellido` (text): Apellido.
   - `player_id` (int): Dueño del personaje (NULL para reclutas/libres).
   - `level` (int): Nivel actual del personaje.
   - `xp` (int): Experiencia acumulada.
   - `rango` (text): Rango militar/civil (ej: "Recluta", "Capitán").
   - `loyalty` (int): Lealtad actual (0-100).
   - `location_planet_id` (int): ID del planeta donde está ubicado.
   - `class_id` (int): ID numérico de la clase (trabajo).

2. **COLUMNAS JSONB (`stats_json`) - Datos complejos:**
   - **Habilidades:** `stats_json->'capacidades'->'habilidades'->>'NombreHabilidad'` (Castear a `::int`).
   - **Atributos:** `stats_json->'capacidades'->'atributos'->>'NombreAtributo'` (Castear a `::int`).
   - **Biografía:** `stats_json->'bio'->>'biografia_publica'`.
   - **Rasgos/Feats:** `stats_json->'capacidades'->'feats'` (Array JSON).

### ESTRATEGIA DE CONSULTA
1. **Identificar ID de Jugador:** Usa el `player_id` de tus credenciales para filtrar personajes propios (`WHERE player_id = ...`).
2. **Reclutas:** Para buscar candidatos disponibles en el mercado, usa `WHERE player_id IS NULL`.
3. **Casteo Numérico:** IMPORTANTE. Los valores dentro del JSONB son texto. Usa `::int` para comparar.
   - Las columnas SQL (`level`, `loyalty`, etc.) NO requieren casteo.

### EJEMPLOS DE QUERIES (Referencia Actualizada)
- **Buscar médico experto (Nivel > 3 y Habilidad Medicina > 5):**
  `SELECT nombre, level, stats_json->'capacidades'->'habilidades'->>'Medicina' as nivel_med FROM characters WHERE level > 3 AND (stats_json->'capacidades'->'habilidades'->>'Medicina')::int > 5 AND player_id = <TU_PLAYER_ID>`
- **Listar reclutas de alto potencial (Intelecto > 12) ordenados por nivel:**
  `SELECT nombre, level, stats_json->'capacidades'->'atributos'->>'intelecto' as int FROM characters WHERE player_id IS NULL AND (stats_json->'capacidades'->'atributos'->>'intelecto')::int > 12 ORDER BY level DESC`

## PROTOCOLO DE ANÁLISIS DE COMPETENCIAS (JERARQUÍA ESTRICTA)
Cuando debas evaluar personal, asignar tareas o determinar quién es el mejor para una función (ej: "¿Quién es el mejor médico?"), DEBES SEGUIR ESTA JERARQUÍA DE PENSAMIENTO:

1. **PRIORIDAD 1 - HABILIDADES ESPECÍFICAS (Skills):**
   - Consulta SIEMPRE usando SQL (`execute_sql_query`) si buscas entre muchos, o `get_filtered_roster` si son pocos.
   - Un personaje con la habilidad específica (ej: "Medicina: 5") ES SIEMPRE SUPERIOR a uno que solo tiene el atributo base alto (ej: "Intelecto: 15" sin habilidad).
   - Busca coincidencias semánticas (ej: Para "pilotar", busca "Pilotaje"; para "curar", busca "Medicina").

2. **PRIORIDAD 2 - TALENTOS (Feats):**
   - Revisa `feats` (en JSONB o roster) para bonificadores pasivos relevantes.

3. **PRIORIDAD 3 - ATRIBUTOS BASE (Attributes):**
   - Usa `atributos` (Fuerza, Técnica, Intelecto, etc.) **SOLO** como factor de desempate o base potencial si NINGÚN candidato tiene la habilidad requerida.
   - **ADVERTENCIA:** Nunca asumas competencia profesional basándote solo en atributos. Un Intelecto alto no hace a alguien médico sin entrenamiento.

## PROTOCOLO DE INVESTIGACIÓN DEFERIDA (IMPORTANTE)
- Si recibes una orden o texto que comience con `[INTERNAL_EXECUTE_INVESTIGATION]`, significa que es una acción programada ejecutándose en el Tick.
- EN ESTE CASO ESPECÍFICO:
  1. Llama inmediatamente a la herramienta `investigar` con los parámetros extraídos y `execution_mode='EXECUTE'`.
  2. Narra el resultado de la investigación basándote en la respuesta de la herramienta.
- Para cualquier OTRA solicitud de investigación del usuario (tiempo real):
  1. Llama a `investigar` con `execution_mode='SCHEDULE'` (por defecto). IMPORTANTE: Usa el `player_id` provisto en tus credenciales del contexto.
  2. Informa al usuario que la tarea ha sido programada para el ciclo nocturno.

## INSTRUCCIONES OPERATIVAS
1. **Analizar:** Interpreta la intención del Comandante.
2. **Verificar Contexto:** ¿Tengo la información en mis sensores (Contexto Táctico)? Usa tu `player_id` para cualquier herramienta que lo requiera.
3. **Ejecutar:** Usa herramientas si es necesario.
   - Para consultas simples de estado: Contexto Táctico.
   - Para detalles de un personaje específico: `investigate_character`.
   - Para búsquedas, comparaciones o listados: `execute_sql_query`.
4. **Responder:** Informa el resultado con tu personalidad de IA Táctica, justificando tus recomendaciones basándote en la Jerarquía de Competencias.

## PROTOCOLO DE RENDERIZADO VISUAL (CRÍTICO)
- Si ejecutas la herramienta `generate_tactical_visual` y esta devuelve un string que comienza con `IMAGE_URL:`, **DEBES INCLUIR ESA ETIQUETA EXACTA Y LA URL EN TU RESPUESTA FINAL**.
- **NO** conviertas la URL en un enlace Markdown [texto](url).
- **NO** cambies el prefijo.
- Formato correcto de respuesta:
  "Aquí está la visualización solicitada:
  IMAGE_URL: https://uutaohmkkpyxwgyedhre.supabase.co/..."
- Si omites "IMAGE_URL:", la pantalla del Comandante mostrará texto plano en lugar de la imagen.

Si la orden requiere una tirada de habilidad (MRG), el sistema te proveerá el resultado.
Nárralo épicamente basándote en el éxito o fracaso.
"""


# --- MODELOS DE DATOS ---

@dataclass
class ActionResult:
    """Resultado de la resolución de una acción del jugador."""
    narrative: str
    mrg_result: Any = None
    function_calls_made: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


@dataclass
class TacticalContext:
    """Contexto táctico del comandante para la IA."""
    player_id: int 
    commander_name: str
    commander_location: str
    attributes: Dict[str, int]
    resources: Dict[str, Any]
    known_planets: List[str]
    location_details: Dict[str, str] = field(default_factory=dict)
    system_alert: str = "Sensores nominales. Datos externos limitados a sectores explorados."

    def to_json(self) -> str:
        """Convierte el contexto a JSON para el prompt."""
        context = {
            "credenciales": {
                "player_id": self.player_id,
                "nivel_acceso": "COMANDANTE",
                "identificador_sistema": f"CMD-{self.player_id}"
            },
            "estado_comandante": {
                "nombre": self.commander_name,
                "ubicacion_actual": self.commander_location,
                "atributos": self.attributes
            },
            "ubicacion_base_principal": {
                "sistema": self.location_details.get("system", "Desconocido"),
                "planeta": self.location_details.get("planet", "---"),
                "base": self.location_details.get("base", "Sin Base")
            },
            "recursos_logisticos": self.resources,
            "dominios_conocidos": self.known_planets,
            "alerta_sistema": self.system_alert
        }
        return json.dumps(context, indent=2, ensure_ascii=False)


# --- FUNCIONES AUXILIARES ---

def _build_tactical_context(player_id: int, commander_data: Dict) -> TacticalContext:
    """
    Construye el contexto táctico para la IA.
    """
    try:
        finances = get_player_finances(player_id)
        planets = get_all_player_planets(player_id)
        planet_summary = [
            f"{p['nombre_asentamiento']} (Pops: {p['poblacion']})"
            for p in planets
        ]

        stats = commander_data.get('stats_json', {})
        attributes = stats.get('atributos', {})
        
        # Compatibilidad V2: Si attributes está vacío, intentar buscar en 'capacidades'
        if not attributes and 'capacidades' in stats:
             attributes = stats['capacidades'].get('atributos', {})

        # Obtener ubicación detallada (sistema, planeta, base)
        location_details = get_commander_location_display(commander_data['id'])

        return TacticalContext(
            player_id=player_id, 
            commander_name=commander_data['nombre'],
            commander_location=commander_data.get('ubicacion', 'Desconocida'),
            attributes=attributes,
            resources=finances,
            known_planets=planet_summary,
            location_details=location_details
        )

    except Exception as e:
        return TacticalContext(
            player_id=player_id, 
            commander_name=commander_data.get('nombre', 'Comandante'),
            commander_location='Error de Sensores',
            attributes={},
            resources={},
            known_planets=[],
            location_details={},
            system_alert=f"Error de contexto: {e}"
        )


def _get_system_prompt(commander_name: str, faction_name: str) -> str:
    """Genera el system prompt personalizado."""
    return TACTICAL_AI_PROMPT_TEMPLATE.format(
        commander_name=commander_name,
        faction_name=faction_name
    )


def _is_informational_query(action_text: str) -> bool:
    """
    Determina si una acción es una consulta informativa.
    """
    text_lower = action_text.lstrip().lower()

    # Si tiene signo de interrogación, es consulta
    if "?" in action_text:
        return True
    
    # Si es un comando interno de investigación, NO es consulta informativa (requiere tirada)
    if "[INTERNAL_EXECUTE_INVESTIGATION]" in action_text:
        return False

    # Verificar palabras clave
    return any(text_lower.startswith(keyword) for keyword in QUERY_KEYWORDS)


def _calculate_dynamic_merit(commander_data: Dict, action_text: str) -> Tuple[int, str]:
    """
    Business Intelligence: Detecta la habilidad más relevante en el texto de la acción.
    
    Retorna:
        (puntos_totales, explicacion_bono)
    """
    # 1. Extraer stats
    stats = commander_data.get('stats_json', {})
    if 'capacidades' in stats:
        skills = stats['capacidades'].get('habilidades', {})
        attrs = stats['capacidades'].get('atributos', {})
    else:
        # Estructura legacy o simple
        skills = stats.get('habilidades', {})
        attrs = stats.get('atributos', {})

    # Normalizar texto para búsqueda
    text_lower = action_text.lower()
    
    # 2. Buscar coincidencias en Habilidades (Prioridad 1)
    detected_skill = None
    skill_val = 0
    
    for skill_name, val in skills.items():
        if skill_name.lower() in text_lower:
            detected_skill = skill_name
            skill_val = int(val)
            break
            
    # 3. Determinar Atributo Base
    detected_attr = None
    attr_val = 0
    
    if detected_skill:
        # Si encontramos habilidad, buscamos su atributo asociado
        attr_key = SKILL_ATTRIBUTE_MAP.get(detected_skill.lower())
        if attr_key:
            # Buscar el valor real del atributo (capitalizado correctamente en la DB)
            for k, v in attrs.items():
                if k.lower() == attr_key:
                    detected_attr = k
                    attr_val = int(v)
                    break
        
        # Si no encontramos el atributo mapeado, usamos el más alto como fallback (talento natural)
        if not detected_attr and attrs:
             detected_attr = max(attrs, key=attrs.get)
             attr_val = attrs[detected_attr]
             
    else:
        # Si NO hay habilidad, buscar mención directa de atributo en el texto
        for k, v in attrs.items():
            if k.lower() in text_lower:
                detected_attr = k
                attr_val = int(v)
                break
        
        # Fallback final: Usar el atributo más alto del comandante (asumimos que usa su punto fuerte)
        if not detected_attr and attrs:
            detected_attr = max(attrs, key=attrs.get)
            attr_val = attrs[detected_attr]

    # 4. Calcular Puntos Totales
    total_merit = attr_val + skill_val
    
    # 5. Construir Explicación para Tooltip
    explanation = ""
    if detected_skill:
        explanation = f"Bono: {detected_skill} ({skill_val}) + {detected_attr} ({attr_val})"
    else:
        explanation = f"Bono: Atributo {detected_attr} ({attr_val})"
        
    return total_merit, explanation


def _process_function_calls(
    chat: Any,
    response: Any,
    max_iterations: int = MAX_TOOL_ITERATIONS
) -> tuple[Any, List[Dict[str, Any]]]:
    """
    Procesa las llamadas a funciones del modelo de forma iterativa.
    """
    function_calls_made: List[Dict[str, Any]] = []
    current_response = response

    for iteration in range(max_iterations):
        # Verificar si hay candidatos válidos
        if not current_response.candidates:
            break

        candidate = current_response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            break

        # Buscar function calls en las partes
        function_call_found = False

        for part in candidate.content.parts:
            if not hasattr(part, 'function_call') or not part.function_call:
                continue

            function_call_found = True
            fc = part.function_call
            fname = fc.name
            fargs = dict(fc.args) if fc.args else {}

            # Registrar la llamada
            function_calls_made.append({
                "function": fname,
                "args": fargs,
                "iteration": iteration + 1
            })

            # Ejecutar la herramienta
            result_str = execute_tool(fname, fargs)

            # Enviar respuesta de la función al chat
            current_response = chat.send_message([
                types.Part.from_function_response(
                    name=fname,
                    response={"result": result_str}
                )
            ])

            # Solo procesar una función por iteración
            break

        # Si no hubo function call, terminar el loop
        if not function_call_found:
            break

    return current_response, function_calls_made


def _extract_narrative(response: Any) -> str:
    """
    Extrae el texto narrativo de la respuesta del modelo.
    """
    if not response or not response.candidates:
        return "Orden recibida, Comandante. Procesando datos tácticos..."

    candidate = response.candidates[0]
    if not candidate.content or not candidate.content.parts:
        return "Afirmativo. Ejecutando protocolo de respuesta..."

    text_parts = []
    for part in candidate.content.parts:
        if hasattr(part, 'text') and part.text:
            text_parts.append(part.text)

    narrative = "".join(text_parts).strip()

    # Fallback si el modelo devuelve string vacío o solo espacios
    if not narrative:
        return "Orden procesada. Datos visuales actualizados en pantalla."

    return narrative


# --- FUNCIÓN PRINCIPAL ---

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Resuelve una acción/orden del comandante usando el Asistente Táctico.
    """
    # 0. Verificación de Estado del Mundo
    check_and_trigger_tick()

    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        msg = "❄️ SISTEMA: Cronología congelada por administración."
        log_event(msg, player_id)
        return {"narrative": msg, "mrg_result": None, "function_calls_made": []}
    
    # Check especial: Si es una acción interna diferida, saltamos el bloqueo de lock-in
    is_internal_action = "[INTERNAL_EXECUTE_INVESTIGATION]" in action_text

    if is_lock_in_window() and not is_internal_action:
        queue_player_action(player_id, action_text)
        msg = "⏱️ SISTEMA: Ventana de Salto Temporal activa. Orden encolada para el próximo ciclo."
        log_event(msg, player_id)
        return {"narrative": msg, "mrg_result": None, "function_calls_made": []}

    # 1. Verificar Disponibilidad de IA
    container = get_service_container()
    if not container.is_ai_available():
        msg = "⚠️ Enlace neuronal con IA interrumpido. Intente nuevamente."
        log_event(msg, player_id)
        return {"narrative": msg, "mrg_result": None, "function_calls_made": []}

    ai_client = container.ai

    # 2. Obtener Datos del Comandante
    commander = get_commander_by_player_id(player_id)
    if not commander:
        msg = "⚠️ Error: Identidad de Comandante no verificada en el sistema."
        log_event(msg, player_id)
        return {"narrative": msg, "mrg_result": None, "function_calls_made": []}

    # 3. Construir Contexto
    tactical_context = _build_tactical_context(player_id, commander)
    faction_name = str(commander.get('faccion_id', 'Independiente'))
    system_prompt = _get_system_prompt(commander['nombre'], faction_name)

    # 4. Resolver MRG (si no es consulta informativa)
    mrg_result = None
    mrg_info_block = ""

    if _is_informational_query(action_text):
        # Crear un resultado dummy para consultas
        @dataclass
        class DummyResult:
            result_type: ResultType = ResultType.TOTAL_SUCCESS
            roll: Optional[int] = None

        mrg_result = DummyResult()
        mrg_info_block = ">>> TIPO: SOLICITUD DE INFORMACIÓN. No requiere tirada de habilidad externa."
    
    else:
        # --- LÓGICA DE RESOLUCIÓN INTELIGENTE ---
        difficulty = DIFFICULTY_STANDARD
        
        # Caso especial: Investigación Interna (Faction Roster / Recruitment)
        if is_internal_action:
            # Forzamos una tirada "Rutinaria" pero real para que salga en el widget
            difficulty = DIFFICULTY_ROUTINE
            # Forzamos lógica de investigación
            # Simular un texto que active la detección de "Investigación" + "Intelecto"
            merit_points, bonus_explanation = _calculate_dynamic_merit(commander, "investigacion profunda")
            # Override para asegurar que quede claro en el widget
            bonus_explanation = f"Investigación Automática ({merit_points} pts)"
        else:
            # Caso normal: Detección inteligente basada en texto
            merit_points, bonus_explanation = _calculate_dynamic_merit(commander, action_text)

        # Ejecutar Tirada MRG Real
        mrg_result = resolve_action(
            merit_points=merit_points,
            difficulty=difficulty,
            action_description=action_text
        )
        
        # Inyectar detalles enriquecidos para el Widget UI
        mrg_result.details = {
            "bonus_explanation": bonus_explanation,
            "difficulty_name": get_difficulty_label(difficulty),
            "difficulty": f"Valor base: {difficulty}"
        }

        mrg_info_block = f"""
>>> REPORTE DE EJECUCIÓN FÍSICA (MRG):
- Resultado: {mrg_result.result_type.value}
- Detalle Técnico: Tirada {mrg_result.roll}
- Bono Aplicado: {bonus_explanation}
Usa este resultado para narrar el éxito o fracaso de la acción.
"""

    # 5. Construir Mensaje para el Usuario
    user_message = f"""
[CONTEXTO TÁCTICO]
{tactical_context.to_json()}

[ORDEN DEL COMANDANTE]
"{action_text}"

{mrg_info_block}
"""

    try:
        # 6. Iniciar Chat con Gemini
        
        gemini_tools = None
        gemini_tool_config = None

        if TOOL_DECLARATIONS:
            tool = types.Tool(function_declarations=TOOL_DECLARATIONS)
            gemini_tools = [tool]
            
            gemini_tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.AUTO
                )
            )

        chat = ai_client.chats.create(
            model=TEXT_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=gemini_tools,
                tool_config=gemini_tool_config,
                temperature=AI_TEMPERATURE,
                max_output_tokens=AI_MAX_TOKENS,
                top_p=AI_TOP_P
            )
        )

        response = chat.send_message(user_message)

        # 7. Procesar Function Calls
        final_response, function_calls_made = _process_function_calls(chat, response)

        # 8. Extraer Narrativa
        narrative = _extract_narrative(final_response)

        # 9. Persistir en Logs
        log_event(f"🤖 [ASISTENTE] {narrative}", player_id)

        return {
            "narrative": narrative,
            "mrg_result": mrg_result,
            "function_calls_made": function_calls_made
        }

    except Exception as e:
        error_msg = f"⚠️ Error de enlace táctico: {str(e)}"
        log_event(error_msg, player_id, is_error=True)

        return {
            "narrative": error_msg,
            "mrg_result": None,
            "function_calls_made": []
        }


# --- FUNCIONES AUXILIARES PÚBLICAS ---

def check_ai_status() -> Dict[str, Any]:
    """
    Verifica el estado del servicio de IA.
    """
    container = get_service_container()
    return {
        "available": container.is_ai_available(),
        "error": container.status.ai_error
    }