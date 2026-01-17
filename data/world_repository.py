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
    Recupera los detalles de ubicación del comandante para el HUD.
    Determina si está en una nave o en un asentamiento y devuelve nombres legibles.
    """
    # Valores por defecto si no se encuentra nada
    loc_data = {
        "system": "Sector Desconocido", 
        "planet": "Espacio Profundo", 
        "base": "Sin Señal"
    }

    try:
        # 1. Verificar si el comandante está a bordo de una nave (Capitán)
        # Nota: En Genesis v1.5, el comandante se asigna como 'capitan_id' de una nave.
        resp_ship = supabase.table("ships").select("nombre, ubicacion_system_id")\
            .eq("capitan_id", commander_id).maybe_single().execute()
        
        if resp_ship.data:
            ship = resp_ship.data
            system_id = ship.get("ubicacion_system_id")
            
            # Base es la Nave
            loc_data["base"] = f"Nave {ship.get('nombre')}"
            
            # Obtener nombre del sistema
            if system_id:
                loc_data["system"] = f"Sector {system_id}" # Fallback
                try:
                    # Intenta obtener el nombre real si la tabla systems tiene columna 'nombre'
                    resp_sys = supabase.table("systems").select("nombre").eq("id", system_id).maybe_single().execute()
                    if resp_sys.data and resp_sys.data.get("nombre"):
                        loc_data["system"] = resp_sys.data.get("nombre")
                except:
                    pass
            
            # Si está en nave y no aterrizado, el planeta es "Espacio Profundo" u "Orbita"
            loc_data["planet"] = "Espacio Profundo" 
            
            return loc_data

        # 2. TODO: Lógica futura para cuando el comandante esté asignado a un Asset terrestre (Edificio/Base)
        # Aquí se consultaría la tabla 'planet_assets' o 'characters.ubicacion' si cambia la lógica.
        
        return loc_data

    except Exception as e:
        # Silenciar error en UI, loguear en backend
        log_event(f"Error HUD Location: {e}", is_error=True)
        return loc_data