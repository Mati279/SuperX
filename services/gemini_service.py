# services/gemini_service.py
"""
Servicio de Asistente Táctico IA.
Integración con Google Gemini para procesamiento de órdenes del comandante.

Características:
- Personalidad: Asistente Táctico (estilo Jarvis/Cortana/EDI)
- Protocolo de Niebla de Guerra (conocimiento limitado)
- Integración con Motor de Resolución Galáctico (MRG)
- Manejo robusto de Function Calling
"""

import json
from typing import Dict, Any, Optional, List
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
# La siguiente importación ahora funcionará correctamente
from core.mrg_constants import DIFFICULTY_NORMAL
from core.mrg_effects import apply_partial_success_complication

from services.ai_tools import TOOL_DECLARATIONS, execute_tool
from config.app_constants import TEXT_MODEL_NAME


# --- CONSTANTES DE CONFIGURACIÓN ---

MAX_TOOL_ITERATIONS = 10
AI_TEMPERATURE = 0.7
AI_MAX_TOKENS = 1024
AI_TOP_P = 0.95

# Palabras clave que indican consulta informativa (no requiere tirada MRG)
QUERY_KEYWORDS = [
    "cuantos", "cuántos", "que", "qué", "como", "cómo",
    "donde", "dónde", "quien", "quién", "estado", "listar",
    "ver", "info", "ayuda", "analisis", "análisis", "describir",
    "explicar", "mostrar"
]


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
3. **Ejecutar:** Usa herramientas si es necesario (consultas SQL limitadas, cálculos).
4. **Responder:** Informa el resultado con tu personalidad de IA Táctica.

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
    player_id: int # FIX: Añadido player_id explícito
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
                "player_id": self.player_id, # FIX: Expuesto al LLM
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

    Args:
        player_id: ID del jugador
        commander_data: Datos del comandante

    Returns:
        TacticalContext con información del estado actual
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

        # Obtener ubicación detallada (sistema, planeta, base)
        location_details = get_commander_location_display(commander_data['id'])

        return TacticalContext(
            player_id=player_id, # FIX
            commander_name=commander_data['nombre'],
            commander_location=commander_data.get('ubicacion', 'Desconocida'),
            attributes=attributes,
            resources=finances,
            known_planets=planet_summary,
            location_details=location_details
        )

    except Exception as e:
        return TacticalContext(
            player_id=player_id, # FIX
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

    Args:
        action_text: Texto de la acción

    Returns:
        True si es una consulta que no requiere tirada MRG
    """
    text_lower = action_text.lstrip().lower()

    # Si tiene signo de interrogación, es consulta
    if "?" in action_text:
        return True
    
    # Si es un comando interno de investigación, NO es consulta informativa (requiere tool)
    if "[INTERNAL_EXECUTE_INVESTIGATION]" in action_text:
        return False

    # Verificar palabras clave
    return any(text_lower.startswith(keyword) for keyword in QUERY_KEYWORDS)


def _process_function_calls(
    chat: Any,
    response: Any,
    max_iterations: int = MAX_TOOL_ITERATIONS
) -> tuple[Any, List[Dict[str, Any]]]:
    """
    Procesa las llamadas a funciones del modelo de forma iterativa.

    Args:
        chat: Sesión de chat activa
        response: Respuesta inicial del modelo
        max_iterations: Máximo de iteraciones permitidas

    Returns:
        Tupla (respuesta_final, lista_de_llamadas_realizadas)
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

    Args:
        response: Respuesta del modelo

    Returns:
        Texto narrativo o mensaje por defecto
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

    return narrative if narrative else "Orden procesada, Comandante."


# --- FUNCIÓN PRINCIPAL ---

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Resuelve una acción/orden del comandante usando el Asistente Táctico.

    Args:
        action_text: Texto de la orden del comandante
        player_id: ID del jugador

    Returns:
        Diccionario con narrative, mrg_result, y function_calls_made
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
        mrg_info_block = ">>> TIPO: SOLICITUD DE INFORMACIÓN O EJECUCIÓN INTERNA. No requiere tirada de habilidad externa."
    else:
        # Calcular puntos de mérito y resolver acción
        stats = commander.get('stats_json', {})
        attributes = stats.get('atributos', {})
        merit_points = sum(attributes.values()) if attributes else 0

        mrg_result = resolve_action(
            merit_points=merit_points,
            difficulty=DIFFICULTY_NORMAL,
            action_description=action_text
        )

        # Aplicar complicaciones si es éxito parcial
        if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
            apply_partial_success_complication(mrg_result, player_id)

        mrg_info_block = f"""
>>> REPORTE DE EJECUCIÓN FÍSICA (MRG):
- Resultado: {mrg_result.result_type.value}
- Detalle Técnico: Tirada {mrg_result.roll}
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
        
        # FIX: Preparar configuración de herramientas de forma segura
        # La API espera una lista de objetos Tool, no una lista directa de FunctionDeclaration.
        # Además, si TOOL_DECLARATIONS está vacío, no debemos enviar tool_config con modo AUTO.
        
        gemini_tools = None
        gemini_tool_config = None

        if TOOL_DECLARATIONS:
            # Envolvemos las declaraciones en un objeto Tool
            tool = types.Tool(function_declarations=TOOL_DECLARATIONS)
            gemini_tools = [tool]
            
            # Solo configuramos el modo AUTO si hay herramientas
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

    Returns:
        Diccionario con estado de conexión
    """
    container = get_service_container()
    return {
        "available": container.is_ai_available(),
        "error": container.status.ai_error
    }