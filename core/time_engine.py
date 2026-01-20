# core/time_engine.py
from datetime import datetime, time
import pytz
import random
import time as time_lib  # Para el sleep del backoff
import logging

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
from data.database import get_supabase
from data.character_repository import update_character

# Configuración de Logging Profesional
logger = logging.getLogger(__name__)

def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()

from data.player_repository import get_player_credits, update_player_credits
from data.log_repository import log_event, clear_player_logs

# FIX: Eliminado MalusType ya que no existe en MRG v2.1
from core.mrg_engine import resolve_action, ResultType

# IMPORT NUEVO: Servicio de Eventos Narrativos
from services.event_service import generate_tick_event

# Forzamos la zona horaria a Argentina (GMT-3)
SAFE_TIMEZONE = pytz.timezone('America/Argentina/Buenos_Aires')

# Flag global para evitar reentrada en la misma instancia de memoria
_IS_PROCESSING_TICK = False

def get_server_time() -> datetime:
    """Retorna la hora actual en GMT-3."""
    return datetime.now(SAFE_TIMEZONE)

def get_current_tick() -> int:
    """
    Retorna el número de tick actual.
    Wrapper sobre get_world_state para uso fácil en otros módulos (ej: Mercado).
    """
    state = get_world_state()
    return state.get("current_tick", 1)

def is_lock_in_window() -> bool:
    """Retorna True si estamos en la ventana de bloqueo (23:50 - 00:00)."""
    now = get_server_time()
    start_lock = time(23, 50)
    current_time = now.time()
    return current_time >= start_lock

def check_and_trigger_tick() -> None:
    """
    Verifica si debemos ejecutar un Tick (Lazy Tick).
    Implementa Backoff Exponencial para manejar bloqueos de concurrencia [Errno 11].
    """
    global _IS_PROCESSING_TICK
    
    if _IS_PROCESSING_TICK:
        return

    now = get_server_time()
    today_date_iso = now.date().isoformat()
    
    max_retries = 3
    retry_delay = 0.5 # Segundos iniciales

    for attempt in range(max_retries):
        try:
            # Intentamos ejecutar el tick en la DB de forma atómica.
            if try_trigger_db_tick(today_date_iso):
                _execute_game_logic_tick(now)
            break # Éxito o ya procesado por otro
            
        except BlockingIOError:
            # Error 11: El recurso está bloqueado por otro proceso/instancia
            if attempt < max_retries - 1:
                wait = retry_delay * (2 ** attempt) + (random.uniform(0, 0.1))
                logger.warning(f"Tick detectó recurso ocupado. Reintentando en {wait:.2f}s (Intento {attempt+1})")
                time_lib.sleep(wait)
            else:
                logger.error("No se pudo disparar el Tick tras múltiples reintentos por bloqueo de IO.")
        except Exception as e:
            logger.error(f"Error inesperado al intentar disparar Tick: {e}")
            break

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
    global _IS_PROCESSING_TICK
    if _IS_PROCESSING_TICK:
        return
        
    _IS_PROCESSING_TICK = True
    tick_start = datetime.now()

    try:
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

        # 8. Fase de Progresión de Conocimiento de Personal
        _phase_knowledge_progression(current_tick)

        duration = (datetime.now() - tick_start).total_seconds()
        log_event(f"✅ Ciclo solar completado en {duration:.2f}s. Sistemas nominales.")
        
    except Exception as e:
        logger.critical(f"FALLO CRÍTICO DURANTE EL TICK: {e}", exc_info=True)
        log_event(f"❌ ERROR CRÍTICO EN TICK: {e}", is_error=True)
    finally:
        _IS_PROCESSING_TICK = False


# --- IMPLEMENTACIÓN DE FASES ---

