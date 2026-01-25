# data/character_repository.py (Completo)
"""
Repositorio de Personajes.
Gestiona la persistencia de personajes usando el modelo V2 Híbrido (SQL + JSON).
Implementa el patrón Extract & Clean para sincronizar columnas SQL con metadatos JSON.
Actualizado v5.1.4: Estandarización de IDs de Roles (Fix Error 22P02).
Actualizado v5.1.5: Fix Error Reclutamiento (recruit_candidate_db).
Actualizado v5.1.6: Garantía de KnowledgeLevel en creación.
Actualizado v5.1.7: Corrección de mapeo SQL en sistema de conocimiento (observer_player_id).
Actualizado v5.1.8: Persistencia robusta de KnowledgeLevel (Fix Source of Truth).
Actualizado v5.1.9: Fix Critical Mismatch Column (observer_player_id -> player_id).
Actualizado v5.2.0: Fix ImportError COMMANDER_LOCATION (Refactorización de Ubicaciones).
Actualizado v5.2.1: Soporte para actualización de ubicacion_local en reclutamiento.
Refactorizado v10.0: Purga de ubicación en JSON (Ubicación SQL como Source of Truth).
"""

from typing import Dict, Any, Optional, List, Tuple
import copy
from data.database import get_supabase
from data.log_repository import log_event


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()

# Importamos KnowledgeLevel para tipado y validación
from core.models import BiologicalSex, CharacterRole, KnowledgeLevel, CommanderData
from core.rules import calculate_skills
from config.app_constants import (
    COMMANDER_RANK,
    COMMANDER_STATUS
)

# --- CONSTANTES DE MAPEO ---
CLASS_ID_MAP = {
    "Novato": 0, "Soldado": 1, "Piloto": 2, "Ingeniero": 3, 
    "Diplomático": 4, "Espía": 5, "Hacker": 6, "Comandante": 99,
    "Desconocida": 0
}

# MAPEO DE ROLES A IDS (Fix v5.1.4)
ROLE_ID_MAP = {
    "Sin Asignar": 0,
    "Comandante": 1,
    "Piloto": 2,
    "Artillero": 3,
    "Ingeniero": 4,
    "Médico": 5,
    "Científico": 6,
    "Diplomático": 7,
    "Infante": 8
}

STATUS_ID_MAP = {
    "Disponible": 1,
    "En Misión": 2,
    "Herido": 3,
    "Fallecido": 4,
    "Entrenando": 5,
    "En Tránsito": 6,
    "Candidato": 7,
    "Retirado": 99,
    "Sin Asignar": 1
}

