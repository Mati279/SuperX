# core/mrg_effects.py
import random
from typing import Dict, Any

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
from data.player_repository import get_player_finances, update_player_credits

def apply_benefit(
    benefit: BenefitType, 
    player_id: int, 
    character_id: int,
    mission_energy_cost: int = 0
) -> str:
    """Aplica un beneficio seleccionado por éxito total/crítico."""
    narrative = ""
    
    if benefit == BenefitType.EFFICIENCY:
        refund = int(mission_energy_cost * BENEFIT_EFFICIENCY_REFUND)
        # Aquí idealmente devolveríamos energía, pero por simplicidad damos créditos
        # o asumimos que la energía se maneja en otro lado. 
        # Para el MVP, damos un bono pequeño de créditos representando 'recursos salvados'
        finances = get_player_finances(player_id)
        current_credits = finances.get("creditos", 0)
        bonus_credits = 100 # Valor simbólico si no hay coste de energía traqueado
        update_player_credits(player_id, current_credits + bonus_credits)
        narrative = f"Recursos optimizados. Se recuperan {bonus_credits} CI equivalentes en energía."

    elif benefit == BenefitType.PRESTIGE:
        # TODO: Llamar al servicio de prestigio real
        narrative = f"La facción gana reconocimiento público (+{BENEFIT_PRESTIGE_GAIN*100}% Prestigio)."

    elif benefit == BenefitType.IMPETUS:
        # TODO: Reducir cooldown real del personaje
        narrative = "El operativo termina fresco y listo para la acción inmediata (-1 Tick cooldown)."

    return narrative

def apply_malus(
    malus: MalusType,
    player_id: int,
    character_id: int
) -> str:
    """Aplica un malus seleccionado por fracaso total/pifia."""
    narrative = ""

    if malus == MalusType.OPERATIVE_DOWN:
        update_character(character_id, {"estado": ENTITY_STATUS_INCAPACITATED})
        narrative = f"El operativo ha resultado herido y requiere {MALUS_OPERATIVE_DOWN_TICKS} Ticks de recuperación."

    elif malus == MalusType.DISCREDIT:
        # TODO: Llamar al servicio de prestigio real
        narrative = f"El fracaso se hace público. La reputación cae (-{MALUS_DISCREDIT_LOSS*100}% Prestigio)."

    elif malus == MalusType.EXPOSURE:
        # TODO: Marcar flag de exposición en la facción
        narrative = "La seguridad operacional se ha roto. El enemigo conoce nuestra posición."

    return narrative

def apply_partial_success_complication(result: MRGResult, player_id: int) -> None:
    """
    Genera y aplica una complicación menor automática para Éxitos Parciales.
    No cambia el resultado de éxito, pero añade sabor o costos menores.
    """
    complications = [
        "Desgaste de equipo menor (-10 Materiales)",
        "Fatiga leve del personal",
        "Retraso administrativo en el reporte",
        "Ruido en los sensores durante la operación"
    ]
    comp = random.choice(complications)
    log_event(f"⚠️ Complicación: {comp}", player_id)