def _phase_decrement_and_persistence():
    """Fase 1: Reducción de contadores y actualización de estados temporales."""
    log_event("running phase 1: Decremento y Persistencia...")

    try:
        db = _get_db()

        # 1. Decrement mission remaining days
        missions_res = db.table("characters")\
            .select("id, player_id, nombre, stats_json")\
            .eq("estado", "En Mision")\
            .execute()

        for char in (missions_res.data or []):
            stats = char.get('stats_json', {})
            mission = stats.get('active_mission', {})
            remaining = mission.get('remaining_days', 0)

            if remaining > 0:
                mission['remaining_days'] = remaining - 1
                stats['active_mission'] = mission
                update_character(char['id'], {"stats_json": stats})

                if mission['remaining_days'] == 0:
                    log_event(f"Mission ready for resolution: {char['nombre']}", char.get('player_id'))

        # 2. Heal wounded characters
        wounded_res = db.table("characters")\
            .select("id, player_id, nombre, stats_json")\
            .eq("estado", "Herido")\
            .execute()

        for char in (wounded_res.data or []):
            stats = char.get('stats_json', {})
            wound_ticks = stats.get('wound_ticks_remaining', 2)

            if wound_ticks > 1:
                stats['wound_ticks_remaining'] = wound_ticks - 1
                update_character(char['id'], {"stats_json": stats})
            else:
                stats.pop('wound_ticks_remaining', None)
                update_character(char['id'], {
                    "estado": "Disponible",
                    "ubicacion": "Barracones",
                    "stats_json": stats
                })
                log_event(f"{char['nombre']} has recovered from injuries.", char.get('player_id'))

    except Exception as e:
        logger.error(f"Error en fase de decremento: {e}")

def _phase_concurrency_resolution():
    """Fase 2: Procesamiento de la Cola de Acciones y Conflictos."""
    log_event("running phase 2: Resolución de Simultaneidad...")

    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)
    pending_actions = get_all_pending_actions()

    if not pending_actions:
        return

    log_event(f"Procesando {len(pending_actions)} acciones encolada(s)...")

    from services.gemini_service import resolve_player_action

    for item in pending_actions:
        player_id = item['player_id']
        action_text = item['action_text']
        action_id = item['id']

        try:
            if "[INTERNAL_SEARCH_CANDIDATES]" in action_text:
                _process_candidate_search(player_id, current_tick)
                mark_action_processed(action_id, "PROCESSED")
                continue

            if "[INTERNAL_EXECUTE_INVESTIGATION]" in action_text:
                _process_investigation(player_id, action_text)
                mark_action_processed(action_id, "PROCESSED")
                continue

            log_event(f"Ejecutando orden diferida ID {action_id}...", player_id)
            resolve_player_action(action_text, player_id)
            mark_action_processed(action_id, "PROCESSED")

        except Exception as e:
            logger.error(f"Error procesando orden diferida {action_id}: {e}")
            mark_action_processed(action_id, "ERROR")


def _process_candidate_search(player_id: int, current_tick: int):
    """Procesa la búsqueda de nuevos candidatos de reclutamiento (ASÍNCRONO)."""
    from data.recruitment_repository import clear_untracked_candidates
    from services.character_generation_service import generate_character_pool

    try:
        clear_untracked_candidates(player_id)
        new_candidates = generate_character_pool(
            player_id=player_id,
            pool_size=3,
            location_planet_id=None
        )

        count = len(new_candidates)
        if count > 0:
            log_event(f"RECLUTAMIENTO: Búsqueda completada. {count} nuevos candidatos disponibles.", player_id)
        else:
            log_event("RECLUTAMIENTO: La red no encontró candidatos viables.", player_id)
    except Exception as e:
        logger.error(f"Error en búsqueda de candidatos: {e}")


