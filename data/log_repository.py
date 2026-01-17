# data/log_repository.py
import datetime
from typing import List, Dict, Any
from .database import supabase

def log_event(message: str, player_id: int = None, event_type: str = "GENERAL"):
    """
    Registra un evento en la tabla de logs de la base de datos.
    """
    log_data = {
        "message": message,
        "player_id": player_id,
        "event_type": event_type,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    try:
        supabase.table("logs").insert(log_data).execute()
    except Exception as e:
        print(f"Error al registrar log: {e}")

def get_recent_logs(player_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Obtiene los logs más recientes para un jugador específico.
    Se ha eliminado st.cache_data para garantizar la sincronización en tiempo real del chat.
    """
    try:
        response = supabase.table("logs") \
            .select("*") \
            .eq("player_id", player_id) \
            .order("created_at", descending=True) \
            .limit(limit) \
            .execute()
        
        return response.data if response.data else []
    except Exception as e:
        print(f"Error al obtener logs: {e}")
        return []

def clear_player_logs(player_id: int):
    """
    Elimina el historial de logs de un jugador (útil para resets de pruebas).
    """
    try:
        supabase.table("logs").delete().eq("player_id", player_id).execute()
    except Exception as e:
        print(f"Error al limpiar logs: {e}")