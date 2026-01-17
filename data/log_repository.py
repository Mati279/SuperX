# data/log_repository.py
import datetime
from typing import List, Dict, Any
from .database import supabase

def log_event(message: str, player_id: int = None, event_type: str = "GENERAL"):
    """
    Registra un evento en la tabla de logs de la base de datos.
    """
    # Validar tipos básicos para evitar fallos silenciosos
    if player_id is None:
        print("⚠️ Advertencia: Intento de loggear sin player_id")
        return

    # FIX: Ajuste al esquema real de la DB (ver db_setup.sql)
    # message -> evento_texto
    # created_at -> fecha_evento
    # event_type -> NO EXISTE en la tabla logs, se ignora
    log_data = {
        "evento_texto": str(message),
        "player_id": int(player_id), 
        "fecha_evento": datetime.datetime.now().isoformat()
    }
    
    try:
        supabase.table("logs").insert(log_data).execute()
    except Exception as e:
        # IMPORTANTE: Imprimir el error real
        print(f"❌ ERROR CRÍTICO AL GUARDAR LOG: {e}")
        # Opcional: re-lanzar si quieres que rompa la app para debuggear
        # raise e 

def get_recent_logs(player_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Obtiene los logs más recientes.
    SIN CACHÉ y con reporte de errores explícito.
    """
    if player_id is None:
        return []

    try:
        # FIX: 'descending' no es válido, se usa 'desc'
        # FIX: 'created_at' no existe, se usa 'fecha_evento'
        response = supabase.table("logs") \
            .select("*") \
            .eq("player_id", int(player_id)) \
            .order("fecha_evento", desc=True) \
            .limit(limit) \
            .execute()
        
        data = response.data
        if data is None:
            return []
        return data

    except Exception as e:
        print(f"❌ ERROR CRÍTICO AL LEER LOGS: {e}")
        return []

def clear_player_logs(player_id: int):
    """
    Elimina el historial de logs de un jugador.
    """
    try:
        supabase.table("logs").delete().eq("player_id", int(player_id)).execute()
    except Exception as e:
        print(f"Error al limpiar logs: {e}")