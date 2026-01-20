# core/mrg_engine.py
"""
Motor de Resolución Galáctico (MRG).
Implementa la lógica de 2d50 y evaluación de resultados.
Refactorizado v2.1: Función pura sin gestión de efectos secundarios.
"""
import random
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from .mrg_constants import (
    DICE_SIDES,
    CRITICAL_SUCCESS_MIN,
    CRITICAL_FAILURE_MAX,
    MARGIN_TOTAL_SUCCESS,
    MARGIN_PARTIAL_SUCCESS,
    MARGIN_PARTIAL_FAILURE,
    ASYMPTOTIC_MAX_BONUS,
    ASYMPTOTIC_K_FACTOR
)
from data.log_repository import log_event


class ResultType(Enum):
    """Tipos de resultado posibles según Reglas v2.1."""
    CRITICAL_SUCCESS = "critical_success"  # 96-100 (Anula margen)
    TOTAL_SUCCESS = "total_success"        # Margen > 25
    PARTIAL_SUCCESS = "partial_success"    # Margen 0 a 25
    PARTIAL_FAILURE = "partial_failure"    # Margen -25 a 0
    TOTAL_FAILURE = "total_failure"        # Margen < -25
    CRITICAL_FAILURE = "critical_failure"  # 2-5 (Anula margen)


@dataclass
class MRGRoll:
    """Representación física de la tirada de dados."""
    die_1: int
    die_2: int

    @property
    def total(self) -> int:
        return self.die_1 + self.die_2


@dataclass
class MRGResult:
    """
    Resultado matemático de una resolución.
    Objeto de valor inmutable y sin estado de efectos.
    """
    roll: MRGRoll
    merit_points: int
    bonus_applied: int
    difficulty: int
    margin: int
    result_type: ResultType
    action_description: str = ""

    @property
    def success(self) -> bool:
        """Determina si el resultado es un éxito positivo (Crítico, Total o Parcial)."""
        return self.result_type in [
            ResultType.CRITICAL_SUCCESS,
            ResultType.TOTAL_SUCCESS,
            ResultType.PARTIAL_SUCCESS
        ]


def roll_2d50() -> MRGRoll:
    """
    Genera una distribución triangular (Campana) entre 2 y 100.
    Media estadística: 51.
    """
    return MRGRoll(
        die_1=random.randint(1, DICE_SIDES),
        die_2=random.randint(1, DICE_SIDES)
    )


def calculate_asymptotic_bonus(merit_points: int) -> int:
    """
    Calcula el bono con saturación asintótica (Regla 3.2 v2.1).
    Asegura que el bono sea siempre >= 0 y redondeado al entero más cercano.
    Max Bono ajustado a 50 según nuevas especificaciones.
    """
    if merit_points <= 0:
        return 0
        
    # Bono_Final = Max_Bono * (Puntos / (Puntos + K))
    raw_bonus = ASYMPTOTIC_MAX_BONUS * (merit_points / (merit_points + ASYMPTOTIC_K_FACTOR))
    
    return int(round(raw_bonus))


def determine_result_type(roll: MRGRoll, margin: int) -> ResultType:
    """
    Determina el grado de éxito/fracaso.
    PRIORIDAD: Los extremos del dado (Críticos) anulan el margen matemático.
    """
    # 1. Chequeo de Extremos Críticos (Prioridad Absoluta)
    if roll.total >= CRITICAL_SUCCESS_MIN:
        return ResultType.CRITICAL_SUCCESS
    
    if roll.total <= CRITICAL_FAILURE_MAX:
        return ResultType.CRITICAL_FAILURE

    # 2. Resolución por Margen (Regla 3.3)
    if margin > MARGIN_TOTAL_SUCCESS:      # > +25
        return ResultType.TOTAL_SUCCESS
    
    elif margin >= MARGIN_PARTIAL_SUCCESS: # 0 a +25
        return ResultType.PARTIAL_SUCCESS
        
    elif margin >= MARGIN_PARTIAL_FAILURE: # -25 a 0
        return ResultType.PARTIAL_FAILURE
        
    else:                                  # < -25
        return ResultType.TOTAL_FAILURE


def resolve_action(
    merit_points: int,
    difficulty: int,
    action_description: str = "",
    player_id: Optional[int] = None
) -> MRGResult:
    """
    Ejecuta una acción completa del MRG.
    Función pura: (Stats, Dif) -> Resultado.
    """
    # 1. Tirada física
    roll = roll_2d50()

    # 2. Cálculo de bonos (Asintótico)
    bonus = calculate_asymptotic_bonus(merit_points)

    # 3. Cálculo de Margen
    margin = (roll.total + bonus) - difficulty

    # 4. Determinación de Resultado
    result_type = determine_result_type(roll, margin)

    # 5. Auditoría (Logging)
    try:
        log_msg = (
            f"🎲 MRG [{action_description}]: "
            f"2d50({roll.total}) + Bono({bonus}) - Dif({difficulty}) "
            f"= Margen({margin}) >> {result_type.name} "
            f"(Puntos: {merit_points})"
        )
        
        log_event(
            message=log_msg,
            player_id=player_id,
            event_type="MRG_AUDIT"
        )
    except Exception as e:
        # Fallo en log no debe romper el flujo del juego
        print(f"⚠️ Error en auditoría MRG: {e}")

    return MRGResult(
        roll=roll,
        merit_points=merit_points,
        bonus_applied=bonus,
        difficulty=difficulty,
        margin=margin,
        result_type=result_type,
        action_description=action_description
    )