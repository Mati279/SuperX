# core/time_engine.py
from datetime import datetime, time
import pytz
import random
# Imports del repositorio de mundo
from data.world_repository import (
    get_world_state,
    try_trigger_db_tick,
    force_db_tick,
    get_all_pending_actions,
    mark_action_processed
)
from data.player_repository import get_all_players
# Imports para la lógica del MRG (Misiones)
from data.database import supabase
from data.character_repository import update_character
from data.player_repository import get_player_credits, update_player_credits
from data.log_repository import log_event, clear_player_logs

from core.mrg_engine import resolve_action, ResultType, MalusType

# IMPORT NUEVO: Servicio de Eventos Narrativos
from services.event_service import generate_tick_event

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

    # FASE PREVIA: Limpiar logs de todos los jugadores antes del tick
    all_players = get_all_players()
    for p in all_players:
        clear_player_logs(p['id'])

    log_event(f"🔄 INICIANDO PROCESAMIENTO DE TICK: {execution_time.isoformat()}")

    # Obtener número de tick actual para referencias
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)

    # 0. FASE NARRATIVA: Evento Global
    log_event("running phase 0: Generación de Evento Global...")
    generate_tick_event(current_tick)

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
        
        for item in pending_actions:
            player_id = item['player_id']
            action_text = item['action_text']
            action_id = item['id']
            
            try:
                log_event(f"▶ Ejecutando orden diferida ID {action_id}...", player_id)
                resolve_player_action(action_text, player_id)
                mark_action_processed(action_id, "PROCESSED")
                
            except Exception as e:
                log_event(f"❌ Error procesando orden diferida {action_id}: {e}", player_id, is_error=True)
                mark_action_processed(action_id, "ERROR")
    else:
        pass

def _phase_prestige_calculation():
    """
    Fase 3: Cálculo y transferencia de Prestigio (Suma Cero).
    - Transferencias por conflictos resueltos.
    - Aplicación de 'Fricción': Redistribución pasiva hacia el centro.
    """
    # log_event("running phase 3: Prestigio...")
    pass

def _phase_macroeconomics():
    """
    Fase 4: Economía Macro (MMFR).
    - Generación de recursos base.
    - Flujo de Caja (CI).
    - Procesamiento de edificios y producción planetaria.
    """
    log_event("running phase 4: Macroeconomía (MMFR)...")

    # Importación local para evitar circular imports
    from core.economy_engine import run_global_economy_tick

    try:
        run_global_economy_tick()
    except Exception as e:
        log_event(f"Error crítico en fase macroeconómica: {e}", is_error=True)

def _phase_social_logistics():
    """
    Fase 5: Logística Social y POPs.
    - Verificación de ocupación de infraestructuras (ya manejado en economy_engine).
    - Cálculo de salud/felicidad de la población.
    - Ajustes demográficos.
    """
    log_event("running phase 5: Logística Social y POPs...")

    # NOTA: La desactivación en cascada ya se maneja en economy_engine
    # Esta fase puede usarse para:
    # - Crecimiento/declive de población
    # - Eventos de felicidad
    # - Migraciones entre planetas

    # TODO: Implementar mecánicas de demografía avanzada
    pass

def _phase_mission_resolution():
    """
    Fase 6: Resolución de Misiones (MRG v2.0).
    Utiliza el motor de 2d50 con márgenes de éxito/fracaso.
    """
    log_event("running phase 6: Resolución de Misiones (MRG 2d50)...")
    
    try:
        # 1. Obtener operativos en misión
        response = supabase.table("characters").select("*").eq("estado", "En Misión").execute()
        active_operatives = response.data if response.data else []
        
        if not active_operatives:
            return

        for char in active_operatives:
            player_id = char['player_id']
            stats = char.get('stats_json', {})
            mission_data = stats.get('active_mission', {})
            
            # Datos de Misión
            difficulty = mission_data.get('difficulty', 50)
            base_reward = mission_data.get('reward', 200)
            risk_attr_name = mission_data.get('attribute', 'fuerza').lower()
            
            # Obtener Puntos de Mérito (Atributo + Habilidad si existiera)
            # Por ahora usamos el atributo raw como base de mérito
            attr_value = stats.get('atributos', {}).get(risk_attr_name, 10)
            
            # --- RESOLUCIÓN MRG ---
            result = resolve_action(
                merit_points=attr_value,
                difficulty=difficulty,
                action_description=f"Misión de {char['nombre']}"
            )
            
            # --- INTERPRETACIÓN DE RESULTADOS ---
            narrative = ""
            new_status = "Disponible"
            current_credits = get_player_credits(player_id)
            
            # 1. ÉXITOS (Total o Parcial)
            if result.result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                
                # Recompensa base
                reward = base_reward
                
                if result.result_type == ResultType.PARTIAL_SUCCESS:
                    # Éxito Parcial: "Complicación menor" -> Reducción de recompensa o fatiga leve
                    # Implementación: 75% de la recompensa
                    reward = int(base_reward * 0.75)
                    narrative = f"⚠️ ÉXITO PARCIAL: {char['nombre']} cumplió el objetivo con complicaciones. (Margen {result.margin}). Ganancia: {reward} C."
                
                else:
                    # Éxito Total / Crítico
                    # BONUS AUTOMÁTICO (Por ser tick nocturno): Eficiencia (+10% extra créditos por ahora)
                    bonus_cr = int(base_reward * 0.10)
                    reward += bonus_cr
                    prefix = "🌟 CRÍTICO" if result.result_type == ResultType.CRITICAL_SUCCESS else "✅ ÉXITO TOTAL"
                    narrative = f"{prefix}: {char['nombre']} triunfó magistralmente. (Roll {result.roll.total}). Ganancia: {reward} C."

                # Aplicar recompensa
                update_player_credits(player_id, current_credits + reward)
                
                # Actualizar personaje (Limpio)
                if 'active_mission' in stats: del stats['active_mission']
                update_character(char['id'], {
                    "estado": "Disponible", 
                    "ubicacion": "Barracones",
                    "stats_json": stats
                })

            # 2. FRACASOS (Total o Parcial)
            else:
                if result.result_type == ResultType.PARTIAL_FAILURE:
                    # Fracaso Parcial: "Objetivo no se cumple, se pierden recursos, posición segura"
                    new_status = "Disponible" # Vuelve, pero con las manos vacías
                    narrative = f"🔸 FRACASO PARCIAL: {char['nombre']} no logró el objetivo y tuvo que abortar. (Margen {result.margin})."
                
                else:
                    # Fracaso Total / Crítico (Pifia)
                    # CONSECUENCIA AUTOMÁTICA: Baja Operativa (Herido)
                    new_status = "Herido"
                    prefix = "💀 PIFIA" if result.result_type == ResultType.CRITICAL_FAILURE else "❌ FRACASO TOTAL"
                    narrative = f"{prefix}: {char['nombre']} sufrió un accidente grave durante la misión. (Roll {result.roll.total}). Pasa a Enfermería."

                if 'active_mission' in stats: del stats['active_mission']
                update_character(char['id'], {
                    "estado": new_status, 
                    "ubicacion": "Enfermería" if new_status == "Herido" else "Barracones",
                    "stats_json": stats
                })

            # Log final
            log_event(narrative, player_id)

    except Exception as e:
        log_event(f"Error crítico en MRG phase: {e}", is_error=True)

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