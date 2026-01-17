# core/rules.py
from typing import Dict
from .constants import SKILL_MAPPING, ATTRIBUTE_SOFT_CAP, ATTRIBUTE_COST_MULTIPLIER

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    """
    Calcula las habilidades de un personaje basándose en sus atributos.

    Implementa la fórmula MPA (Media Ponderada de Atributos):
    Habilidad = ((Atributo_Primario * 0.7) + (Atributo_Secundario * 0.3)) / 2

    Args:
        attributes: Un diccionario con los nombres de los atributos y sus valores.

    Returns:
        Un diccionario con los nombres de las habilidades y sus valores calculados.
    """
    # TODO: Implementar "+ Modificadores de Clase" de la fórmula original.
    # Actualmente la función no recibe la clase del personaje como parámetro.

    skills = {}
    if not attributes:
        return {}

    # Aseguramos que las claves de atributos estén en minúsculas para coincidencias
    attrs_safe = {k.lower(): v for k, v in attributes.items()}

    # Pesos para la Media Ponderada de Atributos (MPA)
    PRIMARY_WEIGHT = 0.7
    SECONDARY_WEIGHT = 0.3

    for skill, (primary_attr, secondary_attr) in SKILL_MAPPING.items():
        # Índice [0] = Atributo Primario, Índice [1] = Atributo Secundario
        primary_val = attrs_safe.get(primary_attr, 0)
        secondary_val = attrs_safe.get(secondary_attr, 0)

        # Fórmula MPA: ((A1 * 0.7) + (A2 * 0.3)) / 2
        weighted_avg = ((primary_val * PRIMARY_WEIGHT) + (secondary_val * SECONDARY_WEIGHT)) / 2
        skills[skill] = int(round(weighted_avg))

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
