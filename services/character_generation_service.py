# services/character_generation_service.py
"""
Servicio de Generación de Personajes con IA.
Actualizado para generar Biografías Escalonadas (Tiered Biography System).
"""

import random
import json
import re
import traceback
import time
import uuid
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
    FEAT_LEVELS,
    BIO_ACCESS_SUPERFICIAL # Constante de acceso
)

from config.app_constants import TEXT_MODEL_NAME


# =============================================================================
# CONSTANTES DE GENERACIÓN
# =============================================================================

AGE_MIN = 16
AGE_MAX = 70
PREDOMINANT_RACE_CHANCE = 0.5
DEFAULT_RANK = "Iniciado"

# Prompt actualizado para 3 niveles de biografía estrictos
IDENTITY_GENERATION_PROMPT = """
Actúa como un Oficial de Inteligencia de una facción galáctica.
Genera el dossier para un nuevo operativo.

DATOS TÉCNICOS:
- Raza: {race}
- Clase: {char_class}
- Nivel: {level}
- Sexo: {sex}
- Edad: {age} años
- Personalidad: {traits}
- Atributos top: {top_attributes}

INSTRUCCIONES DE GENERACIÓN (3 NIVELES):
1. NOMBRE y APELLIDO: Coherentes con la raza.
2. BIO SUPERFICIAL (Público - 1 oración): Solo una descripción visual o impresión rápida. Ej: "Humano robusto con cicatrices de combate, mirada cansada." o "Androide de serie brillante, movimientos precisos."
3. BIO CONOCIDA (Estándar - 40 palabras aprox): Resumen profesional para el expediente. Formación, especialidad táctica y evaluación de desempeño.
4. BIO PROFUNDA (Privado - 60-80 palabras): Secretos, ganchos narrativos, traumas pasados o motivaciones ocultas que podrían derivar en misiones personales.

⚠️ REGLAS TÉCNICAS ⚠️
- Responde SOLO con JSON válido.
- NO uses comillas dobles (") dentro de los textos.
"""


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

@dataclass
class RecruitmentContext:
    player_id: int
    location_planet_id: Optional[int] = None
    predominant_race: Optional[str] = None
    min_level: int = 1
    max_level: int = 1
    force_race: Optional[str] = None
    force_class: Optional[str] = None


@dataclass
class GeneratedIdentity:
    nombre: str
    apellido: str
    bio_superficial: str
    bio_conocida: str
    bio_profunda: str


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _get_top_attributes(attributes: Dict[str, int], count: int = 2) -> str:
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top = sorted_attrs[:count]
    return ", ".join([f"{attr.capitalize()}: {val}" for attr, val in top])


def _generate_base_attributes() -> Dict[str, int]:
    return {
        "fuerza": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "agilidad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "tecnica": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "intelecto": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "voluntad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "presencia": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
    }


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
        if skill_keys:
            skill = random.choice(skill_keys)
            boosted[skill] += 1
    return boosted


def _select_race(context: RecruitmentContext) -> tuple[str, Dict[str, Any]]:
    if context.force_race and context.force_race in RACES:
        return context.force_race, RACES[context.force_race]
    if context.predominant_race and random.random() < PREDOMINANT_RACE_CHANCE:
        if context.predominant_race in RACES:
            return context.predominant_race, RACES[context.predominant_race]
    race_name, race_data = random.choice(list(RACES.items()))
    return race_name, race_data


