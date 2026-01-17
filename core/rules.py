# core/rules.py
from typing import Dict
from .constants import SKILL_MAPPING, ATTRIBUTE_SOFT_CAP, ATTRIBUTE_COST_MULTIPLIER

def calculate_skills(attributes: Dict[str, int]) -> Dict[str, int]:
    """
    Calcula las habilidades de un personaje basándose en sus atributos.

    Implementa la fórmula MPA (Media Ponderada de Atributos):
    Habilidad = ((Atributo_Primario * 0.7) + (Atributo_Secundario * 0.3))

    Nota: Se ha eliminado la división por 2 para que las skills compartan la 
    escala 5-20 de los atributos según el documento de diseño.
    """
    skills = {}
    if not attributes:
        return {}

    attrs_safe = {k.lower(): v for k, v in attributes.items()}

    # Pesos para la Media Ponderada de Atributos (MPA)
    PRIMARY_WEIGHT = 0.7
    SECONDARY_WEIGHT = 0.3

    for skill, (primary_attr, secondary_attr) in SKILL_MAPPING.items():
        primary_val = attrs_safe.get(primary_attr, 0)
        secondary_val = attrs_safe.get(secondary_attr, 0)

        # Fórmula MPA corregida: (A1 * 0.7) + (A2 * 0.3)
        weighted_avg = (primary_val * PRIMARY_WEIGHT) + (secondary_val * SECONDARY_WEIGHT)
        skills[skill] = int(round(weighted_avg))

    return skills

def calculate_attribute_cost(start_val: int, target_val: int) -> int:
    """
    Calcula el costo total en puntos para aumentar un atributo.
    REGLA: Subir un punto por encima del Soft Cap (15) cuesta el doble.
    """
    if target_val <= start_val:
        return 0

    cost = 0
    for v in range(start_val + 1, target_val + 1):
        if v > ATTRIBUTE_SOFT_CAP:
            cost += ATTRIBUTE_COST_MULTIPLIER
        else:
            cost += 1
            
    return cost

def get_color_for_level(value: int) -> str:
    """
    Retorna un código de color Hexagonal basado en la escala 5-20.
    - 5-8:  Rojo (Deficiente/Básico)
    - 9-12: Naranja/Amarillo (Estándar)
    - 13-16: Verde (Profesional)
    - 17-20: Cian (Élite/Maestro)
    """
    if value <= 8:
        return "#ff4b4b" # Rojo
    elif value <= 12:
        return "#f6c45b" # Ámbar
    elif value <= 16:
        return "#56d59f" # Verde
    else:
        return "#5bc0de" # Cian/Legendario