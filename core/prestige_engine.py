# core/prestige_engine.py
"""
Motor de cálculo de prestigio y hegemonía.

Este módulo implementa todas las mecánicas del sistema de prestigio:
- Cálculo de IDP (Índice de Disparidad de Poder)
- Transferencias PVP con anti-bullying
- Fricción galáctica (redistribución automática)
- Recompensas PvE (Suma cero)
- Verificación de condiciones de hegemonía
- Validación de suma cero
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from .prestige_constants import *


class FactionState(Enum):
    """Estados de poder de una facción."""
    HEGEMONIC = STATE_NAME_HEGEMONIC
    NORMAL = STATE_NAME_NORMAL
    IRRELEVANT = STATE_NAME_IRRELEVANT
    COLLAPSED = STATE_NAME_COLLAPSED


@dataclass
class PrestigeTransfer:
    """Registro de una transferencia de prestigio PVP."""
    attacker_id: int
    defender_id: int
    base_amount: float
    idp_multiplier: float
    final_amount: float
    reason: str


# ============================================================
# CÁLCULOS DE IDP Y TRANSFERENCIAS
# ============================================================

def calculate_idp(attacker_prestige: float, defender_prestige: float) -> float:
    """
    Calcula el Índice de Disparidad de Poder.

    Fórmula: IDP = max(0, 1 + (P_Victima - P_Atacante) / 20)

    Esta fórmula implementa el sistema de riesgo asimétrico:
    - Atacar "hacia arriba" (a alguien más fuerte) = mayor ganancia
    - Atacar "hacia abajo" (a alguien más débil) = menor ganancia o cero (anti-bullying)

    Args:
        attacker_prestige: Prestigio del atacante (0-100)
        defender_prestige: Prestigio del defensor (0-100)

    Returns:
        float: Multiplicador IDP (0.0 o mayor). 0 significa no hay transferencia (anti-bullying).

    Examples:
        >>> calculate_idp(10, 25)  # Atacante débil vs fuerte
        1.75
        >>> calculate_idp(40, 5)   # Atacante fuerte vs débil (bullying)
        0.0
    """
    raw_idp = 1.0 + (defender_prestige - attacker_prestige) / IDP_DIVISOR
    return max(IDP_MINIMUM, raw_idp)


def calculate_transfer(
    base_event: float,
    attacker_prestige: float,
    defender_prestige: float
) -> Tuple[float, float]:
    """
    Calcula la transferencia de prestigio en un conflicto PVP.

    Args:
        base_event: Valor base del evento (ej: 1.0 para victoria menor, 3.0 para mayor)
        attacker_prestige: Prestigio del atacante
        defender_prestige: Prestigio del defensor

    Returns:
        Tuple de (cantidad_final, idp_usado)

    Examples:
        >>> calculate_transfer(1.0, 15, 25)
        (1.5, 1.5)  # IDP = 1.5, transferencia = 1.5%
    """
    idp = calculate_idp(attacker_prestige, defender_prestige)
    transfer = base_event * idp
    return (transfer, idp)


# ============================================================
# CÁLCULOS PVE (SUMA CERO)
# ============================================================

def calculate_pve_reward(
    target_faction_id: int,
    reward_amount: float,
    current_factions: Dict[int, float]
) -> Dict[int, float]:
    """
    Calcula la redistribución de prestigio por un hito PvE.

    Mecánica Suma Cero:
    1. La facción objetivo gana `reward_amount`.
    2. El resto de facciones (N-1) pagan equitativamente ese monto.
    3. Se aplica la normalización para asegurar 100% total y floor en 0.

    Args:
        target_faction_id: ID de la facción que logró el hito.
        reward_amount: Cantidad de prestigio a ganar (ej: 0.2, 0.5, 1.0).
        current_factions: Dict {faction_id: prestigio_actual}.

    Returns:
        Dict {faction_id: nuevo_prestigio} con el estado final calculado y normalizado.
    """
    adjustments: Dict[int, float] = {}
    
    # Identificar a los "pagadores" (todos menos el objetivo)
    others = [fid for fid in current_factions if fid != target_faction_id]
    
    if not others:
        # Caso borde: Solo existe una facción, no hay cambio relativo posible
        return current_factions.copy()

    # 1. Ganancia del objetivo
    adjustments[target_faction_id] = reward_amount

    # 2. Pérdida distribuida (Suma cero inicial)
    # Si reward es 1.0 y hay 4 otros, cada uno pierde 0.25
    loss_per_faction = reward_amount / len(others)
    
    for other_id in others:
        adjustments[other_id] = -loss_per_faction

    # 3. Aplicar cambios con seguridad (Floor 0 y Normalización 100%)
    return apply_prestige_changes(current_factions, adjustments)


# ============================================================
# DETERMINACIÓN DE ESTADOS
# ============================================================

def determine_faction_state(prestige: float, is_hegemon: bool = False) -> FactionState:
    """
    Determina el estado de poder de una facción según su prestigio.

    Args:
        prestige: Prestigio actual de la facción (0-100)
        is_hegemon: Si la facción es actualmente hegemón

    Returns:
        FactionState: El estado correspondiente

    Jerarquía de estados:
    - HEGEMONIC: ≥25% o es hegemón actual
    - COLLAPSED: <2%
    - IRRELEVANT: <5%
    - NORMAL: 5-25%
    """
    if prestige >= HEGEMONY_THRESHOLD or is_hegemon:
        return FactionState.HEGEMONIC
    elif prestige < COLLAPSE_THRESHOLD:
        return FactionState.COLLAPSED
    elif prestige < IRRELEVANCE_THRESHOLD:
        return FactionState.IRRELEVANT
    else:
        return FactionState.NORMAL


def check_hegemony_ascension(prestige: float, current_state: FactionState) -> bool:
    """
    Verifica si una facción debe ascender a Hegemón.

    Args:
        prestige: Prestigio actual
        current_state: Estado actual de la facción

    Returns:
        bool: True si debe ascender a Hegemón
    """
    return prestige >= HEGEMONY_THRESHOLD and current_state != FactionState.HEGEMONIC


def check_hegemony_fall(prestige: float, current_state: FactionState) -> bool:
    """
    Verifica si un Hegemón debe caer.

    Regla de Amortiguación (Buffer 25/20):
    - Ascenso: >25%
    - Caída: <20%
    - Buffer: Entre 20-25% el hegemón mantiene estatus

    Esto previene que maniobras tácticas pequeñas causen ping-pong de hegemonía.

    Args:
        prestige: Prestigio actual
        current_state: Estado actual de la facción

    Returns:
        bool: True si debe perder el estatus de Hegemón
    """
    return current_state == FactionState.HEGEMONIC and prestige < HEGEMONY_FALL_THRESHOLD


# ============================================================
# FRICCIÓN GALÁCTICA (REDISTRIBUCIÓN AUTOMÁTICA)
# ============================================================

def calculate_friction(factions: Dict[int, float]) -> Dict[int, float]:
    """
    Calcula la fricción galáctica (redistribución automática por tick).

    Mecánicas:
    1. Impuesto Imperial: Facciones >20% pierden 0.5% por tick
    2. Subsidio de Supervivencia: El monto drenado se redistribuye equitativamente
       entre facciones <5%

    Esto implementa "rubber banding" para:
    - Prevenir snowball descontrolado
    - Dar oportunidades de recuperación
    - Mantener el juego dinámico

    Args:
        factions: Dict de {faction_id: prestigio_actual}

    Returns:
        Dict de {faction_id: ajuste}
        - Positivo = gana prestigio (subsidio)
        - Negativo = pierde prestigio (fricción)

    Examples:
        >>> calculate_friction({1: 30.0, 2: 25.0, 3: 3.0})
        {1: -0.5, 2: -0.5, 3: 1.0}  # Dos pagan, uno recibe
    """
    adjustments = {fid: 0.0 for fid in factions}
    total_drained = 0.0

    # Fase 1: Drenar de facciones poderosas (Impuesto Imperial)
    for fid, prestige in factions.items():
        if prestige > FRICTION_THRESHOLD:
            drain = FRICTION_RATE
            adjustments[fid] = -drain
            total_drained += drain

    # Fase 2: Identificar receptores (facciones en problemas)
    receivers = [fid for fid, p in factions.items() if p < SUBSIDY_THRESHOLD]

    # Fase 3: Distribuir equitativamente (Subsidio de Supervivencia)
    if receivers and total_drained > 0:
        subsidy_per_faction = total_drained / len(receivers)
        for fid in receivers:
            adjustments[fid] += subsidy_per_faction

    return adjustments


# ============================================================
# APLICACIÓN DE CAMBIOS Y NORMALIZACIÓN
# ============================================================

def apply_prestige_changes(
    factions: Dict[int, float],
    adjustments: Dict[int, float]
) -> Dict[int, float]:
    """
    Aplica cambios de prestigio manteniendo la suma = 100 (suma cero estricta).

    Proceso:
    1. Aplica todos los ajustes
    2. Previene prestigio negativo (floor a 0)
    3. Normaliza para mantener suma total = 100

    Args:
        factions: Estado actual {faction_id: prestigio}
        adjustments: Cambios a aplicar {faction_id: delta}

    Returns:
        Nuevo estado {faction_id: nuevo_prestigio}

    Note:
        La normalización garantiza que incluso con errores de redondeo,
        la suma siempre sea exactamente 100%.
    """
    new_prestiges = {}

    # Paso 1: Aplicar ajustes con floor a 0
    for fid, current in factions.items():
        new_prestiges[fid] = max(0.0, current + adjustments.get(fid, 0.0))

    # Paso 2: Normalizar para mantener suma = 100
    total = sum(new_prestiges.values())
    if total > 0:
        factor = PRESTIGE_TOTAL / total
        new_prestiges = {fid: p * factor for fid, p in new_prestiges.items()}
    else:
        # Caso extremo: todo en 0, redistribuir equitativamente
        equal_share = PRESTIGE_TOTAL / len(new_prestiges)
        new_prestiges = {fid: equal_share for fid in new_prestiges}

    return new_prestiges


# ============================================================
# VALIDACIÓN
# ============================================================

def validate_zero_sum(factions: Dict[int, float], tolerance: float = PRESTIGE_SUM_TOLERANCE) -> bool:
    """
    Valida que el prestigio total sea exactamente 100 (con tolerancia mínima).

    Args:
        factions: Estado actual {faction_id: prestigio}
        tolerance: Tolerancia permitida (default: 0.01%)

    Returns:
        bool: True si la suma está dentro de tolerancia

    Examples:
        >>> validate_zero_sum({1: 33.33, 2: 33.33, 3: 33.34})
        True
        >>> validate_zero_sum({1: 50.0, 2: 48.0})
        False
    """
    total = sum(factions.values())
    return abs(total - PRESTIGE_TOTAL) < tolerance


# ============================================================
# UTILIDADES
# ============================================================

def get_top_faction(factions: Dict[int, float]) -> Tuple[int, float]:
    """
    Obtiene la facción con mayor prestigio.

    Args:
        factions: Dict de {faction_id: prestigio}

    Returns:
        Tuple de (faction_id, prestigio) de la facción líder
    """
    if not factions:
        return (0, 0.0)
    return max(factions.items(), key=lambda x: x[1])


def calculate_prestige_difference(faction_a: float, faction_b: float) -> float:
    """
    Calcula la diferencia de prestigio entre dos facciones.

    Args:
        faction_a: Prestigio de facción A
        faction_b: Prestigio de facción B

    Returns:
        float: Diferencia (positivo si A > B)
    """
    return faction_a - faction_b


def is_near_hegemony(prestige: float, threshold_distance: float = 3.0) -> bool:
    """
    Verifica si una facción está cerca del umbral de hegemonía.

    Args:
        prestige: Prestigio actual
        threshold_distance: Distancia al umbral (default: 3%)

    Returns:
        bool: True si está a menos de threshold_distance del 25%
    """
    return abs(prestige - HEGEMONY_THRESHOLD) < threshold_distance