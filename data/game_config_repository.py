# data/game_config_repository.py
from typing import Dict
from .database import supabase
from data.log_repository import log_event

def get_game_config() -> Dict[str, str]:
    """
    Obtiene la configuración del juego (descripción del mundo, reglas)
    desde la tabla 'game_config'.

    Returns:
        Un diccionario donde las claves son los 'key' de la tabla
        y los valores son los 'value'.
    """
    try:
        response = supabase.table("game_config").select("key", "value").execute()
        if response.data:
            return {item['key']: item['value'] for item in response.data}
    except Exception as e:
        log_event(f"Error crítico al leer la configuración del juego: {e}", is_error=True)
    
    # Devuelve un diccionario vacío si hay un error o no hay configuración
    return {}

def get_current_tick() -> int:
    """
    Obtiene el tick actual del juego.
    Esta función actúa como puente hacia world_repository para evitar ciclos de importación
    con character_repository.
    """
    try:
        # Importación local para evitar ciclos de dependencia circulares
        from data.world_repository import get_world_state
        state = get_world_state()
        return state.get("current_tick", 1)
    except Exception as e:
        log_event(f"Error recuperando current_tick en config: {e}", is_error=True)
        return 1