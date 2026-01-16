# data/world_repository.py
from typing import Dict, Any, Optional
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