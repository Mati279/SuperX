# data/world_repository.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .database import supabase
from data.log_repository import log_event

def get_world_state() -> Dict[str, Any]:
    """Obtiene el estado actual del mundo (ticks, freeze)."""
    try:
        response = supabase.table("world_state").select("*").single().execute()
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
        supabase.table("action_queue").insert(data).execute()
        log_event(f"Acción encolada para el siguiente ciclo.", player_id)
        return True
    except Exception as e:
        log_event(f"Error encolando acción: {e}", player_id, is_error=True)
        return False

def try_trigger_db_tick(target_date_iso: str) -> bool:
    """
    Llama a la función RPC de Supabase para intentar reclamar el Tick.
    Retorna True si este proceso fue el ganador y debe ejecutar la lógica.
    """
    try:
        # Llamamos a la función SQL creada en el paso 1
        response = supabase.rpc("try_process_tick", {"target_date": target_date_iso}).execute()
        return response.data # True o False
    except Exception as e:
        log_event(f"Error RPC try_process_tick: {e}", is_error=True)
        return False

def force_db_tick() -> bool:
    """
    DEBUG: Fuerza la actualización del tick en DB ignorando la fecha.
    """
    try:
        # 1. Obtener estado actual
        current = get_world_state()
        new_tick = current.get('current_tick', 1) + 1
        
        # 2. Forzar actualización
        supabase.table("world_state").update({
            "current_tick": new_tick,
            "last_tick_processed_at": datetime.utcnow().isoformat()
        }).eq("id", 1).execute()
        
        return True
    except Exception as e:
        log_event(f"Error forzando tick (DEBUG): {e}", is_error=True)
        return False

def get_pending_actions_count(player_id: int) -> int:
    """Cuenta cuántas acciones tiene encoladas el jugador."""
    try:
        response = supabase.table("action_queue").select("id", count="exact")\
            .eq("player_id", player_id).eq("status", "PENDING").execute()
        return response.count if response.count else 0
    except Exception:
        return 0

def get_all_pending_actions() -> List[Dict[str, Any]]:
    """Recupera todas las acciones pendientes para procesar en el Tick."""
    try:
        response = supabase.table("action_queue").select("*").eq("status", "PENDING").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error recuperando cola de acciones: {e}", is_error=True)
        return []

def mark_action_processed(action_id: int, result_status: str) -> None:
    """
    Actualiza el estado de una acción tras el tick.
    result_status: 'PROCESSED' o 'ERROR'
    """
    try:
        supabase.table("action_queue").update({
            "status": result_status,
            "processed_at": datetime.utcnow().isoformat()
        }).eq("id", action_id).execute()
    except Exception as e:
        log_event(f"Error actualizando estado de acción {action_id}: {e}", is_error=True)

def get_commander_location_display(commander_id: int) -> Dict[str, str]:
    """
    Recupera los detalles de ubicación del comandante basándose ÚNICAMENTE
    en su BASE PLANETARIA. Ignora naves.
    """
    loc_data = {
        "system": "Sector Desconocido", 
        "planet": "Planeta Desconocido", 
        "base": "Sin Base"
    }

    try:
        # 1. Obtener el player_id asociado al comandante
        char_res = supabase.table("characters").select("player_id").eq("id", commander_id).maybe_single().execute()
        if not char_res.data:
            return loc_data
        
        player_id = char_res.data.get("player_id")

        # 2. Buscar el ASENTAMIENTO PRINCIPAL (Base) en planet_assets
        # Se toma el de mayor población o el primero encontrado.
        asset_res = supabase.table("planet_assets")\
            .select("system_id, planet_id, nombre_asentamiento")\
            .eq("player_id", player_id)\
            .order("poblacion", desc=True)\
            .limit(1)\
            .maybe_single()\
            .execute()
        
        if asset_res.data:
            asset = asset_res.data
            system_id = asset.get("system_id")
            planet_id = asset.get("planet_id")
            
            loc_data["base"] = asset.get("nombre_asentamiento", "Base Principal")
            
            # 3. Obtener Nombre Real del Sistema
            if system_id:
                try:
                    sys_res = supabase.table("systems").select("nombre").eq("id", system_id).maybe_single().execute()
                    if sys_res.data:
                        loc_data["system"] = sys_res.data.get("nombre", f"Sector {system_id}")
                except Exception:
                    loc_data["system"] = f"Sector {system_id}"

            # 4. Obtener Nombre Real del Planeta
            if planet_id:
                try:
                    pl_res = supabase.table("planets").select("nombre").eq("id", planet_id).maybe_single().execute()
                    if pl_res.data:
                        loc_data["planet"] = pl_res.data.get("nombre", "Planeta Desconocido")
                except Exception:
                    pass
            
        return loc_data

    except Exception as e:
        log_event(f"Error obteniendo ubicación HUD: {e}", is_error=True)
        return loc_data