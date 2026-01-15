# data/player_repository.py
from typing import Dict, Any, Optional, IO
from .database import supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image

def get_player_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Busca un jugador por su nombre de usuario.

    Args:
        name: El nombre del jugador.

    Returns:
        Un diccionario con los datos del jugador o None si no se encuentra.
    """
    try:
        response = supabase.table("players").select("*").eq("nombre", name).single().execute()
        return response.data
    except Exception:
        # PostgREST devuelve un error si .single() no encuentra nada, lo cual es normal.
        return None

def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]:
    """
    Autentica a un jugador por nombre y PIN.

    Args:
        name: El nombre de usuario.
        pin: El PIN de 4 dígitos.

    Returns:
        Los datos del jugador si la autenticación es exitosa, None en caso contrario.
    """
    player = get_player_by_name(name)
    if player and verify_password(player['pin'], pin):
        return player
    return None

def register_player_account(
    user_name: str, 
    pin: str, 
    faction_name: str, 
    banner_file: Optional[IO[bytes]]
) -> Optional[Dict[str, Any]]:
    """
    Crea una nueva cuenta de jugador y su facción.

    Args:
        user_name: Nombre de usuario para el login.
        pin: PIN de 4 dígitos para el login.
        faction_name: Nombre de la facción del jugador.
        banner_file: (Opcional) El archivo del estandarte de la facción.

    Returns:
        Un diccionario con los datos del nuevo jugador o None si falla.
    """
    # Primero, verificar si el nombre de usuario ya existe.
    if get_player_by_name(user_name):
        log_event(f"Intento de registro con nombre de usuario duplicado: {user_name}", is_error=True)
        raise ValueError("El nombre de Comandante ya está en uso.")

    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    
    new_player_data = {
        "nombre": user_name,
        "pin": hash_password(pin),
        "faccion_nombre": faction_name,
        "banner_url": banner_url
    }
    
    try:
        response = supabase.table("players").insert(new_player_data).execute()
        if response.data:
            log_event(f"Nueva cuenta de jugador creada: {user_name}")
            return response.data[0]
    except Exception as e:
        log_event(f"Error al registrar cuenta de jugador: {e}", is_error=True)
        # No devolvemos el error crudo al usuario final por seguridad.
        raise Exception("Ocurrió un error en el sistema al crear la cuenta.")
    
    return None
