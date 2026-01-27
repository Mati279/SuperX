# core/time_engine.py (Completo)
# V10.0: Añadidas fases 1.5 (Llegadas de Tránsito) y 2.5 (Detección de Encuentros)
# V10.4: Añadida fase 3.5 (Actualización Diferida de Soberanía)
# V19.0: Reset de unidades CONSTRUCTING en fase de limpieza.
from datetime import datetime, time
import pytz
import random
import time as time_lib  # Para el sleep del backoff
import logging
import re 

# Imports del repositorio de mundo
from data.world_repository import (
    get_world_state,
    try_trigger_db_tick,
    force_db_tick,
    get_all_pending_actions,
    mark_action_processed
)
from data.player_repository import get_all_players, get_player_credits, update_player_credits
from data.log_repository import log_event, clear_player_logs
# Imports para la lógica del MRG (Misiones)
from data.database import get_supabase
from data.character_repository import update_character, STATUS_ID_MAP

# Configuración de Logging Profesional
logger = logging.getLogger(__name__)

def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()

from core.mrg_engine import resolve_action, ResultType
# IMPORT NUEVO: Servicio de Eventos Narrativos
from services.event_service import generate_tick_event

# IMPORT V4.3.2: Constantes y Motor Unificado de Prestigio
from core.prestige_constants import FRICTION_RATE
from core.prestige_engine import (
    process_hegemony_tick,
    calculate_friction,
    apply_prestige_changes
)

# IMPORT V10.0: Motores de Movimiento y Detección
from core.movement_engine import process_transit_arrivals
from core.detection_engine import process_detection_phase
from data.unit_repository import reset_all_movement_locks, decrement_transit_ticks

# IMPORT V10.4: Soberanía Diferida
from data.planet_repository import update_planet_sovereignty

