# core/character_engine.py
"""
Motor de Personajes - Lógica pura de generación, progresión y level up.
Basado en el Protocolo de Génesis v1.5 (Módulo 19 de las reglas).

NO toca DB ni UI - Solo cálculos y transformaciones de datos.
"""

import random
from typing import Dict, Any, List, Tuple, Optional
from core.constants import RACES, CLASSES, SKILL_MAPPING
from core.rules import calculate_skills

# =============================================================================
# CONSTANTES DE PROGRESIÓN (Basadas en Módulo 19)
# =============================================================================

# Tabla de XP por nivel (Nivel 6 = 3265 XP según reglas)
# Fórmula aproximada: XP = (Nivel * (Nivel - 1) * 500) + 500
XP_TABLE = {
    1: 0,
    2: 500,
    3: 1500,
    4: 3000,
    5: 5000,
    6: 7500,
    7: 10500,
    8: 14000,
    9: 18000,
    10: 22500,
    11: 27500,
    12: 33000,
    13: 39000,
    14: 45500,
    15: 52500,
    16: 60000,
    17: 68000,
    18: 76500,
    19: 85500,
    20: 95000,  # Nivel máximo
}

# Bonificaciones por nivel (Módulo 19.2)
SKILL_POINTS_PER_LEVEL = 4          # 24 puntos a nivel 6 = 4 por nivel
ATTRIBUTE_POINT_LEVELS = [5, 10, 15, 20]  # Niveles que otorgan +1 atributo
FEAT_LEVELS = [1, 5, 10, 15, 20]    # Niveles que otorgan un Feat

# Constantes de generación
BASE_ATTRIBUTE_MIN = 8
BASE_ATTRIBUTE_MAX = 12
ATTRIBUTE_POOL_LEVEL_1 = 60         # Pool de puntos inicial
MAX_ATTRIBUTE_VALUE = 20
MIN_ATTRIBUTE_VALUE = 3

# Rasgos/Feats disponibles
AVAILABLE_FEATS = [
    "Liderazgo Táctico",
    "Logística Avanzada",
    "Experto en Combate",
    "Piloto As",
    "Genio Técnico",
    "Diplomático Nato",
    "Infiltrador",
    "Médico de Campo",
    "Hacker Élite",
    "Resistencia Sobrehumana",
    "Reflejos Mejorados",
    "Mente Analítica",
    "Carisma Magnético",
    "Voluntad de Hierro",
    "Especialista en Armas"
]


# =============================================================================
# FUNCIONES DE GENERACIÓN DE PERSONAJES
# =============================================================================

