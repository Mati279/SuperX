"""Motor de Resolución Galáctico - Núcleo de mecánicas de dados."""
import random
from typing import Tuple, Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from .mrg_constants import *


class ResultType(Enum):
    """Tipos de resultado posibles."""
    CRITICAL_SUCCESS = "critical_success"
    TOTAL_SUCCESS = "total_success"
    PARTIAL_SUCCESS = "partial_success"
    PARTIAL_FAILURE = "partial_failure"
    TOTAL_FAILURE = "total_failure"
    CRITICAL_FAILURE = "critical_failure"


class BenefitType(Enum):
    """Beneficios seleccionables en Éxito Total."""
    EFFICIENCY = "eficiencia"
    PRESTIGE = "prestigio"
    IMPETUS = "impetu"


class MalusType(Enum):
    """Malus seleccionables en Fracaso Total."""
    OPERATIVE_DOWN = "baja_operativa"
    DISCREDIT = "descredito"
    EXPOSURE = "exposicion"


@dataclass
class MRGRoll:
    """Resultado de una tirada 2d50."""
    die_1: int
    die_2: int

    @property
    def total(self) -> int:
        return self.die_1 + self.die_2

    @property
    def is_critical_success(self) -> bool:
        return self.total >= CRITICAL_SUCCESS_MIN

    @property
    def is_critical_failure(self) -> bool:
        return self.total <= CRITICAL_FAILURE_MAX


@dataclass
class MRGResult:
    """Resultado completo de una resolución MRG."""
    # Datos de la tirada
    roll: MRGRoll
    merit_points: int
    bonus_applied: int
    difficulty: int
    margin: int

    # Resultado
    result_type: ResultType

    # Selección requerida
    requires_player_choice: bool = False
    available_benefits: List[BenefitType] = field(default_factory=list)
    available_malus: List[MalusType] = field(default_factory=list)

    # Selección realizada (se llena después)
    selected_benefit: Optional[BenefitType] = None
    selected_malus: Optional[MalusType] = None

    # Metadatos
    action_description: str = ""
    entity_id: Optional[int] = None
    entity_name: str = ""


def roll_2d50() -> MRGRoll:
    """Realiza una tirada de 2d50."""
    return MRGRoll(
        die_1=random.randint(1, DICE_SIDES),
        die_2=random.randint(1, DICE_SIDES)
    )


def calculate_asymptotic_bonus(
    merit_points: int,
    max_bonus: int = ASYMPTOTIC_MAX_BONUS,
    k_factor: int = ASYMPTOTIC_K_FACTOR
) -> int:
    """
    Calcula el bono con saturación asintótica.

    Fórmula: Bono_Final = Max_Bono × (Puntos / (Puntos + K))

    Esto crea una curva que se acerca pero nunca alcanza Max_Bono,
    evitando personajes "invencibles".
    """
    if merit_points <= 0:
        return 0

    raw_bonus = max_bonus * (merit_points / (merit_points + k_factor))
    return int(round(raw_bonus))


def calculate_merit_from_attributes(
    attributes: Dict[str, int],
    relevant_attrs: List[str]
) -> int:
    """
    Calcula puntos de mérito sumando atributos relevantes.

    Args:
        attributes: Dict con todos los atributos del personaje
        relevant_attrs: Lista de atributos que aplican a esta acción

    Returns:
        Suma de los atributos relevantes
    """
    total = 0
    for attr in relevant_attrs:
        attr_lower = attr.lower()
        total += attributes.get(attr_lower, 0)
    return total


def determine_result_type(roll: MRGRoll, margin: int) -> ResultType:
    """
    Determina el tipo de resultado basado en la tirada y el margen.

    Prioridad:
    1. Críticos (tirada extrema) override el margen
    2. Si no hay crítico, se evalúa por margen
    """
    # Críticos primero
    if roll.is_critical_success:
        return ResultType.CRITICAL_SUCCESS
    if roll.is_critical_failure:
        return ResultType.CRITICAL_FAILURE

    # Por margen
    if margin > TOTAL_SUCCESS_MARGIN:
        return ResultType.TOTAL_SUCCESS
    elif margin >= PARTIAL_SUCCESS_MARGIN:
        return ResultType.PARTIAL_SUCCESS
    elif margin >= PARTIAL_FAILURE_MARGIN:
        return ResultType.PARTIAL_FAILURE
    else:
        return ResultType.TOTAL_FAILURE


