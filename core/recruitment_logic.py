# core/recruitment_logic.py
from typing import Dict, Any, Tuple, Optional
from config.app_constants import (
    DEFAULT_RECRUIT_RANK,
    DEFAULT_RECRUIT_STATUS,
    DEFAULT_RECRUIT_LOCATION
)
from core.models import KnowledgeLevel, CharacterStatus

def can_recruit(player_credits: int, candidate_cost: int) -> Tuple[bool, str]:
    """
    Verifica si un jugador tiene suficientes créditos para reclutar a un candidato.
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
    Prepara la ACTUALIZACIÓN del personaje para convertirlo de Candidato a Activo.
    
    Args:
        player_id: ID del jugador.
        player_credits: Créditos actuales.
        candidate: El diccionario del personaje (recuperado de characters DB).

    Returns:
        Tuple: (nuevos_creditos, update_data_para_db)
    """
    # 1. Validar fondos (UI debe pre-validar, pero por seguridad)
    # Nota: candidate["costo"] viene inyectado por el repositorio en el refactor
    costo = candidate.get("costo", 100)
    
    can_afford, _ = can_recruit(player_credits, costo)
    if not can_afford:
        raise ValueError("Intento de reclutar sin créditos suficientes.")

    # 2. Calcular balance
    new_credits = player_credits - costo
    
    # 3. Determinar conocimiento inicial (basado en si fue investigado)
    initial_knowledge = KnowledgeLevel.UNKNOWN
    outcome = candidate.get("investigation_outcome")
    if outcome and outcome in ["SUCCESS", "CRIT_SUCCESS"]:
        initial_knowledge = KnowledgeLevel.KNOWN

    # 4. Preparar payload de ACTUALIZACIÓN (no creación)
    # Limpiamos la metadata de reclutamiento del JSON para no ensuciar,
    # o la dejamos como histórico. Preferiblemente limpiar o marcar como reclutado.
    
    stats = candidate.get("stats_json", {}).copy()
    if "recruitment_data" in stats:
        # Opcional: Podríamos borrar stats["recruitment_data"] 
        # o dejarlo como log. Vamos a actualizar ticks_reclutado.
        pass
    
    # IMPORTANTE: La actualización del nivel de conocimiento se debe manejar
    # externamente (repo set_character_knowledge_level) ya que ahora es tabla relacional.
    # Aquí devolvemos los datos para actualizar la entidad Character.

    update_data = {
        "rango": DEFAULT_RECRUIT_RANK,
        "estado": DEFAULT_RECRUIT_STATUS, # "Disponible"
        "ubicacion": DEFAULT_RECRUIT_LOCATION,
        # Señal para el controller/repo de que debe actualizar el conocimiento también
        "initial_knowledge_level": initial_knowledge 
    }

    return new_credits, update_data