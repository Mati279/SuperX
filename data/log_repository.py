# data/log_repository.py
"""
Repositorio de Logs.
Gestiona el registro de eventos del sistema.
"""

import datetime
from typing import List, Dict, Any, Optional

from data.database import get_supabase


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


def log_event(
    message: str,
    player_id: Optional[int] = None,
    event_type: str = "GENERAL",
    is_error: bool = False
) -> None:
    """
    Registra un evento en la tabla de logs de la base de datos.

    Args:
        message: Mensaje del evento
        player_id: ID del jugador (opcional para eventos globales)
        event_type: Tipo de evento (GENERAL, ERROR, ECONOMY, etc.)
        is_error: Si es un error (para formateo de mensaje)
    """
    # Para eventos globales sin player_id, solo imprimir
    if player_id is None:
        prefix = "❌ ERROR: " if is_error else "📋 "
        print(f"{prefix}{message}")
        return

    # Formatear mensaje si es error
    final_message = f"❌ {message}" if is_error else message

    log_data = {
        "evento_texto": str(final_message),
        "player_id": int(player_id),
        "fecha_evento": datetime.datetime.now().isoformat()
    }

    try:
        _get_db().table("logs").insert(log_data).execute()
    except Exception as e:
        # Imprimir el error pero no fallar
        print(f"❌ ERROR CRÍTICO AL GUARDAR LOG: {e}")


def get_recent_logs(player_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Obtiene los logs más recientes de un jugador.

    Args:
        player_id: ID del jugador
        limit: Cantidad máxima de logs a retornar

    Returns:
        Lista de logs ordenados por fecha descendente
    """
    if player_id is None:
        return []

    try:
        response = _get_db().table("logs") \
            .select("*") \
            .eq("player_id", int(player_id)) \
            .order("fecha_evento", desc=True) \
            .limit(limit) \
            .execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"❌ ERROR CRÍTICO AL LEER LOGS: {e}")
        return []


def clear_player_logs(player_id: int) -> bool:
    """
    Elimina el historial de logs de un jugador.

    Args:
        player_id: ID del jugador

    Returns:
        True si la operación fue exitosa
    """
    try:
        _get_db().table("logs").delete().eq("player_id", int(player_id)).execute()
        return True
    except Exception as e:
        print(f"Error al limpiar logs: {e}")
        return False


def get_global_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Obtiene los logs más recientes de todos los jugadores.

    Args:
        limit: Cantidad máxima de logs

    Returns:
        Lista de logs globales
    """
    try:
        response = _get_db().table("logs") \
            .select("*") \
            .order("fecha_evento", desc=True) \
            .limit(limit) \
            .execute()

        return response.data if response.data else []

    except Exception as e:
        print(f"❌ ERROR AL LEER LOGS GLOBALES: {e}")
        return []
