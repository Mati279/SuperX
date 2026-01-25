# services/character_generation_service.py (Completo)
"""
Servicio de Generación de Personajes con IA.
Actualizado para Especialización de Personajes de Alto Nivel y Biografías Coherentes.
Implementa distribución ponderada de atributos y habilidades según la clase.
Debug v2.4: Implementada reparación de JSON robusta y refuerzo de prompt para escape de comillas.
Actualizado v5.1.0: Biografía consolidada de 3 niveles y limpieza de campos legacy.
Actualizado v5.1.6: Soporte para 'initial_knowledge_level' en reclutamiento directo.
Actualizado v5.2.0: Restricción de Origen a Biomas Habitables y mejora de Lore.
Corrección v5.2.1: Uso de cliente Supabase para consultas de planetas (Fix ImportError).
Actualizado V9.0: Soporte para coordenadas precisas (Hero Spawn) en RecruitmentContext.
Refactorizado V10: Inyección de coordenadas SQL en diccionario de retorno y limpieza de JSON.
Actualizado V10.1: Resolución automática de coordenadas de base en generación de pool y reclutamiento.
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

from data.database import get_service_container, get_supabase
from data.log_repository import log_event
from data.character_repository import create_character
from data.planet_repository import get_planet_by_id, get_player_base_coordinates
from data.world_repository import get_world_state
from utils.helpers import clean_json_string, try_repair_json

from core.constants import RACES, CLASSES, SKILL_MAPPING
from core.world_constants import HABITABLE_BIRTH_BIOMES
from core.rules import calculate_skills
from core.models import BiologicalSex, CharacterRole, KnowledgeLevel, CharacterStatus
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
    BIO_ACCESS_UNKNOWN,
)

from config.app_constants import TEXT_MODEL_NAME


# =============================================================================
# CONSTANTES DE GENERACIÓN
# =============================================================================

AGE_MIN = 16
AGE_MAX = 70
PREDOMINANT_RACE_CHANCE = 0.5
DEFAULT_RANK = "Iniciado"

# Prompt actualizado para Gemini 2.0 Flash con refuerzo de seguridad JSON
IDENTITY_GENERATION_PROMPT = """
Actúa como un Oficial de Inteligencia de una facción galáctica.
Genera el dossier para un nuevo operativo altamente especializado.

DATOS TÉCNICOS:
- Raza: {race}
- Clase: {char_class}
- Nivel: {level}
- Sexo: {sex}
- Edad: {age} años
- Personalidad: {traits}
- Origen: Nacido en {birth_planet} ({birth_biome})
- Atributos clave: {top_attributes}
- Especialidades técnicas (Habilidades): {top_skills}

INSTRUCCIONES DE GENERACIÓN (3 NIVELES):
1. NOMBRE y APELLIDO: Coherentes con la raza.
2. BIOGRAFIA CORTA (Público - 1 oración): Solo una descripción visual o impresión rápida.
3. BIO CONOCIDA (Estándar - 40 palabras aprox): Resumen profesional. DEBE mencionar su origen en {birth_planet} y cómo el entorno ({birth_biome}) influyó en sus habilidades.
4. BIO PROFUNDA (Privado - 60-80 palabras): Secretos, traumas o motivaciones ocultas.

⚠️ INSTRUCCIÓN ESPECIAL: 'apariencia_visual' (ADN VISUAL) ⚠️
Genera una descripción técnica densa (NO narrativa) de sus rasgos físicos inmutables.
Debe incluir:
- ROSTRO: Estructura ósea, textura de piel, detalles exactos de ojos (color, implantes).
- CABELLO: EstILO, textura (ej: wet-look), corte exacto.
- CUERPO: Constitución, cibernética visible (materiales, luces), cicatrices.
- ATUENDO: Tejidos específicos (ej: cuero de búfalo desgastado), marcas de uso, logotipos.
DENSIDAD OBJETIVO: ~80-100 palabras. Estilo "Prompt de Stable Diffusion/Midjourney".

