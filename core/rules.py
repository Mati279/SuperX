# core/rules.py
from typing import Dict
from .constants import SKILL_MAPPING, ATTRIBUTE_SOFT_CAP, ATTRIBUTE_COST_MULTIPLIER

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    """
    Calcula las habilidades de un personaje basándose en sus atributos.

    Args:
        attributes: Un diccionario con los nombres de los atributos y sus valores.

    Returns:
        Un diccionario con los nombres de las habilidades y sus valores calculados.
    """
    skills = {}
    if not attributes:
        return {}
    
    # Aseguramos que las claves de atributos estén en minúsculas para coincidencias
    attrs_safe = {k.lower(): v for k, v in attributes.items()}
    
    for skill, (attr1, attr2) in SKILL_MAPPING.items():
        val1 = attrs_safe.get(attr1, 0)
        val2 = attrs_safe.get(attr2, 0)
        skills[skill] = val1 + val2
        
    return skills

def calculate_attribute_cost(start_val: int, target_val: int) -> int:
    """
    Calcula el costo total en puntos para aumentar un atributo desde un valor inicial a un valor final.
    
    REGLA: Subir un punto de atributo por encima de ATTRIBUTE_SOFT_CAP cuesta el doble.

    Args:
        start_val: El valor inicial del atributo.
        target_val: El valor final del atributo.

    Returns:
        El costo total en puntos.
    """
    if target_val <= start_val:
        return 0

    cost = 0
    # Iteramos por cada punto que se quiere subir para aplicar la regla de costo.
    for v in range(start_val + 1, target_val + 1):
        if v > ATTRIBUTE_SOFT_CAP:
            cost += ATTRIBUTE_COST_MULTIPLIER  # Cuesta el doble
        else:
            cost += 1
            
    return cost
