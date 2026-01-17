# data/log_repository.py
from typing import List, Dict, Any, Optional
from data.database import supabase

def log_event(message: str, player_id: Optional[int] = None, is_error: bool = False) -> None:
    """
    Registra un evento en la base de datos.
    BLINDADO: Si falla por FK (jugador borrado), lo guarda como log de sistema anónimo.
    Nota: created_at se genera automáticamente en Supabase.
    """
    print(f"[LOG] {message}")  # Debug en consola

    try:
        data = {
            "player_id": player_id,
            "message": message,
            "is_error": is_error
        }
        supabase.table("logs").insert(data).execute()

    except Exception as e:
        # Si falla (ej: el jugador fue borrado en un rollback), intentamos loguear sin player_id
        error_msg = str(e)
        if "foreign key constraint" in error_msg or "23503" in error_msg:
            print(f"⚠️ Aviso: No se pudo asociar log al player_id {player_id}. Guardando como anónimo.")
            try:
                data["player_id"] = None  # Guardar como log de sistema
                supabase.table("logs").insert(data).execute()
            except:
                print(f"❌ Fallo total de logging: {message}")
        else:
            print(f"❌ Error crítico logging: {e}")

def get_recent_logs(player_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Obtiene los logs más recientes de un jugador.
    Renombrado: Antes get_player_logs, ahora get_recent_logs para compatibilidad con UI.
    Nota: Usa 'id' para ordenar ya que es autoincremental (más reciente = mayor id).
    """
    try:
        response = supabase.table("logs")\
            .select("*")\
            .eq("player_id", player_id)\
            .order("id", desc=True)\
            .limit(limit)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error recuperando logs: {e}")
        return []