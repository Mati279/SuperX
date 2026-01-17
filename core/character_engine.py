# core/character_engine.py
"""
Motor de Personajes - Lógica pura de generación, progresión y level up.
Refactorizado para generar la estructura completa del CharacterSchema V2.

NOTA: Para generación de personajes con IA, usar:
    services.character_generation_service.generate_random_character_with_ai()

Este módulo provee la lógica base de progresión y la generación sin IA.
"""

import random
from typing import Dict, Any, List, Tuple, Optional
from core.constants import RACES, CLASSES, SKILL_MAPPING
from core.rules import calculate_skills
from core.models import BiologicalSex, CharacterRole
from config.app_constants import (
    RECRUIT_AGE_MIN,
    RECRUIT_AGE_MAX,
    CLASS_ASSIGNMENT_MIN_LEVEL,
    DEFAULT_RECRUIT_RANK
)

# =============================================================================
# CONSTANTES DE PROGRESIÓN (Basadas en Módulo 19)
# =============================================================================

XP_TABLE = {
    1: 0, 2: 500, 3: 1500, 4: 3000, 5: 5000, 6: 7500, 7: 10500, 8: 14000,
    9: 18000, 10: 22500, 11: 27500, 12: 33000, 13: 39000, 14: 45500, 15: 52500,
    16: 60000, 17: 68000, 18: 76500, 19: 85500, 20: 95000
}

SKILL_POINTS_PER_LEVEL = 4
ATTRIBUTE_POINT_LEVELS = [5, 10, 15, 20]
FEAT_LEVELS = [1, 5, 10, 15, 20]

# Atributos base (alineados con SKILL_MAPPING)
BASE_ATTRIBUTE_MIN = 5
BASE_ATTRIBUTE_MAX = 9  # Modificado de 10 a 9
MAX_ATTRIBUTE_VALUE = 20
MIN_ATTRIBUTE_VALUE = 3

# Lista de atributos del sistema (alineados con SKILL_MAPPING en constants.py)
ATTRIBUTE_NAMES = ["fuerza", "agilidad", "tecnica", "intelecto", "voluntad", "presencia"]

AVAILABLE_FEATS = [
    "Liderazgo Táctico", "Logística Avanzada", "Experto en Combate", "Piloto As",
    "Genio Técnico", "Diplomático Nato", "Infiltrador", "Médico de Campo",
    "Hacker Élite", "Resistencia Sobrehumana", "Reflejos Mejorados",
    "Mente Analítica", "Carisma Magnético", "Voluntad de Hierro", "Especialista en Armas"
]

