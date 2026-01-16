# services/gemini_service.py
import json
from typing import Dict, Any, Optional
from data.database import ai_client
from data.log_repository import log_event
from data.game_config_repository import get_game_config
from data.character_repository import get_commander_by_player_id, update_character
from data.world_repository import queue_player_action, get_world_state

# Importar el motor de tiempo
from core.time_engine import check_and_trigger_tick, is_lock_in_window

# Importar constantes
from config.app_constants import TEXT_MODEL_NAME, IMAGE_MODEL_NAME

# Importar Motor de Resolución Galáctico (MRG)
from core.mrg_engine import resolve_action, DIFFICULTY_PRESETS
from core.mrg_constants import DIFFICULTY_NORMAL
from core.mrg_effects import apply_partial_success_complication

def _get_narrative_guidance(result_type) -> str:
    """
    Retorna guía narrativa para la IA basada en el tipo de resultado MRG.
    """
    from core.mrg_engine import ResultType

    guidance = {
        ResultType.CRITICAL_SUCCESS: "¡Éxito excepcional! Narra una hazaña memorable que inspire asombro.",
        ResultType.TOTAL_SUCCESS: "Éxito limpio y profesional. La acción se ejecuta perfectamente.",
        ResultType.PARTIAL_SUCCESS: "Éxito con complicación. El objetivo se logra pero algo sale mal o genera problemas.",
        ResultType.PARTIAL_FAILURE: "Fracaso con dignidad. La acción falla pero el personaje conserva su posición.",
        ResultType.TOTAL_FAILURE: "Fracaso significativo. Las cosas salen mal de manera notable.",
        ResultType.CRITICAL_FAILURE: "¡Desastre catastrófico! Narra un fallo épico y memorable."
    }

    return guidance.get(result_type, "Narra el resultado de la acción.")


# ... (Mantén la función generate_image igual) ...
def generate_image(prompt: str, player_id: int) -> Optional[Any]:
    # (Código original de generate_image sin cambios)
    if not ai_client:
        log_event("Intento de generar imagen sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no esta disponible.")

    try:
        response = ai_client.models.generate_images(
            model=IMAGE_MODEL_NAME,
            prompt=prompt,
        )
        log_event(f"Se ha generado una imagen con el prompt: '{prompt}'", player_id)
        return response
    except Exception as e:
        log_event(f"Error durante la generacion de la imagen con la IA: {e}", player_id, is_error=True)
        raise ConnectionError("Ocurrio un error al comunicarse con el servicio de IA para generar la imagen.")


