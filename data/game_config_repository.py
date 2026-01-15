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
