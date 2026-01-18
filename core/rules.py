# core/rules.py
from typing import Dict, Any, Tuple
from core.constants import SKILL_MAPPING, ATTRIBUTE_COST_MULTIPLIER
from core.models import KnowledgeLevel

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    """
    Calcula los valores de habilidades basados en los atributos base.
    Formula: (Attr1 + Attr2) * 2
    """
    skills = {}
    for skill_name, (attr1, attr2) in SKILL_MAPPING.items():
        val1 = attributes.get(attr1, 0)
        val2 = attributes.get(attr2, 0)
        # Formula base: Suma de atributos asociados * 2
        skills[skill_name] = (val1 + val2) * 2
    return skills

def calculate_attribute_cost(start_val: int, target_val: int) -> int:
    """
    Calcula el costo de XP para subir un atributo.
    Costo acumulativo triangular * multiplicador.
    """
    total_cost = 0
    for v in range(start_val, target_val):
        # El costo de subir DE v A v+1
        # Ejemplo: de 5 a 6 -> costo base basado en 6
        cost = v * ATTRIBUTE_COST_MULTIPLIER
        total_cost += cost
    return total_cost

def get_color_for_level(value: int) -> str:
    """Retorna un color hex para UI según el nivel de atributo/skill."""
    if value < 20: return "#888888" # Gris (Bajo)
    if value < 40: return "#ffffff" # Blanco (Normal)
    if value < 60: return "#56d59f" # Verde (Bueno)
    if value < 80: return "#5eb5f5" # Azul (Superior)
    if value < 100: return "#a06be0" # Púrpura (Élite)
    return "#f6c45b" # Dorado (Legendario)

# --- REGLAS DE CONOCIMIENTO (NUEVO) ---

KNOWLEDGE_THRESHOLDS_TICKS = {
    KnowledgeLevel.UNKNOWN: 0,
    KnowledgeLevel.KNOWN: 50,    # ~2 días reales (si 1 tick = 1 hora)
    KnowledgeLevel.FRIEND: 200   # ~1 semana real
}

def calculate_passive_knowledge_progress(
    ticks_in_service: int,
    current_level: KnowledgeLevel
) -> Tuple[KnowledgeLevel, float]:
    """
    Calcula si el personaje ha subido de nivel de conocimiento por mera convivencia (pasivo).
    Retorna (Nuevo Nivel, Progreso %)
    """
    # Si ya es Amigo, max out
    if current_level == KnowledgeLevel.FRIEND:
        return KnowledgeLevel.FRIEND, 100.0

    # Determinar siguiente hito
    next_level = KnowledgeLevel.KNOWN if current_level == KnowledgeLevel.UNKNOWN else KnowledgeLevel.FRIEND
    required_ticks = KNOWLEDGE_THRESHOLDS_TICKS[next_level]
    
    # Calcular progreso
    if ticks_in_service >= required_ticks:
        return next_level, 100.0
    
    # Progreso porcentual hacia el siguiente nivel
    prev_ticks = KNOWLEDGE_THRESHOLDS_TICKS[current_level]
    progress = ((ticks_in_service - prev_ticks) / (required_ticks - prev_ticks)) * 100
    return current_level, max(0.0, min(100.0, progress))