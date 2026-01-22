# data/world_repository.py (Completo)
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

def has_pending_investigation(player_id: int) -> bool:
    """Verifica si el jugador ya tiene una investigación en curso (PENDING)."""
    try:
        # Buscamos acciones pendientes que contengan el comando interno de investigación
        response = _get_db().table("action_queue")\
            .select("action_text")\
            .eq("player_id", player_id)\
            .eq("status", "PENDING")\
            .execute()

        if not response or not response.data:
            return False

        for action in response.data:
            if "[INTERNAL_EXECUTE_INVESTIGATION]" in action.get("action_text", ""):
                return True
        return False
    except Exception:
        return False


def has_pending_search(player_id: int) -> bool:
    """Verifica si el jugador tiene una busqueda de candidatos pendiente."""
    try:
        response = _get_db().table("action_queue")\
            .select("action_text")\
            .eq("player_id", player_id)\
            .eq("status", "PENDING")\
            .execute()

        if not response or not response.data:
            return False

        for action in response.data:
            if "[INTERNAL_SEARCH_CANDIDATES]" in action.get("action_text", ""):
                return True
        return False
    except Exception:
        return False


def get_investigating_target_info(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene informacion sobre la investigacion pendiente.
    Retorna dict con target_type, target_id, target_name si existe.
    """
    try:
        response = _get_db().table("action_queue")\
            .select("action_text")\
            .eq("player_id", player_id)\
            .eq("status", "PENDING")\
            .execute()

        if not response or not response.data:
            return None

        import re
        for action in response.data:
            text = action.get("action_text", "")
            if "[INTERNAL_EXECUTE_INVESTIGATION]" not in text:
                continue

            result = {}

            # Extraer target_type
            type_match = re.search(r"target_type=(\w+)", text)
            if type_match:
                result["target_type"] = type_match.group(1)

            # Extraer candidate_id o character_id
            id_match = re.search(r"(?:candidate_id|character_id)=(\d+)", text)
            if id_match:
                result["target_id"] = int(id_match.group(1))

            # Extraer nombre (formato antiguo: sobre 'nombre')
            name_match = re.search(r"sobre '([^']+)'", text)
            if name_match:
                result["target_name"] = name_match.group(1)

            return result if result else None

        return None
    except Exception:
        return None

def try_trigger_db_tick(target_date_iso: str) -> bool:
    """Llama a la función RPC de Supabase para intentar reclamar el Tick."""
    try:
        response = _get_db().rpc("try_process_tick", {"target_date": target_date_iso}).execute()
        return response.data if response else False
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
        return response.count if response and response.count else 0
    except Exception:
        return 0

def get_all_pending_actions() -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("action_queue").select("*").eq("status", "PENDING").execute()
        return response.data if response and response.data else []
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
        # CORRECCIÓN: Validación robusta para evitar NoneType attribute 'data'
        char_res = _get_db().table("characters").select("player_id").eq("id", commander_id).maybe_single().execute()
        if not char_res or not char_res.data:
            return default_loc
        
        player_id = char_res.data.get("player_id")

        # 2. Buscar el ASENTAMIENTO PRINCIPAL (Base) en planet_assets
        # CORRECCIÓN: Validación robusta para evitar NoneType attribute 'data'
        asset_res = _get_db().table("planet_assets")\
            .select("system_id, planet_id, nombre_asentamiento")\
            .eq("player_id", player_id)\
            .order("poblacion", desc=True)\
            .limit(1)\
            .maybe_single()\
            .execute()
        
        if not asset_res or not asset_res.data:
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
                sys_res = _get_db().table("systems").select("name").eq("id", asset["system_id"]).maybe_single().execute()
                if sys_res and sys_res.data:
                    loc_data["system"] = sys_res.data.get("name")
            except Exception:
                pass

        # 4. Obtener Nombre Real del Planeta
        if asset.get("planet_id"):
            try:
                pl_res = _get_db().table("planets").select("name").eq("id", asset["planet_id"]).maybe_single().execute()
                if pl_res and pl_res.data:
                    loc_data["planet"] = pl_res.data.get("name")
            except Exception:
                pass
            
        return loc_data

    except Exception as e:
        log_event(f"Error obteniendo ubicación HUD: {e}", is_error=True)
        return default_loc


# --- FUNCIONES PARA OBTENER SISTEMAS Y PLANETAS DE LA BD ---

def get_all_systems_from_db() -> List[Dict[str, Any]]:
    """Obtiene todos los sistemas estelares de la base de datos."""
    try:
        response = _get_db().table("systems").select("*, security, security_breakdown").execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sistemas de BD: {e}", is_error=True)
        return []


def get_system_by_id(system_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un sistema por su ID."""
    try:
        response = _get_db().table("systems").select("*, security, security_breakdown").eq("id", system_id).maybe_single().execute()
        return response.data if response and response.data else None
    except Exception:
        return None


def get_planets_by_system_id(system_id: int) -> List[Dict[str, Any]]:
    """Obtiene todos los planetas de un sistema."""
    try:
        response = _get_db().table("planets").select("*").eq("system_id", system_id).order("orbital_ring").execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del sistema {system_id}: {e}", is_error=True)
        return []


def get_starlanes_from_db() -> List[Dict[str, Any]]:
    """Obtiene todas las rutas estelares."""
    try:
        response = _get_db().table("starlanes").select("*").execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo starlanes: {e}", is_error=True)
        return []

# --- ACTUALIZACIÓN DE CONTROL (V4.3.0) ---

def update_system_controller(system_id: int, faction_id: Optional[int]) -> bool:
    """
    Actualiza la facción que controla el sistema en la base de datos.
    Se usa para marcar el dominio > 50% de los planetas.
    """
    try:
        _get_db().table("systems").update({
            "controlling_faction_id": faction_id
        }).eq("id", system_id).execute()
        
        status = f"Facción {faction_id}" if faction_id else "Neutral/Disputado"
        log_event(f"Control del Sistema {system_id} actualizado a: {status}", event_type="GALAXY_CONTROL")
        return True
    except Exception as e:
        log_event(f"Error actualizando controlador de sistema {system_id}: {e}", is_error=True)
        return False

# --- V4.4: SEGURIDAD DE SISTEMAS ---

def update_system_security(system_id: int, security: float) -> bool:
    """Actualiza la seguridad promedio del sistema."""
    try:
        _get_db().table("systems").update({"security": security}).eq("id", system_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando seguridad sistema {system_id}: {e}", is_error=True)
        return False

def update_system_security_data(system_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """
    Actualiza la seguridad agregada y su desglose detallado en la tabla 'systems'.
    """
    try:
        _get_db().table("systems").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", system_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando seguridad detallada sistema {system_id}: {e}", is_error=True)
        return False