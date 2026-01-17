# services/character_generation_service.py
"""
Servicio de Generación de Personajes con IA.
Coordina la creación de personajes aleatorios integrando:
- Generación de atributos (character_engine)
- Generación de identidad por IA (nombre, apellido, biografía)
- Reglas de reclutamiento (raza predominante, clase por nivel)
- Persistencia en base de datos

El flujo es:
1. Generar estructura base del personaje (character_engine)
2. IA genera nombre, apellido y biografía basándose en los atributos
3. Guardar en BD
"""

import random
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from google.genai import types

from data.database import get_service_container
from data.log_repository import log_event
from data.character_repository import create_character
from data.planet_repository import get_planet_by_id

from core.constants import RACES, CLASSES
from core.rules import calculate_skills
from core.models import BiologicalSex, CharacterRole
from core.character_engine import (
    get_xp_for_level,
    AVAILABLE_FEATS,
    PERSONALITY_TRAITS,
    BASE_ATTRIBUTE_MIN,
    BASE_ATTRIBUTE_MAX,
    MAX_ATTRIBUTE_VALUE,
    SKILL_POINTS_PER_LEVEL,
    ATTRIBUTE_POINT_LEVELS,
    FEAT_LEVELS
)

from config.app_constants import TEXT_MODEL_NAME


# =============================================================================
# CONSTANTES DE GENERACIÓN
# =============================================================================

# Rango de edad según especificación
AGE_MIN = 16
AGE_MAX = 70

# Probabilidad de raza predominante en reclutamiento en base
PREDOMINANT_RACE_CHANCE = 0.5

# Rango por defecto para nuevos reclutas
DEFAULT_RANK = "Iniciado"

# Prompt para generación de identidad por IA
IDENTITY_GENERATION_PROMPT = """
Eres un generador de identidades para personajes de un juego de ciencia ficción espacial.

DATOS DEL PERSONAJE A NOMBRAR:
- Raza: {race}
- Clase: {char_class}
- Nivel: {level}
- Sexo: {sex}
- Edad: {age} años
- Rasgos de personalidad: {traits}
- Atributos destacados: {top_attributes}

INSTRUCCIONES:
1. Genera un NOMBRE y APELLIDO apropiados para la raza y ambientación sci-fi.
   - Humano: Nombres occidentales/internacionales variados
   - Cyborg: Nombres con prefijos técnicos o alfanuméricos
   - Marciano: Nombres con sonoridad latina/mediterránea
   - Selenita: Nombres etéreos, con sonidos suaves
   - Androide: Designaciones técnicas o nombres elegidos

2. Escribe una BIOGRAFÍA CORTA (2-3 oraciones máximo) que:
   - Sintetice la esencia del personaje
   - Mencione en qué destaca según sus atributos
   - Sugiera posibles roles/funciones en una tripulación
   - Sea coherente con la edad y nivel

FORMATO DE RESPUESTA (JSON estricto):
{{
  "nombre": "Nombre",
  "apellido": "Apellido",
  "biografia": "Biografía corta aquí."
}}

Responde SOLO con el JSON, sin texto adicional.
"""


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

@dataclass
class RecruitmentContext:
    """Contexto para el reclutamiento de un personaje."""
    player_id: int
    location_planet_id: Optional[int] = None
    predominant_race: Optional[str] = None
    min_level: int = 1
    max_level: int = 1
    force_race: Optional[str] = None
    force_class: Optional[str] = None


@dataclass
class GeneratedIdentity:
    """Identidad generada por la IA."""
    nombre: str
    apellido: str
    biografia: str


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _get_top_attributes(attributes: Dict[str, int], count: int = 2) -> str:
    """Obtiene los atributos más altos del personaje."""
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top = sorted_attrs[:count]
    return ", ".join([f"{attr.capitalize()}: {val}" for attr, val in top])


def _generate_base_attributes() -> Dict[str, int]:
    """Genera atributos base aleatorios."""
    return {
        "fuerza": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "agilidad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "tecnica": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "intelecto": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "voluntad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "presencia": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
    }


