# services/gemini_service.py
import json
import logging
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
from core.mrg_constants import DIFFICULTY_NORMAL
from core.mrg_effects import apply_partial_success_complication

from services.ai_tools import TOOL_DECLARATIONS, execute_tool
from config.app_constants import TEXT_MODEL_NAME

# Configuración de logger
logger = logging.getLogger(__name__)

# --- CONSTANTES DE CONFIGURACIÓN ---
MAX_TOOL_ITERATIONS = 8 # Reducido ligeramente para evitar timeouts de Streamlit
AI_TEMPERATURE = 0.2
AI_MAX_TOKENS = 4096
AI_TOP_P = 0.95

QUERY_KEYWORDS = [
    "cuantos", "cuántos", "que", "qué", "como", "cómo",
    "donde", "dónde", "quien", "quién", "estado", "listar",
    "ver", "info", "ayuda", "analisis", "análisis", "describir",
    "explicar", "mostrar"
]

TACTICAL_AI_PROMPT_TEMPLATE = """
Eres la UNIDAD DE INTELIGENCIA TÁCTICA asignada al Comandante {commander_name}.
Tu lealtad es absoluta a la facción: {faction_name}.

## PROTOCOLO DE CONOCIMIENTO LIMITADO (NIEBLA DE GUERRA)
- NO ERES OMNISCIENTE. Solo accedes a datos del [CONTEXTO TÁCTICO] o herramientas.
- Si no hay datos, informa "Sensores fuera de rango" o "Sin registros".

## PROTOCOLO DE BASE DE DATOS (SQL)
- Para análisis masivos o comparaciones, USA `execute_sql_query`.
- IMPORTANTE: Los campos JSONB como `stats_json->'capacidades'->'atributos'->>'fuerza'` deben castearse a `::int` para comparaciones numéricas.

## MANEJO DE ERRORES DE HERRAMIENTAS
- Si una herramienta devuelve un error, NO TE RINDAS. Analiza el mensaje, corrige tu lógica (especialmente sintaxis SQL o nombres) y reintenta.

## INSTRUCCIONES OPERATIVAS
1. Analizar intención.
2. Usar herramientas si el contexto no es suficiente.
3. Responder de forma militar y eficiente.
"""

@dataclass
class TacticalContext:
    player_id: int
    commander_name: str
    commander_location: str
    attributes: Dict[str, int]
    resources: Dict[str, Any]
    known_planets: List[str]
    location_details: Dict[str, str] = field(default_factory=dict)
    system_alert: str = "Sensores nominales."

    def to_json(self) -> str:
        context = {
            "credenciales": {"player_id": self.player_id, "nivel_acceso": "COMANDANTE"},
            "estado_comandante": {"nombre": self.commander_name, "ubicacion": self.commander_location, "atributos": self.attributes},
            "recursos": self.resources,
            "dominios": self.known_planets,
            "alerta": self.system_alert
        }
        return json.dumps(context, indent=2, ensure_ascii=False)

def _build_tactical_context(player_id: int, commander_data: Dict) -> TacticalContext:
    try:
        finances = get_player_finances(player_id)
        planets = get_all_player_planets(player_id)
        planet_summary = [f"{p['nombre_asentamiento']} (Pops: {p['poblacion']})" for p in planets]
        stats = commander_data.get('stats_json', {})
        return TacticalContext(
            player_id=player_id,
            commander_name=commander_data['nombre'],
            commander_location=commander_data.get('ubicacion', 'Desconocida'),
            attributes=stats.get('atributos', {}),
            resources=finances,
            known_planets=planet_summary,
            location_details=get_commander_location_display(commander_data['id'])
        )
    except Exception as e:
        logger.error(f"Error construyendo contexto: {e}")
        return TacticalContext(player_id=player_id, commander_name="Comandante", commander_location="Error", attributes={}, resources={}, known_planets=[])

