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
        if response and response.data:
            return response.data
        return {"last_tick_processed_at": None, "is_frozen": False, "current_tick": 1}
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
        response = _get_db().table("action_queue").insert(data).execute()
        if not response:
            log_event("Error crítico: No hubo respuesta al encolar acción.", player_id, is_error=True)
            return False
            
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
        response = _get_db().table("world_state").update({
            "current_tick": new_tick,
            "last_tick_processed_at": datetime.utcnow().isoformat()
        }).eq("id", 1).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error forzando tick (DEBUG): {e}", is_error=True)
        return False

def get_pending_actions_count(player_id: int) -> int:
    try:
        response = _get_db().table("action_queue").select("id", count="exact")\
            .eq("player_id", player_id).eq("status", "PENDING").execute()
        return response.count if response and response.count is not None else 0
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
        char_res = _get_db().table("characters").select("player_id").eq("id", commander_id).maybe_single().execute()
        
        # Guard: Validación de respuesta nula
        if not char_res or not char_res.data:
            return default_loc
        
        player_id = char_res.data.get("player_id")

        # 2. Buscar el ASENTAMIENTO PRINCIPAL (Base) en planet_assets
        # Refactor V5.8: Ordenamiento corregido a 'population'
        asset_res = _get_db().table("planet_assets")\
            .select("system_id, planet_id, nombre_asentamiento")\
            .eq("player_id", player_id)\
            .order("population", desc=True)\
            .limit(1)\
            .maybe_single()\
            .execute()
        
        # Guard: Validación de respuesta nula para activos
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
                sys_res = _get_db().table("systems").select("name").eq("id", asset["system_id"]).single().execute()
                if sys_res and sys_res.data:
                    loc_data["system"] = sys_res.data.get("name")
            except Exception:
                pass

        # 4. Obtener Nombre Real del Planeta
        if asset.get("planet_id"):
            try:
                pl_res = _get_db().table("planets").select("name").eq("id", asset["planet_id"]).single().execute()
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
        response = _get_db().table("systems").select("*, security, security_breakdown").eq("id", system_id).single().execute()
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

def update_system_controller(system_id: int, controller_id: Optional[int]) -> bool:
    """
    Actualiza la entidad (Facción o Jugador) que controla el sistema en la base de datos.
    Se usa para marcar el dominio > 50% de los planetas o para asignaciones Debug.
    
    Nota V8.1: 'controller_id' puede ser un faction_id o un player_id, dependiendo
    de si la DB tiene la constraint FK deshabilitada.
    """
    try:
        # Se usa 'controlling_faction_id' por legado, pero puede contener player_id
        # si se ha removido la FK constraint.
        response = _get_db().table("systems").update({
            "controlling_faction_id": controller_id
        }).eq("id", system_id).execute()
        
        if response:
            status = f"Entidad {controller_id}" if controller_id else "Neutral/Disputado"
            log_event(f"Control del Sistema {system_id} actualizado a: {status}", event_type="GALAXY_CONTROL")
            return True
        return False
    except Exception as e:
        log_event(f"Error actualizando controlador de sistema {system_id}: {e}", is_error=True)
        return False

# --- V4.4: SEGURIDAD DE SISTEMAS ---

def update_system_security(system_id: int, security: float) -> bool:
    """Actualiza la seguridad promedio del sistema."""
    try:
        response = _get_db().table("systems").update({"security": security}).eq("id", system_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad sistema {system_id}: {e}", is_error=True)
        return False

def update_system_security_data(system_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """
    Actualiza la seguridad agregada y su desglose detallado en la tabla 'systems'.
    """
    try:
        response = _get_db().table("systems").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", system_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad detallada sistema {system_id}: {e}", is_error=True)
        return False


# --- V8.0: SECTORES Y EDIFICIOS ESTELARES ---

def get_stellar_sector_by_system(system_id: int) -> Optional[Dict[str, Any]]:
    """
    V8.0: Obtiene el sector estelar de un sistema.

    Args:
        system_id: ID del sistema.

    Returns:
        Dict con datos del sector estelar o None si no existe.
    """
    try:
        response = _get_db().table("sectors")\
            .select("*")\
            .eq("system_id", system_id)\
            .is_("planet_id", "null")\
            .single()\
            .execute()
        return response.data if response and response.data else None
    except Exception as e:
        log_event(f"Error obteniendo sector estelar del sistema {system_id}: {e}", is_error=True)
        return None


def get_stellar_buildings_by_system(system_id: int, player_id: int) -> List[Dict[str, Any]]:
    """
    V8.0: Obtiene los edificios estelares de un sistema controlados por un jugador.

    Args:
        system_id: ID del sistema.
        player_id: ID del jugador.

    Returns:
        Lista de edificios estelares del jugador en ese sistema.
    """
    try:
        # Primero obtenemos el sector estelar del sistema
        sector = get_stellar_sector_by_system(system_id)
        if not sector:
            return []

        sector_id = sector.get("id")

        # Buscamos edificios en ese sector que pertenezcan al jugador
        # Nota: Asumimos una tabla 'stellar_buildings' o reutilizamos 'planet_buildings'
        # con un campo sector_id. Ajustar según esquema real.
        try:
            response = _get_db().table("stellar_buildings")\
                .select("*")\
                .eq("sector_id", sector_id)\
                .eq("player_id", player_id)\
                .execute()
            return response.data if response and response.data else []
        except Exception:
            # Si la tabla stellar_buildings no existe, intentamos con planet_buildings
            # usando el sector_id del sector estelar
            try:
                response = _get_db().table("planet_buildings")\
                    .select("*")\
                    .eq("sector_id", sector_id)\
                    .eq("player_id", player_id)\
                    .execute()
                return response.data if response and response.data else []
            except Exception:
                return []
    except Exception as e:
        log_event(f"Error obteniendo edificios estelares del sistema {system_id}: {e}", is_error=True)
        return []


def create_stellar_building(
    system_id: int,
    player_id: int,
    building_type: str
) -> Optional[Dict[str, Any]]:
    """
    V8.0: Crea un edificio estelar en el sector estelar de un sistema.

    Args:
        system_id: ID del sistema.
        player_id: ID del jugador.
        building_type: Tipo de edificio (ej: 'stellar_fortress', 'trade_beacon').

    Returns:
        Dict con el edificio creado o None si falla.
    """
    try:
        sector = get_stellar_sector_by_system(system_id)
        if not sector:
            log_event(f"No existe sector estelar en sistema {system_id}", player_id, is_error=True)
            return None

        sector_id = sector.get("id")

        # Verificar slots disponibles
        max_slots = sector.get("max_slots", 3)
        existing = get_stellar_buildings_by_system(system_id, player_id)
        if len(existing) >= max_slots:
            log_event(f"Sector estelar lleno en sistema {system_id}", player_id, is_error=True)
            return None

        # Crear el edificio
        data = {
            "sector_id": sector_id,
            "player_id": player_id,
            "building_type": building_type,
            "is_active": True
        }

        try:
            response = _get_db().table("stellar_buildings").insert(data).execute()
        except Exception:
            # Fallback a planet_buildings si stellar_buildings no existe
            response = _get_db().table("planet_buildings").insert(data).execute()

        if response and response.data:
            log_event(f"Edificio estelar {building_type} construido en sistema {system_id}", player_id)
            return response.data[0] if isinstance(response.data, list) else response.data
        return None
    except Exception as e:
        log_event(f"Error creando edificio estelar: {e}", player_id, is_error=True)
        return None