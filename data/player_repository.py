# data/player_repository.py
from typing import Dict, Any, Optional, IO
import uuid # IMPORTANTE: Para generar tokens únicos
# CORRECCIÓN: Importación absoluta confirmada
from data.database import supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image

def get_player_by_name(name: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("players").select("*").eq("nombre", name).single().execute()
        return response.data
    except Exception:
        return None

def get_player_by_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida un token de sesión y devuelve el jugador asociado."""
    if not token: return None
    try:
        response = supabase.table("players").select("*").eq("session_token", token).single().execute()
        return response.data
    except Exception:
        return None

def create_session_token(player_id: int) -> str:
    """Genera un nuevo token, lo guarda en DB y lo devuelve."""
    new_token = str(uuid.uuid4())
    try:
        supabase.table("players").update({"session_token": new_token}).eq("id", player_id).execute()
        return new_token
    except Exception as e:
        log_event(f"Error al crear sesión: {e}", is_error=True)
        return ""

def clear_session_token(player_id: int) -> None:
    """Elimina el token de sesión de la base de datos."""
    try:
        supabase.table("players").update({"session_token": None}).eq("id", player_id).execute()
    except Exception as e:
        log_event(f"Error al cerrar sesión: {e}", is_error=True)

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
    if get_player_by_name(user_name):
        log_event(f"Intento de registro con nombre de usuario duplicado: {user_name}", is_error=True)
        raise ValueError("El nombre de Comandante ya está en uso.")

    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    
    new_player_data = {
        "nombre": user_name,
        "pin": hash_password(pin),
        "faccion_nombre": faction_name,
        "banner_url": banner_url,
        # Valores iniciales por defecto definidos en DB, pero se pueden forzar aquí si se desea
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

# --- Funciones de Gestión Económica (MMFR) ---

def get_player_finances(player_id: int) -> Dict[str, int]:
    """
    Obtiene todos los recursos económicos del jugador.
    
    Returns:
        Diccionario con creditos, materiales, componentes, celulas_energia, influencia.
    """
    try:
        response = supabase.table("players")\
            .select("creditos, materiales, componentes, celulas_energia, influencia")\
            .eq("id", player_id).single().execute()
        
        if response.data:
            return response.data
        return {
            "creditos": 0, "materiales": 0, "componentes": 0, 
            "celulas_energia": 0, "influencia": 0
        }
    except Exception as e:
        log_event(f"Error al obtener finanzas para ID {player_id}: {e}", player_id, is_error=True)
        return {
            "creditos": 0, "materiales": 0, "componentes": 0, 
            "celulas_energia": 0, "influencia": 0
        }

def get_player_credits(player_id: int) -> int:
    """Wrapper legacy para obtener solo créditos."""
    finances = get_player_finances(player_id)
    return finances.get("creditos", 0)

def update_player_resources(player_id: int, updates: Dict[str, int]) -> bool:
    """
    Actualiza uno o varios recursos del jugador.
    
    Args:
        player_id: ID del jugador.
        updates: Diccionario con los campos a actualizar (ej: {"creditos": 500, "materiales": 10})
    """
    try:
        supabase.table("players").update(updates).eq("id", player_id).execute()
        # Log simplificado para no saturar
        log_event(f"Recursos actualizados: {list(updates.keys())}", player_id)
        return True
    except Exception as e:
        log_event(f"Error actualizando recursos ID {player_id}: {e}", player_id, is_error=True)
        return False

def update_player_credits(player_id: int, new_credits: int) -> bool:
    """Wrapper legacy para actualizar solo créditos."""
    return update_player_resources(player_id, {"creditos": new_credits})