def _select_class(level: int, force_class: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
    if force_class and force_class in CLASSES:
        return force_class, CLASSES[force_class]
    if level < 3:
        return "Novato", {"desc": "Recién reclutado, aún sin especialización.", "bonus_attr": None}
    class_name, class_data = random.choice(list(CLASSES.items()))
    return class_name, class_data


def _generate_fallback_identity(race: str, sex: BiologicalSex) -> GeneratedIdentity:
    """Genera identidades con las 3 capas si la IA falla."""
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
    surnames = ["Voss", "Riker", "Thorne", "Stark", "Chen", "Vale", "Kross", "Pike", "Sol"]
    
    race_names = names_by_race.get(race, names_by_race["Humano"])
    sex_names = race_names.get(sex, race_names[BiologicalSex.MALE])
    
    name = random.choice(sex_names)
    surname = random.choice(surnames)

    return GeneratedIdentity(
        nombre=name,
        apellido=surname,
        bio_superficial=f"{race} de aspecto estándar. Parece competente.",
        bio_conocida=f"Operativo {race} reclutado recientemente. Su expediente indica habilidades básicas de combate y adaptación a entornos hostiles.",
        bio_profunda=f"ARCHIVOS CORRUPTOS. Hay menciones a una operación fallida en el sector 7, pero los detalles han sido borrados intencionalmente."
    )


# =============================================================================
# GENERACIÓN DE IDENTIDAD CON IA
# =============================================================================

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
    Versión síncrona de generación de identidad con IA usando Schema Estricto para 3 BIOS.
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

    # 1. Schema Estricto para las 3 biografías
    identity_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "nombre": types.Schema(type=types.Type.STRING),
            "apellido": types.Schema(type=types.Type.STRING),
            "bio_superficial": types.Schema(type=types.Type.STRING, description="Máx 1 oración. Visual/Hint."),
            "bio_conocida": types.Schema(type=types.Type.STRING, description="Perfil profesional. 40 palabras."),
            "bio_profunda": types.Schema(type=types.Type.STRING, description="Secretos y ganchos de misión."),
        },
        required=["nombre", "apellido", "bio_superficial", "bio_conocida", "bio_profunda"]
    )

    # 2. Configuración
    safety_config = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE
        ),
    ]

    generation_config = types.GenerateContentConfig(
        temperature=0.85,
        max_output_tokens=1200,
        response_mime_type="application/json",
        response_schema=identity_schema,
        safety_settings=safety_config
    )

    # 3. Loop de Reintentos
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = ai_client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=prompt,
                config=generation_config
            )

            if response and response.text:
                try:
                    data = json.loads(response.text)
                    return GeneratedIdentity(
                        nombre=data.get("nombre", "SinNombre"),
                        apellido=data.get("apellido", ""),
                        bio_superficial=data.get("bio_superficial", f"{race} con aspecto preparado."),
                        bio_conocida=data.get("bio_conocida", f"Historial estándar de {char_class}."),
                        bio_profunda=data.get("bio_profunda", "Sin secretos registrados.")
                    )
                except json.JSONDecodeError:
                    continue
        except Exception:
            time.sleep(1)

    log_event(f"Fallo generación IA (3 layers). Usando fallback.", is_error=True)
    return _generate_fallback_identity(race, sex)


# =============================================================================
# FUNCIÓN PRINCIPAL DE GENERACIÓN
# =============================================================================

def generate_random_character_with_ai(
    context: RecruitmentContext,
    existing_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    existing_names = existing_names or []
    level = random.randint(context.min_level, context.max_level)
    xp = get_xp_for_level(level)
    race_name, race_data = _select_race(context)
    class_name, class_data = _select_class(level, context.force_class)
    age = random.randint(AGE_MIN, AGE_MAX)
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

    # Generación de identidad (3 Capas)
    identity = generate_identity_with_ai_sync(
        race=race_name,
        char_class=class_name,
        level=level,
        sex=sex,
        age=age,
        traits=traits,
        attributes=attributes
    )

    full_name = f"{identity.nombre} {identity.apellido}"
    attempts = 0
    max_attempts = 10

    while full_name in existing_names and attempts < max_attempts:
        fallback_id = _generate_fallback_identity(race_name, sex)
        # Add numeric suffix after first few attempts
        suffix = f"-{random.randint(100, 999)}" if attempts > 3 else ""
        identity = GeneratedIdentity(
            fallback_id.nombre, fallback_id.apellido + suffix,
            identity.bio_superficial, identity.bio_conocida, identity.bio_profunda
        )
        full_name = f"{identity.nombre} {identity.apellido}"
        attempts += 1

    # Final fallback: add UUID suffix to guarantee uniqueness
    if full_name in existing_names:
        uuid_suffix = str(uuid.uuid4())[:4].upper()
        identity = GeneratedIdentity(
            identity.nombre, f"{identity.apellido}-{uuid_suffix}",
            identity.bio_superficial, identity.bio_conocida, identity.bio_profunda
        )
        full_name = f"{identity.nombre} {identity.apellido}"
        log_event(f"Character name collision resolved with UUID: {full_name}", context.player_id)

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

    # Estructura JSON actualizada con las 3 capas
    stats_json = {
        "bio": {
            "nombre": identity.nombre,
            "apellido": identity.apellido,
            "edad": age,
            "sexo": sex.value,
            # Campo legacy: Ahora apunta a SUPERFICIAL (la corta)
            "biografia_corta": identity.bio_superficial,
            # Nuevos campos
            "bio_superficial": identity.bio_superficial,
            "bio_conocida": identity.bio_conocida,
            "bio_profunda": identity.bio_profunda,
            "nivel_acceso": BIO_ACCESS_SUPERFICIAL,
            "ticks_reclutado": 0
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
    # Wrapper simple
    context = RecruitmentContext(
        player_id=player_id,
        location_planet_id=location_planet_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )
    try:
        character_data = generate_random_character_with_ai(context, existing_names)
        result = create_character(player_id, character_data)
        if result:
            log_event(
                f"Reclutado: {character_data['nombre']} ({character_data['stats_json']['taxonomia']['raza']})",
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
    # Wrapper simple
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