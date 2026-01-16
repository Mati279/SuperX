# services/gemini_service.py
import json
from typing import Dict, Any, Optional

from data.database import ai_client
from data.log_repository import log_event
from data.game_config_repository import get_game_config
from data.character_repository import get_commander_by_player_id, update_character

# Modelos usados segun el tipo de peticion
TEXT_MODEL_NAME = "gemini-2.5-flash"
IMAGE_MODEL_NAME = "imagen-3.0-generate-001"


def generate_image(prompt: str, player_id: int) -> Optional[Any]:
    """
    Genera una imagen usando el modelo de IA de Gemini.

    Args:
        prompt: La descripcion de la imagen a generar.
        player_id: El ID del jugador que solicita la imagen.

    Returns:
        La respuesta del servicio de IA o None si ocurre un error.
    """
    if not ai_client:
        log_event("Intento de generar imagen sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no esta disponible.")

    try:
        # Llama a la API de Gemini para generar la imagen con el modelo dedicado
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
    Resuelve la accion de un jugador usando el modelo de IA de Gemini.

    REGLA: Esta funcion es el unico lugar donde se debe llamar a la IA de texto.

    Args:
        action_text: La accion que el jugador quiere realizar.
        player_id: El ID del jugador que realiza la accion.

    Returns:
        Un diccionario con la respuesta de la IA (narrativa y actualizaciones)
        o None si ocurre un error.
    """
    if not ai_client:
        log_event("Intento de resolver accion sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no esta disponible.")

    # 1. Obtener la configuracion del juego (mundo, reglas)
    game_config = get_game_config()
    if not game_config:
        raise ValueError("No se pudo cargar la configuracion del juego desde la base de datos.")

    # 2. Obtener el estado actual del personaje del jugador
    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("No se encontro un comandante para el jugador.")

    # Preparamos un estado de juego simplificado para el prompt
    game_state = {"commander": commander}

    # 3. Construir el prompt para la IA
    prompt = f"""
    Eres un Game Master de una partida de rol de ciencia ficcion.
    Tu unica salida debe ser un JSON valido, sin usar markdown.

    Mundo: {game_config.get('world_description','Universo de ciencia ficcion generico.')}
    Reglas: {game_config.get('rules','Las acciones se resuelven de forma narrativa.')}
    Estado Actual del Juego: {json.dumps(game_state, default=str)}

    Accion del Jugador: "{action_text}"

    Responde con el siguiente formato JSON:
    {{
        "narrative": "Una descripcion creativa y detallada de lo que sucede como resultado de la accion.",
        "updates": [
            {{
                "table": "characters",
                "id": {commander['id']},
                "data": {{ "campo_a_actualizar": "nuevo_valor" }}
            }}
        ]
    }}
    """

    try:
        # 4. Llamar a la API de Gemini para texto
        response = ai_client.models.generate_content(model=TEXT_MODEL_NAME, contents=prompt)

        # Limpiar la respuesta para asegurar que sea un JSON valido
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned_text)

        # 5. Procesar las actualizaciones devueltas por la IA
        if "updates" in result:
            for update_instruction in result["updates"]:
                table = update_instruction.get("table")
                record_id = update_instruction.get("id")
                data_to_update = update_instruction.get("data")

                if table == "characters" and record_id and data_to_update:
                    try:
                        update_character(record_id, data_to_update)
                    except Exception as e:
                        # Loggear un error si la actualizacion especifica falla
                        log_event(f"IA intento una actualizacion invalida para la tabla {table}: {e}", player_id, is_error=True)

        # 6. Registrar la narrativa
        narrative = result.get("narrative", "La accion no tuvo un resultado claro.")
        log_event(narrative, player_id)

        return result

    except json.JSONDecodeError as e:
        log_event(f"Error al decodificar la respuesta JSON de la IA: {e}\nRespuesta recibida: {response.text}", player_id, is_error=True)
        raise ValueError("La IA devolvio una respuesta en un formato inesperado.")
    except Exception as e:
        log_event(f"Error durante la resolucion de la accion con la IA: {e}", player_id, is_error=True)
        raise ConnectionError("Ocurrio un error al comunicarse con el servicio de IA.")