PERSONALITY_TRAITS = [
    "Valiente", "Cauteloso", "Ambicioso", "Leal", "Traicionero", "Optimista",
    "Cínico", "Pragmático", "Idealista", "Agresivo", "Pacífico", "Curioso",
    "Tradicionalista", "Rebelde", "Disciplinado", "Caótico"
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
    Genera un personaje completo siguiendo el nuevo CharacterSchema V2.

    NOTA: Esta función genera nombres localmente. Para generación con IA,
    usar services.character_generation_service.generate_random_character_with_ai()
    """
    existing_names = existing_names or []

    # 1. Determinar nivel y XP
    level = random.randint(min_level, max_level)
    xp = get_xp_for_level(level)

    # 2. Selección de Raza
    race_name, race_data = random.choice(list(RACES.items()))

    # 3. Selección de Clase (REGLA: Obligatoria a nivel CLASS_ASSIGNMENT_MIN_LEVEL, sino Novato)
    if level >= CLASS_ASSIGNMENT_MIN_LEVEL:
        class_name, class_data = random.choice(list(CLASSES.items()))
    else:
        class_name = "Novato"
        class_data = {"desc": "Recién reclutado, aún sin especialización.", "bonus_attr": None}

    # 4. Generar Bio (Nombre, Apellido, Edad, Sexo)
    name, surname = _generate_full_name(race_name, existing_names)
    age = random.randint(RECRUIT_AGE_MIN, RECRUIT_AGE_MAX)
    sex = random.choice([BiologicalSex.MALE, BiologicalSex.FEMALE])
    
    # 5. Generar Atributos
    attributes = _generate_base_attributes()
    
    # Bonus Racial
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in attributes:
            attributes[attr] = min(attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)
    
    # Bonus Clase (si aplica)
    if class_name != "Novato" and class_data.get("bonus_attr"):
        bonus_attr = class_data["bonus_attr"]
        if bonus_attr in attributes:
            attributes[bonus_attr] = min(attributes[bonus_attr] + 1, MAX_ATTRIBUTE_VALUE)

    # Puntos extra por nivel
    extra_attr_points = sum(1 for lvl in ATTRIBUTE_POINT_LEVELS if lvl <= level)
    _distribute_random_points(attributes, extra_attr_points)

    # 6. Habilidades y Feats
    skills = calculate_skills(attributes)
    skill_points = level * SKILL_POINTS_PER_LEVEL
    skills = _boost_skills(skills, skill_points)

    num_feats = sum(1 for lvl in FEAT_LEVELS if lvl <= level)
    feats = random.sample(AVAILABLE_FEATS, min(num_feats, len(AVAILABLE_FEATS)))

    # 7. Personalidad y Comportamiento
    traits = random.sample(PERSONALITY_TRAITS, k=2)

    # 8. Ensamblar Estructura V2 (Mapping a CharacterSchema)
    
    stats_json = {
        "bio": {
            "nombre": name,
            "apellido": surname,
            "edad": age,
            "sexo": sex.value,
            "biografia_corta": f"{race_name} {class_name}. {traits[0]} y {traits[1]}."
        },
        "taxonomia": {
            "raza": race_name,
            "transformaciones": []
        },
        "progresion": {
            "nivel": level,
            "clase": class_name,
            "xp": xp,
            "xp_next": get_xp_for_level(level + 1) if level < 20 else xp,
            "rango": DEFAULT_RECRUIT_RANK if level < 5 else "Oficial"
        },
        "capacidades": {
            "atributos": attributes,
            "habilidades": skills,
            "feats": feats
        },
        "comportamiento": {
            "rasgos_personalidad": traits,
            "relaciones": []
        },
        "logistica": {
            "equipo": [],
            "slots_ocupados": 0,
            "slots_maximos": 10
        },
        "estado": {
            "estados_activos": ["Disponible"],
            "sistema_actual": "Desconocido",
            "ubicacion_local": "Barracones",
            "rol_asignado": CharacterRole.NONE.value,
            "accion_actual": "Esperando asignación"
        }
    }

    # Retorno compatible con lo que espera el repositorio para inserción
    return {
        "nombre": f"{name} {surname}",
        "rango": stats_json["progresion"]["rango"],
        "estado": "Disponible",
        "ubicacion": "Barracones",
        "stats_json": stats_json
    }


def _generate_full_name(race: str, existing: List[str]) -> Tuple[str, str]:
    """Genera nombre y apellido separados."""
    names = ["Kira", "Zane", "Nova", "Rex", "Luna", "Orion", "Vega", "Atlas", "Cyrus", "Maya", "Dax", "Koda"]
    surnames = ["Voss", "Riker", "Thorne", "Stark", "Chen", "Vale", "Kross", "Pike", "Sol", "Merrick"]
    
    for _ in range(50):
        n = random.choice(names)
        s = random.choice(surnames)
        full = f"{n} {s}"
        if full not in existing:
            return n, s
    return f"{race}", f"Unit-{random.randint(100,999)}"


def _generate_base_attributes() -> Dict[str, int]:
    """Genera atributos base aleatorios usando los nombres del sistema."""
    return {attr: random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX) for attr in ATTRIBUTE_NAMES}

def _distribute_random_points(attributes: Dict[str, int], points: int) -> None:
    attr_keys = list(attributes.keys())
    for _ in range(points):
        attr = random.choice(attr_keys)
        if attributes[attr] < MAX_ATTRIBUTE_VALUE:
            attributes[attr] += 1

def _boost_skills(skills: Dict[str, int], points: int) -> Dict[str, int]:
    skill_keys = list(skills.keys())
    boosted = skills.copy()
    for _ in range(points):
        skill = random.choice(skill_keys)
        boosted[skill] += 1
    return boosted

# =============================================================================
# FUNCIONES DE PROGRESIÓN (Helper)
# =============================================================================

def get_xp_for_level(level: int) -> int:
    return XP_TABLE.get(level, XP_TABLE[20])

def get_level_from_xp(xp: int) -> int:
    current_level = 1
    for level, required_xp in sorted(XP_TABLE.items()):
        if xp >= required_xp:
            current_level = level
        else:
            break
    return current_level

def calculate_level_progress(current_xp: int, stored_level: Optional[int] = None) -> Dict[str, Any]:
    level_from_xp = get_level_from_xp(current_xp)
    
    if stored_level is not None:
        current_level = stored_level
        can_level_up = level_from_xp > stored_level and stored_level < 20
    else:
        current_level = level_from_xp
        can_level_up = False

    if current_level >= 20:
        return {"current_level": 20, "can_level_up": False, "progress_percent": 100}

    xp_current = XP_TABLE[current_level]
    xp_next = XP_TABLE[current_level + 1]
    xp_progress = current_xp - xp_current
    xp_total_needed = xp_next - xp_current
    
    percent = min(100, int((xp_progress / xp_total_needed) * 100)) if xp_total_needed > 0 else 100
    
    return {
        "current_level": current_level,
        "next_level": current_level + 1,
        "progress_percent": percent,
        "can_level_up": can_level_up or (current_xp >= xp_next)
    }

def apply_level_up(character_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Aplica level up sobre la estructura V2.
    """
    stats = character_data.get("stats_json", {})
    # Adaptar acceso a la nueva estructura
    prog = stats.get("progresion", {})
    caps = stats.get("capacidades", {})
    
    current_level = prog.get("nivel", 1)
    current_xp = prog.get("xp", 0)
    
    progress = calculate_level_progress(current_xp, stored_level=current_level)
    if not progress.get("can_level_up"):
        raise ValueError("XP insuficiente para ascender.")

    new_level = current_level + 1
    changes = {"bonificaciones": []}

    # Copias para modificar
    new_stats = stats.copy()
    new_prog = prog.copy()
    new_caps = caps.copy()
    
    new_attributes = new_caps.get("atributos", {}).copy()
    new_skills = new_caps.get("habilidades", {}).copy()
    new_feats = new_caps.get("feats", []).copy()

    # 1. Clase a Nivel 3 (Lógica especial)
    # Si sube a nivel 3, debería elegir clase. Aquí simulamos o dejamos pendiente.
    if new_level == 3 and new_prog.get("clase") == "Novato":
        changes["bonificaciones"].append("¡ELECCIÓN DE CLASE DISPONIBLE!")
        # Por defecto asignamos una random si no hay input (o se manejaría en UI)
        new_class_name, _ = random.choice(list(CLASSES.items()))
        new_prog["clase"] = new_class_name 
        changes["bonificaciones"].append(f"Clase asignada: {new_class_name}")

    # 2. Skill Points
    changes["bonificaciones"].append(f"+{SKILL_POINTS_PER_LEVEL} puntos de habilidad")
    skill_keys = list(new_skills.keys())
    if skill_keys:
        for _ in range(SKILL_POINTS_PER_LEVEL):
            skill = random.choice(skill_keys)
            new_skills[skill] += 1

    # 3. Attribute Points
    if new_level in ATTRIBUTE_POINT_LEVELS:
        changes["bonificaciones"].append("+1 punto de atributo")
        attr_keys = list(new_attributes.keys())
        if attr_keys:
            chosen = random.choice(attr_keys)
            if new_attributes[chosen] < MAX_ATTRIBUTE_VALUE:
                new_attributes[chosen] += 1
                changes["bonificaciones"].append(f"+1 {chosen.capitalize()}")

    # 4. Feats
    if new_level in FEAT_LEVELS:
        available = [f for f in AVAILABLE_FEATS if f not in new_feats]
        if available:
            new_feat = random.choice(available)
            new_feats.append(new_feat)
            changes["bonificaciones"].append(f"Nuevo rasgo: {new_feat}")

    # Actualizar estructura
    new_prog["nivel"] = new_level
    new_prog["xp_next"] = get_xp_for_level(new_level + 1) if new_level < 20 else current_xp
    
    new_caps["atributos"] = new_attributes
    new_caps["habilidades"] = new_skills
    new_caps["feats"] = new_feats
    
    new_stats["progresion"] = new_prog
    new_stats["capacidades"] = new_caps

    return new_stats, changes

def calculate_recruitment_cost(character: Dict[str, Any]) -> int:
    """Calcula costo basado en estructura V2."""
    stats = character.get("stats_json", {})
    level = stats.get("progresion", {}).get("nivel", 1)
    attrs = stats.get("capacidades", {}).get("atributos", {})
    
    base_cost = level * 200
    attr_sum = sum(attrs.values()) if attrs else 30
    return int((base_cost + attr_sum * 5) * random.uniform(0.9, 1.1))