# core/detection_engine.py (Completo)
"""
Motor de Detección V14.1.
Implementa checks de detección entre unidades usando MRG 2d50.
Incluye sistema de interdicción para unidades con módulos especiales.

V14.1 Nuevas funcionalidades:
- resolve_detection_round: Tirada competida Detección vs Sigilo/Evasión
- resolve_mutual_detection: Detección bidireccional (Conflicto/Emboscada)
- resolve_escape_attempt: Mecánica de huida y caza
- Lógica de revelación de entidades con estado HIDDEN
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from core.mrg_engine import resolve_action, MRGResult, ResultType
from core.mrg_constants import DIFFICULTY_STANDARD, DIFFICULTY_CHALLENGING
from core.models import UnitSchema, UnitStatus, UnitMemberSchema
from core.movement_constants import INTERDICTION_MODULE_ID
from core.rules import calculate_skills
from core.detection_constants import (
    GROUP_SIZE_PENALTY_PER_ENTITY,
    STEALTH_MODE_DEFENSE_BONUS,
    DETECTION_TOTAL_SUCCESS_MARGIN,
    DETECTION_BASE_DIFFICULTY,
    DetectionOutcome,
    DetectionEnvironment,
    DISORIENTED_MAX_LOCAL_MOVES,
    SKILL_DETECTION,
    SKILL_STEALTH_GROUND,
    SKILL_SENSOR_EVASION,
    SKILL_TACTICAL_ESCAPE,
    SKILL_HUNT
)
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


# =============================================================================
# V14.1: SISTEMA DE DETECCIÓN COMPETIDA, EMBOSCADA Y HUIDA
# =============================================================================

class RevealLevel(str, Enum):
    """Nivel de información revelada sobre una entidad."""
    NONE = "NONE"           # No detectado, permanece oculto
    PRESENCE = "PRESENCE"   # Solo se sabe que hay algo
    PARTIAL = "PARTIAL"     # Nombre y tipo revelados
    FULL = "FULL"           # Información completa


@dataclass
class EntityRevealInfo:
    """Información revelada sobre una entidad específica."""
    entity_type: str        # 'character' o 'troop'
    entity_id: int
    name: str
    reveal_level: RevealLevel
    stealth_score: int      # Valor de sigilo/evasión usado
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompetitiveDetectionResult:
    """Resultado de una ronda de detección competida (V14.1)."""
    success: bool                   # Si el atacante logró detectar al defensor
    is_total_success: bool          # Si fue éxito total (+25 margen)
    mrg_result: MRGResult           # Resultado completo del MRG
    entities_revealed: List[EntityRevealInfo] = field(default_factory=list)
    worst_defender_revealed: Optional[EntityRevealInfo] = None


@dataclass
class MutualDetectionResult:
    """Resultado de detección mutua entre dos unidades (V14.1)."""
    outcome: str                    # CONFLICT, AMBUSH_A, AMBUSH_B, MUTUAL_STEALTH
    unit_a_detects_b: bool
    unit_b_detects_a: bool
    unit_a_revealed: List[EntityRevealInfo]  # Entidades de A reveladas a B
    unit_b_revealed: List[EntityRevealInfo]  # Entidades de B reveladas a A
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EscapeAttemptResult:
    """Resultado de un intento de escape (V14.1)."""
    entity_id: int
    entity_type: str
    escaped: bool
    mrg_result: Optional[MRGResult]
    is_auto_escape: bool = False    # True si escapó por estar HIDDEN


# --- FUNCIONES HELPER V14.1 ---

def _get_member_attributes(member: UnitMemberSchema) -> Dict[str, int]:
    """
    Obtiene los atributos de un miembro de unidad.
    Extrae del snapshot 'details' si está disponible.
    """
    if member.details and 'attributes' in member.details:
        return member.details['attributes']
    if member.details and 'atributos' in member.details:
        return member.details['atributos']
    # Defaults seguros
    return {
        'fuerza': 5, 'agilidad': 5, 'tecnica': 5,
        'intelecto': 5, 'voluntad': 5, 'presencia': 5
    }


def _get_member_skill(member: UnitMemberSchema, skill_name: str) -> int:
    """
    Obtiene el valor de una habilidad específica de un miembro.
    Calcula desde atributos si no está pre-calculado.
    """
    # Intentar obtener de skills pre-calculados
    if member.details and 'habilidades' in member.details:
        skills = member.details['habilidades']
        if skill_name in skills:
            return skills[skill_name]

    # Calcular desde atributos
    attrs = _get_member_attributes(member)
    calculated = calculate_skills(attrs)
    return calculated.get(skill_name, 20)  # Default 20 si no existe


def _get_troop_skill_value(troop_type: str, skill_name: str) -> int:
    """
    Obtiene un valor de habilidad aproximado para tropas basado en tipo.
    Las tropas no tienen atributos individuales, usan valores fijos por tipo.
    """
    troop_skill_matrix = {
        'INFANTRY': {
            SKILL_DETECTION: 30,
            SKILL_STEALTH_GROUND: 35,
            SKILL_SENSOR_EVASION: 20,
            SKILL_TACTICAL_ESCAPE: 30,
            SKILL_HUNT: 30
        },
        'MECH': {
            SKILL_DETECTION: 40,
            SKILL_STEALTH_GROUND: 15,
            SKILL_SENSOR_EVASION: 25,
            SKILL_TACTICAL_ESCAPE: 20,
            SKILL_HUNT: 35
        },
        'AEROSPACE': {
            SKILL_DETECTION: 45,
            SKILL_STEALTH_GROUND: 10,
            SKILL_SENSOR_EVASION: 40,
            SKILL_TACTICAL_ESCAPE: 35,
            SKILL_HUNT: 40
        },
        'ARMORED': {
            SKILL_DETECTION: 35,
            SKILL_STEALTH_GROUND: 10,
            SKILL_SENSOR_EVASION: 20,
            SKILL_TACTICAL_ESCAPE: 15,
            SKILL_HUNT: 30
        }
    }

    type_skills = troop_skill_matrix.get(troop_type, troop_skill_matrix['INFANTRY'])
    return type_skills.get(skill_name, 25)


def calculate_group_average_skill(
    unit: UnitSchema,
    skill_name: str
) -> Tuple[int, List[Tuple[int, str, int]]]:
    """
    Calcula el promedio de una habilidad para todos los miembros de una unidad.

    Returns:
        Tuple de (promedio, lista de (entity_id, entity_type, skill_value))
    """
    if not unit.members:
        return 0, []

    skill_values: List[Tuple[int, str, int]] = []

    for member in unit.members:
        if member.entity_type == 'character':
            skill_val = _get_member_skill(member, skill_name)
        else:  # troop
            troop_type = member.details.get('type', 'INFANTRY') if member.details else 'INFANTRY'
            skill_val = _get_troop_skill_value(troop_type, skill_name)

        skill_values.append((member.entity_id, member.entity_type, skill_val))

    total = sum(sv[2] for sv in skill_values)
    avg = total // len(skill_values) if skill_values else 0

    return avg, skill_values


def determine_detection_environment(unit: UnitSchema) -> str:
    """
    Determina si la unidad está en ambiente terrestre o espacial.
    """
    if unit.status == UnitStatus.GROUND:
        return DetectionEnvironment.GROUND
    return DetectionEnvironment.SPACE


def get_defense_skill_for_environment(environment: str) -> str:
    """
    Retorna la habilidad de defensa apropiada según el ambiente.
    """
    if environment == DetectionEnvironment.GROUND:
        return SKILL_STEALTH_GROUND
    return SKILL_SENSOR_EVASION


# --- FUNCIONES PRINCIPALES V14.1 ---

def resolve_detection_round(
    attacker: UnitSchema,
    defender: UnitSchema,
    player_id: Optional[int] = None
) -> CompetitiveDetectionResult:
    """
    Ejecuta una ronda de detección competida donde el atacante intenta detectar al defensor.

    Mecánica V14.1:
    1. Calcula promedio de Detección del atacante
    2. Calcula promedio de Sigilo (tierra) o Evasión de Sensores (espacio) del defensor
    3. Aplica penalizador de grupo: -2 a defensa por cada entidad >1 en el bando defensor
    4. Aplica bono de sigilo: +15 a defensa si STEALTH_MODE activo
    5. Tirada competida: Detección vs (Dificultad Base + Defensa + Modificadores)

    Resultados:
    - Éxito: Se conoce presencia y se revela la entidad con PEOR stat de sigilo
    - Éxito Total (+25 margen): MRG individual contra cada miembro restante

    IMPORTANTE: Entidades NO reveladas deben iniciar combate en estado HIDDEN.
    """
    # 1. Determinar ambiente
    environment = determine_detection_environment(defender)
    defense_skill = get_defense_skill_for_environment(environment)

    # 2. Calcular promedios
    attack_avg, _ = calculate_group_average_skill(attacker, SKILL_DETECTION)
    defense_avg, defense_scores = calculate_group_average_skill(defender, defense_skill)

    # 3. Penalizador de grupo: -2 por cada entidad mayor a 1
    defender_count = len(defender.members)
    group_penalty = (defender_count - 1) * GROUP_SIZE_PENALTY_PER_ENTITY if defender_count > 1 else 0

    # 4. Bono de sigilo si está en STEALTH_MODE
    stealth_bonus = STEALTH_MODE_DEFENSE_BONUS if defender.status == UnitStatus.STEALTH_MODE else 0

    # 5. Calcular dificultad efectiva
    # Dificultad = Base + Defensa promedio + Bonus sigilo + Penalizador grupo (negativo)
    effective_difficulty = DETECTION_BASE_DIFFICULTY + defense_avg + stealth_bonus + group_penalty

    # 6. Ejecutar MRG
    mrg_result = resolve_action(
        merit_points=attack_avg,
        difficulty=effective_difficulty,
        action_description=f"Detección Competida: {attacker.name} -> {defender.name}",
        player_id=player_id,
        details={
            "attack_avg": attack_avg,
            "defense_avg": defense_avg,
            "group_penalty": group_penalty,
            "stealth_bonus": stealth_bonus,
            "environment": environment,
            "defender_count": defender_count
        }
    )

    # 7. Procesar resultado
    entities_revealed: List[EntityRevealInfo] = []
    worst_revealed: Optional[EntityRevealInfo] = None

    if mrg_result.success:
        # Ordenar defensores por skill (menor = peor = revelado primero)
        sorted_defenders = sorted(defense_scores, key=lambda x: x[2])

        if sorted_defenders:
            # El peor siempre es revelado en cualquier éxito
            worst = sorted_defenders[0]
            worst_member = next(
                (m for m in defender.members if m.entity_id == worst[0] and m.entity_type == worst[1]),
                None
            )

            if worst_member:
                worst_revealed = EntityRevealInfo(
                    entity_type=worst[1],
                    entity_id=worst[0],
                    name=worst_member.name,
                    reveal_level=RevealLevel.FULL,
                    stealth_score=worst[2],
                    details=worst_member.details or {}
                )
                entities_revealed.append(worst_revealed)

        # 8. Éxito Total (+25): MRG individual contra cada miembro restante
        is_total = mrg_result.margin >= DETECTION_TOTAL_SUCCESS_MARGIN

        if is_total and len(sorted_defenders) > 1:
            for entity_id, entity_type, skill_val in sorted_defenders[1:]:
                # MRG individual: atacante vs skill individual + bonus sigilo
                individual_diff = DETECTION_BASE_DIFFICULTY + skill_val + stealth_bonus
                individual_result = resolve_action(
                    merit_points=attack_avg,
                    difficulty=individual_diff,
                    action_description=f"Detección Individual: {attacker.name} -> Entity {entity_id}",
                    player_id=player_id
                )

                member = next(
                    (m for m in defender.members if m.entity_id == entity_id and m.entity_type == entity_type),
                    None
                )

                if individual_result.success and member:
                    entities_revealed.append(EntityRevealInfo(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        name=member.name,
                        reveal_level=RevealLevel.PARTIAL,
                        stealth_score=skill_val,
                        details=member.details or {}
                    ))

        # 9. Auditoría detallada
        revealed_names = [e.name for e in entities_revealed]
        log_event(
            message=(
                f"🔍 DETECCIÓN COMPETIDA [{attacker.name} vs {defender.name}]: "
                f"Margen {mrg_result.margin} ({'Éxito Total' if is_total else 'Éxito'}) - "
                f"Revelados: {revealed_names} ({len(entities_revealed)}/{defender_count})"
            ),
            player_id=player_id,
            event_type="DETECTION_AUDIT"
        )

        return CompetitiveDetectionResult(
            success=True,
            is_total_success=is_total,
            mrg_result=mrg_result,
            entities_revealed=entities_revealed,
            worst_defender_revealed=worst_revealed
        )

    # Fracaso en detección
    log_event(
        message=f"🔍 DETECCIÓN COMPETIDA [{attacker.name} vs {defender.name}]: Falló (Margen {mrg_result.margin})",
        player_id=player_id,
        event_type="DETECTION_AUDIT"
    )

    return CompetitiveDetectionResult(
        success=False,
        is_total_success=False,
        mrg_result=mrg_result,
        entities_revealed=[],
        worst_defender_revealed=None
    )


def resolve_mutual_detection(
    unit_a: UnitSchema,
    unit_b: UnitSchema,
    player_a_id: Optional[int] = None,
    player_b_id: Optional[int] = None
) -> MutualDetectionResult:
    """
    Resuelve detección mutua entre dos unidades (V14.1).

    Determina la situación resultante:
    - CONFLICT: Ambos se detectan -> Intercambio de información revelada
    - AMBUSH_A: Solo A detecta a B -> A decide si atacar (emboscada)
    - AMBUSH_B: Solo B detecta a A -> B decide si atacar (emboscada)
    - MUTUAL_STEALTH: Ninguno detecta al otro -> Se cruzan sin verse

    IMPORTANTE:
    - Las entidades NO reveladas inician cualquier combate posterior en estado HIDDEN
    - Si una unidad es detectada mientras estaba en STEALTH_MODE, entra como 'disoriented'
    - V14.2: Si hay TOTAL_FAILURE (pifia), la unidad se desorienta automáticamente.
    """
    # Detección A -> B
    result_a_to_b = resolve_detection_round(unit_a, unit_b, player_a_id)

    # Detección B -> A
    result_b_to_a = resolve_detection_round(unit_b, unit_a, player_b_id)

    # Determinar outcome
    if result_a_to_b.success and result_b_to_a.success:
        outcome = DetectionOutcome.CONFLICT
    elif result_a_to_b.success and not result_b_to_a.success:
        outcome = DetectionOutcome.AMBUSH_A
    elif not result_a_to_b.success and result_b_to_a.success:
        outcome = DetectionOutcome.AMBUSH_B
    else:
        outcome = DetectionOutcome.MUTUAL_STEALTH

    # V14.2: Lógica de Fallo Total (Pifia) -> Desorientación
    # Si A pifia al detectar a B, A se desorienta
    if result_a_to_b.mrg_result.result_type == ResultType.TOTAL_FAILURE:
        mark_unit_disoriented(unit_a)
        log_event(f"😵 Fallo crítico en detección: {unit_a.name} queda desorientada", player_a_id)

    # Si B pifia al detectar a A, B se desorienta
    if result_b_to_a.mrg_result.result_type == ResultType.TOTAL_FAILURE:
        mark_unit_disoriented(unit_b)
        log_event(f"😵 Fallo crítico en detección: {unit_b.name} queda desorientada", player_b_id)

    # Compilar entidades reveladas
    unit_a_revealed = result_b_to_a.entities_revealed  # A revelado a B
    unit_b_revealed = result_a_to_b.entities_revealed  # B revelado a A

    # Log de auditoría completo
    log_event(
        message=(
            f"⚔️ DETECCIÓN MUTUA: {unit_a.name} vs {unit_b.name} -> {outcome} | "
            f"A revela {len(unit_b_revealed)} de {len(unit_b.members)} | "
            f"B revela {len(unit_a_revealed)} de {len(unit_a.members)}"
        ),
        player_id=player_a_id,
        event_type="DETECTION_AUDIT"
    )

    return MutualDetectionResult(
        outcome=outcome,
        unit_a_detects_b=result_a_to_b.success,
        unit_b_detects_a=result_b_to_a.success,
        unit_a_revealed=unit_a_revealed,
        unit_b_revealed=unit_b_revealed,
        details={
            "mrg_a_to_b": {
                "margin": result_a_to_b.mrg_result.margin,
                "result_type": result_a_to_b.mrg_result.result_type.value,
                "is_total": result_a_to_b.is_total_success
            },
            "mrg_b_to_a": {
                "margin": result_b_to_a.mrg_result.margin,
                "result_type": result_b_to_a.mrg_result.result_type.value,
                "is_total": result_b_to_a.is_total_success
            }
        }
    )


def get_hidden_entities(
    unit: UnitSchema,
    revealed_entities: List[EntityRevealInfo]
) -> List[UnitMemberSchema]:
    """
    Obtiene las entidades de una unidad que NO fueron reveladas.
    Estas entidades deben iniciar combate en estado HIDDEN.
    """
    revealed_ids = {(e.entity_id, e.entity_type) for e in revealed_entities}

    hidden = []
    for member in unit.members:
        if (member.entity_id, member.entity_type) not in revealed_ids:
            hidden.append(member)

    return hidden


def mark_unit_disoriented(
    unit: UnitSchema,
    revealed_while_stealth: bool = False
) -> UnitSchema:
    """
    Marca una unidad como desacomodada (disoriented).

    Consecuencias:
    - Restricción a 1 movimiento local por tick (si está en stealth)
    - Puede iniciar combate con desventaja

    Se aplica cuando:
    - La unidad estaba en STEALTH_MODE y fue detectada
    - Fallo crítico (Pifia) en detección
    """
    unit.disoriented = True
    
    if revealed_while_stealth:
        # Resetear status de sigilo al estado base si fue revelada
        if unit.status == UnitStatus.STEALTH_MODE:
            # Determinar nuevo estado según ubicación
            if unit.location_sector_id is not None:
                unit.status = UnitStatus.GROUND
            else:
                unit.status = UnitStatus.SPACE

    return unit


# --- MECÁNICA DE HUIDA Y CAZA V14.1 ---

def resolve_escape_attempt(
    escaping_member: UnitMemberSchema,
    pursuer_unit: UnitSchema,
    is_hidden: bool = False,
    player_id: Optional[int] = None
) -> EscapeAttemptResult:
    """
    Resuelve un intento de escape de una entidad individual.

    Mecánica V14.1:
    - Huida Garantizada: Si la entidad está HIDDEN -> Escape automático
    - Escape Táctico: Entidades detectadas tiran Escape Táctico vs Promedio Caza

    Consecuencias:
    - Escape exitoso: La entidad puede formar nueva unidad, recibe mov gratis
    - Escape fallido: Entra en combate como disoriented
    """
    # Escape automático para entidades ocultas (HIDDEN)
    if is_hidden:
        log_event(
            message=f"🏃 ESCAPE AUTOMÁTICO: {escaping_member.name} (estado HIDDEN)",
            player_id=player_id,
            event_type="DETECTION_AUDIT"
        )

        return EscapeAttemptResult(
            entity_id=escaping_member.entity_id,
            entity_type=escaping_member.entity_type,
            escaped=True,
            mrg_result=None,
            is_auto_escape=True
        )

    # Escape táctico para entidades detectadas
    escape_skill = _get_member_skill(escaping_member, SKILL_TACTICAL_ESCAPE)
    hunt_avg, _ = calculate_group_average_skill(pursuer_unit, SKILL_HUNT)

    # Dificultad = Base + Promedio de Caza de perseguidores
    escape_difficulty = DETECTION_BASE_DIFFICULTY + hunt_avg

    mrg_result = resolve_action(
        merit_points=escape_skill,
        difficulty=escape_difficulty,
        action_description=f"Escape Táctico: {escaping_member.name}",
        player_id=player_id,
        details={
            "escape_skill": escape_skill,
            "hunt_avg": hunt_avg
        }
    )

    escaped = mrg_result.success

    log_event(
        message=(
            f"🏃 ESCAPE TÁCTICO [{escaping_member.name}]: "
            f"{'Exitoso' if escaped else 'Fallido'} (Margen {mrg_result.margin}) - "
            f"Escape {escape_skill} vs Caza {hunt_avg}"
        ),
        player_id=player_id,
        event_type="DETECTION_AUDIT"
    )

    return EscapeAttemptResult(
        entity_id=escaping_member.entity_id,
        entity_type=escaping_member.entity_type,
        escaped=escaped,
        mrg_result=mrg_result,
        is_auto_escape=False
    )


def resolve_group_escape(
    fleeing_unit: UnitSchema,
    pursuer_unit: UnitSchema,
    revealed_entities: List[EntityRevealInfo],
    player_id: Optional[int] = None
) -> Tuple[List[UnitMemberSchema], List[UnitMemberSchema]]:
    """
    Resuelve escape para toda una unidad.

    Returns:
        Tuple de (escaped_members, captured_members)

    Post-Huida V14.1:
    - Los que escapan forman una nueva unidad
    - Los que escapan reciben movement_locked = False (reset, mov gratis)
    - Los que fallan entran en combate como disoriented
    """
    escaped: List[UnitMemberSchema] = []
    captured: List[UnitMemberSchema] = []

    revealed_ids = {(e.entity_id, e.entity_type) for e in revealed_entities}

    for member in fleeing_unit.members:
        is_hidden = (member.entity_id, member.entity_type) not in revealed_ids

        result = resolve_escape_attempt(
            escaping_member=member,
            pursuer_unit=pursuer_unit,
            is_hidden=is_hidden,
            player_id=player_id
        )

        if result.escaped:
            escaped.append(member)
        else:
            captured.append(member)

    # Log resumen
    log_event(
        message=(
            f"🏃 ESCAPE GRUPAL [{fleeing_unit.name}]: "
            f"{len(escaped)} escaparon ({len([m for m in escaped if (m.entity_id, m.entity_type) not in revealed_ids])} ocultos), "
            f"{len(captured)} capturados/atrapados"
        ),
        player_id=player_id,
        event_type="DETECTION_AUDIT"
    )

    return escaped, captured


def prepare_combat_state(
    unit: UnitSchema,
    revealed_entities: List[EntityRevealInfo],
    was_ambushed: bool = False
) -> Dict[str, Any]:
    """
    Prepara el estado de combate de una unidad después de la fase de detección.

    Marca:
    - Entidades no reveladas como HIDDEN (pueden escapar automáticamente)
    - Unidad como disoriented si fue emboscada mientras estaba en STEALTH_MODE
    - V14.2: Unidad como disoriented si fue revelada mientras estaba en STEALTH_MODE (aunque no fuera emboscada)

    Returns:
        Dict con estado de combate preparado para el motor de combate
    """
    hidden_members = get_hidden_entities(unit, revealed_entities)
    hidden_ids = [(m.entity_id, m.entity_type) for m in hidden_members]

    # Determinar si la unidad estaba en modo sigilo
    was_in_stealth = unit.status == UnitStatus.STEALTH_MODE

    # V14.2: Se desorienta si fue emboscada en sigilo O si fue revelada en sigilo
    is_revealed = len(revealed_entities) > 0
    unit_disoriented = unit.disoriented or (was_in_stealth and (was_ambushed or is_revealed))

    return {
        "unit_id": unit.id,
        "unit_name": unit.name,
        "player_id": unit.player_id,
        "disoriented": unit_disoriented,
        "hidden_member_ids": hidden_ids,
        "revealed_count": len(revealed_entities),
        "hidden_count": len(hidden_members),
        "total_members": len(unit.members),
        "was_in_stealth": was_in_stealth,
        "max_local_moves": DISORIENTED_MAX_LOCAL_MOVES if unit_disoriented else 2
    }


def clean_hidden_state_on_offensive_action(unit: UnitSchema) -> UnitSchema:
    """
    Limpia el estado HIDDEN de una unidad cuando realiza una acción ofensiva.

    Restricción: El estado HIDDEN se pierde al atacar, ya que revela la posición.
    """
    if unit.status == UnitStatus.HIDDEN:
        if unit.location_sector_id is not None:
            unit.status = UnitStatus.GROUND
        else:
            unit.status = UnitStatus.SPACE

    return unit