# core/time_engine.py
from datetime import datetime, time
import pytz
import random
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

# --- ORQUESTADOR DEL TICK ---

def _execute_game_logic_tick(execution_time: datetime):
    """
    Lógica pesada del juego que ocurre cuando cambia el día.
    Sigue un flujo lineal estricto para garantizar consistencia de datos.
    """
    tick_start = datetime.now()
    log_event(f"🔄 INICIANDO PROCESAMIENTO DE TICK: {execution_time.isoformat()}")

    # 1. Fase de Decremento (Countdowns y Persistencia)
    _phase_decrement_and_persistence()

    # 2. Resolución de Simultaneidad (Conflictos en el mismo Tick)
    _phase_concurrency_resolution()

    # 3. Fase de Prestigio (Suma Cero)
    _phase_prestige_calculation()

    # 4. Fase Macro económica (MMFR)
    _phase_macroeconomics()

    # 5. Fase de Logística Social y Salud de POPs
    _phase_social_logistics()

    # 6. Fase de Resolución de Misiones y Eventos de Personaje (MRG)
    _phase_mission_resolution()

    # 7. Fase de Limpieza y Auditoría
    _phase_cleanup_and_audit()
    
    duration = (datetime.now() - tick_start).total_seconds()
    log_event(f"✅ Ciclo solar completado en {duration:.2f}s. Sistemas nominales.")


# --- IMPLEMENTACIÓN DE FASES ---

def _phase_decrement_and_persistence():
    """
    Fase 1: Reducción de contadores y actualización de estados temporales.
    - Misiones: Remaining_Days - 1. Si llega a 0 -> Ready for Resolution.
    - Entidades: Actualización de heridas/fatiga.
    - Facciones: Decremento de buffs/debuffs (Hegemónico, Paria).
    """
    log_event("running phase 1: Decremento y Persistencia...")
    # TODO: Implementar lógica de decremento de días de misión.
    # TODO: Implementar recuperación de salud/fatiga de personajes.
    pass

def _phase_concurrency_resolution():
    """
    Fase 2: Procesamiento de la Cola de Acciones y Conflictos.
    - Transacciones: Prioridad por Timestamp.
    - Posicionales: Protocolo de Intercepción (Bloqueo si hay disputa).
    - Ejecución de órdenes diferidas (Lock-in).
    """
    log_event("running phase 2: Resolución de Simultaneidad...")
    
    # Procesar la cola de acciones pendientes (Lock-in del día anterior)
    pending_actions = get_all_pending_actions()
    
    if pending_actions:
        log_event(f"📂 Procesando {len(pending_actions)} acciones encolada(s)...")
        
        # Importación local para evitar Circular Import Error
        from services.gemini_service import resolve_player_action
        
        # TODO: Aquí deberíamos ordenar `pending_actions` por timestamp para respetar la prioridad atómica.
        # pending_actions.sort(key=lambda x: x['created_at'])

        for item in pending_actions:
            player_id = item['player_id']
            action_text = item['action_text']
            action_id = item['id']
            
            try:
                log_event(f"▶ Ejecutando orden diferida ID {action_id}...", player_id)
                
                # Ejecutamos la acción. 
                # NOTA: Si implementamos lógica de intercepción de mapa, deberíamos
                # analizar primero todas las acciones de movimiento antes de ejecutarlas individualmente.
                resolve_player_action(action_text, player_id)
                
                mark_action_processed(action_id, "PROCESSED")
                
            except Exception as e:
                log_event(f"❌ Error procesando orden diferida {action_id}: {e}", player_id, is_error=True)
                mark_action_processed(action_id, "ERROR")
    else:
        # log_event("📂 No hay acciones pendientes en la cola.") # Comentado para reducir ruido
        pass

def _phase_prestige_calculation():
    """
    Fase 3: Cálculo y transferencia de Prestigio (Suma Cero).
    - Transferencias por conflictos resueltos.
    - Aplicación de 'Fricción': Redistribución pasiva hacia el centro.
    """
    # log_event("running phase 3: Prestigio...")
    # TODO: Implementar lógica de transferencia de puntos de victoria/prestigio.
    pass

def _phase_macroeconomics():
    """
    Fase 4: Economía Macro (MMFR).
    - Generación de recursos base.
    - Flujo de Caja (CI).
    - Penalizadores por estados negativos de personajes en sectores.
    """
    # log_event("running phase 4: Macroeconomía...")
    # TODO: Iterar sobre jugadores/facciones y generar créditos/recursos diarios.
    pass

def _phase_social_logistics():
    """
    Fase 5: Logística Social y POPs.
    - Verificación de ocupación de infraestructuras.
    - Cálculo de salud/felicidad de la población.
    """
    # log_event("running phase 5: Logística Social...")
    # TODO: Verificar capacidad de soporte vital vs tripulación/población.
    pass

def _phase_mission_resolution():
    """
    Fase 6: Resolución de Misiones (MRG).
    - Para misiones que llegaron a 0 en la Fase 1.
    - Tiradas: 2d50 + Bonos.
    - Eventos aleatorios.
    """
    # log_event("running phase 6: Resolución de Misiones...")
    # TODO: Buscar misiones con estado 'Resolving'.
    # Ejemplo de lógica futura:
    # roll = random.randint(1, 50) + random.randint(1, 50)
    # outcome = calculate_outcome(roll, bonuses)
    pass

def _phase_cleanup_and_audit():
    """
    Fase 7: Limpieza y Mantenimiento.
    - Cobro de upkeep (costos de mantenimiento).
    - Archivar logs viejos.
    """
    # log_event("running phase 7: Limpieza...")
    # TODO: Restar créditos por mantenimiento de naves/edificios.
    pass

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