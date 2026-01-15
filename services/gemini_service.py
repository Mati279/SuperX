# services/gemini_service.py
import json
from typing import Dict, Any, Optional

from data.database import ai_client
from data.log_repository import log_event
from data.game_config_repository import get_game_config
from data.character_repository import get_commander_by_player_id, update_character

# Constante para el nombre del modelo de texto
TEXT_MODEL_NAME = 'gemini-2.5-flash'

# Constante para el nombre del modelo de imagen (ej: 'imagen-3.0-generate-001')
# Usamos un modelo que soporte generación de imágenes.
# Reemplazar con el modelo específico y más económico cuando se decida.
IMAGE_MODEL_NAME = 'gemini-2.5-flash'


def generate_image(prompt: str, player_id: int) -> Optional[Any]:
    """
    Genera una imagen usando el modelo de IA de Gemini.

    Args:
        prompt: La descripción de la imagen a generar.
        player_id: El ID del jugador que solicita la imagen.

    Returns:
        La respuesta del servicio de IA o None si ocurre un error.
    """
    if not ai_client:
        log_event("Intento de generar imagen sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no está disponible.")

    try:
        # Llama a la API de Gemini para generar la imagen
        response = ai_client.generate_content(
            model=IMAGE_MODEL_NAME,
            prompt=prompt
        )
        log_event(f"Se ha generado una imagen con el prompt: '{prompt}'", player_id)
        return response
    except Exception as e:
        log_event(f"Error durante la generación de la imagen con la IA: {e}", player_id, is_error=True)
        raise ConnectionError("Ocurrió un error al comunicarse con el servicio de IA para generar la imagen.")


def resolve_player_action(action_text: str, player_id: int) -> Optional[Dict[str, Any]]:
    """
    Resuelve la acción de un jugador usando el modelo de IA de Gemini.

    REGLA: Esta función es el ÚNICO lugar donde se debe llamar a la IA de texto.

    Args:
        action_text: La acción que el jugador quiere realizar.
        player_id: El ID del jugador que realiza la acción.

    Returns:
        Un diccionario con la respuesta de la IA (narrativa y actualizaciones)
        o None si ocurre un error.
    """
    if not ai_client:
        log_event("Intento de resolver acción sin cliente de IA inicializado.", player_id, is_error=True)
        raise ConnectionError("El servicio de IA no está disponible.")

    # 1. Obtener la configuración del juego (mundo, reglas)
    game_config = get_game_config()
    if not game_config:
        raise ValueError("No se pudo cargar la configuración del juego desde la base de datos.")

    # 2. Obtener el estado actual del personaje del jugador
    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("No se encontró un comandante para el jugador.")
    
    # Preparamos un estado de juego simplificado para el prompt
    game_state = {"commander": commander}

    # 3. Construir el prompt para la IA
    prompt = f"""
    Eres un Game Master de una partida de rol de ciencia ficción.
    Tu única salida debe ser un JSON válido, sin usar markdown.
    
    Mundo: {game_config.get('world_description','Universo de ciencia ficción genérico.')}
    Reglas: {game_config.get('rules','Las acciones se resuelven de forma narrativa.')}
    Estado Actual del Juego: {json.dumps(game_state, default=str)}
    
    Acción del Jugador: "{action_text}"
    
    Responde con el siguiente formato JSON:
    {{
        "narrative": "Una descripción creativa y detallada de lo que sucede como resultado de la acción.",
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
        # 4. Llamar a la API de Gemini
        response = ai_client.models.generate_content(model=TEXT_MODEL_NAME, contents=prompt)
        
        # Limpiar la respuesta para asegurar que sea un JSON válido
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
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
                        # Loggear un error si la actualización específica falla
                        log_event(f"IA intentó una actualización inválida para la tabla {table}: {e}", player_id, is_error=True)

        # 6. Registrar la narrativa
        narrative = result.get("narrative", "La acción no tuvo un resultado claro.")
        log_event(narrative, player_id)
        
        return result

    except json.JSONDecodeError as e:
        log_event(f"Error al decodificar la respuesta JSON de la IA: {e}\nRespuesta recibida: {response.text}", player_id, is_error=True)
        raise ValueError("La IA devolvió una respuesta en un formato inesperado.")
    except Exception as e:
        log_event(f"Error durante la resolución de la acción con la IA: {e}", player_id, is_error=True)
        raise ConnectionError(f"Ocurrió un error al comunicarse con el servicio de IA.")
