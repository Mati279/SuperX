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
import re
import traceback
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

AGE_MIN = 16
AGE_MAX = 70
PREDOMINANT_RACE_CHANCE = 0.5
DEFAULT_RANK = "Iniciado"

# Prompt ENDURECIDO para evitar errores de JSON
IDENTITY_GENERATION_PROMPT = """
Actúa como un Oficial de Reclutamiento Veterano de una facción galáctica.
Genera la identidad para un nuevo operativo con estos datos:

DATOS TÉCNICOS:
- Raza: {race}
- Clase: {char_class}
- Nivel: {level}
- Sexo: {sex}
- Edad: {age} años
- Personalidad: {traits}
- Atributos top: {top_attributes}

INSTRUCCIONES:
1. Genera NOMBRE y APELLIDO adecuados a la raza.
2. Escribe una BIOGRAFÍA (50-80 palabras) con trasfondo, perfil psicológico y rol táctico.

⚠️ REGLAS CRÍTICAS DE FORMATO JSON ⚠️
1. Responde ÚNICAMENTE con un objeto JSON válido. Nada de markdown, nada de ```json.
2. **PROHIBIDO** usar comillas dobles (") DENTRO de los textos. Usa comillas simples (') si es necesario.
   - MAL: "biografia": "Dijo "hola" y se fue"
   - BIEN: "biografia": "Dijo 'hola' y se fue"
3. El texto de la biografía debe ser UNA SOLA LÍNEA, sin saltos de línea reales.

ESTRUCTURA REQUERIDA:
{{
  "nombre": "NombreDelPj",
  "apellido": "ApellidoDelPj",
  "biografia": "Texto continuo de la biografía sin comillas dobles internas."
}}
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
    biografia: str


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
    
    return GeneratedIdentity(
        nombre=random.choice(sex_names),
        apellido=random.choice(surnames),
        biografia=f"{race} reclutado recientemente. Identidad provisional por fallo de enlace neuronal."
    )


def _sanitize_json_output(text: str) -> str:
    """
    Limpia y repara strings JSON rotos comunes antes del parseo.
    """
    if not text:
        return "{}"
    
    # 1. Quitar bloques de código Markdown
    text = re.sub(r"```(?:json)?", "", text)
    text = text.replace("```", "")
    
    # 2. Recortar espacios
    text = text.strip()
    
    # 3. Intentar extraer el objeto JSON principal
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    
    # 4. Eliminar "Trailing Commas" (coma antes de cierre de llave o corchete)
    #    Ej: { "a": 1, } -> { "a": 1 }
    text = re.sub(r",\s*\}", "}", text)
    text = re.sub(r",\s*\]", "]", text)
    
    # 5. Intentar arreglar saltos de línea literales dentro de strings (muy común que rompa JSON)
    #    Reemplaza saltos de línea reales por espacios, excepto si parecen formato
    text = text.replace("\n", " ")
    
    return text


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
    Versión síncrona de generación de identidad con IA con manejo robusto de errores.
    """
    container = get_service_container()

    if not container.is_ai_available():
        print("⚠️ IA no disponible. Usando fallback.")
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

    raw_response_text = ""
    sanitized_text = ""

    try:
        # Aumentamos max_output_tokens para evitar cortes (Unterminated string)
        response = ai_client.models.generate_content(
            model=TEXT_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=800,  # AUMENTADO de 600
                response_mime_type="application/json"
            )
        )

        if response and response.text:
            raw_response_text = response.text
            
            # Intento de limpieza
            sanitized_text = _sanitize_json_output(raw_response_text)
            
            # Parseo con strict=False para ser más tolerante
            data = json.loads(sanitized_text, strict=False)
            
            return GeneratedIdentity(
                nombre=data.get("nombre", "SinNombre"),
                apellido=data.get("apellido", ""),
                biografia=data.get("biografia", f"{race} {char_class}.")
            )
        else:
            log_event("IA retornó respuesta vacía.", is_error=True)

    except json.JSONDecodeError as e:
        # LOGGING DETALLADO PARA DEBUG
        error_msg = f"❌ JSON PARSE ERROR: {str(e)}"
        print(f"\n{error_msg}")
        print(f"--- RAW TEXT ---\n{raw_response_text}\n----------------")
        print(f"--- SANITIZED ---\n{sanitized_text}\n----------------")
        
        # Registrar en la base de datos de logs para persistencia
        log_event(f"Error generando personaje. JSON corrupto: {str(e)}. Ver consola para raw.", is_error=True)
        
    except Exception as e:
        # Otros errores (red, modelo no encontrado, etc)
        print(f"🔴 ERROR CRÍTICO IA: {traceback.format_exc()}")
        log_event(f"Error crítico IA: {str(e)}", is_error=True)

    # Si algo falló, SIEMPRE devolvemos fallback para no romper el juego
    print("⚠️ Ejecutando Fallback Identity por error previo.")
    return _generate_fallback_identity(race, sex)


# Async wrapper si fuera necesario (mantenido por compatibilidad)
async def _generate_identity_with_ai(
    race: str, char_class: str, level: int, sex: BiologicalSex, age: int, traits: List[str], attributes: Dict[str, int]
) -> GeneratedIdentity:
    return generate_identity_with_ai_sync(race, char_class, level, sex, age, traits, attributes)


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

    # Generación de identidad
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
    while full_name in existing_names and attempts < 5:
        fallback_id = _generate_fallback_identity(race_name, sex)
        # Mantener la biografía rica si la original fue de IA y válida
        new_bio = identity.biografia if "Identidad provisional" not in identity.biografia else fallback_id.biografia
        identity = GeneratedIdentity(fallback_id.nombre, fallback_id.apellido, new_bio)
        full_name = f"{identity.nombre} {identity.apellido}"
        attempts += 1

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