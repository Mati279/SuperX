# core/generator.py
import random
from typing import Dict, Any, List
from core.constants import RACES, CLASSES

def generate_random_candidate(existing_names: List[str]) -> Dict[str, Any]:
    """
    Genera un único candidato para reclutamiento de forma procedural.
    No utiliza IA para velocidad y ahorro de costos.

    Args:
        existing_names: Una lista de nombres ya en uso para evitar duplicados.

    Returns:
        Un diccionario representando al candidato con sus stats y costo.
    """
    
    # 1. Seleccionar Raza y Clase aleatoriamente
    race_name, race_data = random.choice(list(RACES.items()))
    class_name, class_data = random.choice(list(CLASSES.items()))
    
    # 2. Generar un nombre único simple (para evitar colisiones)
    # En un juego real, aquí usaríamos una lista de nombres y apellidos.
    # Por simplicidad, usamos un patrón "Raza-Clase-Numero".
    while True:
        suffix = random.randint(100, 999)
        name = f"{race_name}-{class_name}-{suffix}"
        if name not in existing_names:
            break

    # 3. Generar Atributos base y aplicar bonus racial
    attributes = {
        "fuerza": random.randint(1, 5),
        "agilidad": random.randint(1, 5),
        "intelecto": random.randint(1, 5),
        "tecnica": random.randint(1, 5),
        "presencia": random.randint(1, 5),
        "voluntad": random.randint(1, 5),
    }
    
    for attr, bonus in race_data.get("bonus", {}).items():
        attributes[attr] += bonus

    # 4. Calcular el Nivel y el Costo del candidato
    # El nivel es la suma de sus atributos base.
    level = sum(attributes.values())
    
    # El costo se basa en el nivel, con un factor aleatorio para variabilidad.
    base_cost = level * 25
    cost_multiplier = random.uniform(0.8, 1.2)
    cost = int(base_cost * cost_multiplier)

    # 5. Ensamblar el diccionario del candidato
    candidate = {
        "nombre": name,
        "nivel": level,
        "raza": race_name,
        "clase": class_name,
        "costo": cost,
        "stats_json": {
            "bio": {
                "raza": race_name,
                "clase": class_name,
                "descripcion_raza": race_data["desc"],
                "descripcion_clase": class_data["desc"]
            },
            "atributos": attributes
        }
    }
    
    return candidate

def generate_candidate_pool(pool_size: int = 3, existing_names: List[str] = []) -> List[Dict[str, Any]]:
    """
    Crea una lista de candidatos aleatorios para el centro de reclutamiento.

    Args:
        pool_size: El número de candidatos a generar.
        existing_names: Nombres existentes para evitar duplicados.

    Returns:
        Una lista de diccionarios de candidatos.
    """
    candidates = []
    current_names = list(existing_names)
    for _ in range(pool_size):
        candidate = generate_random_candidate(current_names)
        candidates.append(candidate)
        current_names.append(candidate["nombre"])
        
    return candidates