def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Resuelve la acción del jugador usando MRG + IA, respetando las reglas de tiempo STRT.
    """

    # --- 0. GUARDIANES DE TIEMPO (STRT) ---

    # A. Lazy Tick Check: Asegurar que el mundo esté al día antes de procesar nada.
    check_and_trigger_tick()

    # B. Chequeo de Estado Congelado (Freeze)
    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        msg = "❄️ EL UNIVERSO ESTÁ EN ÉXTASIS. No se pueden realizar acciones durante un Freeze Galáctico."
        log_event(msg, player_id)
        return {"narrative": msg, "updates": []}

    # C. Chequeo de Ventana de Bloqueo (Lock-in)
    if is_lock_in_window():
        success = queue_player_action(player_id, action_text)
        if success:
            msg = "⚠️ VENTANA DE BLOQUEO ACTIVA (23:50 - 00:00). Tu orden ha sido encriptada y puesta en cola para ejecución al inicio del próximo Ciclo Solar."
        else:
            msg = "Error al encolar la orden. Intente nuevamente."

        # Devolvemos un resultado ficticio para que la UI lo muestre, pero NO llamamos a la IA.
        return {"narrative": msg, "updates": []}

    # --- FIN GUARDIANES ---

    if not ai_client:
        log_event("Intento de resolver accion sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no esta disponible.")

    # 1. Obtener la configuracion del juego
    game_config = get_game_config()
    if not game_config:
        raise ValueError("No se pudo cargar la configuracion del juego.")

    # 2. Obtener el estado actual del personaje
    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("No se encontro un comandante para el jugador.")

    # --- NUEVO: RESOLUCIÓN MRG ---

    # Extraer atributos del comandante
    stats = commander.get('stats_json', {})
    attributes = stats.get('atributos', {})

    # Calcular mérito (suma de todos los atributos relevantes)
    # Por ahora usamos todos los atributos; en el futuro la IA podría determinar cuáles aplican
    merit_points = sum(attributes.values()) if attributes else 0

    # Determinar dificultad (por ahora default NORMAL, en el futuro la IA la determina)
    difficulty = DIFFICULTY_NORMAL

    # Ejecutar tirada MRG
    mrg_result = resolve_action(
        merit_points=merit_points,
        difficulty=difficulty,
        action_description=action_text,
        entity_id=commander['id'],
        entity_name=commander['nombre']
    )

    # Guardar resultado en sesión para que la UI lo muestre
    import streamlit as st
    st.session_state.pending_mrg_result = mrg_result

    # Si es éxito parcial, aplicar complicación automática
    from core.mrg_engine import ResultType
    if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
        apply_partial_success_complication(mrg_result, player_id)

    # --- FIN NUEVO ---

    game_state = {"commander": commander}

    # 3. Construir el prompt para la IA (incluyendo resultado MRG)
    mrg_summary = f"""

    RESULTADO DE TIRADA MRG (Motor de Resolución Galáctico):
    - Tirada: {mrg_result.roll.die_1} + {mrg_result.roll.die_2} = {mrg_result.roll.total}
    - Bono del Comandante: +{mrg_result.bonus_applied} (basado en mérito: {mrg_result.merit_points})
    - Dificultad: {mrg_result.difficulty}
    - Margen: {mrg_result.margin}
    - Resultado: {mrg_result.result_type.value}

    IMPORTANTE: Tu narrativa debe ser coherente con este resultado mecánico.
    {_get_narrative_guidance(mrg_result.result_type)}
    """

    prompt = f"""
    Eres un Game Master de una partida de rol de ciencia ficcion.
    Tu unica salida debe ser un JSON valido, sin usar markdown.

    Mundo: {game_config.get('world_description','Universo scifi generico.')}
    Reglas: {game_config.get('rules','Acciones narrativas.')}
    Estado Actual: {json.dumps(game_state, default=str)}

    Accion del Jugador: "{action_text}"
    {mrg_summary}

    Responde JSON:
    {{
        "narrative": "Descripcion detallada y dramatica que refleje el resultado de la tirada.",
        "updates": [
            {{ "table": "characters", "id": {commander['id']}, "data": {{ "campo": "valor" }} }}
        ]
    }}
    """

    try:
        # 4. Llamar a Gemini
        response = ai_client.models.generate_content(model=TEXT_MODEL_NAME, contents=prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned_text)

        # 5. Procesar actualizaciones
        if "updates" in result:
            for update_instruction in result["updates"]:
                table = update_instruction.get("table")
                record_id = update_instruction.get("id")
                data_to_update = update_instruction.get("data")

                if table == "characters" and record_id and data_to_update:
                    try:
                        update_character(record_id, data_to_update)
                    except Exception as e:
                        log_event(f"Error update IA: {e}", player_id, is_error=True)

        # 6. Registrar narrativa
        narrative = result.get("narrative", "Resultado incierto.")
        log_event(narrative, player_id)

        return result

    except json.JSONDecodeError as e:
        log_event(f"Error JSON IA: {e}", player_id, is_error=True)
        raise ValueError("La IA fallo al formatear la respuesta.")
    except Exception as e:
        log_event(f"Error general IA: {e}", player_id, is_error=True)
        raise ConnectionError("Error de comunicacion con la IA.")