def _process_investigation(player_id: int, action_text: str):
    """Procesa una investigación de personaje (candidato o miembro)."""
    import re
    from data.character_repository import get_commander_by_player_id, get_character_by_id
    from data.recruitment_repository import get_candidate_by_id

    try:
        target_type = "CANDIDATE"
        target_id = None
        debug_outcome = None

        type_match = re.search(r"target_type=(\w+)", action_text)
        if type_match: target_type = type_match.group(1)

        id_match = re.search(r"(?:candidate_id|character_id)=(\d+)", action_text)
        if id_match: target_id = int(id_match.group(1))

        if not target_id:
            return

        commander = get_commander_by_player_id(player_id)
        if not commander: return

        commander_stats = commander.get("stats_json", {})
        commander_skills = commander_stats.get("capacidades", {}).get("habilidades", {})
        cmd_merit = (commander_skills.get("Sigilo físico", 5) + commander_skills.get("Infiltración urbana", 5)) // 2

        target_name = "Objetivo"
        target_merit = 50

        if target_type == "CANDIDATE":
            candidate = get_candidate_by_id(target_id)
            if not candidate: return
            target_name = candidate.get("nombre", "Candidato")
            target_stats = candidate.get("stats_json", {})
            target_skills = target_stats.get("capacidades", {}).get("habilidades", {})
            target_merit = (target_skills.get("Sigilo físico", 5) + target_skills.get("Infiltración urbana", 5)) // 2 + 40
        else:
            character = get_character_by_id(target_id)
            if not character: return
            target_name = character.get("nombre", "Miembro")
            target_stats = character.get("stats_json", {})
            target_skills = target_stats.get("capacidades", {}).get("habilidades", {})
            target_merit = (target_skills.get("Sigilo físico", 5) + target_skills.get("Infiltración urbana", 5)) // 2 + 40

        result = resolve_action(merit_points=cmd_merit, difficulty=target_merit, action_description=f"Investigación sobre {target_name}")

        outcome = "FAIL"
        if result.result_type == ResultType.CRITICAL_SUCCESS: outcome = "CRIT_SUCCESS"
        elif result.result_type in [ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]: outcome = "SUCCESS"
        elif result.result_type == ResultType.CRITICAL_FAILURE: outcome = "CRIT_FAIL"

        if target_type == "CANDIDATE":
            _apply_candidate_investigation_result(player_id, target_id, target_name, outcome)
        else:
            _apply_member_investigation_result(player_id, target_id, target_name, outcome)
    except Exception as e:
        logger.error(f"Error en investigación: {e}")


def _apply_candidate_investigation_result(player_id: int, candidate_id: int, name: str, outcome: str):
    from data.recruitment_repository import apply_investigation_result, remove_candidate, set_investigation_state
    if outcome == "CRIT_SUCCESS":
        apply_investigation_result(candidate_id, outcome)
        log_event(f"INTEL CRITICO: Información comprometedora sobre {name}. Descuento 30% aplicado.", player_id)
    elif outcome == "SUCCESS":
        apply_investigation_result(candidate_id, outcome)
        log_event(f"INTEL: Investigación exitosa sobre {name}.", player_id)
    elif outcome == "CRIT_FAIL":
        set_investigation_state(candidate_id, False)
        remove_candidate(candidate_id)
        log_event(f"INTEL FALLIDO: {name} detectó la investigación y huyó.", player_id)
    else:
        set_investigation_state(candidate_id, False)
        log_event(f"INTEL: Investigación sobre {name} sin resultados.", player_id)

def _apply_member_investigation_result(player_id: int, character_id: int, name: str, outcome: str):
    from data.character_repository import set_character_knowledge_level
    from core.models import KnowledgeLevel
    if outcome in ["CRIT_SUCCESS", "SUCCESS"]:
        set_character_knowledge_level(character_id, player_id, KnowledgeLevel.KNOWN)
        log_event(f"INTEL: Datos de {name} actualizados a nivel CONOCIDO.", player_id)
    else:
        log_event(f"INTEL: Investigación sobre {name} sin resultados.", player_id)

def _phase_prestige_calculation():
    """Fase 3: Cálculo y transferencia de Prestigio."""
    log_event("running phase 3: Prestigio...")
    try:
        from data.faction_repository import get_all_factions, update_faction_prestige
        factions = get_all_factions()
        if not factions or len(factions) < 2: return
        FRICTION_RATE = 0.005
        high_factions = [f for f in factions if f.get('prestige', 0) > 0.20]
        low_factions = [f for f in factions if f.get('prestige', 0) < 0.05]
        if high_factions and low_factions:
            total_friction = sum(f.get('prestige', 0) * FRICTION_RATE for f in high_factions)
            share_per_low = total_friction / len(low_factions)
            for f in high_factions: update_faction_prestige(f['id'], f.get('prestige', 0) * (1 - FRICTION_RATE))
            for f in low_factions: update_faction_prestige(f['id'], f.get('prestige', 0) + share_per_low)
    except Exception as e:
        logger.error(f"Error en fase de prestigio: {e}")

