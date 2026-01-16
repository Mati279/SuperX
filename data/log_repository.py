# data/log_repository.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from data.database import supabase

def log_event(message: str, player_id: Optional[int] = None, is_error: bool = False) -> None:
    """
    Registra un evento en la base de datos.
    BLINDADO: Si falla por FK (jugador no existe), lo guarda como log de sistema o lo imprime.
    """
    print(f"[LOG] {message}")  # Siempre imprimir en consola servidor
    
    try:
        data = {
            "player_id": player_id,
            "message": message,
            "is_error": is_error,
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("logs").insert(data).execute()
        
    except Exception as e:
        # Si falla (ej: el jugador fue borrado en un rollback), intentamos loguear sin player_id
        error_msg = str(e)
        if "foreign key constraint" in error_msg or "23503" in error_msg:
            print(f"⚠️ Aviso: No se pudo asociar log al player_id {player_id} (posiblemente borrado). Guardando como anónimo.")
            try:
                data["player_id"] = None # Guardar como log de sistema
                supabase.table("logs").insert(data).execute()
            except:
                print(f"❌ Fallo total de logging: {message}")
        else:
            print(f"❌ Error crítico logging: {e}")

def get_player_logs(player_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        response = supabase.table("logs")\
            .select("*")\
            .eq("player_id", player_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error recuperando logs: {e}")
        return []