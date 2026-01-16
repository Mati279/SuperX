# data/character_repository.py
from typing import Dict, Any, Optional
from .database import supabase
from data.log_repository import log_event
from core.rules import calculate_skills
from config.app_constants import (
    COMMANDER_RANK,
    COMMANDER_STATUS,
    COMMANDER_LOCATION
)

def get_commander_by_player_id(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene el personaje comandante de un jugador.

    Args:
        player_id: El ID del jugador.

    Returns:
        Un diccionario con los datos del comandante o None si no se encuentra.
    """
    try:
        response = supabase.table("characters").select("*").eq("player_id", player_id).eq("es_comandante", True).single().execute()
        return response.data
    except Exception:
        # Es normal que PostgREST falle si no hay un comandante.
        return None

def create_commander(
    player_id: int,
    name: str, 
    bio_data: Dict[str, Any], 
    attributes: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """
    Crea un nuevo personaje Comandante en la base de datos.

    Args:
        player_id: El ID del jugador al que pertenece el comandante.
        name: El nombre del comandante.
        bio_data: Diccionario con la biografía (raza, clase, etc.).
        attributes: Diccionario con los atributos finales del comandante.

    Returns:
        El objeto del personaje creado o None si falla.
    """
    try:
        # La lógica de negocio (cálculo de habilidades) se llama antes de la inserción.
        habilidades = calculate_skills(attributes)
        
        stats_json = {
            "bio": bio_data,
            "atributos": attributes,
            "habilidades": habilidades
        }

        new_char_data = {
            "player_id": player_id,
            "nombre": name,
            "rango": COMMANDER_RANK,
            "es_comandante": True,
            "stats_json": stats_json,
            "estado": COMMANDER_STATUS,
            "ubicacion": COMMANDER_LOCATION
        }
        
        response = supabase.table("characters").insert(new_char_data).execute()
        if response.data:
            log_event(f"Nuevo comandante '{name}' creado para el jugador ID {player_id}.", player_id)
            return response.data[0]
        return None
        
    except Exception as e:
        log_event(f"Error creando comandante para el jugador ID {player_id}: {e}", player_id, is_error=True)
        raise Exception("Error del sistema al guardar el comandante.")

def create_character(player_id: int, character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Crea un nuevo personaje (no comandante) en la base de datos.
    Usado para reclutamiento.

    Args:
        player_id: El ID del jugador que recluta.
        character_data: Diccionario con los datos del nuevo personaje,
                        preparado por recruitment_logic.

    Returns:
        El objeto del personaje creado o None si falla.
    """
    try:
        # La lógica de negocio (cálculo de habilidades) se aplica aquí también
        attributes = character_data.get("stats_json", {}).get("atributos", {})
        habilidades = calculate_skills(attributes)
        
        # Asegurarse de que el JSON de stats esté completo
        if "habilidades" not in character_data.get("stats_json", {}):
            character_data["stats_json"]["habilidades"] = habilidades

        response = supabase.table("characters").insert(character_data).execute()
        
        if response.data:
            nombre = character_data.get('nombre', 'Nuevo Recluta')
            log_event(f"Nuevo personaje '{nombre}' reclutado por el jugador ID {player_id}.", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error reclutando personaje para el jugador ID {player_id}: {e}", player_id, is_error=True)
        raise Exception("Error del sistema al guardar el nuevo personaje.")


def get_all_characters_by_player_id(player_id: int) -> list[Dict[str, Any]]:
    """
    Obtiene todos los personajes (no solo el comandante) de un jugador.

    Args:
        player_id: El ID del jugador.

    Returns:
        Una lista de diccionarios, cada uno representando un personaje.
    """
    try:
        response = supabase.table("characters").select("*").eq("player_id", player_id).execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error al obtener todos los personajes del jugador ID {player_id}: {e}", player_id, is_error=True)
        return []

def update_character(character_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Actualiza los datos de un personaje específico.

    Args:
        character_id: El ID del personaje a actualizar.
        data: Un diccionario con los campos y nuevos valores a actualizar.

    Returns:
        El objeto del personaje actualizado o None si falla.
    """
    try:
        response = supabase.table("characters").update(data).eq("id", character_id).execute()
        if response.data:
            log_event(f"Personaje ID {character_id} actualizado.")
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error al actualizar personaje ID {character_id}: {e}", is_error=True)
        raise Exception("Error del sistema al actualizar datos.")