def _distribute_random_points(attributes: Dict[str, int], points: int) -> None:
    """Distribuye puntos aleatorios en atributos."""
    attr_keys = list(attributes.keys())
    for _ in range(points):
        attr = random.choice(attr_keys)
        if attributes[attr] < MAX_ATTRIBUTE_VALUE:
            attributes[attr] += 1


def _boost_skills(skills: Dict[str, int], points: int) -> Dict[str, int]:
    """Aumenta habilidades con puntos adicionales."""
    skill_keys = list(skills.keys())
    boosted = skills.copy()
    for _ in range(points):
        if skill_keys:
            skill = random.choice(skill_keys)
            boosted[skill] += 1
    return boosted


def _select_race(context: RecruitmentContext) -> tuple[str, Dict[str, Any]]:
    """
    Selecciona la raza del personaje.
    Regla: 50% probabilidad de raza predominante si está en base.
    """
    if context.force_race and context.force_race in RACES:
        return context.force_race, RACES[context.force_race]

    # Regla de reclutamiento en base
    if context.predominant_race and random.random() < PREDOMINANT_RACE_CHANCE:
        if context.predominant_race in RACES:
            return context.predominant_race, RACES[context.predominant_race]

    # Selección aleatoria
    race_name, race_data = random.choice(list(RACES.items()))
    return race_name, race_data


def _select_class(level: int, force_class: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
    """
    Selecciona la clase del personaje.
    Regla: Novato obligatorio para nivel 1-2, aleatorio para 3+.
    """
    if force_class and force_class in CLASSES:
        return force_class, CLASSES[force_class]

    if level < 3:
        return "Novato", {"desc": "Recién reclutado, aún sin especialización.", "bonus_attr": None}

    class_name, class_data = random.choice(list(CLASSES.items()))
    return class_name, class_data


def _generate_fallback_identity(race: str, sex: BiologicalSex) -> GeneratedIdentity:
    """Genera una identidad de respaldo si la IA falla."""
    # Nombres por raza
    names_by_race = {
        "Humano": {
            BiologicalSex.MALE: ["Marcus", "Adrian", "Victor", "Leon", "Dante"],
            BiologicalSex.FEMALE: ["Elena", "Maya", "Zara", "Nova", "Iris"]
        },
        "Cyborg": {
            BiologicalSex.MALE: ["CX-7", "Neo-Kade", "Axl-9", "Vex", "Rho-Marcus"],
            BiologicalSex.FEMALE: ["CY-Nova", "Syn-7", "Ada-X", "Nyx-3", "Vera-2"]
        },
        "Marciano": {
            BiologicalSex.MALE: ["Aurelio", "Valerio", "Ciro", "Marco", "Luca"],
            BiologicalSex.FEMALE: ["Lucia", "Valentina", "Aurora", "Stella", "Mira"]
        },
        "Selenita": {
            BiologicalSex.MALE: ["Selene", "Arian", "Cael", "Lior", "Elan"],
            BiologicalSex.FEMALE: ["Luna", "Aria", "Seraphina", "Lyra", "Celeste"]
        },
        "Androide": {
            BiologicalSex.MALE: ["UNIT-7", "ADAM-3", "NEXUS", "PRIME-1", "ECHO"],
            BiologicalSex.FEMALE: ["EVE-2", "ARIA-7", "NOVA-X", "IRIS", "ATHENA-1"]
        }
    }

    surnames = ["Voss", "Riker", "Thorne", "Stark", "Chen", "Vale", "Kross", "Pike", "Sol", "Merrick",
                "Castellano", "Reyes", "Volkov", "Tanaka", "Schmidt", "Okonkwo"]

    race_names = names_by_race.get(race, names_by_race["Humano"])
    sex_names = race_names.get(sex, race_names[BiologicalSex.MALE])

    nombre = random.choice(sex_names)
    apellido = random.choice(surnames)

    return GeneratedIdentity(
        nombre=nombre,
        apellido=apellido,
        biografia=f"{race} reclutado recientemente. Pendiente de evaluación completa."
    )


# =============================================================================
# GENERACIÓN DE IDENTIDAD CON IA
# =============================================================================

async def _generate_identity_with_ai(
    race: str,
    char_class: str,
    level: int,
    sex: BiologicalSex,
    age: int,
    traits: List[str],
    attributes: Dict[str, int]
) -> GeneratedIdentity:
    """
    Genera nombre, apellido y biografía usando la IA.
    Fallback a generación local si falla.
    """
    container = get_service_container()

    if not container.is_ai_available():
        return _generate_fallback_identity(race, sex)

    ai_client = container.ai

    prompt = IDENTITY_GENERATION_PROMPT.format(
        race=race,
        char_class=char_class,
        level=level,
        sex=sex.value,
        age=age,
        traits=", ".join(traits),
        top_attributes=_get_top_attributes(attributes)
    )

    try:
        response = ai_client.models.generate_content(
            model=TEXT_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=256
            )
        )

        if response and response.text:
            # Parsear JSON de la respuesta
            text = response.text.strip()
            # Limpiar posibles marcadores de código
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            return GeneratedIdentity(
                nombre=data.get("nombre", "Sin Nombre"),
                apellido=data.get("apellido", ""),
                biografia=data.get("biografia", f"{race} {char_class}.")
            )

    except Exception as e:
        log_event(f"Error generando identidad con IA: {e}", is_error=True)

    return _generate_fallback_identity(race, sex)