def _phase_macroeconomics():
    """Fase 4: Economía Macro (MMFR)."""
    log_event("running phase 4: Macroeconomía (MMFR)...")
    from core.economy_engine import run_global_economy_tick
    try:
        run_global_economy_tick()
    except Exception as e:
        logger.error(f"Error crítico en fase macroeconómica: {e}")

def _phase_social_logistics():
    """Fase 5: Logística Social y POPs."""
    log_event("running phase 5: Logística Social y POPs...")
    try:
        from data.planet_repository import get_all_player_planets, update_planet_asset
        players = get_all_players()
        for player in players:
            planets = get_all_player_planets(player['id'])
            for planet in planets:
                pop = planet.get('poblacion', 0)
                if pop <= 0: continue
                happiness = planet.get('felicidad', 1.0)
                growth_rate = 0.01 + (max(0, happiness - 1.0) * 0.02) if happiness >= 0.8 else -0.01
                new_pop = max(10, int(pop * (1 + growth_rate)))
                if new_pop != pop:
                    update_planet_asset(planet['id'], {"poblacion": new_pop, "pops_activos": new_pop})
    except Exception as e:
        logger.error(f"Error en fase social: {e}")

def _phase_mission_resolution():
    """Fase 6: Resolución de Misiones (MRG v2.0)."""
    log_event("running phase 6: Resolución de Misiones (MRG 2d50)...")
    try:
        response = _get_db().table("characters").select("*").eq("estado", "En Misión").execute()
        active_operatives = response.data or []
        for char in active_operatives:
            player_id = char['player_id']
            stats = char.get('stats_json', {})
            mission_data = stats.get('active_mission', {})
            attr_value = stats.get('atributos', {}).get(mission_data.get('attribute', 'fuerza').lower(), 10)
            result = resolve_action(merit_points=attr_value, difficulty=mission_data.get('difficulty', 50), action_description=f"Misión de {char['nombre']}")
            
            reward = 0
            if result.result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                reward = int(mission_data.get('reward', 200) * (0.75 if result.result_type == ResultType.PARTIAL_SUCCESS else 1.1))
                update_player_credits(player_id, get_player_credits(player_id) + reward)
                msg = f"✅ ÉXITO: {char['nombre']} completó misión. Recompensa: {reward} C."
                status, loc = "Disponible", "Barracones"
            else:
                status = "Herido" if result.result_type == ResultType.CRITICAL_FAILURE else "Disponible"
                loc = "Enfermería" if status == "Herido" else "Barracones"
                msg = f"❌ FRACASO: {char['nombre']} falló la misión."
                if status == "Herido": msg += " Sufrió heridas graves."
            
            if 'active_mission' in stats: del stats['active_mission']
            update_character(char['id'], {"estado": status, "ubicacion": loc, "stats_json": stats})
            log_event(msg, player_id)
    except Exception as e:
        logger.error(f"Error en fase de misiones: {e}")

def _phase_cleanup_and_audit():
    """Fase 7: Limpieza y Mantenimiento."""
    log_event("running phase 7: Limpieza...")
    try:
        from data.recruitment_repository import expire_old_candidates
        current_tick = get_world_state().get('current_tick', 1)
        for player in get_all_players(): expire_old_candidates(player['id'], current_tick)
    except Exception as e:
        logger.error(f"Error en limpieza: {e}")

def _phase_knowledge_progression(current_tick: int):
    """Fase 8: Progresión de Conocimiento Pasivo."""
    log_event("running phase 8: Progresión de Conocimiento...")
    try:
        from core.character_engine import process_passive_knowledge_updates
        for player in get_all_players(): process_passive_knowledge_updates(player['id'], current_tick)
    except Exception as e:
        logger.error(f"Error en progresión de conocimiento: {e}")

def get_world_status_display() -> dict:
    """Genera la información para el widget del reloj en la UI."""
    state = get_world_state()
    now = get_server_time()
    status = "OPERATIVO"
    if state.get("is_frozen"): status = "CONGELADO"
    elif is_lock_in_window(): status = "BLOQUEO"
    return {
        "tick": state.get("current_tick", 1),
        "time": now.strftime("%H:%M"),
        "status": status,
        "is_frozen": state.get("is_frozen", False),
        "is_lock_in": is_lock_in_window()
    }