# core/rules.py
from typing import Dict, Any, Tuple, Optional
from core.constants import SKILL_MAPPING, ATTRIBUTE_COST_MULTIPLIER
from core.models import KnowledgeLevel

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    skills = {}
    for skill_name, (attr1, attr2) in SKILL_MAPPING.items():
        val1 = attributes.get(attr1, 0)
        val2 = attributes.get(attr2, 0)
        skills[skill_name] = (val1 + val2) * 2
    return skills

def calculate_attribute_cost(start_val: int, target_val: int) -> int:
    total_cost = 0
    for v in range(start_val, target_val):
        cost = v * ATTRIBUTE_COST_MULTIPLIER
        total_cost += cost
    return total_cost

def get_color_for_level(value: int) -> str:
    if value < 20: return "#888888"
    if value < 40: return "#ffffff"
    if value < 60: return "#56d59f"
    if value < 80: return "#5eb5f5"
    if value < 100: return "#a06be0"
    return "#f6c45b"

# --- REGLAS DE CONOCIMIENTO ---

# Umbral base para nivel FRIEND (ajustado por Presencia)
KNOWLEDGE_THRESHOLD_FRIEND_BASE = 50  # 50 ticks base siendo KNOWN


def calculate_ticks_required_for_known(presence_value: int) -> int:
    """
    Calcula los ticks necesarios para alcanzar el nivel KNOWN desde UNKNOWN.
    Regla: 20 ticks + (10 - Presencia)
    - Si Presencia > 10, reduce el tiempo (personajes carismáticos se abren antes).
    - Si Presencia < 10, aumenta el tiempo (personajes reservados tardan más).
    """
    base_ticks = 20
    modifier = 10 - presence_value
    return max(1, base_ticks + modifier)


def calculate_ticks_required_for_friend(presence_value: int) -> int:
    """
    Calcula los ticks TOTALES necesarios para alcanzar FRIEND desde reclutamiento.
    Incluye los ticks de UNKNOWN->KNOWN más los ticks de KNOWN->FRIEND.

    Regla: (ticks para KNOWN) + 50 + (10 - Presencia)
    """
    ticks_for_known = calculate_ticks_required_for_known(presence_value)
    friend_base = KNOWLEDGE_THRESHOLD_FRIEND_BASE
    modifier = 10 - presence_value
    ticks_for_friend_phase = max(1, friend_base + modifier)
    return ticks_for_known + ticks_for_friend_phase


def calculate_passive_knowledge_progress(
    ticks_in_service: int,
    current_level: KnowledgeLevel,
    character_attributes: Dict[str, int]
) -> Tuple[KnowledgeLevel, float]:
    """
    Calcula el progreso de conocimiento pasivo.
    Requiere los atributos del personaje para aplicar la fórmula de Presencia.

    Returns:
        Tuple de (nuevo_nivel, porcentaje_progreso)
    """
    # Si ya es Amigo, ya completó todo
    if current_level == KnowledgeLevel.FRIEND:
        return KnowledgeLevel.FRIEND, 100.0

    presence = character_attributes.get("presencia", 10)

    if current_level == KnowledgeLevel.UNKNOWN:
        # Progreso hacia KNOWN
        required_ticks = calculate_ticks_required_for_known(presence)

        if ticks_in_service >= required_ticks:
            return KnowledgeLevel.KNOWN, 100.0

        # Calcular porcentaje de progreso
        progress = (ticks_in_service / required_ticks) * 100 if required_ticks > 0 else 0
        return KnowledgeLevel.UNKNOWN, max(0.0, min(100.0, progress))

    else:
        # current_level == KNOWN, progreso hacia FRIEND
        ticks_for_known = calculate_ticks_required_for_known(presence)
        total_required = calculate_ticks_required_for_friend(presence)

        if ticks_in_service >= total_required:
            return KnowledgeLevel.FRIEND, 100.0

        # Calcular porcentaje de progreso en la fase KNOWN->FRIEND
        ticks_in_friend_phase = ticks_in_service - ticks_for_known
        friend_phase_duration = total_required - ticks_for_known

        if friend_phase_duration <= 0:
            friend_phase_duration = 1

        progress = (ticks_in_friend_phase / friend_phase_duration) * 100 if ticks_in_friend_phase > 0 else 0
        return KnowledgeLevel.KNOWN, max(0.0, min(100.0, progress))


# --- REGLAS DE CONTROL GALÁCTICO (V4.3.0) ---

def calculate_system_control(system_id: int):
    """
    Determina qué facción controla el sistema basándose en la mayoría de planetas (>50%).
    Actualiza la tabla 'systems' mediante el world_repository.
    """
    # Importaciones locales para evitar ciclos de importación circular
    from data.world_repository import get_planets_by_system_id, update_system_controller
    from data.player_repository import get_player_by_id

    planets = get_planets_by_system_id(system_id)
    if not planets:
        return

    total_planets = len(planets)
    faction_counts = {}

    for planet in planets:
        # Se asume que el control del sistema depende de quién domina la superficie
        owner_id = planet.get("surface_owner_id")
        if owner_id:
            player = get_player_by_id(owner_id)
            if player and player.get("faction_id"):
                f_id = player["faction_id"]
                faction_counts[f_id] = faction_counts.get(f_id, 0) + 1

    # Determinar si alguna facción tiene mayoría absoluta (> 50%)
    new_controller_id = None
    for f_id, count in faction_counts.items():
        if count > (total_planets / 2):
            new_controller_id = f_id
            break
    
    # Impactar el cambio en la base de datos
    update_system_controller(system_id, new_controller_id)