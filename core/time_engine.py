# core/time_engine.py
from datetime import datetime, time
import pytz
from data.world_repository import (
    get_world_state, 
    try_trigger_db_tick, 
    force_db_tick,
    get_all_pending_actions, 
    mark_action_processed
)
from data.log_repository import log_event

# Forzamos la zona horaria a Argentina (GMT-3)
SAFE_TIMEZONE = pytz.timezone('America/Argentina/Buenos_Aires')

def get_server_time() -> datetime:
    """Retorna la hora actual en GMT-3."""
    return datetime.now(SAFE_TIMEZONE)

def is_lock_in_window() -> bool:
    """Retorna True si estamos en la ventana de bloqueo (23:50 - 00:00)."""
    now = get_server_time()
    # Definir ventana: 23:50 a 23:59:59
    start_lock = time(23, 50)
    current_time = now.time()
    return current_time >= start_lock

def check_and_trigger_tick() -> None:
    """
    Verifica si debemos ejecutar un Tick (Lazy Tick).
    Esta función debe llamarse al cargar la app o antes de una acción.
    """
    now = get_server_time()
    today_date_iso = now.date().isoformat() # YYYY-MM-DD
    
    # Intentamos ejecutar el tick en la DB de forma atómica.
    if try_trigger_db_tick(today_date_iso):
        _execute_game_logic_tick(now)

def debug_force_tick() -> None:
    """
    DEBUG: Ejecuta el tick manualmente saltándose las validaciones de fecha.
    """
    now = get_server_time()
    log_event("🛠️ COMANDO DEBUG: Forzando Tick Galáctico...")
    
    if force_db_tick():
        _execute_game_logic_tick(now)
    else:
        log_event("❌ Falló el forzado del tick en DB.")

def _execute_game_logic_tick(execution_time: datetime):
    """
    Lógica pesada del juego que ocurre cuando cambia el día.
    Generación de recursos, movimiento de flotas, etc.
    """
    log_event(f"🔄 INICIANDO PROCESAMIENTO DE TICK: {execution_time.isoformat()}")
    
    # 1. PROCESAR COLA DE ACCIONES (LOCK-IN)
    pending_actions = get_all_pending_actions()
    
    if pending_actions:
        log_event(f"📂 Procesando {len(pending_actions)} acciones encolada(s)...")
        
        # Importación local para evitar Circular Import Error
        # time_engine -> gemini_service -> time_engine (¡Boom!)
        from services.gemini_service import resolve_player_action
        
        for item in pending_actions:
            player_id = item['player_id']
            action_text = item['action_text']
            action_id = item['id']
            
            try:
                log_event(f"▶ Ejecutando orden diferida ID {action_id}...", player_id)
                
                # Ejecutamos la acción como si el jugador la acabara de enviar.
                # Nota: resolve_player_action tiene guardias de tiempo, pero como el Tick
                # ocurre teóricamente a las 00:00:01, ya no estamos en la ventana 23:50-00:00,
                # así que la acción pasará.
                resolve_player_action(action_text, player_id)
                
                mark_action_processed(action_id, "PROCESSED")
                
            except Exception as e:
                log_event(f"❌ Error procesando orden diferida {action_id}: {e}", player_id, is_error=True)
                mark_action_processed(action_id, "ERROR")
    else:
        log_event("📂 No hay acciones pendientes en la cola.")

    # 2. OTROS EVENTOS DEL SISTEMA (Recursos, Movimiento, etc.)
    # ... Aquí agregarías lógica futura para regenerar recursos o mover naves ...
    
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