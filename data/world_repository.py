# data/world_repository.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from data.database import get_supabase
from data.log_repository import log_event


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()

def get_world_state() -> Dict[str, Any]:
    """Obtiene el estado actual del mundo (ticks, freeze)."""
    try:
        response = _get_db().table("world_state").select("*").single().execute()
        return response.data
    except Exception as e:
        log_event(f"Error obteniendo world_state: {e}", is_error=True)
        return {"last_tick_processed_at": None, "is_frozen": False, "current_tick": 1}

def queue_player_action(player_id: int, action_text: str) -> bool:
    """Inserta una acción en la cola de espera."""
    try:
        data = {
            "player_id": player_id,
            "action_text": action_text,
            "status": "PENDING"
        }
        _get_db().table("action_queue").insert(data).execute()
        log_event(f"Acción encolada para el siguiente ciclo.", player_id)
        return True
    except Exception as e:
        log_event(f"Error encolando acción: {e}", player_id, is_error=True)
        return False

def try_trigger_db_tick(target_date_iso: str) -> bool:
    """Llama a la función RPC de Supabase para intentar reclamar el Tick."""
    try:
        response = supabase.rpc("try_process_tick", {"target_date": target_date_iso}).execute()
        return response.data # True o False
    except Exception as e:
        log_event(f"Error RPC try_process_tick: {e}", is_error=True)
        return False

def force_db_tick() -> bool:
    """DEBUG: Fuerza la actualización del tick en DB."""
    try:
        current = get_world_state()
        new_tick = current.get('current_tick', 1) + 1
        _get_db().table("world_state").update({
            "current_tick": new_tick,
            "last_tick_processed_at": datetime.utcnow().isoformat()
        }).eq("id", 1).execute()
        return True
    except Exception as e:
        log_event(f"Error forzando tick (DEBUG): {e}", is_error=True)
        return False

def get_pending_actions_count(player_id: int) -> int:
    try:
        response = _get_db().table("action_queue").select("id", count="exact")\
            .eq("player_id", player_id).eq("status", "PENDING").execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def get_all_pending_actions() -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("action_queue").select("*").eq("status", "PENDING").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error recuperando cola de acciones: {e}", is_error=True)
        return []

def mark_action_processed(action_id: int, result_status: str) -> None:
    try:
        _get_db().table("action_queue").update({
            "status": result_status,
            "processed_at": datetime.utcnow().isoformat()
        }).eq("id", action_id).execute()
    except Exception as e:
        log_event(f"Error actualizando estado de acción {action_id}: {e}", is_error=True)

def get_commander_location_display(commander_id: int) -> Dict[str, str]:
    """
    Recupera los detalles de ubicación del comandante basándose ÚNICAMENTE
    en su BASE PLANETARIA (Asset).
    Retorna: { 'system': 'NombreSistema', 'planet': 'NombrePlaneta', 'base': 'NombreBase' }
    """
    default_loc = {
        "system": "Sector Desconocido", 
        "planet": "---", 
        "base": "Sin Base"
    }

    try:
        # 1. Obtener el player_id asociado al comandante
        char_res = _get_db().table("characters").select("player_id").eq("id", commander_id).maybe_single().execute()
        if not char_res.data:
            return default_loc
        
        player_id = char_res.data.get("player_id")

        # 2. Buscar el ASENTAMIENTO PRINCIPAL (Base) en planet_assets
        # Priorizamos por población o fecha de creación
        asset_res = _get_db().table("planet_assets")\
            .select("system_id, planet_id, nombre_asentamiento")\
            .eq("player_id", player_id)\
            .order("poblacion", desc=True)\
            .limit(1)\
            .maybe_single()\
            .execute()
        
        if not asset_res.data:
            return default_loc

        asset = asset_res.data
        loc_data = {
            "base": asset.get("nombre_asentamiento", "Base"),
            "system": f"Sector {asset.get('system_id')}",
            "planet": f"Planeta {asset.get('planet_id')}"
        }
        
        # 3. Obtener Nombre Real del Sistema
        if asset.get("system_id"):
            try:
                sys_res = _get_db().table("systems").select("name").eq("id", asset["system_id"]).single().execute()
                if sys_res.data:
                    loc_data["system"] = sys_res.data.get("name")
            except Exception:
                pass

        # 4. Obtener Nombre Real del Planeta
        if asset.get("planet_id"):
            try:
                pl_res = _get_db().table("planets").select("name").eq("id", asset["planet_id"]).single().execute()
                if pl_res.data:
                    loc_data["planet"] = pl_res.data.get("name")
            except Exception:
                pass
            
        return loc_data

    except Exception as e:
        log_event(f"Error obteniendo ubicación HUD: {e}", is_error=True)
        return default_loc


# --- FUNCIONES PARA OBTENER SISTEMAS Y PLANETAS DE LA BD ---

def get_all_systems_from_db() -> List[Dict[str, Any]]:
    """
    Obtiene todos los sistemas estelares de la base de datos.

    Returns:
        Lista de sistemas con id, name, x, y, star_class
    """
    try:
        response = _get_db().table("systems").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sistemas de BD: {e}", is_error=True)
        return []


def get_system_by_id(system_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene un sistema por su ID.

    Args:
        system_id: ID del sistema

    Returns:
        Diccionario con datos del sistema o None
    """
    try:
        response = _get_db().table("systems").select("*").eq("id", system_id).single().execute()
        return response.data if response.data else None
    except Exception:
        return None


def get_planets_by_system_id(system_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los planetas de un sistema.

    Args:
        system_id: ID del sistema

    Returns:
        Lista de planetas del sistema
    """
    try:
        response = _get_db().table("planets").select("*").eq("system_id", system_id).order("orbital_ring").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del sistema {system_id}: {e}", is_error=True)
        return []


def get_starlanes_from_db() -> List[Dict[str, Any]]:
    """
    Obtiene todas las rutas estelares (conexiones entre sistemas).

    Returns:
        Lista de starlanes con system_a_id, system_b_id, distance
    """
    try:
        response = _get_db().table("starlanes").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo starlanes: {e}", is_error=True)
        return []