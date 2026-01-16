# data/player_repository.py
from typing import Dict, Any, Optional, IO
import uuid 
# Importamos supabase primero para asegurar que el módulo base esté cargado
from data.database import supabase
# Importamos log_event después. Si log_repository importa database, ya estará en caché.
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
    """Obtiene todos los recursos económicos del jugador."""
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
    finances = get_player_finances(player_id)
    return finances.get("creditos", 0)

def update_player_resources(player_id: int, updates: Dict[str, int]) -> bool:
    try:
        supabase.table("players").update(updates).eq("id", player_id).execute()
        log_event(f"Recursos actualizados: {list(updates.keys())}", player_id)
        return True
    except Exception as e:
        log_event(f"Error actualizando recursos ID {player_id}: {e}", player_id, is_error=True)
        return False

def update_player_credits(player_id: int, new_credits: int) -> bool:
    return update_player_resources(player_id, {"creditos": new_credits})