"""Aplicación de efectos de beneficios y malus del MRG."""
from typing import Optional, Dict, Any
from data.log_repository import log_event
from data.character_repository import update_character
from .mrg_engine import MRGResult, BenefitType, MalusType
from .mrg_constants import (
    BENEFIT_EFFICIENCY_REFUND,
    BENEFIT_PRESTIGE_GAIN,
    BENEFIT_IMPETUS_TICK_REDUCTION,
    MALUS_OPERATIVE_DOWN_TICKS,
    MALUS_DISCREDIT_LOSS,
    ENTITY_STATUS_INCAPACITATED,
    ENTITY_STATUS_EXPOSED
)


def apply_benefit(
    result: MRGResult,
    benefit: BenefitType,
    player_id: int,
    faction_id: Optional[int] = None,
    energy_spent: int = 0
) -> Dict[str, Any]:
    """
    Aplica el beneficio seleccionado por el jugador.

    Args:
        result: El resultado MRG que generó el beneficio
        benefit: El beneficio elegido
        player_id: ID del jugador
        faction_id: ID de la facción (para prestigio)
        energy_spent: Energía gastada en la acción (para eficiencia)

    Returns:
        Dict con detalles del efecto aplicado
    """
    effect_applied = {
        "benefit": benefit.value,
        "success": False,
        "details": {}
    }

    if benefit == BenefitType.EFFICIENCY:
        # Devolver 50% de energía
        refund = int(energy_spent * BENEFIT_EFFICIENCY_REFUND)
        # TODO: Llamar a player_repository para añadir energía
        # from data.player_repository import add_player_energy
        # add_player_energy(player_id, refund)
        effect_applied["success"] = True
        effect_applied["details"] = {"energy_refunded": refund}
        log_event(f"⚡ Eficiencia: {result.entity_name} recupera {refund} de energía.", player_id)

    elif benefit == BenefitType.PRESTIGE:
        # Añadir prestigio a la facción
        if faction_id:
            # TODO: Importar y llamar al sistema de prestigio
            # from data.faction_repository import add_faction_prestige
            # add_faction_prestige(faction_id, BENEFIT_PRESTIGE_GAIN)
            effect_applied["success"] = True
            effect_applied["details"] = {"prestige_gained": BENEFIT_PRESTIGE_GAIN}
            log_event(f"🌟 Prestigio: La facción gana +{BENEFIT_PRESTIGE_GAIN}% por la hazaña de {result.entity_name}.", player_id)

    elif benefit == BenefitType.IMPETUS:
        # Marcar entidad con bonus de velocidad para siguiente misión
        if result.entity_id:
            # Obtener el character actual para preservar otros campos
            from data.character_repository import get_character_by_id
            character = get_character_by_id(result.entity_id)
            if character:
                stats = character.get('stats_json', {})
                stats['impetu_bonus'] = BENEFIT_IMPETUS_TICK_REDUCTION
                update_character(result.entity_id, {"stats_json": stats})
                effect_applied["success"] = True
                effect_applied["details"] = {"tick_reduction": BENEFIT_IMPETUS_TICK_REDUCTION}
                log_event(f"🚀 Ímpetu: {result.entity_name} completará su siguiente misión {BENEFIT_IMPETUS_TICK_REDUCTION} tick(s) más rápido.", player_id)

    return effect_applied


def apply_malus(
    result: MRGResult,
    malus: MalusType,
    player_id: int,
    faction_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Aplica el malus seleccionado por el jugador.

    Args:
        result: El resultado MRG que generó el malus
        malus: El malus elegido
        player_id: ID del jugador
        faction_id: ID de la facción (para descrédito)

    Returns:
        Dict con detalles del efecto aplicado
    """
    effect_applied = {
        "malus": malus.value,
        "success": False,
        "details": {}
    }

    if malus == MalusType.OPERATIVE_DOWN:
        # Incapacitar entidad por 2 ticks
        if result.entity_id:
            from data.character_repository import get_character_by_id
            character = get_character_by_id(result.entity_id)
            if character:
                stats = character.get('stats_json', {})
                stats['estado'] = ENTITY_STATUS_INCAPACITATED
                stats['ticks_recuperacion'] = MALUS_OPERATIVE_DOWN_TICKS
                update_character(result.entity_id, {"stats_json": stats})
                effect_applied["success"] = True
                effect_applied["details"] = {"ticks_down": MALUS_OPERATIVE_DOWN_TICKS}
                log_event(f"🏥 Baja Operativa: {result.entity_name} queda fuera de servicio por {MALUS_OPERATIVE_DOWN_TICKS} ticks.", player_id)

    elif malus == MalusType.DISCREDIT:
        # Quitar prestigio a la facción
        if faction_id:
            # TODO: Importar y llamar al sistema de prestigio
            # from data.faction_repository import remove_faction_prestige
            # remove_faction_prestige(faction_id, MALUS_DISCREDIT_LOSS)
            effect_applied["success"] = True
            effect_applied["details"] = {"prestige_lost": MALUS_DISCREDIT_LOSS}
            log_event(f"📉 Descrédito: La facción pierde -{MALUS_DISCREDIT_LOSS}% de prestigio por el fracaso de {result.entity_name}.", player_id)

    elif malus == MalusType.EXPOSURE:
        # Marcar entidad como expuesta
        if result.entity_id:
            from data.character_repository import get_character_by_id
            character = get_character_by_id(result.entity_id)
            if character:
                stats = character.get('stats_json', {})
                stats['estado'] = ENTITY_STATUS_EXPOSED
                stats['ubicacion_expuesta'] = True
                update_character(result.entity_id, {"stats_json": stats})
                effect_applied["success"] = True
                effect_applied["details"] = {"exposed": True}
                log_event(f"👁️ Exposición: ¡La ubicación de {result.entity_name} ha sido revelada al enemigo!", player_id)

    return effect_applied


def apply_partial_success_complication(
    result: MRGResult,
    player_id: int
) -> Dict[str, Any]:
    """
    Aplica una complicación automática para éxitos parciales.
    El sistema elige aleatoriamente una complicación menor.
    """
    import random

    complications = [
        ("fatiga", "La entidad sufre fatiga leve. -1 a la siguiente tirada."),
        ("recurso_extra", "Se consumieron recursos adicionales inesperados."),
        ("tiempo_extra", "La acción tomó más tiempo del esperado. +1 tick de retraso."),
        ("atencion", "La acción atrajo atención no deseada."),
    ]

    complication, description = random.choice(complications)

    log_event(f"⚠️ Complicación: {result.entity_name} - {description}", player_id)

    # TODO: Aplicar efectos mecánicos según el tipo de complicación
    if complication == "fatiga" and result.entity_id:
        from data.character_repository import get_character_by_id
        character = get_character_by_id(result.entity_id)
        if character:
            stats = character.get('stats_json', {})
            stats['penalidad_temporal'] = -1
            update_character(result.entity_id, {"stats_json": stats})

    return {
        "complication": complication,
        "description": description
    }