REGLAS TÉCNICAS:
- Responde SOLO con JSON válido.
- CRITICAL: Escape all double quotes inside text fields with backslashes (\\") and avoid newlines within strings.
- Si necesitas usar comillas dentro de un texto, usa comillas simples (') obligatoriamente.
"""


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

@dataclass
class RecruitmentContext:
    player_id: Optional[int] # Puede ser None para pools globales/locales
    location_planet_id: Optional[int] = None
    location_system_id: Optional[int] = None # V9.0: Coordenada explícita
    location_sector_id: Optional[int] = None # V9.0: Coordenada explícita
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
    apariencia_visual: str 


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _get_top_attributes(attributes: Dict[str, int], count: int = 2) -> str:
    sorted_attrs = sorted(attributes.items(), key=lambda x: x[1], reverse=True)
    top = sorted_attrs[:count]
    return ", ".join([f"{attr.capitalize()}: {val}" for attr, val in top])

def _get_top_skills(skills: Dict[str, int], count: int = 3) -> str:
    sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
    top = sorted_skills[:count]
    return ", ".join([f"{name} ({val})" for name, val in top])


def _generate_base_attributes() -> Dict[str, int]:
    return {
        "fuerza": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "agilidad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "tecnica": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "intelecto": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "voluntad": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
        "presencia": random.randint(BASE_ATTRIBUTE_MIN, BASE_ATTRIBUTE_MAX),
    }


def _distribute_random_points(attributes: Dict[str, int], points: int, primary_attr: Optional[str] = None) -> None:
    attr_keys = list(attributes.keys())
    for _ in range(points):
        if primary_attr and primary_attr in attributes and random.random() < 0.7:
            target_attr = primary_attr
        else:
            target_attr = random.choice(attr_keys)
        if attributes[target_attr] < MAX_ATTRIBUTE_VALUE:
            attributes[target_attr] += 1


def _boost_skills(skills: Dict[str, int], points: int, primary_attr: Optional[str] = None) -> Dict[str, int]:
    skill_keys = list(skills.keys())
    boosted = skills.copy()
    linked_skills = []
    if primary_attr:
        for skill_name, (attr1, attr2) in SKILL_MAPPING.items():
            if skill_name in boosted and (attr1 == primary_attr or attr2 == primary_attr):
                linked_skills.append(skill_name)
    for _ in range(points):
        if linked_skills and random.random() < 0.6:
            skill = random.choice(linked_skills)
        else:
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


def _select_birth_planet(preferred_system_id: Optional[int] = None) -> tuple[str, str]:
    """
    Selecciona un planeta de origen que cumpla con las condiciones de habitabilidad.
    Utiliza el cliente Supabase para consultas seguras.
    """
    db = get_supabase()
    
    # 1. Intentar encontrar planeta habitable en el sistema actual
    if preferred_system_id:
        try:
            response = db.table("planets")\
                .select("name, biome")\
                .eq("system_id", preferred_system_id)\
                .in_("biome", HABITABLE_BIRTH_BIOMES)\
                .limit(20)\
                .execute()
            
            candidates = response.data
            if candidates:
                choice = random.choice(candidates)
                return choice["name"], choice["biome"]
        except Exception as e:
            # Fallback silencioso si falla la consulta local
            pass
    
    # 2. Fallback: Cualquier planeta habitable de la galaxia (Sample random)
    try:
        response = db.table("planets")\
            .select("name, biome")\
            .in_("biome", HABITABLE_BIRTH_BIOMES)\
            .limit(50)\
            .execute()
        
        candidates = response.data
        if candidates:
            choice = random.choice(candidates)
            return choice["name"], choice["biome"]
            
    except Exception as e:
        log_event(f"Error seleccionando planeta de origen (Fallback): {e}", is_error=True)

    # 3. Fallback Último Recurso
    return "Estación Espacial Nómada", "Artificial"


def _calculate_recruitment_cost(stats_json: Dict[str, Any]) -> int:
    try:
        level = stats_json.get("progresion", {}).get("nivel", 1)
        attributes = stats_json.get("capacidades", {}).get("atributos", {})
        base_cost = 50
        level_cost = level * 50
        total_attributes = sum(attributes.values())
        attr_cost = total_attributes * 3
        return base_cost + level_cost + attr_cost
    except Exception:
        return 100


def _generate_fallback_identity(race: str, sex: BiologicalSex) -> GeneratedIdentity:
    """Genera identidades con las 3 capas si la IA falla. ADN Visual incluido."""
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
        bio_superficial=f"{race} de aspecto estándar.",
        bio_conocida=f"Operativo {race} reclutado recientemente. Su expediente indica habilidades básicas.",
        bio_profunda=f"ARCHIVOS CORRUPTOS. Hay menciones a una operación fallida.",
        apariencia_visual=f"{race} estándar con uniforme táctico básico. Complexión atlética, mirada neutral." 
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
    attributes: Dict[str, int],
    skills: Dict[str, int],
    birth_planet: str,
    birth_biome: str
) -> GeneratedIdentity:
    """
    Versión síncrona con logging extendido y manejo de errores legible.
    Utiliza try_repair_json para robustecer el parsing ante respuestas truncadas.
    """
    container = get_service_container()

    if not container.is_ai_available():
        log_event("AI_WARNING: API Gemini no detectada. Usando fallback.", is_error=True)
        return _generate_fallback_identity(race, sex)

    ai_client = container.ai

    prompt = IDENTITY_GENERATION_PROMPT.format(
        race=race,
        char_class=char_class,
        level=level,
        sex=sex.value,
        age=age,
        traits=", ".join(traits),
        top_attributes=_get_top_attributes(attributes),
        top_skills=_get_top_skills(skills),
        birth_planet=birth_planet,
        birth_biome=birth_biome
    )

    identity_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "nombre": types.Schema(type=types.Type.STRING),
            "apellido": types.Schema(type=types.Type.STRING),
            "bio_superficial": types.Schema(type=types.Type.STRING),
            "bio_conocida": types.Schema(type=types.Type.STRING),
            "bio_profunda": types.Schema(type=types.Type.STRING),
            "apariencia_visual": types.Schema(type=types.Type.STRING),
        },
        required=["nombre", "apellido", "bio_superficial", "bio_conocida", "bio_profunda", "apariencia_visual"]
    )

    generation_config = types.GenerateContentConfig(
        temperature=0.85,
        max_output_tokens=1500,
        response_mime_type="application/json",
        response_schema=identity_schema
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            log_event(f"AI_DEBUG: Llamando a Gemini (Intento {attempt+1})...")
            response = ai_client.models.generate_content(
                model=TEXT_MODEL_NAME,
                contents=prompt,
                config=generation_config
            )

            if response and response.text:
                # Intentamos reparación inteligente de JSON antes de desistir
                data = try_repair_json(response.text)
                
                if data:
                    log_event(f"AI_DEBUG: Identidad generada para {data.get('nombre')}.")
                    return GeneratedIdentity(
                        nombre=data.get("nombre", "SinNombre"),
                        apellido=data.get("apellido", ""),
                        bio_superficial=data.get("bio_superficial", f"{race} con aspecto preparado."),
                        bio_conocida=data.get("bio_conocida", f"Historial estándar de {char_class}."),
                        bio_profunda=data.get("bio_profunda", "Sin secretos registrados."),
                        apariencia_visual=data.get("apariencia_visual", "") 
                    )
                else:
                    log_event(f"AI_ERROR: Fallo crítico de parseo/reparación (Intento {attempt+1}). Raw: {response.text[:100]}...", is_error=True)
                    continue
        except Exception as e:
            log_event(f"AI_CRITICAL: Error en generate_content: {str(e)}", is_error=True)
            time.sleep(1)

    log_event("AI_DEBUG: Falló generación IA tras reintentos. Usando fallback.", is_error=True)
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
    
    primary_attr = class_data.get("bonus_attr")
    age = random.randint(AGE_MIN, AGE_MAX)
    sex = random.choice([BiologicalSex.MALE, BiologicalSex.FEMALE])
    
    attributes = _generate_base_attributes()
    
    # Aplicar bonus de raza
    for attr, bonus in race_data.get("bonus", {}).items():
        if attr in attributes:
            attributes[attr] = min(attributes[attr] + bonus, MAX_ATTRIBUTE_VALUE)
    
    # Bonus de clase primaria
    if class_name != "Novato" and primary_attr:
        if primary_attr in attributes:
            attributes[primary_attr] = min(attributes[primary_attr] + 1, MAX_ATTRIBUTE_VALUE)
            
    extra_attr_points = sum(1 for lvl in ATTRIBUTE_POINT_LEVELS if lvl <= level)
    _distribute_random_points(attributes, extra_attr_points, primary_attr)
    
    skills = calculate_skills(attributes)
    skill_points = level * SKILL_POINTS_PER_LEVEL
    skills = _boost_skills(skills, skill_points, primary_attr)
    
    num_feats = sum(1 for lvl in FEAT_LEVELS if lvl <= level)
    feats = random.sample(AVAILABLE_FEATS, min(num_feats, len(AVAILABLE_FEATS)))
    traits = random.sample(PERSONALITY_TRAITS, k=2)

    # --- SELECCIÓN DE PLANETA DE ORIGEN Y UBICACIÓN ACTUAL ---
    # V9.0: Priorizamos coordenadas explícitas del contexto si existen (Hero Spawn)
    # Refactor V10: Eliminado default "Barracones" - usar nombre del planeta
    location_system_id = context.location_system_id
    location_sector_id = context.location_sector_id
    location_name = None  # Se asignará desde el planeta
    system_name = "Desconocido"
    planet_id_for_spawn = context.location_planet_id

    if planet_id_for_spawn:
        try:
            planet_info = get_planet_by_id(planet_id_for_spawn)
            if planet_info:
                # Usar nombre del planeta como ubicación local (no string genérico)
                location_name = planet_info.get("name", "Base")
                if not location_system_id:
                    location_system_id = planet_info.get("system_id")
                system_name = f"Sistema {location_system_id}"
        except Exception: pass

    # Fallback: Si no hay nombre, usar "Centro de Reclutamiento" (contexto de pool)
    if not location_name:
        location_name = "Centro de Reclutamiento"
    
    # Determinar planeta de nacimiento válido (Habitable)
    # Puede ser distinto de la ubicación actual
    birth_planet, birth_biome = _select_birth_planet(location_system_id)

    identity = generate_identity_with_ai_sync(
        race=race_name,
        char_class=class_name,
        level=level,
        sex=sex,
        age=age,
        traits=traits,
        attributes=attributes,
        skills=skills,
        birth_planet=birth_planet,
        birth_biome=birth_biome
    )

    # --- LÓGICA DE RESOLUCIÓN DE COLISIONES ---
    full_name = f"{identity.nombre} {identity.apellido}"
    attempts = 0
    max_attempts = 10

    while full_name in existing_names and attempts < max_attempts:
        fallback_id = _generate_fallback_identity(race_name, sex)
        suffix = f"-{random.randint(100, 999)}" if attempts > 3 else ""
        identity = GeneratedIdentity(
            fallback_id.nombre, fallback_id.apellido + suffix,
            identity.bio_superficial, identity.bio_conocida, identity.bio_profunda, identity.apariencia_visual
        )
        full_name = f"{identity.nombre} {identity.apellido}"
        attempts += 1

    if full_name in existing_names:
        uuid_suffix = str(uuid.uuid4())[:4].upper()
        identity = GeneratedIdentity(
            identity.nombre, f"{identity.apellido}-{uuid_suffix}",
            identity.bio_superficial, identity.bio_conocida, identity.bio_profunda, identity.apariencia_visual
        )
        full_name = f"{identity.nombre} {identity.apellido}"
        log_event(f"Character name collision resolved with UUID: {full_name}", context.player_id)

    stats_json = {
        "bio": {
            "nombre": identity.nombre,
            "apellido": identity.apellido,
            "edad": age,
            "sexo": sex.value,
            # Mapeo consolidado v5.1.0 (Sin bio_superficial)
            "biografia_corta": identity.bio_superficial,
            "bio_conocida": identity.bio_conocida,
            "bio_profunda": identity.bio_profunda,
            "apariencia_visual": identity.apariencia_visual,
            "origen": {
                "planeta": birth_planet,
                "bioma": birth_biome
            },
            "nivel_acceso": BIO_ACCESS_UNKNOWN,
            "ticks_reclutado": 0,
            "ticks_como_conocido": 0,
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
            "sistema_actual": system_name,
            "ubicacion_local": location_name,
            "rol_asignado": CharacterRole.NONE.value,
            "accion_actual": "Esperando asignación",
            # NOTA V10: Se mantiene temporalmente para que el repositorio extraiga los datos a SQL.
            # La función _extract_and_clean_data en character_repository.py se encargará de
            # hacer el pop() de este diccionario para que NO persista en el JSON final.
            "ubicacion": { 
                "system_id": location_system_id,
                "planet_id": context.location_planet_id,
                "sector_id": location_sector_id,
                "ubicacion_local": location_name
            }
        }
    }

    return {
        "nombre": full_name,
        "rango": DEFAULT_RANK,
        "estado": "Disponible",
        "ubicacion": location_name,
        "es_comandante": False,
        "location_system_id": location_system_id, # Inyectado para DB
        "location_planet_id": context.location_planet_id, # Inyectado para DB
        "location_sector_id": location_sector_id, # Inyectado para DB (Refactor V10)
        "stats_json": stats_json
    }

def recruit_character_with_ai(
    player_id: int,
    location_planet_id: Optional[int] = None,
    location_system_id: Optional[int] = None, # V9.0
    location_sector_id: Optional[int] = None, # V9.0
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1,
    existing_names: Optional[List[str]] = None,
    initial_knowledge_level: Optional[KnowledgeLevel] = None
) -> Optional[Dict[str, Any]]:
    """
    Recluta un personaje directamente (sin pasar por pool de candidatos).
    Soporta initial_knowledge_level para tripulación inicial y coordenadas precisas para Hero Spawn.
    V10.1: Resolución automática de coordenadas de base si no se especifican.
    """
    # --- V10.1: Fallback a coordenadas de base ---
    if not location_planet_id and player_id:
        try:
            base_coords = get_player_base_coordinates(player_id)
            if base_coords.get("planet_id"):
                location_system_id = base_coords.get("system_id")
                location_planet_id = base_coords.get("planet_id")
                location_sector_id = base_coords.get("sector_id")
        except Exception:
            pass # Fallback silencioso

    context = RecruitmentContext(
        player_id=player_id,
        location_planet_id=location_planet_id,
        location_system_id=location_system_id,
        location_sector_id=location_sector_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )
    try:
        character_data = generate_random_character_with_ai(context, existing_names)
        
        # Inyectar nivel de conocimiento inicial si se proporciona
        if initial_knowledge_level:
            character_data["initial_knowledge_level"] = initial_knowledge_level
            
        result = create_character(player_id, character_data)
        if result:
            log_event(f"Reclutado: {character_data['nombre']} ({character_data['stats_json']['taxonomia']['raza']}) - Nivel: {min_level}", player_id)
            return result
        return None
    except Exception as e:
        log_event(f"Error en reclutamiento con IA: {e}", player_id, is_error=True)
        raise e

def generate_character_pool(
    player_id: Optional[int],
    pool_size: int = 3,
    location_planet_id: Optional[int] = None,
    location_system_id: Optional[int] = None,
    location_sector_id: Optional[int] = None,
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1,
    force_max_skills: bool = False
) -> List[Dict[str, Any]]:
    """
    Genera un pool de candidatos para reclutamiento.
    Refactor V10: Soporta coordenadas completas de ubicación (system, planet, sector).
    V10.1: Resolución automática de coordenadas de base si no se especifican.
    """
    # --- V10.1: Fallback a coordenadas de base ---
    # Esto asegura que los reclutas aparezcan en el Centro de Reclutamiento de la Base
    if not location_planet_id and player_id:
        try:
            base_coords = get_player_base_coordinates(player_id)
            if base_coords.get("planet_id"):
                location_system_id = base_coords.get("system_id")
                location_planet_id = base_coords.get("planet_id")
                location_sector_id = base_coords.get("sector_id")
        except Exception:
            pass # Fallback silencioso

    context = RecruitmentContext(
        player_id=player_id,
        location_planet_id=location_planet_id,
        location_system_id=location_system_id,
        location_sector_id=location_sector_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )
    
    try:
        state = get_world_state()
        current_tick = state.get('current_tick', 1)
    except Exception: current_tick = 1

    candidates = []
    existing_names: List[str] = []
    
    log_event(f"SISTEMA: Generando pool de {pool_size} candidatos.", player_id)

    for i in range(pool_size):
        try:
            char_data = generate_random_character_with_ai(context, existing_names)
            char_data["ubicacion"] = "Centro de Reclutamiento"

            if force_max_skills:
                skills_dict = char_data.get("stats_json", {}).get("capacidades", {}).get("habilidades", {})
                for s in skills_dict: skills_dict[s] = 99
            
            cost = _calculate_recruitment_cost(char_data["stats_json"])
            char_data["stats_json"]["recruitment_data"] = {
                "costo": cost,
                "tick_created": current_tick,
                "is_tracked": False,
                "is_being_investigated": False,
                "investigation_outcome": None,
                "discount_applied": False
            }
            
            char_data["estado"] = CharacterStatus.CANDIDATE.value
            char_data["initial_knowledge_level"] = KnowledgeLevel.UNKNOWN
            
            saved_candidate = create_character(player_id, char_data)
            
            if saved_candidate:
                saved_candidate["costo"] = cost 
                candidates.append(saved_candidate)
                existing_names.append(saved_candidate["nombre"])
        except Exception as e:
            log_event(f"Error crítico generando candidato {i+1}: {e}", player_id, is_error=True)
            continue
            
    return candidates