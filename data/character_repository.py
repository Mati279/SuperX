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


def update_commander_profile(
    player_id: int,
    bio_data: Dict[str, Any],
    attributes: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """
    Actualiza el perfil del comandante existente con bio y atributos personalizados.
    Usado en el Paso 3 del wizard de registro, después de que genesis_engine
    ya creó el comandante base en Paso 1.

    Args:
        player_id: El ID del jugador dueño del comandante.
        bio_data: Diccionario con la biografía (raza, clase, edad, etc.).
        attributes: Diccionario con los atributos finales elegidos por el usuario.

    Returns:
        El objeto del comandante actualizado o None si falla.
    """
    try:
        habilidades = calculate_skills(attributes)

        stats_json = {
            "bio": bio_data,
            "atributos": attributes,
            "habilidades": habilidades
        }

        response = supabase.table("characters")\
            .update({"stats_json": stats_json})\
            .eq("player_id", player_id)\
            .eq("es_comandante", True)\
            .execute()

        if response.data:
            log_event(f"Perfil del comandante actualizado para jugador ID {player_id}.", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error actualizando comandante para jugador ID {player_id}: {e}", player_id, is_error=True)
        raise Exception("Error del sistema al actualizar el comandante.")

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


def get_character_by_id(character_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene un personaje específico por su ID.

    Args:
        character_id: El ID del personaje.

    Returns:
        Diccionario con los datos del personaje o None.
    """
    try:
        response = supabase.table("characters").select("*").eq("id", character_id).single().execute()
        if response.data and isinstance(response.data, dict):
            return response.data
        return None
    except Exception:
        return None


def update_character_xp(character_id: int, new_xp: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Actualiza el XP de un personaje en su stats_json.

    Args:
        character_id: ID del personaje.
        new_xp: Nuevo valor total de XP.
        player_id: ID del jugador para logging (opcional).

    Returns:
        El personaje actualizado o None si falla.
    """
    try:
        # Obtener personaje actual
        char = get_character_by_id(character_id)
        if not char:
            return None

        # Actualizar XP en stats_json
        stats = char.get("stats_json", {})
        old_xp = stats.get("xp", 0)
        stats["xp"] = new_xp

        # Guardar
        response = supabase.table("characters")\
            .update({"stats_json": stats})\
            .eq("id", character_id)\
            .execute()

        if response.data:
            xp_diff = new_xp - old_xp
            sign = "+" if xp_diff >= 0 else ""
            log_event(f"XP actualizado para {char['nombre']}: {sign}{xp_diff} (Total: {new_xp})", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error actualizando XP para personaje ID {character_id}: {e}", player_id, is_error=True)
        return None


def add_xp_to_character(character_id: int, xp_amount: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Añade XP a un personaje (suma al valor actual).

    Args:
        character_id: ID del personaje.
        xp_amount: Cantidad de XP a añadir (puede ser negativo).
        player_id: ID del jugador para logging.

    Returns:
        El personaje actualizado o None si falla.
    """
    try:
        char = get_character_by_id(character_id)
        if not char:
            return None

        stats = char.get("stats_json", {})
        current_xp = stats.get("xp", 0)
        new_xp = max(0, current_xp + xp_amount)  # No permitir XP negativo

        return update_character_xp(character_id, new_xp, player_id)

    except Exception as e:
        log_event(f"Error añadiendo XP a personaje ID {character_id}: {e}", player_id, is_error=True)
        return None


def update_character_stats(character_id: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Actualiza el stats_json completo de un personaje.

    Args:
        character_id: ID del personaje.
        new_stats_json: Nuevo diccionario de stats completo.
        player_id: ID del jugador para logging.

    Returns:
        El personaje actualizado o None si falla.
    """
    try:
        response = supabase.table("characters")\
            .update({"stats_json": new_stats_json})\
            .eq("id", character_id)\
            .execute()

        if response.data and len(response.data) > 0:
            result = response.data[0]
            char_name = result.get("nombre", "Desconocido") if isinstance(result, dict) else "Desconocido"
            log_event(f"Stats actualizados para {char_name}.", player_id)
            return result if isinstance(result, dict) else None
        return None

    except Exception as e:
        log_event(f"Error actualizando stats para personaje ID {character_id}: {e}", player_id, is_error=True)
        return None


def update_character_level(character_id: int, new_level: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Actualiza el nivel y stats de un personaje después de level up.

    Args:
        character_id: ID del personaje.
        new_level: Nuevo nivel.
        new_stats_json: Stats actualizados con bonificaciones de nivel.
        player_id: ID del jugador para logging.

    Returns:
        El personaje actualizado o None si falla.
    """
    try:
        # Obtener nombre para el log
        char = get_character_by_id(character_id)
        char_name = char.get("nombre", "Desconocido") if char else "Desconocido"

        response = supabase.table("characters")\
            .update({
                "stats_json": new_stats_json
            })\
            .eq("id", character_id)\
            .execute()

        if response.data:
            log_event(f"{char_name} ha ascendido a Nivel {new_level}!", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error en level up para personaje ID {character_id}: {e}", player_id, is_error=True)
        return None


def recruit_character(player_id: int, character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Recluta un nuevo personaje (alias de create_character para claridad semántica).

    Args:
        player_id: ID del jugador que recluta.
        character_data: Datos del personaje a reclutar.

    Returns:
        El personaje creado o None si falla.
    """
    return create_character(player_id, character_data)