def generate_identity_with_ai_sync(
    race: str,
    char_class: str,
    level: int,
    sex: BiologicalSex,
    age: int,
    traits: List[str],
    attributes: Dict[str, int]
) -> GeneratedIdentity:
    """
    Versión síncrona de generación de identidad con IA.
    """
    container = get_service_container()

    if not container.is_ai_available():
        return _generate_fallback_identity(race, sex)

    ai_client = container.ai

    prompt = IDENTITY_GENERATION_PROMPT.format(
        race=race,
        char_class=char_class,
        level=level,
        sex=sex.value,
        age=age,
        traits=", ".join(traits),
        top_attributes=_get_top_attributes(attributes)
    )

    try:
        response = ai_client.models.generate_content(
            model=TEXT_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.9,
                max_output_tokens=256
            )
        )

        if response and response.text:
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            return GeneratedIdentity(
                nombre=data.get("nombre", "Sin Nombre"),
                apellido=data.get("apellido", ""),
                biografia=data.get("biografia", f"{race} {char_class}.")
            )

    except Exception as e:
        log_event(f"Error generando identidad con IA: {e}", is_error=True)

    return _generate_fallback_identity(race, sex)


# =============================================================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# =============================================================================

def generate_random_character_with_ai(
    context: RecruitmentContext,
    existing_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Genera un personaje completo con identidad generada por IA.

    Args:
        context: Contexto de reclutamiento con ubicación, nivel, etc.
        existing_names: Lista de nombres existentes para evitar duplicados

    Returns:
        Dict listo para persistir en BD (formato character_repository)
    """
    existing_names = existing_names or []

    # 1. Determinar nivel y XP
    level = random.randint(context.min_level, context.max_level)
    xp = get_xp_for_level(level)

    # 2. Selección de Raza (con regla de raza predominante)
    race_name, race_data = _select_race(context)

    # 3. Selección de Clase (con regla de nivel)
    class_name, class_data = _select_class(level, context.force_class)

    # 4. Generar datos biológicos
    age = random.randint(AGE_MIN, AGE_MAX)
    sex = random.choice([BiologicalSex.MALE, BiologicalSex.FEMALE])

    # 5. Generar Atributos
    attributes = _generate_base_attributes()

    # Bonus Racial
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in attributes:
            attributes[attr] = min(attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)

    # Bonus de Clase (si aplica)
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

    # 7. Personalidad
    traits = random.sample(PERSONALITY_TRAITS, k=2)

    # 8. Generar Identidad con IA
    identity = generate_identity_with_ai_sync(
        race=race_name,
        char_class=class_name,
        level=level,
        sex=sex,
        age=age,
        traits=traits,
        attributes=attributes
    )

    # Evitar nombres duplicados
    full_name = f"{identity.nombre} {identity.apellido}"
    attempts = 0
    while full_name in existing_names and attempts < 5:
        identity = _generate_fallback_identity(race_name, sex)
        full_name = f"{identity.nombre} {identity.apellido}"
        attempts += 1

    # 9. Determinar ubicación
    location = "Barracones"
    system = "Desconocido"

    if context.location_planet_id:
        try:
            planet = get_planet_by_id(context.location_planet_id)
            if planet:
                location = planet.get("name", "Base")
                system = f"Sistema {planet.get('system_id', 'Desconocido')}"
        except Exception:
            pass

    # 10. Ensamblar Estructura V2
    stats_json = {
        "bio": {
            "nombre": identity.nombre,
            "apellido": identity.apellido,
            "edad": age,
            "sexo": sex.value,
            "biografia_corta": identity.biografia
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
            "rango": DEFAULT_RANK
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
            "sistema_actual": system,
            "ubicacion_local": location,
            "rol_asignado": CharacterRole.NONE.value,
            "accion_actual": "Esperando asignación"
        }
    }

    # Retorno compatible con character_repository
    return {
        "nombre": full_name,
        "rango": DEFAULT_RANK,
        "estado": "Disponible",
        "ubicacion": location,
        "es_comandante": False,
        "stats_json": stats_json
    }


def recruit_character_with_ai(
    player_id: int,
    location_planet_id: Optional[int] = None,
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1,
    existing_names: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Recluta un nuevo personaje y lo guarda en la BD.

    Esta es la función principal que coordina:
    1. Generación del personaje con IA
    2. Persistencia en base de datos
    3. Logging del evento

    Args:
        player_id: ID del jugador que recluta
        location_planet_id: ID del planeta donde se recluta (para raza predominante)
        predominant_race: Raza predominante del planeta (opcional)
        min_level: Nivel mínimo del recluta
        max_level: Nivel máximo del recluta
        existing_names: Nombres existentes para evitar duplicados

    Returns:
        Dict con datos del personaje creado, o None si falla
    """
    context = RecruitmentContext(
        player_id=player_id,
        location_planet_id=location_planet_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )

    try:
        # Generar personaje con IA
        character_data = generate_random_character_with_ai(context, existing_names)

        # Persistir en BD
        result = create_character(player_id, character_data)

        if result:
            log_event(
                f"Reclutado: {character_data['nombre']} ({character_data['stats_json']['taxonomia']['raza']} {character_data['stats_json']['progresion']['clase']})",
                player_id
            )
            return result

        return None

    except Exception as e:
        log_event(f"Error en reclutamiento con IA: {e}", player_id, is_error=True)
        return None


def generate_character_pool(
    player_id: int,
    pool_size: int = 3,
    location_planet_id: Optional[int] = None,
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1
) -> List[Dict[str, Any]]:
    """
    Genera un pool de candidatos para que el jugador elija.
    NO los guarda en BD - solo genera los datos.

    Args:
        player_id: ID del jugador
        pool_size: Cantidad de candidatos a generar
        location_planet_id: ID del planeta
        predominant_race: Raza predominante
        min_level: Nivel mínimo
        max_level: Nivel máximo

    Returns:
        Lista de candidatos generados
    """
    context = RecruitmentContext(
        player_id=player_id,
        location_planet_id=location_planet_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )

    candidates = []
    existing_names: List[str] = []

    for _ in range(pool_size):
        try:
            character = generate_random_character_with_ai(context, existing_names)
            candidates.append(character)
            existing_names.append(character["nombre"])
        except Exception as e:
            log_event(f"Error generando candidato: {e}", player_id, is_error=True)

    return candidates
