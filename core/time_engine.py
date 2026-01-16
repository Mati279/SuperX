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
from config.app_constants import (
    TIMEZONE_NAME,
    LOCK_IN_WINDOW_START_HOUR,
    LOCK_IN_WINDOW_START_MINUTE
)

# MRG Imports
import random
from data.database import supabase
from data.character_repository import update_character
from data.player_repository import get_player_credits, update_player_credits

# Forzamos la zona horaria a Argentina (GMT-3)
SAFE_TIMEZONE = pytz.timezone(TIMEZONE_NAME)

def get_server_time() -> datetime:
    """Retorna la hora actual en GMT-3."""
    return datetime.now(SAFE_TIMEZONE)

def is_lock_in_window() -> bool:
    """Retorna True si estamos en la ventana de bloqueo (23:50 - 00:00)."""
    now = get_server_time()
    # Definir ventana: 23:50 a 23:59:59
    start_lock = time(LOCK_IN_WINDOW_START_HOUR, LOCK_IN_WINDOW_START_MINUTE)
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

        # Ordenar acciones por timestamp para respetar la prioridad atómica (FIFO)
        pending_actions.sort(key=lambda x: x.get('created_at', ''))

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
    - Procesa transferencias pendientes de conflictos
    - Aplica Fricción Galáctica (redistribución automática)
    - Verifica condiciones de Hegemonía
    - Decrementa contadores de victoria
    """
    from core.prestige_engine import (
        calculate_friction,
        apply_prestige_changes,
        check_hegemony_ascension,
        check_hegemony_fall,
        validate_zero_sum,
        FactionState,
        HEGEMONY_VICTORY_TICKS
    )
    from data.faction_repository import (
        get_prestige_map,
        get_all_factions,
        batch_update_prestige,
        set_hegemony_status,
        decrement_hegemony_counters
    )

    log_event("🏛️ Ejecutando Fase 3: Prestigio y Hegemonía...")

    # 1. Obtener estado actual de todas las facciones
    factions = get_all_factions()
    if not factions:
        log_event("⚠️ No hay facciones en el sistema", is_error=True)
        return

    prestige_map = {f["id"]: float(f["prestigio"]) for f in factions}

    # 2. Decrementar contadores de victoria de hegemones
    winners = decrement_hegemony_counters()
    if winners:
        for winner in winners:
            log_event(f"🏆🏆🏆 ¡¡¡{winner['nombre']} HA GANADO POR HEGEMONÍA TEMPORAL!!!")
            # TODO: Implementar lógica de fin de partida
        return  # Si hay un ganador, no procesar más

    # 3. Calcular y aplicar Fricción Galáctica
    friction_adjustments = calculate_friction(prestige_map)

    # Log de fricción detallado
    for fid, adj in friction_adjustments.items():
        if adj != 0:
            faction_name = next((f["nombre"] for f in factions if f["id"] == fid), f"ID{fid}")
            if adj < 0:
                log_event(f"📉 Fricción Imperial: {faction_name} pierde {abs(adj):.2f}% de prestigio")
            else:
                log_event(f"📈 Subsidio de Supervivencia: {faction_name} recibe {adj:.2f}% de prestigio")

    # 4. Aplicar cambios manteniendo suma = 100
    new_prestige_map = apply_prestige_changes(prestige_map, friction_adjustments)

    # 5. Verificar transiciones de hegemonía
    for faction in factions:
        fid = faction["id"]
        old_prestige = prestige_map[fid]
        new_prestige = new_prestige_map[fid]
        was_hegemon = faction.get("es_hegemon", False)

        # ¿Ascenso a Hegemón?
        if not was_hegemon and new_prestige >= 25.0:
            set_hegemony_status(fid, True, HEGEMONY_VICTORY_TICKS)
            log_event(f"👑 ¡¡¡{faction['nombre']} ASCIENDE A HEGEMÓN!!! Contador de victoria: {HEGEMONY_VICTORY_TICKS} ticks")

        # ¿Caída de Hegemonía? (debe caer por debajo del 20%, no del 25%)
        elif was_hegemon and new_prestige < 20.0:
            set_hegemony_status(fid, False, 0)
            log_event(f"💔 {faction['nombre']} PIERDE EL ESTATUS DE HEGEMÓN (cayó a {new_prestige:.2f}%)")

    # 6. Guardar cambios en DB
    if batch_update_prestige(new_prestige_map):
        log_event("✅ Prestigio actualizado correctamente")

        # Mostrar estado actual
        sorted_factions = sorted(new_prestige_map.items(), key=lambda x: x[1], reverse=True)
        top_3 = sorted_factions[:3]
        faction_names = {f["id"]: f["nombre"] for f in factions}

        ranking = " | ".join([f"{faction_names.get(fid, '?')}: {pres:.1f}%" for fid, pres in top_3])
        log_event(f"📊 Top 3 Facciones: {ranking}")
    else:
        log_event("❌ Error actualizando prestigio en base de datos", is_error=True)

    # 7. Validar suma cero
    if not validate_zero_sum(new_prestige_map):
        total = sum(new_prestige_map.values())
        log_event(f"⚠️ ADVERTENCIA: Prestigio total = {total:.2f}% (debería ser 100%)", is_error=True)

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
    Busca personajes 'En Misión', tira dados (d100 + Atributo vs Dificultad) y asigna recompensas o heridas.
    """
    log_event("running phase 6: Resolución de Misiones (MRG)...")
    
    try:
        # 1. Obtener todos los personajes que están actualmente en misión
        response = supabase.table("characters").select("*").eq("estado", "En Misión").execute()
        active_operatives = response.data if response.data else []
        
        if not active_operatives:
            return

        for char in active_operatives:
            player_id = char['player_id']
            
            # Recuperar datos de la misión del JSON o usar defaults
            stats = char.get('stats_json', {})
            mission_data = stats.get('active_mission', {})
            
            difficulty = mission_data.get('difficulty', 50)
            reward = mission_data.get('reward', 200)
            risk_attr = mission_data.get('attribute', 'fuerza').lower()
            
            # Obtener valor del atributo del personaje
            attr_value = stats.get('atributos', {}).get(risk_attr, 10)
            
            # --- Mecánica de Resolución ---
            roll = random.randint(1, 100)
            total_score = roll + attr_value
            
            narrative = ""
            new_status = "Disponible"
            
            if total_score >= difficulty:
                # ÉXITO: Dar créditos y liberar agente
                current_credits = get_player_credits(player_id)
                update_player_credits(player_id, current_credits + reward)
                
                narrative = f"✅ Misión EXITOSA: {char['nombre']} cumplió el objetivo. (Roll: {roll}+{attr_value} vs DC{difficulty}). +{reward} Créditos."
                if 'active_mission' in stats: del stats['active_mission']
                
                update_character(char['id'], {
                    "estado": "Disponible", 
                    "ubicacion": "Barracones", 
                    "stats_json": stats
                })
            else:
                # FALLO: Herida o Fatiga según margen de error
                margin = difficulty - total_score
                new_status = "Herido" if margin > 20 else "Descansando"
                ubicacion = "Enfermería" if new_status == "Herido" else "Barracones"
                
                narrative = f"❌ Misión FALLIDA: {char['nombre']} fracasó. Estado: {new_status}. (Roll: {roll}+{attr_value} vs DC{difficulty})."
                if 'active_mission' in stats: del stats['active_mission']

                update_character(char['id'], {
                    "estado": new_status, 
                    "ubicacion": ubicacion, 
                    "stats_json": stats
                })

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