def generate_random_character(
    min_level: int = 1,
    max_level: int = 1,
    existing_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Genera un personaje completo con stats aleatorios siguiendo las reglas del juego.

    Args:
        min_level: Nivel mínimo del personaje generado.
        max_level: Nivel máximo del personaje generado.
        existing_names: Lista de nombres a evitar para duplicados.

    Returns:
        Diccionario completo del personaje listo para insertar en DB.
    """
    existing_names = existing_names or []

    # 1. Determinar nivel
    level = random.randint(min_level, max_level)
    xp = get_xp_for_level(level)

    # 2. Seleccionar raza y clase
    race_name, race_data = random.choice(list(RACES.items()))
    class_name, class_data = random.choice(list(CLASSES.items()))

    # 3. Generar nombre único
    name = _generate_unique_name(race_name, class_name, existing_names)

    # 4. Generar atributos base
    attributes = _generate_base_attributes()

    # 5. Aplicar bonus racial
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in attributes:
            attributes[attr] = min(attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)

    # 6. Aplicar bonus de clase
    bonus_attr = class_data.get("bonus_attr", "")
    if bonus_attr in attributes:
        attributes[bonus_attr] = min(attributes[bonus_attr] + 1, MAX_ATTRIBUTE_VALUE)

    # 7. Aplicar puntos extra por nivel
    extra_attr_points = sum(1 for lvl in ATTRIBUTE_POINT_LEVELS if lvl <= level)
    _distribute_random_points(attributes, extra_attr_points)

    # 8. Calcular habilidades
    skills = calculate_skills(attributes)

    # 9. Distribuir puntos de habilidad por nivel
    skill_points = level * SKILL_POINTS_PER_LEVEL
    skills = _boost_skills(skills, skill_points)

    # 10. Asignar feats por nivel
    num_feats = sum(1 for lvl in FEAT_LEVELS if lvl <= level)
    feats = random.sample(AVAILABLE_FEATS, min(num_feats, len(AVAILABLE_FEATS)))

    # 11. Ensamblar el personaje
    character = {
        "nombre": name,
        "nivel": level,
        "xp": xp,
        "raza": race_name,
        "clase": class_name,
        "stats_json": {
            "nivel": level,
            "xp": xp,
            "bio": {
                "raza": race_name,
                "clase": class_name,
                "descripcion_raza": race_data["desc"],
                "descripcion_clase": class_data["desc"]
            },
            "atributos": attributes,
            "habilidades": skills,
            "feats": feats
        }
    }

    return character


def _generate_unique_name(race: str, char_class: str, existing: List[str]) -> str:
    """Genera un nombre único para el personaje."""
    prefixes = ["Kira", "Zane", "Nova", "Rex", "Luna", "Orion", "Vega", "Atlas",
                "Cyrus", "Maya", "Echo", "Axel", "Jade", "Nero", "Lyra", "Cade",
                "Ivy", "Dax", "Aria", "Koda", "Zara", "Finn", "Nyx", "Cole"]
    suffixes = ["-7", "-X", "-9", "-V", "-3", "-K", "-Prime", "-Alpha", "-Zero"]

    for _ in range(100):  # Máximo 100 intentos
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes) if random.random() > 0.5 else f"-{random.randint(1, 999)}"
        name = f"{prefix}{suffix}"
        if name not in existing:
            return name

    # Fallback con timestamp
    return f"{race}-{char_class}-{random.randint(10000, 99999)}"


def _generate_base_attributes() -> Dict[str, int]:
    """Genera atributos base aleatorios."""
    return {
        "fuerza": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "agilidad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "intelecto": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "tecnica": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "presencia": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "voluntad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
    }


def _distribute_random_points(attributes: Dict[str, int], points: int) -> None:
    """Distribuye puntos aleatorios entre los atributos (in-place)."""
    attr_keys = list(attributes.keys())
    for _ in range(points):
        attr = random.choice(attr_keys)
        if attributes[attr] < MAX_ATTRIBUTE_VALUE:
            attributes[attr] += 1


def _boost_skills(skills: Dict[str, int], points: int) -> Dict[str, int]:
    """Distribuye puntos de habilidad adicionales."""
    skill_keys = list(skills.keys())
    boosted = skills.copy()

    for _ in range(points):
        skill = random.choice(skill_keys)
        boosted[skill] += 1

    return boosted


# =============================================================================
# FUNCIONES DE PROGRESIÓN Y LEVEL UP
# =============================================================================

def get_xp_for_level(level: int) -> int:
    """Obtiene el XP necesario para alcanzar un nivel específico."""
    return XP_TABLE.get(level, XP_TABLE[20])


def get_level_from_xp(xp: int) -> int:
    """Calcula el nivel actual basado en el XP total."""
    current_level = 1
    for level, required_xp in sorted(XP_TABLE.items()):
        if xp >= required_xp:
            current_level = level
        else:
            break
    return current_level


def calculate_level_progress(current_xp: int) -> Dict[str, Any]:
    """
    Calcula el progreso hacia el siguiente nivel.

    Args:
        current_xp: XP actual del personaje.

    Returns:
        Diccionario con información de progreso:
        - current_level: Nivel actual
        - next_level: Siguiente nivel
        - xp_current: XP para el nivel actual
        - xp_next: XP necesario para el siguiente nivel
        - xp_progress: XP acumulado hacia el siguiente nivel
        - xp_needed: XP faltante para subir
        - progress_percent: Porcentaje de progreso (0-100)
        - can_level_up: Si puede subir de nivel ahora
    """
    current_level = get_level_from_xp(current_xp)

    # Nivel máximo
    if current_level >= 20:
        return {
            "current_level": 20,
            "next_level": 20,
            "xp_current": XP_TABLE[20],
            "xp_next": XP_TABLE[20],
            "xp_progress": 0,
            "xp_needed": 0,
            "progress_percent": 100,
            "can_level_up": False
        }

    xp_current_level = XP_TABLE[current_level]
    xp_next_level = XP_TABLE[current_level + 1]
    xp_for_next = xp_next_level - xp_current_level
    xp_progress = current_xp - xp_current_level
    xp_needed = xp_next_level - current_xp
    progress_percent = min(100, int((xp_progress / xp_for_next) * 100)) if xp_for_next > 0 else 100

    return {
        "current_level": current_level,
        "next_level": current_level + 1,
        "xp_current": xp_current_level,
        "xp_next": xp_next_level,
        "xp_progress": xp_progress,
        "xp_needed": max(0, xp_needed),
        "progress_percent": progress_percent,
        "can_level_up": current_xp >= xp_next_level
    }


def apply_level_up(character_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Aplica el level up a un personaje si tiene suficiente XP.

    Args:
        character_data: Diccionario completo del personaje (de la DB).

    Returns:
        Tupla con:
        - Nuevo stats_json actualizado
        - Diccionario con los cambios aplicados (para mostrar al jugador)

    Raises:
        ValueError: Si el personaje no tiene suficiente XP para subir.
    """
    stats = character_data.get("stats_json", {})
    current_xp = stats.get("xp", 0)
    current_level = stats.get("nivel", 1)

    progress = calculate_level_progress(current_xp)

    if not progress["can_level_up"]:
        raise ValueError(f"XP insuficiente. Necesitas {progress['xp_needed']} XP más.")

    # Calcular nuevo nivel
    new_level = progress["next_level"]

    # Preparar cambios
    changes = {
        "nivel_anterior": current_level,
        "nivel_nuevo": new_level,
        "bonificaciones": []
    }

    # Copiar stats para modificar
    new_stats = stats.copy()
    new_stats["nivel"] = new_level

    # Copiar atributos y habilidades
    new_attributes = stats.get("atributos", {}).copy()
    new_skills = stats.get("habilidades", {}).copy()
    new_feats = stats.get("feats", []).copy()

    # 1. Otorgar puntos de habilidad
    skill_points_gained = SKILL_POINTS_PER_LEVEL
    changes["bonificaciones"].append(f"+{skill_points_gained} puntos de habilidad")

    # Distribuir automáticamente (el jugador puede redistribuir después)
    skill_keys = list(new_skills.keys())
    for _ in range(skill_points_gained):
        skill = random.choice(skill_keys)
        new_skills[skill] += 1

    # 2. Verificar si otorga punto de atributo
    if new_level in ATTRIBUTE_POINT_LEVELS:
        changes["bonificaciones"].append("+1 punto de atributo")
        # Añadir a un atributo aleatorio (el jugador puede redistribuir)
        attr_keys = list(new_attributes.keys())
        chosen_attr = random.choice(attr_keys)
        if new_attributes[chosen_attr] < MAX_ATTRIBUTE_VALUE:
            new_attributes[chosen_attr] += 1
            changes["bonificaciones"].append(f"+1 {chosen_attr.capitalize()}")

    # 3. Verificar si otorga feat
    if new_level in FEAT_LEVELS:
        changes["bonificaciones"].append("+1 Rasgo/Feat")
        available = [f for f in AVAILABLE_FEATS if f not in new_feats]
        if available:
            new_feat = random.choice(available)
            new_feats.append(new_feat)
            changes["bonificaciones"].append(f"Nuevo rasgo: {new_feat}")

    # Actualizar stats
    new_stats["atributos"] = new_attributes
    new_stats["habilidades"] = new_skills
    new_stats["feats"] = new_feats

    return new_stats, changes


def add_xp(stats_json: Dict[str, Any], xp_amount: int) -> Dict[str, Any]:
    """
    Añade XP a un personaje y actualiza su stats_json.

    Args:
        stats_json: El JSON de stats actual del personaje.
        xp_amount: Cantidad de XP a añadir.

    Returns:
        Nuevo stats_json con XP actualizado.
    """
    new_stats = stats_json.copy()
    current_xp = new_stats.get("xp", 0)
    new_stats["xp"] = current_xp + xp_amount
    return new_stats


def reroll_character_stats(character_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Regenera los atributos de un personaje manteniendo nivel, XP y clase.
    Útil para debug/testing.

    Args:
        character_data: Diccionario del personaje.

    Returns:
        Nuevo stats_json con atributos regenerados.
    """
    stats = character_data.get("stats_json", {})
    level = stats.get("nivel", 1)
    xp = stats.get("xp", 0)
    bio = stats.get("bio", {})
    feats = stats.get("feats", [])

    race_name = bio.get("raza", "Humano")
    class_name = bio.get("clase", "Soldado")

    race_data = RACES.get(race_name, {"bonus": {}})
    class_data = CLASSES.get(class_name, {"bonus_attr": ""})

    # Regenerar atributos
    new_attributes = _generate_base_attributes()

    # Aplicar bonus racial
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in new_attributes:
            new_attributes[attr] = min(new_attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)

    # Aplicar bonus de clase
    bonus_attr = class_data.get("bonus_attr", "")
    if bonus_attr in new_attributes:
        new_attributes[bonus_attr] = min(new_attributes[bonus_attr] + 1, MAX_ATTRIBUTE_VALUE)

    # Aplicar puntos extra por nivel
    extra_attr_points = sum(1 for lvl in ATTRIBUTE_POINT_LEVELS if lvl <= level)
    _distribute_random_points(new_attributes, extra_attr_points)

    # Recalcular habilidades
    new_skills = calculate_skills(new_attributes)
    skill_points = level * SKILL_POINTS_PER_LEVEL
    new_skills = _boost_skills(new_skills, skill_points)

    return {
        "nivel": level,
        "xp": xp,
        "bio": bio,
        "atributos": new_attributes,
        "habilidades": new_skills,
        "feats": feats
    }


# =============================================================================
# FUNCIONES DE CÁLCULO DE COSTOS
# =============================================================================

def calculate_recruitment_cost(character: Dict[str, Any]) -> int:
    """
    Calcula el costo de reclutamiento basado en nivel y atributos.

    Args:
        character: Diccionario del personaje.

    Returns:
        Costo en créditos.
    """
    stats = character.get("stats_json", {})
    level = stats.get("nivel", 1)
    attributes = stats.get("atributos", {})

    # Costo base por nivel
    base_cost = level * 200

    # Bonus por suma de atributos
    attr_sum = sum(attributes.values())
    attr_bonus = attr_sum * 5

    # Varianza aleatoria
    variance = random.uniform(0.85, 1.15)

    total_cost = int((base_cost + attr_bonus) * variance)
    return max(100, total_cost)  # Mínimo 100 créditos
