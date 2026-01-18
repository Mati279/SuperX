# core/rules.py
from typing import Dict, Any, Tuple
from core.constants import SKILL_MAPPING, ATTRIBUTE_COST_MULTIPLIER
from core.models import KnowledgeLevel

# ... (Mantener funciones calculate_skills, calculate_attribute_cost, get_color_for_level) ...
# ... Asegúrate de que el archivo conserve su contenido original ...

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

# --- REGLAS DE CONOCIMIENTO (MODIFICADO) ---

# Umbral fijo solo para nivel AMIGO (o lo que definas a futuro)
KNOWLEDGE_THRESHOLDS_FIXED = {
    KnowledgeLevel.FRIEND: 100   # ~1 semana real (ejemplo)
}

def calculate_ticks_required_for_known(presence_value: int) -> int:
    """
    Calcula los ticks necesarios para alcanzar el nivel KNOWN.
    Regla: 20 ticks + (10 - Presencia)
    - Si Presencia > 10, reduce el tiempo.
    - Si Presencia < 10, aumenta el tiempo.
    """
    base_ticks = 20
    modifier = 10 - presence_value
    # Aseguramos un mínimo de 1 tick para evitar lógica negativa o instantánea absurda
    return max(1, base_ticks + modifier)

def calculate_passive_knowledge_progress(
    ticks_in_service: int,
    current_level: KnowledgeLevel,
    character_attributes: Dict[str, int]
) -> Tuple[KnowledgeLevel, float]:
    """
    Calcula el progreso de conocimiento pasivo.
    Requiere los atributos del personaje para aplicar la fórmula de Presencia.
    """
    # Si ya es Amigo, max out
    if current_level == KnowledgeLevel.FRIEND:
        return KnowledgeLevel.FRIEND, 100.0

    # 1. Determinar meta y ticks requeridos
    if current_level == KnowledgeLevel.UNKNOWN:
        # Fórmula Dinámica para llegar a KNOWN
        presence = character_attributes.get("presencia", 5) # Default 5 (media baja) si no hay dato
        required_ticks = calculate_ticks_required_for_known(presence)
        target_level = KnowledgeLevel.KNOWN
        prev_ticks_milestone = 0
    else:
        # Fórmula Fija para llegar a FRIEND (de momento)
        required_ticks = KNOWLEDGE_THRESHOLDS_FIXED[KnowledgeLevel.FRIEND]
        target_level = KnowledgeLevel.FRIEND
        # Para calcular % de KNOWN a FRIEND, necesitamos saber cuándo empezó KNOWN
        # Como es complejo rastrear el tick exacto del cambio anterior sin más columnas,
        # simplificamos usando el requisito de KNOWN como piso.
        presence = character_attributes.get("presencia", 5)
        prev_ticks_milestone = calculate_ticks_required_for_known(presence)

    # 2. Verificar cumplimiento
    if ticks_in_service >= required_ticks:
        return target_level, 100.0
    
    # 3. Calcular Porcentaje de Progreso
    # Evitar división por cero
    denom = required_ticks - prev_ticks_milestone
    if denom <= 0: denom = 1
    
    current_progress_ticks = ticks_in_service - prev_ticks_milestone
    progress = (current_progress_ticks / denom) * 100
    
    return current_level, max(0.0, min(100.0, progress))