def resolve_action(
    merit_points: int,
    difficulty: int,
    action_description: str = "",
    entity_id: Optional[int] = None,
    entity_name: str = "",
    situational_modifiers: Optional[Dict[str, int]] = None
) -> MRGResult:
    """
    Resuelve una acción mediante el Motor de Resolución Galáctico.

    Args:
        merit_points: Puntos de mérito de la entidad (suma de atributos relevantes)
        difficulty: Dificultad del objetivo (usar DIFFICULTY_* constantes)
        action_description: Descripción de la acción para logs
        entity_id: ID del personaje/activo que realiza la acción
        entity_name: Nombre de la entidad
        situational_modifiers: Modificadores adicionales {"nombre": valor}

    Returns:
        MRGResult con todos los detalles de la resolución
    """
    # 1. Tirar dados
    roll = roll_2d50()

    # 2. Calcular bono asintótico
    base_bonus = calculate_asymptotic_bonus(merit_points)

    # 3. Aplicar modificadores situacionales
    total_bonus = base_bonus
    if situational_modifiers:
        total_bonus += sum(situational_modifiers.values())

    # 4. Calcular margen
    margin = roll.total + total_bonus - difficulty

    # 5. Determinar tipo de resultado
    result_type = determine_result_type(roll, margin)

    # 6. Determinar si requiere selección del jugador
    requires_choice = result_type in [
        ResultType.CRITICAL_SUCCESS,
        ResultType.TOTAL_SUCCESS,
        ResultType.CRITICAL_FAILURE,
        ResultType.TOTAL_FAILURE
    ]

    # 7. Preparar opciones disponibles
    benefits = []
    malus = []

    if result_type in [ResultType.CRITICAL_SUCCESS, ResultType.TOTAL_SUCCESS]:
        benefits = list(BenefitType)
    elif result_type in [ResultType.CRITICAL_FAILURE, ResultType.TOTAL_FAILURE]:
        malus = list(MalusType)

    return MRGResult(
        roll=roll,
        merit_points=merit_points,
        bonus_applied=total_bonus,
        difficulty=difficulty,
        margin=margin,
        result_type=result_type,
        requires_player_choice=requires_choice,
        available_benefits=benefits,
        available_malus=malus,
        action_description=action_description,
        entity_id=entity_id,
        entity_name=entity_name
    )


def get_result_description(result_type: ResultType) -> Dict[str, str]:
    """Retorna textos descriptivos para cada tipo de resultado."""
    descriptions = {
        ResultType.CRITICAL_SUCCESS: {
            "title": "🌟 ¡ÉXITO CRÍTICO!",
            "color": "#FFD700",
            "description": "¡Hazaña extraordinaria! La entidad supera todas las expectativas.",
            "instruction": "Selecciona un BENEFICIO como recompensa:"
        },
        ResultType.TOTAL_SUCCESS: {
            "title": "✅ Éxito Total",
            "color": "#56d59f",
            "description": "Objetivo logrado con maestría. Sin complicaciones.",
            "instruction": "Selecciona un BENEFICIO como recompensa:"
        },
        ResultType.PARTIAL_SUCCESS: {
            "title": "⚠️ Éxito Parcial",
            "color": "#f6c45b",
            "description": "Objetivo logrado, pero con una complicación menor.",
            "instruction": "El sistema aplicará una complicación automática."
        },
        ResultType.PARTIAL_FAILURE: {
            "title": "⚠️ Fracaso Parcial",
            "color": "#f6c45b",
            "description": "El objetivo no se cumple. Se pierden los recursos invertidos.",
            "instruction": "La entidad conserva su posición pero pierde la inversión."
        },
        ResultType.TOTAL_FAILURE: {
            "title": "❌ Fracaso Total",
            "color": "#f06464",
            "description": "El objetivo fracasa estrepitosamente.",
            "instruction": "Debes elegir un MALUS como consecuencia:"
        },
        ResultType.CRITICAL_FAILURE: {
            "title": "💀 ¡PIFIA!",
            "color": "#8B0000",
            "description": "¡Desastre absoluto! Todo lo que podía salir mal, salió peor.",
            "instruction": "Debes elegir un MALUS como consecuencia:"
        }
    }
    return descriptions.get(result_type, {})


def get_benefit_description(benefit: BenefitType) -> Dict[str, str]:
    """Retorna descripción de un beneficio."""
    benefits = {
        BenefitType.EFFICIENCY: {
            "name": "⚡ Eficiencia",
            "description": f"Recuperas el {int(BENEFIT_EFFICIENCY_REFUND * 100)}% del costo de energía de la misión.",
            "effect": "Recursos devueltos"
        },
        BenefitType.PRESTIGE: {
            "name": "🌟 Prestigio",
            "description": f"Tu facción gana +{BENEFIT_PRESTIGE_GAIN}% de Prestigio por el impacto mediático.",
            "effect": "Prestigio aumentado"
        },
        BenefitType.IMPETUS: {
            "name": "🚀 Ímpetu",
            "description": f"La siguiente misión de esta entidad se reduce en {BENEFIT_IMPETUS_TICK_REDUCTION} Tick.",
            "effect": "Siguiente misión acelerada"
        }
    }
    return benefits.get(benefit, {})


def get_malus_description(malus: MalusType) -> Dict[str, str]:
    """Retorna descripción de un malus."""
    malus_info = {
        MalusType.OPERATIVE_DOWN: {
            "name": "🏥 Baja Operativa",
            "description": f"La entidad queda fuera de servicio por {MALUS_OPERATIVE_DOWN_TICKS} Ticks (heridas/reparaciones).",
            "effect": "Entidad incapacitada"
        },
        MalusType.DISCREDIT: {
            "name": "📉 Descrédito",
            "description": f"Tu facción pierde -{MALUS_DISCREDIT_LOSS}% de prestigio por el escándalo.",
            "effect": "Prestigio reducido"
        },
        MalusType.EXPOSURE: {
            "name": "👁️ Exposición",
            "description": "Se revela la ubicación de la entidad o un secreto tecnológico al enemigo.",
            "effect": "Información comprometida"
        }
    }
    return malus_info.get(malus, {})
