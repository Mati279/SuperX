# data/log_repository.py
from .database import supabase
from typing import Optional
import logging

# Configurar logging
logger = logging.getLogger(__name__)

def log_event(text: str, player_id: Optional[int] = None, is_error: bool = False) -> None:
    """
    Registra un evento en la consola y en la tabla 'logs' de la base de datos.

    Args:
        text: El texto del evento a registrar.
        player_id: (Opcional) El ID del jugador asociado al evento.
        is_error: (Opcional) Si es True, prefija el evento con "ERROR:".
    """
    prefix = "ERROR: " if is_error else ""
    full_text = f"{prefix}{text}"

    # Logging estructurado según severidad
    if is_error:
        logger.error(full_text)
    else:
        logger.info(full_text)

    try:
        # Obtener el tick actual del mundo para tener logs contextualizados
        from data.world_repository import get_world_state
        world_state = get_world_state()
        current_tick = world_state.get('current_tick', 1)

        log_data = {"evento_texto": full_text, "turno": current_tick}
        if player_id:
            log_data["player_id"] = player_id

        supabase.table("logs").insert(log_data).execute()

    except Exception as e:
        # Logging crítico si falla el registro en BD
        logger.critical(f"Fallo al registrar evento en la base de datos: {e}")

def get_recent_logs(player_id: Optional[int] = None, limit: int = 10) -> list:
    """
    Obtiene los logs más recientes de la base de datos, opcionalmente por jugador.
    
    Args:
        player_id: (Opcional) El ID del jugador para filtrar los logs.
        limit: El número máximo de logs a obtener.
        
    Returns:
        Una lista de diccionarios con los datos de los logs.
    """
    try:
        query = supabase.table("logs").select("*")
        if player_id:
            query = query.eq("player_id", player_id)
            
        response = query.order("id", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error al obtener logs para el jugador {player_id}: {e}", player_id=player_id, is_error=True)
        return []

