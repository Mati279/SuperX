# core/detection_engine.py
"""
Motor de Detección V10.0.
Implementa checks de detección entre unidades usando MRG 2d50.
Incluye sistema de interdicción para unidades con módulos especiales.
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from collections import defaultdict

from core.mrg_engine import resolve_action, ResultType
from core.mrg_constants import DIFFICULTY_STANDARD, DIFFICULTY_CHALLENGING
from core.models import UnitSchema, UnitStatus
from core.movement_constants import INTERDICTION_MODULE_ID
from data.unit_repository import (
    get_units_at_location,
    get_units_on_starlane,
    cancel_unit_transit,
    get_unit_by_id
)
from data.database import get_supabase
from data.log_repository import log_event


# --- CONSTANTES DE DETECCIÓN ---

# Dificultad base para detección pasiva
DETECTION_DIFFICULTY_BASE = 50

# Modificadores de contexto
DETECTION_MODIFIER_PASSIVE = 10      # +10 dificultad en detección pasiva
DETECTION_MODIFIER_ACTIVE = 0        # Sin modificador en detección activa
DETECTION_MODIFIER_INTERDICTION = -15  # -15 dificultad para interdicción

# Bonos/Penalizaciones por tipo de unidad (basados en composición)
STEALTH_BONUS_AEROSPACE = 15         # Tropas aeroespaciales son más sigilosas
STEALTH_BONUS_INFANTRY = 5           # Infantería tiene algo de sigilo
STEALTH_PENALTY_ARMORED = -10        # Blindados son fáciles de detectar
STEALTH_PENALTY_MECH = -5            # Mechs son algo detectables

# Bonos por sensores
SENSOR_BONUS_GROUND = 10             # Sensores terrestres
SENSOR_BONUS_ORBITAL = 15            # Sensores orbitales
SENSOR_BONUS_ADVANCED = 25           # Sensores avanzados


@dataclass
class DetectionResult:
    """Resultado de un chequeo de detección."""
    detected: bool
    detector_unit_id: int
    detector_player_id: int
    detected_unit_id: int
    detected_player_id: int
    detection_type: str  # 'passive', 'active', 'interdiction'
    mrg_result_type: ResultType
    mrg_margin: int
    mrg_roll: int
    can_interdict: bool = False
    location_type: str = ""  # 'sector', 'ring', 'starlane'


@dataclass
class InterdictionResult:
    """Resultado de un intento de interdicción."""
    success: bool
    interdicting_unit_id: int
    target_unit_id: int
    starlane_id: int
    error_message: str = ""


# --- FUNCIONES DE CÁLCULO DE MÉRITO ---

def calculate_detection_merit(unit: UnitSchema) -> int:
    """
    Calcula los puntos de mérito de detección de una unidad.
    Basado en sensores, tripulación con habilidades de vigilancia, etc.
    """
    merit = 30  # Base de detección

    # TODO: Añadir bonos por módulos de sensores cuando se implementen
    # Por ahora, usar composición de la unidad como proxy

    # Bonus por número de miembros (más ojos = más detección)
    merit += len(unit.members) * 3

    # Si la unidad está en órbita/espacio, mejor detección
    if unit.status == UnitStatus.SPACE:
        merit += SENSOR_BONUS_ORBITAL

    return merit


def calculate_stealth_difficulty(unit: UnitSchema) -> int:
    """
    Calcula la dificultad de detectar a una unidad (su sigilo).
    Unidades con tropas aeroespaciales son más difíciles de detectar.
    """
    difficulty = DETECTION_DIFFICULTY_BASE

    # Contar tipos de tropas
    for member in unit.members:
        if member.entity_type == 'troop':
            details = member.details or {}
            troop_type = details.get('type', 'INFANTRY')

            if troop_type == 'AEROSPACE':
                difficulty += STEALTH_BONUS_AEROSPACE
            elif troop_type == 'INFANTRY':
                difficulty += STEALTH_BONUS_INFANTRY
            elif troop_type == 'ARMORED':
                difficulty += STEALTH_PENALTY_ARMORED
            elif troop_type == 'MECH':
                difficulty += STEALTH_PENALTY_MECH

    # Unidades en tránsito son más difíciles de detectar (en movimiento)
    if unit.status == UnitStatus.TRANSIT:
        difficulty += 10

    # Unidades pequeñas son más sigilosas
    if len(unit.members) <= 2:
        difficulty += 10
    elif len(unit.members) >= 6:
        difficulty -= 10

    return max(difficulty, 25)  # Mínimo dificultad 25


def unit_has_interdiction_module(unit: UnitSchema) -> bool:
    """
    Verifica si la unidad tiene un módulo de interdicción.
    TODO: Implementar cuando se añadan módulos de naves.
    """
    # Por ahora, revisar en details de los miembros si hay módulo
    for member in unit.members:
        if member.details:
            modules = member.details.get('modules', [])
            if INTERDICTION_MODULE_ID in modules:
                return True
    return False


# --- FUNCIÓN PRINCIPAL DE DETECCIÓN ---

def check_detection(
    detector_unit: UnitSchema,
    target_unit: UnitSchema,
    detection_context: str = "passive"
) -> DetectionResult:
    """
    Realiza un chequeo de detección entre dos unidades.

    Args:
        detector_unit: Unidad que intenta detectar
        target_unit: Unidad objetivo
        detection_context: 'passive' (automático), 'active' (ordenado), 'interdiction'

    Returns:
        DetectionResult con el outcome
    """
    # Calcular merit points del detector
    detector_merit = calculate_detection_merit(detector_unit)

    # Calcular dificultad basada en el objetivo
    target_difficulty = calculate_stealth_difficulty(target_unit)

    # Modificadores de contexto
    if detection_context == "passive":
        target_difficulty += DETECTION_MODIFIER_PASSIVE
    elif detection_context == "active":
        target_difficulty += DETECTION_MODIFIER_ACTIVE
    elif detection_context == "interdiction":
        target_difficulty += DETECTION_MODIFIER_INTERDICTION

    # Resolver con MRG
    result = resolve_action(
        merit_points=detector_merit,
        difficulty=target_difficulty,
        action_description=f"Detección de {target_unit.name}",
        player_id=detector_unit.player_id,
        details={
            "detector_id": detector_unit.id,
            "target_id": target_unit.id,
            "context": detection_context
        }
    )

    detected = result.success

    # Verificar capacidad de interdicción
    can_interdict = (
        detected and
        unit_has_interdiction_module(detector_unit) and
        target_unit.status == UnitStatus.TRANSIT
    )

    # Determinar tipo de ubicación
    location_type = "sector"
    if detector_unit.status == UnitStatus.TRANSIT or target_unit.status == UnitStatus.TRANSIT:
        location_type = "starlane"
    elif detector_unit.location_sector_id is None:
        location_type = "ring"

    return DetectionResult(
        detected=detected,
        detector_unit_id=detector_unit.id,
        detector_player_id=detector_unit.player_id,
        detected_unit_id=target_unit.id,
        detected_player_id=target_unit.player_id,
        detection_type=detection_context,
        mrg_result_type=result.result_type,
        mrg_margin=result.margin,
        mrg_roll=result.roll.total,
        can_interdict=can_interdict,
        location_type=location_type
    )


# --- PROCESAMIENTO DE FASE DE DETECCIÓN ---

def process_detection_phase(current_tick: int) -> List[DetectionResult]:
    """
    Procesa detecciones automáticas cuando unidades coinciden en ubicación.
    Llamado durante la fase de Detección del tick.

    Returns:
        Lista de resultados de detección
    """
    detections = []

    # 1. Detectar en sectores/anillos (unidades estacionarias)
    sector_detections = _process_location_detections()
    detections.extend(sector_detections)

    # 2. Detectar en starlanes (unidades en tránsito)
    starlane_detections = _process_starlane_detections()
    detections.extend(starlane_detections)

    # 3. Registrar detecciones en DB
    _log_detection_events(detections, current_tick)

    return detections


def _process_location_detections() -> List[DetectionResult]:
    """
    Procesa detecciones entre unidades en la misma ubicación estacionaria.
    """
    detections = []
    db = get_supabase()

    try:
        # Obtener todas las unidades no en tránsito
        response = db.table("units")\
            .select("*")\
            .neq("status", "TRANSIT")\
            .execute()

        if not response.data:
            return []

        units = response.data

        # Agrupar por ubicación
        location_groups = defaultdict(list)
        for unit_data in units:
            loc_key = (
                unit_data.get('location_system_id'),
                unit_data.get('ring', 0),
                unit_data.get('location_planet_id'),
                unit_data.get('location_sector_id')
            )
            location_groups[loc_key].append(unit_data)

        # Procesar grupos con múltiples facciones
        for loc_key, units_at_loc in location_groups.items():
            # Agrupar por jugador
            by_player = defaultdict(list)
            for u in units_at_loc:
                by_player[u.get('player_id')].append(u)

            # Si hay más de un jugador, hacer checks cruzados
            player_ids = list(by_player.keys())
            if len(player_ids) < 2:
                continue

            # Cada jugador intenta detectar a los demás
            for i, player_a in enumerate(player_ids):
                for player_b in player_ids[i+1:]:
                    # Player A intenta detectar a Player B
                    for unit_a_data in by_player[player_a]:
                        for unit_b_data in by_player[player_b]:
                            unit_a = UnitSchema.from_dict(unit_a_data)
                            unit_b = UnitSchema.from_dict(unit_b_data)

                            # A detecta a B
                            det_result = check_detection(unit_a, unit_b, "passive")
                            detections.append(det_result)

                            # B detecta a A
                            det_result_b = check_detection(unit_b, unit_a, "passive")
                            detections.append(det_result_b)

    except Exception as e:
        log_event(f"Error en detección de ubicación: {e}", is_error=True)

    return detections


def _process_starlane_detections() -> List[DetectionResult]:
    """
    Procesa detecciones entre unidades en la misma starlane.
    """
    detections = []
    db = get_supabase()

    try:
        # Obtener starlanes con múltiples unidades
        response = db.table("units")\
            .select("*")\
            .eq("status", "TRANSIT")\
            .not_.is_("starlane_id", "null")\
            .execute()

        if not response.data:
            return []

        # Agrupar por starlane
        starlane_groups = defaultdict(list)
        for unit_data in response.data:
            starlane_id = unit_data.get('starlane_id')
            if starlane_id:
                starlane_groups[starlane_id].append(unit_data)

        # Procesar grupos con múltiples facciones
        for starlane_id, units_on_lane in starlane_groups.items():
            by_player = defaultdict(list)
            for u in units_on_lane:
                by_player[u.get('player_id')].append(u)

            player_ids = list(by_player.keys())
            if len(player_ids) < 2:
                continue

            # Checks cruzados
            for i, player_a in enumerate(player_ids):
                for player_b in player_ids[i+1:]:
                    for unit_a_data in by_player[player_a]:
                        for unit_b_data in by_player[player_b]:
                            unit_a = UnitSchema.from_dict(unit_a_data)
                            unit_b = UnitSchema.from_dict(unit_b_data)

                            det_result = check_detection(unit_a, unit_b, "passive")
                            detections.append(det_result)

                            det_result_b = check_detection(unit_b, unit_a, "passive")
                            detections.append(det_result_b)

    except Exception as e:
        log_event(f"Error en detección de starlane: {e}", is_error=True)

    return detections


def _log_detection_events(detections: List[DetectionResult], current_tick: int) -> None:
    """
    Registra los eventos de detección en la tabla de auditoría.
    """
    if not detections:
        return

    db = get_supabase()

    for det in detections:
        try:
            data = {
                "tick": current_tick,
                "detector_unit_id": det.detector_unit_id,
                "detector_player_id": det.detector_player_id,
                "detected_unit_id": det.detected_unit_id,
                "detected_player_id": det.detected_player_id,
                "detection_type": det.detection_type,
                "mrg_roll": det.mrg_roll,
                "mrg_margin": det.mrg_margin,
                "detection_successful": det.detected
            }
            db.table("detection_events").insert(data).execute()
        except Exception as e:
            # No fallar por errores de logging
            print(f"Error logging detection event: {e}")

    # Notificar a jugadores de detecciones exitosas
    for det in detections:
        if det.detected:
            log_event(
                f"👁️ ¡Unidad enemiga detectada!",
                det.detector_player_id
            )


# --- SISTEMA DE INTERDICCIÓN ---

def attempt_interdiction(
    interdicting_unit_id: int,
    target_unit_id: int,
    player_id: int,
    current_tick: int
) -> InterdictionResult:
    """
    Intenta interdecir a una unidad en tránsito por starlane.
    Requiere que la unidad tenga Módulo de Interdicción y haya detectado al objetivo.

    Args:
        interdicting_unit_id: ID de la unidad que interdice
        target_unit_id: ID de la unidad objetivo
        player_id: ID del jugador que ordena la interdicción
        current_tick: Tick actual

    Returns:
        InterdictionResult con el resultado
    """
    # Obtener unidades
    interdictor_data = get_unit_by_id(interdicting_unit_id)
    target_data = get_unit_by_id(target_unit_id)

    if not interdictor_data:
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=0,
            error_message="Unidad interdictora no encontrada"
        )

    if not target_data:
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=0,
            error_message="Unidad objetivo no encontrada"
        )

    interdictor = UnitSchema.from_dict(interdictor_data)
    target = UnitSchema.from_dict(target_data)

    # Validaciones
    if interdictor.player_id != player_id:
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=interdictor.starlane_id or 0,
            error_message="No tienes control de la unidad interdictora"
        )

    if not unit_has_interdiction_module(interdictor):
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=interdictor.starlane_id or 0,
            error_message="La unidad no tiene módulo de interdicción"
        )

    if target.status != UnitStatus.TRANSIT:
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=interdictor.starlane_id or 0,
            error_message="El objetivo no está en tránsito"
        )

    if interdictor.starlane_id != target.starlane_id:
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=interdictor.starlane_id or 0,
            error_message="Las unidades no están en la misma starlane"
        )

    starlane_id = interdictor.starlane_id or 0

    # Realizar check de interdicción (más fácil que detección normal)
    det_result = check_detection(interdictor, target, "interdiction")

    if det_result.detected:
        # Interdicción exitosa - sacar ambas unidades de tránsito
        cancel_unit_transit(target.id, current_tick)
        cancel_unit_transit(interdictor.id, current_tick)

        log_event(
            f"⚡ ¡Interdicción exitosa! Unidad '{target.name}' sacada de tránsito",
            player_id
        )
        log_event(
            f"⚠️ ¡Tu unidad '{target.name}' ha sido interdictada!",
            target.player_id
        )

        return InterdictionResult(
            success=True,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=starlane_id
        )
    else:
        log_event(
            f"❌ Intento de interdicción fallido contra '{target.name}'",
            player_id
        )
        return InterdictionResult(
            success=False,
            interdicting_unit_id=interdicting_unit_id,
            target_unit_id=target_unit_id,
            starlane_id=starlane_id,
            error_message="Interdicción fallida"
        )
