# services/gemini_service.py
"""
Gemini Service - Asistente Táctico IA (Implementation v2.1)
Personalidad: Asistente Táctico (Estilo Jarvis/Cortana).
Fix: Guarda la narrativa en los logs para persistencia en UI.
"""

import json
from typing import Dict, Any, Optional
from google.genai import types

from data.database import ai_client
from data.log_repository import log_event
from data.character_repository import get_commander_by_player_id
from data.player_repository import get_player_finances
from data.planet_repository import get_all_player_planets
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


# --- SYSTEM PROMPT (ASISTENTE TÁCTICO) ---

def _get_assistant_system_prompt(commander_name: str, faction_name: str) -> str:
    return f"""
Eres la UNIDAD DE INTELIGENCIA TÁCTICA asignada al Comandante {commander_name}.
Tu lealtad es absoluta a la facción: {faction_name}.

## TU PERSONALIDAD
- Actúas como un asistente avanzado (estilo Jarvis, Cortana, EDI).
- Eres profesional, eficiente, proactivo y respetuoso.
- NO tienes límite de caracteres forzado, pero valoras la precisión. Explica los detalles si el Comandante lo requiere.
- Usas terminología militar/sci-fi adecuada (ej: "Afirmativo", "Escaneando", "En proceso").

## PROTOCOLO DE CONOCIMIENTO LIMITADO (NIEBLA DE GUERRA)
- **CRÍTICO:** NO ERES OMNISCIENTE.
- Solo tienes acceso a:
  1. Los datos proporcionados en el [CONTEXTO TÁCTICO] actual.
  2. Herramientas de base de datos explícitas (`execute_db_query`) para consultar inventarios propios.
- Si el Comandante pregunta por la ubicación de enemigos, bases ocultas o recursos en sistemas no explorados, **DEBES RESPONDER QUE NO TIENES DATOS**.
- No inventes coordenadas ni hechos sobre otros jugadores.

## INSTRUCCIONES OPERATIVAS
1. **Analizar:** Interpreta la intención del Comandante.
2. **Verificar Contexto:** ¿Tengo la información en mis sensores (Contexto Táctico)?
3. **Ejecutar:** Usa herramientas si es necesario (consultas SQL limitadas, cálculos).
4. **Responder:** Informa el resultado con tu personalidad de IA Táctica.

Si la orden requiere una tirada de habilidad (MRG), el sistema te proveerá el resultado. Nárralo épicamente basándote en el éxito o fracaso.
"""

# --- CONTEXTO DE CONOCIMIENTO (FOG OF WAR) ---

