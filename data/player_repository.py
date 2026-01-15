# data/player_repository.py
from typing import Dict, Any, Optional, IO
import uuid # IMPORTANTE: Para generar tokens únicos
from .database import supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image

# ... (Mantén get_player_by_name tal cual estaba) ...
def get_player_by_name(name: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("players").select("*").eq("nombre", name).single().execute()
        return response.data
    except Exception:
        return None

# NUEVA FUNCIÓN: Busca un jugador por su token de sesión
def get_player_by_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida un token de sesión y devuelve el jugador asociado."""
    if not token: return None
    try:
        response = supabase.table("players").select("*").eq("session_token", token).single().execute()
        return response.data
    except Exception:
        return None

# NUEVA FUNCIÓN: Actualiza el token de sesión al loguearse
def create_session_token(player_id: int) -> str:
    """Genera un nuevo token, lo guarda en DB y lo devuelve."""
    new_token = str(uuid.uuid4())
    try:
        supabase.table("players").update({"session_token": new_token}).eq("id", player_id).execute()
        return new_token
    except Exception as e:
        log_event(f"Error al crear sesión: {e}", is_error=True)
        return ""

# NUEVA FUNCIÓN: Borra el token al salir
def clear_session_token(player_id: int) -> None:
    """Elimina el token de sesión de la base de datos."""
    try:
        supabase.table("players").update({"session_token": None}).eq("id", player_id).execute()
    except Exception as e:
        log_event(f"Error al cerrar sesión: {e}", is_error=True)

# ... (Mantén authenticate_player y register_player_account) ...
def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]:
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
    # ... (El código de registro sigue igual) ...
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
        raise Exception("Ocurrió un error en el sistema al crear la cuenta.")
    
    return None

# --- Funciones de Gestión Económica ---

def get_player_credits(player_id: int) -> int:
    """
    Obtiene la cantidad de créditos de un jugador.

    Args:
        player_id: El ID del jugador.

    Returns:
        La cantidad de créditos. Devuelve 0 si hay un error.
    """
    try:
        response = supabase.table("players").select("creditos").eq("id", player_id).single().execute()
        if response.data:
            return response.data.get("creditos", 0)
        return 0
    except Exception as e:
        log_event(f"Error al obtener créditos para el jugador ID {player_id}: {e}", player_id, is_error=True)
        return 0

def update_player_credits(player_id: int, new_credits: int) -> bool:
    """
    Actualiza la cantidad de créditos de un jugador.

    Args:
        player_id: El ID del jugador.
        new_credits: La nueva cantidad de créditos.

    Returns:
        True si la actualización fue exitosa, False en caso contrario.
    """
    try:
        supabase.table("players").update({"creditos": new_credits}).eq("id", player_id).execute()
        log_event(f"Créditos del jugador ID {player_id} actualizados a {new_credits}.", player_id)
        return True
    except Exception as e:
        log_event(f"Error al actualizar créditos para el jugador ID {player_id}: {e}", player_id, is_error=True)
        return False