# --- HELPER: EXTRACT & CLEAN ---
def _extract_and_clean_data(full_stats: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    EXTRACT & CLEAN PATTERN (Refactorizado v5.1.4).
    Separa los datos que van a columnas SQL (Fuente de Verdad) de los que se quedan en JSON.
    Convierte nombres de roles a IDs numéricos para compatibilidad SQL.
    Refactor V10: Elimina la ubicación del JSON tras extraerla.
    """
    stats = copy.deepcopy(full_stats)
    columns = {}

    # 2. Extracción de Datos Biográficos
    if "bio" in stats:
        columns["nombre"] = stats["bio"].get("nombre", "Unknown")
        columns["apellido"] = stats["bio"].get("apellido", "")
        
        if "bio_superficial" in stats["bio"]:
            if not stats["bio"].get("biografia_corta"):
                stats["bio"]["biografia_corta"] = stats["bio"]["bio_superficial"]
            stats["bio"].pop("bio_superficial", None)

        if "portrait_url" in stats["bio"]:
            columns["portrait_url"] = stats["bio"].get("portrait_url")
            stats["bio"].pop("portrait_url", None)
            
        stats["bio"].pop("nombre", None)
        stats["bio"].pop("apellido", None)

    # 3. Extracción de Progresión
    if "progresion" in stats:
        columns["level"] = stats["progresion"].get("nivel", 1)
        columns["xp"] = stats["progresion"].get("xp", 0)
        columns["rango"] = stats["progresion"].get("rango", "Iniciado")
        
        clase_str = stats["progresion"].get("clase", "Novato")
        columns["class_id"] = CLASS_ID_MAP.get(clase_str, 0)
        
        stats["progresion"].pop("nivel", None)
        stats["progresion"].pop("xp", None)
        stats["progresion"].pop("rango", None)

    # 4. Extracción de Estado, Rol (ID) y Ubicación
    if "estado" in stats:
        rol_text = stats["estado"].get("rol_asignado", "Sin Asignar")
        
        # Sincronización de Rol como INTEGER ID (Fix 22P02)
        columns["rol"] = ROLE_ID_MAP.get(rol_text, 0)
        columns["estado_id"] = STATUS_ID_MAP.get(rol_text, 1)
        
        # Extracción de coordenadas SQL si existen en el JSON (para migración o creación)
        loc = stats["estado"].get("ubicacion", {})
        if isinstance(loc, dict):
            columns["location_system_id"] = loc.get("system_id")
            columns["location_planet_id"] = loc.get("planet_id")
            columns["location_sector_id"] = loc.get("sector_id")
        
        # TAREA 2: Limpieza obligatoria. La ubicación NO debe persistir en JSON.
        stats["estado"].pop("ubicacion", None)
        
        stats["estado"].pop("rol_asignado", None)
        
    # 5. Extracción de Comportamiento
    if "comportamiento" in stats:
        if "lealtad" in stats["comportamiento"]:
            columns["loyalty"] = stats["comportamiento"]["lealtad"]
            stats["comportamiento"].pop("lealtad", None)

    return columns, stats


# Helper para migración/compatibilidad
def _ensure_v2_structure(stats_json: Dict, name: str = "") -> Dict:
    """Asegura que el JSON tenga la estructura V2."""
    if "bio" in stats_json:
        return stats_json 
    
    return {
        "bio": {
            "nombre": name.split()[0] if name else "Unit",
            "apellido": name.split()[1] if name and len(name.split()) > 1 else "",
            "edad": 30,
            "sexo": "Desconocido",
            "biografia_corta": "Migrado Auto",
            "bio_conocida": "",
            "bio_profunda": ""
        },
        "taxonomia": {"raza": "Humano", "transformaciones": []},
        "progresion": {
            "nivel": 1,
            "clase": "Novato",
            "xp": 0,
            "rango": "Recluta"
        },
        "capacidades": {
            "atributos": stats_json.get("atributos", {}),
            "habilidades": stats_json.get("habilidades", {}),
            "feats": []
        },
        "comportamiento": {"rasgos_personalidad": [], "relaciones": [], "lealtad": 50},
        "logistica": {"equipo": [], "slots_ocupados": 0, "slots_maximos": 10},
        "estado": {
            "estados_activos": ["Disponible"],
            "rol_asignado": "Sin Asignar"
        }
    }

def get_commander_by_player_id(player_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("characters").select("*").eq("player_id", player_id).eq("es_comandante", True).single().execute()
        return response.data
    except Exception:
        return None

def create_commander(
    player_id: int,
    name: str,
    bio_data: Dict[str, Any],
    attributes: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """Crea un Comandante usando el esquema Híbrido V2."""
    from data.game_config_repository import get_current_tick

    try:
        habilidades = calculate_skills(attributes)
        current_tick = get_current_tick()
        
        parts = name.split(" ", 1)
        nombre_p = parts[0]
        apellido_p = parts[1] if len(parts) > 1 else ""
        
        raza = bio_data.get("raza", "Humano")
        clase = bio_data.get("clase", "Comandante")

        full_stats = {
            "bio": {
                "nombre": nombre_p,
                "apellido": apellido_p,
                "edad": bio_data.get("edad", 30),
                "sexo": bio_data.get("sexo", BiologicalSex.UNKNOWN.value),
                "biografia_corta": bio_data.get("biografia") or f"Comandante {raza}",
                "bio_conocida": "Comandante de la Flota.",
                "bio_profunda": "",
                "apariencia_visual": bio_data.get("apariencia_visual")
            },
            "taxonomia": {"raza": raza, "transformaciones": []},
            "progresion": {
                "nivel": 1,
                "clase": clase,
                "xp": 0,
                "rango": COMMANDER_RANK
            },
            "capacidades": {
                "atributos": attributes,
                "habilidades": habilidades,
                "feats": ["Liderazgo Táctico"]
            },
            "comportamiento": {
                "rasgos_personalidad": ["Liderazgo"],
                "relaciones": [],
                "lealtad": 100 
            },
            "logistica": {"equipo": [], "slots_ocupados": 0, "slots_maximos": 10},
            "estado": {
                "estados_activos": [COMMANDER_STATUS],
                "rol_asignado": CharacterRole.COMMANDER.value,
                "accion_actual": "Iniciando mandato"
                # TAREA 2: Ubicación eliminada del JSON (Manejada por SQL o valores nulos por defecto)
            }
        }

        cols, cleaned_stats = _extract_and_clean_data(full_stats)

        new_char_data = {
            "player_id": player_id,
            "es_comandante": True,
            "recruited_at_tick": current_tick,
            "stats_json": cleaned_stats,
            
            "nombre": cols.get("nombre"),
            "apellido": cols.get("apellido"),
            "rango": cols.get("rango"),
            "level": cols.get("level"),
            "xp": cols.get("xp"),
            "class_id": cols.get("class_id"),
            "estado_id": cols.get("estado_id"),
            "loyalty": cols.get("loyalty", 100),
            
            # Persistencia de ROL como ID INTEGER (Fuente: ROLE_ID_MAP)
            "rol": cols.get("rol", 1), 
            
            "location_system_id": cols.get("location_system_id"),
            "location_planet_id": cols.get("location_planet_id"),
            "location_sector_id": cols.get("location_sector_id")
        }

        response = _get_db().table("characters").insert(new_char_data).execute()
        if response.data:
            cmd_id = response.data[0]["id"]
            set_character_knowledge_level(cmd_id, player_id, KnowledgeLevel.FRIEND)
            log_event(f"Nuevo comandante V2 Híbrido '{name}' creado.", player_id)
            return response.data[0]
        return None

    except Exception as e:
        print(f"DEBUG Error Create Commander: {e}")
        log_event(f"Error creando comandante V2: {e}", player_id, is_error=True)
        raise Exception("Error del sistema al guardar el comandante.")

def update_commander_profile(
    player_id: int,
    bio_data: Dict[str, Any],
    attributes: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """Actualiza perfil respetando Híbrido V2 e IDs de roles."""
    try:
        current = get_commander_by_player_id(player_id)
        if not current: return None
            
        cmd_obj = CommanderData(**current)
        full_stats_model = cmd_obj.sheet
        full_stats_dict = full_stats_model.model_dump()
        
        habilidades = calculate_skills(attributes)
        
        full_stats_dict["bio"]["biografia_corta"] = bio_data.get("biografia") or ""
        full_stats_dict["taxonomia"]["raza"] = bio_data.get("raza", full_stats_dict["taxonomia"]["raza"])
        full_stats_dict["progresion"]["clase"] = bio_data.get("clase", full_stats_dict["progresion"]["clase"])
        full_stats_dict["capacidades"]["atributos"] = attributes
        full_stats_dict["capacidades"]["habilidades"] = habilidades
        
        if "rol" in bio_data:
            full_stats_dict["estado"]["rol_asignado"] = bio_data["rol"]

        cols, cleaned_stats = _extract_and_clean_data(full_stats_dict)

        update_payload = {
            "stats_json": cleaned_stats,
            "class_id": cols.get("class_id"),
            "nombre": cols.get("nombre"),
            "apellido": cols.get("apellido"),
            "rol": cols.get("rol") # ID numérico procesado por ROLE_ID_MAP
        }

        response = _get_db().table("characters")\
            .update(update_payload)\
            .eq("player_id", player_id)\
            .eq("es_comandante", True)\
            .execute()

        return response.data[0] if response.data else None

    except Exception as e:
        print(f"DEBUG Error Update Commander: {e}")
        log_event(f"Error update comandante: {e}", player_id, is_error=True)
        raise Exception(f"Error actualizando perfil: {e}")

def create_character(player_id: Optional[int], character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Persiste un personaje generado con ID de rol numérico."""
    from data.game_config_repository import get_current_tick

    try:
        # Extraemos el nivel inicial si viene en la data, si no, es UNKNOWN por defecto
        # Se elimina del dict para no ensuciar el JSON de stats
        initial_knowledge = character_data.pop("initial_knowledge_level", KnowledgeLevel.UNKNOWN)
        
        tick = character_data.pop("recruited_at_tick", get_current_tick())
        
        stats_input = copy.deepcopy(character_data)
        stats_input.pop("player_id", None)
        
        if "stats_json" in stats_input:
            stats_input = stats_input["stats_json"]

        cols, cleaned_stats = _extract_and_clean_data(stats_input)

        payload = {
            "player_id": player_id,
            "recruited_at_tick": tick,
            "stats_json": cleaned_stats,
            
            "nombre": cols.get("nombre", "Unit"),
            "apellido": cols.get("apellido", ""),
            "level": cols.get("level", 1),
            "xp": cols.get("xp", 0),
            "rango": cols.get("rango", "Iniciado"),
            "class_id": cols.get("class_id", 0),
            "estado_id": cols.get("estado_id", 1),
            "loyalty": cols.get("loyalty", 50),
            "is_npc": False,
            "portrait_url": cols.get("portrait_url"),
            
            # Sincronización de Rol como INTEGER ID
            "rol": cols.get("rol", 0),
            
            "location_system_id": cols.get("location_system_id"),
            "location_planet_id": cols.get("location_planet_id"),
            "location_sector_id": cols.get("location_sector_id")
        }

        response = _get_db().table("characters").insert(payload).execute()
        
        if response.data:
            new_char = response.data[0]
            new_char_id = new_char["id"]
            
            # FIX CRÍTICO: Asegurar que se crea la entrada de conocimiento si hay player_id
            # Esto es vital para la consistencia entre UI de Facción y Reclutamiento
            if player_id is not None:
                kl = initial_knowledge if initial_knowledge else KnowledgeLevel.UNKNOWN
                set_character_knowledge_level(new_char_id, player_id, kl)

            log_event(f"Generado/Reclutado: {payload['nombre']}", player_id)
            return new_char
        return None

    except Exception as e:
        log_event(f"Error reclutando: {e}", player_id, is_error=True)
        raise RuntimeError(f"Error guardando personaje: {e}")

def get_all_characters_by_player_id(player_id: int) -> list[Dict[str, Any]]:
    try:
        response = _get_db().table("characters").select("*").eq("player_id", player_id).execute()
        return response.data if response.data else []
    except Exception:
        return []

get_all_player_characters = get_all_characters_by_player_id

def update_character(character_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("characters").update(data).eq("id", character_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_event(f"Error update char {character_id}: {e}", is_error=True)
        raise Exception("Error actualizando datos.")

def get_character_by_id(character_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("characters").select("*").eq("id", character_id).single().execute()
        return response.data
    except Exception:
        return None

def update_character_xp(character_id: int, new_xp: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("characters").update({"xp": new_xp}).eq("id", character_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_event(f"Error XP update: {e}", player_id, is_error=True)
        return None

def add_xp_to_character(character_id: int, xp_amount: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    try:
        char = get_character_by_id(character_id)
        if not char: return None
        current_xp = char.get("xp", 0)
        return update_character_xp(character_id, current_xp + xp_amount, player_id)
    except Exception:
        return None

def update_character_stats(character_id: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Actualiza stats completos separando SQL y JSON limpio."""
    cols, cleaned_stats = _extract_and_clean_data(new_stats_json)
    
    payload = {"stats_json": cleaned_stats}
    
    for field in ["nombre", "apellido", "level", "xp", "rango", "class_id", "estado_id", "loyalty", "portrait_url", "rol"]:
        if field in cols:
            payload[field] = cols[field]

    return update_character(character_id, payload)


# --- SISTEMA DE CONOCIMIENTO (Fixed: player_id column match) ---

def get_character_knowledge_level(character_id: int, player_id: int) -> KnowledgeLevel:
    try:
        # CORRECCIÓN: Usar 'player_id' en lugar de 'observer_player_id'
        response = _get_db().table("character_knowledge")\
            .select("knowledge_level")\
            .eq("character_id", character_id)\
            .eq("player_id", player_id)\
            .single().execute()
        
        if response.data:
            return KnowledgeLevel(response.data["knowledge_level"])
        return KnowledgeLevel.UNKNOWN
    except Exception:
        return KnowledgeLevel.UNKNOWN

def set_character_knowledge_level(character_id: int, player_id: int, level: KnowledgeLevel) -> bool:
    try:
        # CORRECCIÓN: Usar 'player_id' y ajustar el on_conflict a la nueva estructura
        _get_db().table("character_knowledge").upsert({
            "character_id": character_id,
            "player_id": player_id,
            "knowledge_level": level.value
        }, on_conflict="character_id, player_id").execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando conocimiento (CharID: {character_id}): {e}", player_id, is_error=True)
        return False

# --- WRAPPERS DE RECLUTAMIENTO ---

def recruit_random_character_with_ai(player_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    from services.character_generation_service import recruit_character_with_ai
    return recruit_character_with_ai(player_id, **kwargs)

def get_recruitment_candidates(player_id: int, **kwargs) -> List[Dict[str, Any]]:
    from services.character_generation_service import generate_character_pool
    return generate_character_pool(player_id, **kwargs)

def dismiss_character(character_id: int, player_id: int) -> bool:
    """Despide a un personaje de la facción."""
    try:
        char = get_character_by_id(character_id)
        if not char or char.get("player_id") != player_id:
            return False
            
        if char.get("es_comandante", False):
            return False

        kl = get_character_knowledge_level(character_id, player_id)
        nuevo_estado = STATUS_ID_MAP["Retirado"] if kl == KnowledgeLevel.FRIEND else STATUS_ID_MAP["Disponible"]
        
        payload = {"player_id": None, "estado_id": nuevo_estado}
        
        result = update_character(character_id, payload)
        if result:
            log_event(f"Personal ID {character_id} desvinculado de la facción.", player_id)
            return True
        return False

    except Exception as e:
        log_event(f"Error en dismiss_character: {e}", player_id, is_error=True)
        return False

def recruit_candidate_db(character_id: int, update_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Wrapper específico para reclutar: Convierte dict de alto nivel a columnas SQL validas.
    Soluciona error de columnas inexistentes ('estado', 'ubicacion') en update_character al reclutar.
    Refactor V10: Incluye columnas de ubicación física (system_id, planet_id, sector_id).
    Tarea 2: Elimina lógica de actualización de JSON de ubicación.
    """
    try:
        char = get_character_by_id(character_id)
        if not char: return None

        stats = char.get("stats_json", {})

        # 1. Aplicar cambios al JSON
        new_rank = update_dict.get("rango", "Recluta")
        new_status_str = update_dict.get("estado", "Disponible")
        
        # Extraer IDs de ubicación física (Refactor V10)
        new_system_id = update_dict.get("location_system_id")
        new_planet_id = update_dict.get("location_planet_id")
        new_sector_id = update_dict.get("location_sector_id")

        if "progresion" not in stats: stats["progresion"] = {}
        stats["progresion"]["rango"] = new_rank

        if "estado" not in stats: stats["estado"] = {}
        stats["estado"]["estados_activos"] = [new_status_str]
        stats["estado"]["rol_asignado"] = "Sin Asignar" # Reset rol logic

        # TAREA 2: Eliminar actualización de ubicación en JSON.
        # Eliminadas las líneas que escribían en stats["estado"]["ubicacion"].
        # Limpieza proactiva: asegurar que no quede basura en el JSON.
        stats["estado"].pop("ubicacion", None)

        # 2. Preparar Payload SQL
        # Mapeo explicito de estado (texto -> ID)
        status_id = STATUS_ID_MAP.get(new_status_str, 1)

        payload = {
            "stats_json": stats,
            "rango": new_rank,
            "estado_id": status_id,
            "rol": 0, # Sin Asignar
            # Columnas SQL de ubicación (Source of Truth - Refactor V10)
            "location_system_id": new_system_id,
            "location_planet_id": new_planet_id,
            "location_sector_id": new_sector_id
        }

        return update_character(character_id, payload)

    except Exception as e:
        log_event(f"Error en recruit_candidate_db: {e}", is_error=True)
        return None