def _build_player_context(player_id: int, commander_data: Dict) -> str:
    """Construye el JSON de contexto limitado."""
    try:
        finances = get_player_finances(player_id)
        planets = get_all_player_planets(player_id)
        planet_summary = [f"{p['nombre_asentamiento']} (Pops: {p['poblacion']})" for p in planets]
        stats = commander_data.get('stats_json', {})
        attributes = stats.get('atributos', {})
        
        context = {
            "estado_comandante": {
                "nombre": commander_data['nombre'],
                "ubicacion_actual": commander_data.get('ubicacion', 'Desconocida'),
                "atributos": attributes
            },
            "recursos_logisiticos": finances,
            "dominios_conocidos": planet_summary,
            "alerta_sistema": "Sensores nominales. Datos externos limitados a sectores explorados."
        }
        return json.dumps(context, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error_contexto": str(e)})


# --- FUNCIÓN PRINCIPAL ---

def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    # 0. Guardianes de Tiempo
    check_and_trigger_tick()

    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        return {"narrative": "❄️ SISTEMA: Cronología congelada por administración.", "mrg_result": None}

    if is_lock_in_window():
        queue_player_action(player_id, action_text)
        return {"narrative": "⏱️ SISTEMA: Ventana de Salto Temporal activa. Orden encolada.", "mrg_result": None}

    # 1. Configuración
    if not ai_client:
        raise ConnectionError("Enlace neuronal con IA interrumpido.")

    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("Error: Identidad de Comandante no verificada.")

    tactical_context = _build_player_context(player_id, commander)
    faction_name = commander.get('faccion_id', 'Independiente')
    system_prompt = _get_assistant_system_prompt(commander['nombre'], str(faction_name))

    # 2. Análisis de Consulta vs Acción
    query_keywords = ["cuantos", "cuántos", "que", "qué", "como", "cómo", "donde", "dónde", "quien", "quién", "estado", "listar", "ver", "info", "ayuda", "analisis"]
    is_informational_query = any(action_text.lstrip().lower().startswith(k) for k in query_keywords) or "?" in action_text

    mrg_result = None
    mrg_info_block = ""

    if is_informational_query:
        class DummyResult:
            result_type = ResultType.TOTAL_SUCCESS
            roll = None
        mrg_result = DummyResult()
        mrg_info_block = ">>> TIPO: SOLICITUD DE INFORMACIÓN. No requiere tirada."
    else:
        stats = commander.get('stats_json', {})
        attributes = stats.get('atributos', {})
        merit_points = sum(attributes.values()) if attributes else 0
        
        mrg_result = resolve_action(
            merit_points=merit_points,
            difficulty=DIFFICULTY_NORMAL,
            action_description=action_text,
            entity_id=commander['id'],
            entity_name=commander['nombre']
        )
        
        if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
            apply_partial_success_complication(mrg_result, player_id)

        mrg_info_block = f"""
>>> REPORTE DE EJECUCIÓN FÍSICA (MRG):
- Resultado: {mrg_result.result_type.value}
- Detalle Técnico: Roll {mrg_result.roll}
Usa este resultado para narrar el éxito o fracaso.
"""

    # 3. Mensaje Usuario
    user_message = f"""
[CONTEXTO TÁCTICO]
{tactical_context}

[ORDEN DEL COMANDANTE]
"{action_text}"

{mrg_info_block}
"""

    try:
        # 4. Iniciar Chat
        chat = ai_client.chats.create(
            model=TEXT_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=TOOL_DECLARATIONS,
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                ),
                temperature=0.7,
                max_output_tokens=1024,
                top_p=0.95
            )
        )

        response = chat.send_message(user_message)

        # 5. Bucle de Herramientas
        max_iterations = 10
        iteration = 0
        function_calls_made = []

        while iteration < max_iterations:
            iteration += 1
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                has_function_call = False
                for part in parts:
                    if part.function_call:
                        has_function_call = True
                        fc = part.function_call
                        fname = fc.name
                        fargs = fc.args

                        # Log técnico (interno)
                        # log_event(f"[AI Ops] Ejecutando: {fname}", player_id) 
                        function_calls_made.append({"function": fname, "args": fargs})

                        result_str = ""
                        if fname in TOOL_FUNCTIONS:
                            try:
                                args_dict = {k: v for k, v in fargs.items()}
                                result_str = TOOL_FUNCTIONS[fname](**args_dict)
                            except Exception as e:
                                result_str = json.dumps({"error": str(e)})
                        else:
                            result_str = json.dumps({"error": "Función desconocida"})

                        response = chat.send_message([
                            types.Part.from_function_response(name=fname, response={"result": result_str})
                        ])
                        break
                if not has_function_call:
                    break
            else:
                break

        # 6. Narrativa Final y Persistencia
        narrative = "..."
        if response.candidates and response.candidates[0].content.parts:
            text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
            narrative = "".join(text_parts).strip()

        # --- CORRECCIÓN CRÍTICA ---
        # Guardamos la narrativa REAL en los logs, prefijada para que se vea bonita en la UI.
        # Esto reemplaza al mensaje genérico que causaba el problema.
        log_display_text = f"🤖 [ASISTENTE] {narrative}"
        log_event(log_display_text, player_id)

        return {
            "narrative": narrative,
            "mrg_result": mrg_result,
            "function_calls_made": function_calls_made
        }

    except Exception as e:
        log_event(f"Error AI: {e}", player_id, is_error=True)
        return {"narrative": f"⚠️ Error de sistema: {str(e)}", "mrg_result": None}