def _process_function_calls(chat: Any, response: Any, max_iterations: int = MAX_TOOL_ITERATIONS) -> tuple[Any, List[Dict[str, Any]]]:
    function_calls_made = []
    current_response = response

    for iteration in range(max_iterations):
        if not current_response.candidates:
            logger.error("IA devolvió respuesta sin candidatos.")
            break

        candidate = current_response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            # Diagnóstico de respuesta vacía
            logger.warning(f"Iteración {iteration+1}: Parte de contenido vacía. Forzando cierre o reintento.")
            break

        # Buscar llamadas a funciones
        fc_parts = [p for p in candidate.content.parts if hasattr(p, 'function_call') and p.function_call]
        
        if not fc_parts:
            break # No hay más llamadas, respuesta final alcanzada

        tool_responses = []
        for part in fc_parts:
            fc = part.function_call
            fname = fc.name
            fargs = dict(fc.args) if fc.args else {}
            
            logger.info(f"🤖 Ejecutando Tool: {fname}({fargs})")
            function_calls_made.append({"function": fname, "args": fargs, "iteration": iteration + 1})

            try:
                result_str = execute_tool(fname, fargs)
            except Exception as e:
                result_str = f"Error crítico ejecutando herramienta: {str(e)}"
                logger.error(result_str)

            tool_responses.append(
                types.Part.from_function_response(name=fname, response={"result": result_str})
            )

        # Enviar todas las respuestas de herramientas recolectadas en esta iteración
        try:
            current_response = chat.send_message(tool_responses)
        except Exception as e:
            logger.error(f"Error al enviar respuesta de herramientas a Gemini: {e}")
            break

    return current_response, function_calls_made

def _extract_narrative(response: Any) -> str:
    if not response or not response.candidates:
        return "Conexión neuronal inestable. Intente de nuevo."
    
    parts = response.candidates[0].content.parts
    text_parts = [p.text for p in parts if hasattr(p, 'text') and p.text]
    
    if not text_parts:
        logger.debug(f"Partes de la respuesta sin texto: {parts}")
        return "Procesamiento completado. Datos enviados a su terminal."
        
    return "".join(text_parts).strip()

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    check_and_trigger_tick()

    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        return {"narrative": "❄️ SISTEMA CONGELADO.", "mrg_result": None, "function_calls_made": []}
    
    if is_lock_in_window() and "[INTERNAL_EXECUTE_INVESTIGATION]" not in action_text:
        queue_player_action(player_id, action_text)
        return {"narrative": "⏱️ Ventana de Salto Temporal activa. Orden encolada.", "mrg_result": None, "function_calls_made": []}

    container = get_service_container()
    if not container.is_ai_available():
        return {"narrative": "⚠️ Enlace IA caído.", "mrg_result": None, "function_calls_made": []}

    commander = get_commander_by_player_id(player_id)
    if not commander:
        return {"narrative": "⚠️ Identidad no válida.", "mrg_result": None, "function_calls_made": []}

    tactical_context = _build_tactical_context(player_id, commander)
    system_prompt = TACTICAL_AI_PROMPT_TEMPLATE.format(
        commander_name=commander['nombre'],
        faction_name=str(commander.get('faccion_id', 'Independiente'))
    )

    mrg_result = None
    mrg_info = ""
    
    # Decidir si requiere MRG
    is_query = any(k in action_text.lower() for k in QUERY_KEYWORDS) or "?" in action_text
    
    if is_query or "[INTERNAL" in action_text:
        mrg_info = ">>> SOLICITUD DE INFORMACIÓN."
    else:
        stats = commander.get('stats_json', {})
        merit = sum(stats.get('atributos', {}).values()) if stats.get('atributos') else 10
        mrg_result = resolve_action(merit_points=merit, difficulty=DIFFICULTY_NORMAL, action_description=action_text)
        if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
            apply_partial_success_complication(mrg_result, player_id)
        mrg_info = f">>> RESULTADO FÍSICO (MRG): {mrg_result.result_type.value}"

    user_message = f"[CONTEXTO TÁCTICO]\n{tactical_context.to_json()}\n\n[ORDEN]\n{action_text}\n\n{mrg_info}"

    try:
        gemini_tools = [types.Tool(function_declarations=TOOL_DECLARATIONS)] if TOOL_DECLARATIONS else None
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,
            temperature=AI_TEMPERATURE,
            max_output_tokens=AI_MAX_TOKENS
        )

        chat = container.ai.chats.create(model=TEXT_MODEL_NAME, config=config)
        response = chat.send_message(user_message)
        
        final_response, calls = _process_function_calls(chat, response)
        narrative = _extract_narrative(final_response)

        log_event(f"🤖 [IA] {narrative}", player_id)
        return {"narrative": narrative, "mrg_result": mrg_result, "function_calls_made": calls}

    except Exception as e:
        logger.error(f"Error en enlace táctico: {e}", exc_info=True)
        return {"narrative": f"⚠️ Error de sistema: {str(e)}", "mrg_result": None, "function_calls_made": []}