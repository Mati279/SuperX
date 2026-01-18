# core/rules.py
from typing import Dict
from .constants import (
    SKILL_MAPPING, 
    ATTRIBUTE_SOFT_CAP, 
    ATTRIBUTE_COST_MULTIPLIER,
    MIN_ATTRIBUTE_VALUE,
    MAX_ATTRIBUTE_VALUE
)

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
    
    REGLAS:
    - Rango 5 a 15: Costo 1 punto por nivel.
    - Rango 16 a 20: Costo 2 puntos por nivel (Soft Cap).
    - Máximo absoluto: 20.
    """
    # Validaciones de integridad
    if start_val < MIN_ATTRIBUTE_VALUE:
        # En teoría no debería pasar, pero asumimos costo desde el mínimo si está bugueado
        start_val = MIN_ATTRIBUTE_VALUE
        
    if target_val > MAX_ATTRIBUTE_VALUE:
        raise ValueError(f"El atributo no puede superar el máximo de {MAX_ATTRIBUTE_VALUE}")

    if target_val <= start_val:
        return 0

    cost = 0
    # Iteramos por cada punto que se quiere subir
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