# IMPORT V11.0: Sistema de Bases
from core.base_engine import get_bases_pending_completion, complete_base_upgrade

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
    Implementa Backoff Exponencial para manejar bloqueos de concurrencia.
    """
    global _IS_PROCESSING_TICK
    
    if _IS_PROCESSING_TICK:
        return

    now = get_server_time()
    today_date_iso = now.date().isoformat()
    
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            if try_trigger_db_tick(today_date_iso):
                _execute_game_logic_tick(now)
            break 
            
        except BlockingIOError:
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
    Refactorización V4.3.1: Ciclo de 8 Fases estricto.
    Refactorización V4.3.2: Unificación de lógica de Prestigio.
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

        world_state = get_world_state()
        current_tick = world_state.get('current_tick', 1)

        # 0. FASE NARRATIVA: Evento Global
        log_event("running phase 0: Generación de Evento Global...")
        generate_tick_event(current_tick)

        # 1. Fase de Decremento (Countdowns y Persistencia)
        _phase_decrement_and_persistence()

        # 1.5 V10.0: Fase de Llegadas de Tránsito (Movimiento)
        _phase_movement_arrivals(current_tick)

        # 2. Resolución de Simultaneidad (Conflictos en el mismo Tick)
        _phase_concurrency_resolution()

        # 2.5 V10.0: Fase de Detección de Encuentros
        _phase_detection_encounters(current_tick)

        # 3. Fase de Prestigio (Fricción V4.3 y Hegemonía)
        _phase_prestige_calculation(current_tick)
        
        # 3.5 V10.4: Actualización de Soberanía Diferida (Construcciones Completadas)
        _phase_sovereignty_update(current_tick)

        # 3.6 V11.0: Fase de Mejora de Bases
        _phase_base_upgrades(current_tick)

        # 4. Fase Macro económica (MMFR)
        _phase_macroeconomics()

        # NOTA V4.3.1: Fase 5 (Logística Social) eliminada del ciclo.

        # 6. Fase de Resolución de Misiones y Eventos de Personaje (MRG)
        _phase_mission_resolution()

        # 7. Fase de Limpieza y Auditoría
        _phase_cleanup_and_audit()

        # 7.5 V16.0: Fase de Supervivencia de Tropas
        _phase_troop_survival()

        # 8. Fase de Progresión de Conocimiento de Personal (V4.3)
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
            .eq("estado_id", STATUS_ID_MAP["En Misión"])\
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
            .eq("estado_id", STATUS_ID_MAP["Herido"])\
            .execute()

        for char in (wounded_res.data or []):
            stats = char.get('stats_json', {})
            wound_ticks = stats.get('wound_ticks_remaining', 2)

            if wound_ticks > 1:
                stats['wound_ticks_remaining'] = wound_ticks - 1
                update_character(char['id'], {"stats_json": stats})
            else:
                stats.pop('wound_ticks_remaining', None)
                
                # V4.3.1: Eliminada lógica de "ubicacion_local".
                
                update_character(char['id'], {
                    "estado_id": STATUS_ID_MAP["Disponible"],
                    "stats_json": stats
                })
                log_event(f"{char['nombre']} has recovered from injuries.", char.get('player_id'))

        # 3. Decrement unit transit ticks
        # Se ejecuta para todas las unidades en TRANSIT con ticks > 0
        try:
            updated_transits = decrement_transit_ticks()
            if updated_transits > 0:
                log_event(f"⏳ Actualizados {updated_transits} tránsitos en progreso (tick -1).")
        except Exception as e:
            logger.error(f"Error decrementando tránsitos: {e}")

    except Exception as e:
        logger.error(f"Error en fase de decremento: {e}")


def _phase_movement_arrivals(current_tick: int):
    """
    V10.0: Fase 1.5 - Procesa llegadas de unidades en tránsito.
    Ejecutado después de decrementos y antes de resolución de simultaneidad.
    """
    log_event("running phase 1.5: Llegadas de Tránsito...")

    try:
        # Resetear bloqueos de movimiento del tick anterior
        unlocked = reset_all_movement_locks()
        if unlocked > 0:
            log_event(f"🔓 {unlocked} unidades desbloqueadas para movimiento")

        # Procesar llegadas
        arrivals = process_transit_arrivals(current_tick)

        if arrivals:
            log_event(f"🚀 {len(arrivals)} unidades han completado su tránsito")
            for arrival in arrivals:
                log_event(
                    f"✅ '{arrival['unit_name']}' llegó a {arrival['destination']}",
                    arrival['player_id']
                )

    except Exception as e:
        logger.error(f"Error en fase de movimiento: {e}")
        log_event(f"❌ Error procesando llegadas de tránsito: {e}", is_error=True)


def _phase_detection_encounters(current_tick: int):
    """
    V10.0: Fase 2.5 - Procesa detecciones automáticas entre unidades.
    Ejecutado después de resolución de simultaneidad y antes de prestigio.
    """
    log_event("running phase 2.5: Detección de Encuentros...")

    try:
        detections = process_detection_phase(current_tick)

        # Contar detecciones exitosas
        successful = sum(1 for d in detections if d.detected)

        if successful > 0:
            log_event(f"👁️ {successful} detecciones exitosas registradas")

        # Notificar encuentros significativos (donde se puede interdecir)
        interdiction_opportunities = [d for d in detections if d.can_interdict]
        if interdiction_opportunities:
            for det in interdiction_opportunities:
                log_event(
                    f"⚡ Oportunidad de interdicción detectada",
                    det.detector_player_id
                )

    except Exception as e:
        logger.error(f"Error en fase de detección: {e}")
        log_event(f"❌ Error procesando detecciones: {e}", is_error=True)


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
    """Procesa la búsqueda de nuevos candidatos de reclutamiento."""
    from data.recruitment_repository import clear_untracked_candidates
    from services.character_generation_service import generate_character_pool

    log_event("🔍 INICIANDO PROCESO DE BÚSQUEDA DE CANDIDATOS...", player_id)
    logger.info(f"⚡ _process_candidate_search RUNNING (Player {player_id})")

    try:
        clear_untracked_candidates(player_id)
        new_candidates = generate_character_pool(
            player_id=player_id,
            pool_size=3,
            location_planet_id=None
        )

        candidates_fixed = 0
        if new_candidates:
            for char in new_candidates:
                try:
                    char_id = char.get('id')
                    if not char_id: continue

                    stats = char.get("stats_json", {})
                    if "estado" not in stats: stats["estado"] = {}
                    
                    # V4.3.1: Eliminada lógica de "ubicacion_local".
                    
                    update_character(char_id, {
                        "estado_id": STATUS_ID_MAP["Candidato"],
                        "stats_json": stats
                    })
                    candidates_fixed += 1
                except Exception:
                    pass

        log_event(f"✅ RECLUTAMIENTO COMPLETADO: {candidates_fixed} nuevos expedientes.", player_id)

    except Exception as e:
        logger.error(f"Error CRÍTICO en búsqueda de candidatos: {e}")
        log_event(f"❌ Error crítico en red de reclutamiento.", player_id, is_error=True)


def _process_investigation(player_id: int, action_text: str):
    """Procesa una investigación de personaje."""
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

        debug_match = re.search(r"debug_outcome=(\w+)", action_text)
        if debug_match: debug_outcome = debug_match.group(1)

        if not target_id: return

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

        outcome = "FAIL"
        if debug_outcome:
            outcome = debug_outcome
        else:
            result = resolve_action(merit_points=cmd_merit, difficulty=target_merit, action_description=f"Investigación sobre {target_name}")
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

def _phase_prestige_calculation(current_tick: int):
    """
    Fase 3: Cálculo de Prestigio, Hegemonía y Subsidios (V4.3.2).
    Unificación con motor de prestigio seguro (Suma Cero).
    """
    log_event("running phase 3: Prestigio y Hegemonía...")
    try:
        from data.faction_repository import get_all_factions, update_faction_prestige
        
        # 1. Hegemonía
        game_over = process_hegemony_tick(current_tick)
        if game_over:
            log_event("🏆 JUEGO TERMINADO POR HEGEMONÍA 🏆")
            # Lógica de fin de juego aquí
        
        # 2. Fricción Galáctica V4.3.2: Lógica unificada en prestige_engine
        factions = get_all_factions()
        if not factions: 
            return
            
        # Crear mapa {id: prestige} asegurando float
        factions_map = {f['id']: float(f.get('prestige', 0.0)) for f in factions}
        
        # Calcular ajustes (Drenaje porcentual y Subsidio estricto)
        adjustments = calculate_friction(factions_map)
        
        # Aplicar cambios con normalización (Garantía Suma Cero)
        new_prestige_map = apply_prestige_changes(factions_map, adjustments)
        
        # Persistir cambios
        for fid, new_val in new_prestige_map.items():
            update_faction_prestige(fid, new_val)
                
    except Exception as e:
        logger.error(f"Error en fase de prestigio: {e}")

def _phase_sovereignty_update(current_tick: int):
    """
    Fase 3.5: Actualización de Soberanía por Finalización de Construcciones.
    Detecta edificios que terminaron de construirse en este tick y recalcula
    la propiedad del planeta.
    """
    log_event("running phase 3.5: Actualización de Soberanía...")
    try:
        db = _get_db()
        # Buscar edificios completados en este tick exacto
        # Recuperamos planet_asset_id y hacemos join con assets para obtener planet_id
        response = db.table("planet_buildings")\
            .select("planet_asset_id, planet_assets(planet_id)")\
            .eq("built_at_tick", current_tick)\
            .execute()

        if not response or not response.data:
            return

        # Extraer IDs de planetas únicos
        planet_ids = set()
        for b in response.data:
            asset = b.get("planet_assets")
            if asset and "planet_id" in asset:
                planet_ids.add(asset["planet_id"])
        
        if not planet_ids:
            return

        log_event(f"🏗️ Construcciones finalizadas en {len(planet_ids)} planetas. Recalculando soberanía...")

        count = 0
        for pid in planet_ids:
            update_planet_sovereignty(pid)
            count += 1
        
        if count > 0:
            log_event(f"✅ Soberanía actualizada en {count} sistemas.")

    except Exception as e:
        logger.error(f"Error en fase de soberanía: {e}")


def _phase_base_upgrades(current_tick: int):
    """
    Fase 3.6: Procesamiento de Mejoras de Bases Completadas.
    Detecta bases cuya mejora se completa en este tick y aplica los cambios.
    """
    log_event("running phase 3.6: Mejoras de Bases...")
    try:
        # Obtener bases con mejoras pendientes de completar
        pending_bases = get_bases_pending_completion(current_tick)

        if not pending_bases:
            return

        log_event(f"🏗️ {len(pending_bases)} base(s) completando mejora...")

        completed = 0
        for base in pending_bases:
            base_id = base.get("id")
            if not base_id:
                continue

            target_tier = base.get("upgrade_target_tier", base.get("tier", 1) + 1)
            player_id = base.get("player_id")

            if complete_base_upgrade(base_id):
                completed += 1
                log_event(
                    f"🏰 Base mejorada a Nv.{target_tier} en sector {base.get('sector_id')}",
                    player_id
                )

        if completed > 0:
            log_event(f"✅ {completed} base(s) mejoradas exitosamente.")

    except Exception as e:
        logger.error(f"Error en fase de mejoras de bases: {e}")


def _phase_macroeconomics():
    """Fase 4: Economía Macro (MMFR)."""
    log_event("running phase 4: Macroeconomía (MMFR)...")
    from core.economy_engine import run_global_economy_tick
    try:
        run_global_economy_tick()
    except Exception as e:
        logger.error(f"Error crítico en fase macroeconómica: {e}")

def _phase_mission_resolution():
    """Fase 6: Resolución de Misiones (MRG v2.0)."""
    log_event("running phase 6: Resolución de Misiones (MRG 2d50)...")
    try:
        response = _get_db().table("characters")\
            .select("*")\
            .eq("estado_id", STATUS_ID_MAP["En Misión"])\
            .execute()
            
        active_operatives = response.data or []
        for char in active_operatives:
            player_id = char['player_id']
            stats = char.get('stats_json', {})
            mission_data = stats.get('active_mission', {})
            attr_value = stats.get('atributos', {}).get(mission_data.get('attribute', 'fuerza').lower(), 10)
            result = resolve_action(merit_points=attr_value, difficulty=mission_data.get('difficulty', 50), action_description=f"Misión de {char['nombre']}")
            
            reward = 0
            status_id = STATUS_ID_MAP["Disponible"]
            msg = ""

            if result.result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                reward = int(mission_data.get('reward', 200) * (0.75 if result.result_type == ResultType.PARTIAL_SUCCESS else 1.1))
                update_player_credits(player_id, get_player_credits(player_id) + reward)
                msg = f"✅ ÉXITO: {char['nombre']} completó misión. Recompensa: {reward} C."
            else:
                if result.result_type == ResultType.CRITICAL_FAILURE:
                    status_id = STATUS_ID_MAP["Herido"]
                    msg = f"❌ FRACASO: {char['nombre']} falló la misión. Sufrió heridas graves."
                else:
                    msg = f"❌ FRACASO: {char['nombre']} falló la misión."
            
            # Limpieza de datos de misión activa
            if 'active_mission' in stats: del stats['active_mission']
            
            # V4.3.1: Eliminada lógica de inyección de "ubicacion_local".
            
            update_character(char['id'], {
                "estado_id": status_id,
                "stats_json": stats
            })
            log_event(msg, player_id)
    except Exception as e:
        logger.error(f"Error en fase de misiones: {e}")

def _phase_cleanup_and_audit():
    """Fase 7: Limpieza y Mantenimiento."""
    log_event("running phase 7: Limpieza...")
    try:
        db = _get_db()
        # Limpieza de candidatos expirados
        from data.recruitment_repository import expire_old_candidates
        current_tick = get_world_state().get('current_tick', 1)
        for player in get_all_players(): expire_old_candidates(player['id'], current_tick)
        
        # V19.0: Reset de Unidades Constructoras
        # Las unidades que terminaron de construir (ciclo completado) vuelven a estar disponibles.
        # No usamos Enum aquí para evitar circular import si core/models importa algo que importe time_engine
        res = db.table("units").update({
            "status": "GROUND",
            # No reseteamos moves aquí, eso se maneja si el tick resetea moves globales o en la lógica de refresco
        }).eq("status", "CONSTRUCTING").execute()
        
        if res.data and len(res.data) > 0:
            log_event(f"🔨 {len(res.data)} unidades de construcción han vuelto al servicio activo.")

    except Exception as e:
        logger.error(f"Error en limpieza: {e}")


def _phase_troop_survival():
    """
    V16.0: Fase 7.5 - Procesa supervivencia de tropas en territorios hostiles.
    Las tropas en unidades que exceden su capacidad (basada en líder)
    y están en territorio hostil serán eliminadas.
    """
    log_event("running phase 7.5: Supervivencia de Tropas...")
    try:
        from core.unit_engine import process_troop_survival

        total_removed = 0
        total_units_affected = 0
        current_tick = get_world_state().get('current_tick', 1)

        for player in get_all_players():
            player_id = player['id']
            result = process_troop_survival(player_id, current_tick)

            total_removed += result.get("total_removed", 0)
            total_units_affected += len(result.get("units_affected", []))

        if total_removed > 0:
            log_event(
                f"📉 Supervivencia: {total_removed} tropa(s) perdidas "
                f"en {total_units_affected} unidad(es) por falta de liderazgo en territorio hostil."
            )

    except Exception as e:
        logger.error(f"Error en fase de supervivencia: {e}")


def _phase_knowledge_progression(current_tick: int):
    """Fase 8: Progresión de Conocimiento Pasivo (V4.3)."""
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