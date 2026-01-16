# core/recruitment_logic.py
from typing import Dict, Any, Tuple
from config.app_constants import (
    DEFAULT_RECRUIT_RANK,
    DEFAULT_RECRUIT_STATUS,
    DEFAULT_RECRUIT_LOCATION
)

def can_recruit(player_credits: int, candidate_cost: int) -> Tuple[bool, str]:
    """
    Verifica si un jugador tiene suficientes créditos para reclutar a un candidato.

    Args:
        player_credits: Los créditos actuales del jugador.
        candidate_cost: El costo del candidato.

    Returns:
        Una tupla (bool, str) indicando si es posible y un mensaje.
    """
    if player_credits >= candidate_cost:
        return True, "Créditos suficientes."
    else:
        needed = candidate_cost - player_credits
        return False, f"Créditos insuficientes. Se necesitan {needed} más."

def process_recruitment(
    player_id: int, 
    player_credits: int, 
    candidate: Dict[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    """
    Prepara los datos para el reclutamiento.
    Calcula el nuevo total de créditos y prepara el diccionario del nuevo personaje.

    Args:
        player_id: ID del jugador que recluta.
        player_credits: Créditos actuales del jugador.
        candidate: El diccionario completo del candidato a reclutar.

    Returns:
        Una tupla con (nuevos_creditos_del_jugador, datos_del_nuevo_personaje_para_db).
    """
    # 1. Validar si es posible (aunque la UI ya debería haberlo hecho)
    can_afford, _ = can_recruit(player_credits, candidate['costo'])
    if not can_afford:
        raise ValueError("Intento de reclutar sin créditos suficientes.")

    # 2. Calcular el nuevo balance de créditos
    new_credits = player_credits - candidate['costo']
    
    # 3. Preparar el registro del nuevo personaje para la base de datos
    new_character_data = {
        "player_id": player_id,
        "nombre": candidate["nombre"],
        "rango": DEFAULT_RECRUIT_RANK,
        "es_comandante": False,
        "stats_json": candidate["stats_json"],
        "costo": candidate["costo"],
        "estado": DEFAULT_RECRUIT_STATUS,
        "ubicacion": DEFAULT_RECRUIT_LOCATION
    }

    return new_credits, new_character_data
