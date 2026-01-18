# core/character_engine.py
"""
Motor de Personajes - Lógica pura de generación, progresión y level up.
Refactorizado para generar la estructura completa del CharacterSchema V2.
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

BASE_ATTRIBUTE_MIN = 5
BASE_ATTRIBUTE_MAX = 9
MAX_ATTRIBUTE_VALUE = 20
MIN_ATTRIBUTE_VALUE = 3

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
# CONSTANTES DE BIOGRAFÍA Y ACCESO
# =============================================================================

BIO_ACCESS_UNKNOWN = "desconocido"      # Bio superficial, sin rasgos
BIO_ACCESS_KNOWN = "conocido"           # Bio conocida + rasgos de personalidad
BIO_ACCESS_DEEP = "amigo"               # Bio profunda + secreto

# Aliases para compatibilidad
BIO_ACCESS_SUPERFICIAL = BIO_ACCESS_UNKNOWN

# Ticks requeridos para avanzar de nivel de conocimiento
# "conocido": 20 ticks base (+1 por cada punto de Presencia por debajo de 10)
TICK_THRESHOLD_KNOWN = 20
# "amigo": 50 ticks como "conocido" (no desde el reclutamiento)
TICK_THRESHOLD_DEEP_AS_KNOWN = 50

# Alias para compatibilidad
TICK_THRESHOLD_DEEP = TICK_THRESHOLD_KNOWN + TICK_THRESHOLD_DEEP_AS_KNOWN

# =============================================================================
# TIPOS DE SECRETOS (para biografía profunda)
# =============================================================================

SECRET_TYPE_PROFESSIONAL = "profesional"  # +XP fijo - "mejor entrenamiento al conocerlo"
SECRET_TYPE_PERSONAL = "personal"         # +2 Voluntad - "se siente amigo de la tropa"
SECRET_TYPE_CRITICAL = "critico"          # Misión personal (futuro desarrollo)

# Bonus de secretos
SECRET_PROFESSIONAL_XP_BONUS = 500       # XP que otorga el secreto profesional
SECRET_PERSONAL_WILLPOWER_BONUS = 2      # +2 Voluntad por secreto personal

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
    """
    existing_names = existing_names or []

    level = random.randint(min_level, max_level)
    xp = get_xp_for_level(level)

    race_name, race_data = random.choice(list(RACES.items()))

    if level >= CLASS_ASSIGNMENT_MIN_LEVEL:
        class_name, class_data = random.choice(list(CLASSES.items()))
    else:
        class_name = "Novato"
        class_data = {"desc": "Recién reclutado, aún sin especialización.", "bonus_attr": None}

    name, surname = _generate_full_name(race_name, existing_names)
    age = random.randint(RECRUIT_AGE_MIN, RECRUIT_AGE_MAX)
    sex = random.choice([BiologicalSex.MALE, BiologicalSex.FEMALE])
    
    attributes = _generate_base_attributes()
    
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in attributes:
            attributes[attr] = min(attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)
    
    if class_name != "Novato" and class_data.get("bonus_attr"):
        bonus_attr = class_data["bonus_attr"]
        if bonus_attr in attributes:
            attributes[bonus_attr] = min(attributes[bonus_attr] + 1, MAX_ATTRIBUTE_VALUE)

    extra_attr_points = sum(1 for lvl in ATTRIBUTE_POINT_LEVELS if lvl <= level)
    _distribute_random_points(attributes, extra_attr_points)

    skills = calculate_skills(attributes)
    skill_points = level * SKILL_POINTS_PER_LEVEL
    skills = _boost_skills(skills, skill_points)

    num_feats = sum(1 for lvl in FEAT_LEVELS if lvl <= level)
    feats = random.sample(AVAILABLE_FEATS, min(num_feats, len(AVAILABLE_FEATS)))

    traits = random.sample(PERSONALITY_TRAITS, k=2)

    # TEXTOS DE BIOGRAFÍA GENÉRICOS (Local/Fallback)
    bio_sup = f"{race_name} {class_name}. Se le ve {traits[0].lower()}."
    bio_known = f"Sujeto reclutado en estación remota. Muestra rasgos de personalidad {traits[0]} y {traits[1]}. Historial académico estándar para un {race_name}."
    bio_deep = f"DATOS CLASIFICADOS. El sujeto proviene de un sector en cuarentena. Posible exposición a radiación de vacío."

    stats_json = {
        "bio": {
            "nombre": name,
            "apellido": surname,
            "edad": age,
            "sexo": sex.value,
            "biografia_corta": bio_sup,  # Campo legacy, mantiene la corta
            "bio_superficial": bio_sup,
            "bio_conocida": bio_known,
            "bio_profunda": bio_deep,
            "nivel_acceso": BIO_ACCESS_UNKNOWN,  # Empieza como desconocido
            "ticks_reclutado": 0,
            "ticks_como_conocido": 0,  # Nuevo contador para nivel amigo
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
    prog = stats.get("progresion", {})
    caps = stats.get("capacidades", {})
    
    current_level = prog.get("nivel", 1)
    current_xp = prog.get("xp", 0)
    
    progress = calculate_level_progress(current_xp, stored_level=current_level)
    if not progress.get("can_level_up"):
        raise ValueError("XP insuficiente para ascender.")

    new_level = current_level + 1
    changes = {"bonificaciones": []}

    new_stats = stats.copy()
    new_prog = prog.copy()
    new_caps = caps.copy()
    
    new_attributes = new_caps.get("atributos", {}).copy()
    new_skills = new_caps.get("habilidades", {}).copy()
    new_feats = new_caps.get("feats", []).copy()

    if new_level == 3 and new_prog.get("clase") == "Novato":
        changes["bonificaciones"].append("¡ELECCIÓN DE CLASE DISPONIBLE!")
        new_class_name, _ = random.choice(list(CLASSES.items()))
        new_prog["clase"] = new_class_name 
        changes["bonificaciones"].append(f"Clase asignada: {new_class_name}")

    changes["bonificaciones"].append(f"+{SKILL_POINTS_PER_LEVEL} puntos de habilidad")
    skill_keys = list(new_skills.keys())
    if skill_keys:
        for _ in range(SKILL_POINTS_PER_LEVEL):
            skill = random.choice(skill_keys)
            new_skills[skill] += 1

    if new_level in ATTRIBUTE_POINT_LEVELS:
        changes["bonificaciones"].append("+1 punto de atributo")
        attr_keys = list(new_attributes.keys())
        if attr_keys:
            chosen = random.choice(attr_keys)
            if new_attributes[chosen] < MAX_ATTRIBUTE_VALUE:
                new_attributes[chosen] += 1
                changes["bonificaciones"].append(f"+1 {chosen.capitalize()}")

    if new_level in FEAT_LEVELS:
        available = [f for f in AVAILABLE_FEATS if f not in new_feats]
        if available:
            new_feat = random.choice(available)
            new_feats.append(new_feat)
            changes["bonificaciones"].append(f"Nuevo rasgo: {new_feat}")

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

# =============================================================================
# FUNCIONES DE GESTIÓN DE BIOGRAFÍAS (NUEVO)
# =============================================================================

def get_visible_biography(stats_json: Dict[str, Any]) -> str:
    """
    Retorna la biografía apropiada según el nivel de acceso desbloqueado.
    Prioridad: Profunda > Conocida > Superficial.
    Maneja retrocompatibilidad con personajes viejos.
    """
    bio_data = stats_json.get("bio", {})
    access_level = bio_data.get("nivel_acceso", BIO_ACCESS_KNOWN)  # Legacy -> conocido

    # Textos disponibles (con fallbacks)
    default_bio = bio_data.get("biografia_corta", "Datos no disponibles.")

    bio_sup = bio_data.get("bio_superficial", default_bio)
    bio_known = bio_data.get("bio_conocida", default_bio)
    bio_deep = bio_data.get("bio_profunda", bio_known)

    if access_level == BIO_ACCESS_DEEP:
        return bio_deep
    elif access_level == BIO_ACCESS_KNOWN:
        return bio_known
    else:  # Desconocido/Superficial
        return bio_sup


def should_show_personality_traits(stats_json: Dict[str, Any]) -> bool:
    """
    Determina si se deben mostrar los rasgos de personalidad.
    Solo se muestran si el nivel de acceso es 'conocido' o superior.
    """
    bio_data = stats_json.get("bio", {})
    access_level = bio_data.get("nivel_acceso", BIO_ACCESS_UNKNOWN)
    return access_level in [BIO_ACCESS_KNOWN, BIO_ACCESS_DEEP]


def calculate_ticks_for_known(presencia: int) -> int:
    """
    Calcula los ticks necesarios para pasar a nivel 'conocido'.
    Base: 20 ticks + 1 por cada punto de Presencia por debajo de 10.
    """
    extra_ticks = max(0, 10 - presencia)
    return TICK_THRESHOLD_KNOWN + extra_ticks


def update_character_access_level(stats_json: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Calcula si debe subir el nivel de acceso basado en ticks reclutado.
    Retorna (cambio_ocurrido, nuevo_nivel, tipo_secreto_revelado).
    El tipo_secreto_revelado solo se retorna cuando se alcanza nivel 'amigo'.
    """
    bio_data = stats_json.get("bio", {})
    capacidades = stats_json.get("capacidades", {})
    atributos = capacidades.get("atributos", {})
    presencia = atributos.get("presencia", 10)

    if "ticks_reclutado" not in bio_data:
        bio_data["ticks_reclutado"] = 0

    if "ticks_como_conocido" not in bio_data:
        bio_data["ticks_como_conocido"] = 0

    ticks_total = bio_data["ticks_reclutado"]
    ticks_conocido = bio_data["ticks_como_conocido"]
    current_level = bio_data.get("nivel_acceso", BIO_ACCESS_UNKNOWN)

    # Si es personaje legacy (sin nivel_acceso), lo asumimos conocido y no cambiamos nada
    if "nivel_acceso" not in bio_data:
        bio_data["nivel_acceso"] = BIO_ACCESS_KNOWN
        return False, "", None

    new_level = current_level
    secret_revealed = None

    # Calcular threshold dinámico para 'conocido' basado en presencia
    threshold_known = calculate_ticks_for_known(presencia)

    # Transición a 'amigo' (requiere 50 ticks COMO conocido)
    if current_level == BIO_ACCESS_KNOWN and ticks_conocido >= TICK_THRESHOLD_DEEP_AS_KNOWN:
        new_level = BIO_ACCESS_DEEP
        # Determinar tipo de secreto al azar si no está definido
        if "tipo_secreto" not in bio_data:
            secret_type = random.choice([SECRET_TYPE_PROFESSIONAL, SECRET_TYPE_PERSONAL, SECRET_TYPE_CRITICAL])
            bio_data["tipo_secreto"] = secret_type
            secret_revealed = secret_type
        else:
            secret_revealed = bio_data["tipo_secreto"]

    # Transición a 'conocido'
    elif current_level == BIO_ACCESS_UNKNOWN and ticks_total >= threshold_known:
        new_level = BIO_ACCESS_KNOWN

    if new_level != current_level:
        bio_data["nivel_acceso"] = new_level
        return True, new_level, secret_revealed

    return False, "", None


def apply_secret_bonus(stats_json: Dict[str, Any], secret_type: str) -> Dict[str, Any]:
    """
    Aplica el bonus correspondiente al tipo de secreto revelado.
    Modifica stats_json in-place y retorna los cambios aplicados.
    """
    changes = {"tipo": secret_type, "aplicado": False, "descripcion": ""}
    bio_data = stats_json.get("bio", {})

    if bio_data.get("secreto_aplicado", False):
        changes["descripcion"] = "El secreto ya fue aplicado anteriormente."
        return changes

    if secret_type == SECRET_TYPE_PROFESSIONAL:
        # +XP fijo
        progresion = stats_json.get("progresion", {})
        current_xp = progresion.get("xp", 0)
        progresion["xp"] = current_xp + SECRET_PROFESSIONAL_XP_BONUS
        stats_json["progresion"] = progresion
        changes["aplicado"] = True
        changes["descripcion"] = f"Secreto profesional: +{SECRET_PROFESSIONAL_XP_BONUS} XP (mejor entrenamiento al conocerlo mejor)."

    elif secret_type == SECRET_TYPE_PERSONAL:
        # +2 Voluntad
        capacidades = stats_json.get("capacidades", {})
        atributos = capacidades.get("atributos", {})
        current_will = atributos.get("voluntad", 5)
        atributos["voluntad"] = min(current_will + SECRET_PERSONAL_WILLPOWER_BONUS, MAX_ATTRIBUTE_VALUE)
        capacidades["atributos"] = atributos
        stats_json["capacidades"] = capacidades
        changes["aplicado"] = True
        changes["descripcion"] = f"Secreto personal: +{SECRET_PERSONAL_WILLPOWER_BONUS} Voluntad (se siente amigo de la tropa)."

    elif secret_type == SECRET_TYPE_CRITICAL:
        # Misión personal (futuro desarrollo)
        changes["aplicado"] = True
        changes["descripcion"] = "Secreto crítico: Se revela información de importancia crítica. Misión personal desbloqueada (pendiente de implementación)."

    if changes["aplicado"]:
        bio_data["secreto_aplicado"] = True
        stats_json["bio"] = bio_data

    return changes