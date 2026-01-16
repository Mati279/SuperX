# core/time_engine.py
from datetime import datetime, time
import pytz
from data.world_repository import get_world_state, try_trigger_db_tick
from data.log_repository import log_event

# Forzamos la zona horaria a Argentina (GMT-3)
SAFE_TIMEZONE = pytz.timezone('America/Argentina/Buenos_Aires')

def get_server_time() -> datetime:
    """Retorna la hora actual en GMT-3."""
    return datetime.now(SAFE_TIMEZONE)

def is_lock_in_window() -> bool:
    """Retorna True si estamos en la ventana de bloqueo (23:50 - 00:00)."""
    now = get_server_time()
    return now.time() >= time(23, 50)

def check_and_trigger_tick() -> None:
    """
    Verifica si debemos ejecutar un Tick (Lazy Tick).
    Esta función debe llamarse al cargar la app o antes de una acción.
    """
    now = get_server_time()
    today_date_iso = now.date().isoformat() # YYYY-MM-DD
    
    # Intentamos ejecutar el tick en la DB de forma atómica.
    # Le pasamos la fecha de "hoy". Si la DB dice que el último tick fue ayer,
    # actualizará y devolverá True. Si ya se procesó hoy, devuelve False.
    if try_trigger_db_tick(today_date_iso):
        _execute_game_logic_tick(now)

def _execute_game_logic_tick(execution_time: datetime):
    """
    Lógica pesada del juego que ocurre cuando cambia el día.
    Generación de recursos, movimiento de flotas, etc.
    """
    log_event(f"🔄 EJECUTANDO TICK GALÁCTICO: {execution_time.isoformat()}")
    
    # AQUÍ IRÍA LA LÓGICA DE:
    # 1. Procesar la action_queue pendiente.
    # 2. Regenerar puntos de acción/recursos.
    # 3. Mover naves en tránsito.
    
    # Por ahora, solo dejamos constancia en el log.
    log_event("✅ Ciclo solar completado. Sistemas nominales.")

def get_world_status_display() -> dict:
    """Genera la información para el widget del reloj en la UI."""
    state = get_world_state()
    now = get_server_time()
    
    status = "OPERATIVO"
    if state.get("is_frozen"):
        status = "CONGELADO"
    elif is_lock_in_window():
        status = "BLOQUEO"
        
    return {
        "tick": state.get("current_tick", 1),
        "time": now.strftime("%H:%M"),
        "status": status,
        "is_frozen": state.get("is_frozen", False),
        "is_lock_in": is_lock_in_window()
    }