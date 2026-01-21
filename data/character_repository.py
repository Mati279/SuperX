# data/character_repository.py
from typing import Dict, Any, Optional, List, Tuple
import copy
from data.database import get_supabase
from data.log_repository import log_event


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()

# Importamos KnowledgeLevel para tipado y validación
from core.models import BiologicalSex, CharacterRole, KnowledgeLevel
from core.rules import calculate_skills
from config.app_constants import (
    COMMANDER_RANK,
    COMMANDER_STATUS,
    COMMANDER_LOCATION
)

# --- CONSTANTES DE MAPEO ---
CLASS_ID_MAP = {
    "Novato": 0, "Soldado": 1, "Piloto": 2, "Ingeniero": 3, 
    "Diplomático": 4, "Espía": 5, "Hacker": 6, "Comandante": 99,
    "Desconocida": 0
}

STATUS_ID_MAP = {
    "Disponible": 1,
    "En Misión": 2,
    "Herido": 3,
    "Fallecido": 4,
    "Entrenando": 5,
    "En Tránsito": 6,
    "Candidato": 7,  # Agregado para MMFR
    "Retirado": 99,
    "Sin Asignar": 1
}

# --- HELPER: EXTRACT & CLEAN ---
def _extract_and_clean_data(full_stats: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    EXTRACT & CLEAN PATTERN (Refactorizado MMFR).
    Separa los datos que van a columnas SQL (Fuente de Verdad) de los que se quedan en JSON.
    Retorna (column_data, cleaned_stats_json).
    """
    # 1. Copia para no destruir el objeto original en memoria
    stats = copy.deepcopy(full_stats)
    columns = {}

    # 2. Extracción de Datos Biográficos
    if "bio" in stats:
        columns["nombre"] = stats["bio"].get("nombre", "Unknown")
        columns["apellido"] = stats["bio"].get("apellido", "")
        # Retrato / ADN Visual
        if "apariencia_visual" in stats["bio"]:
            columns["portrait_url"] = stats["bio"]["apariencia_visual"]
            stats["bio"].pop("apariencia_visual", None)
            
        # Limpieza básica bio (mantenemos edad, sexo, bio_corta en JSON)
        stats["bio"].pop("nombre", None)
        stats["bio"].pop("apellido", None)

    # 3. Extracción de Progresión (Fuente de Verdad SQL)
    if "progresion" in stats:
        columns["level"] = stats["progresion"].get("nivel", 1)
        columns["xp"] = stats["progresion"].get("xp", 0)
        columns["rango"] = stats["progresion"].get("rango", "Recluta")
        
        clase_str = stats["progresion"].get("clase", "Novato")
        columns["class_id"] = CLASS_ID_MAP.get(clase_str, 0)
        
        # Limpieza total de datos numéricos del JSON
        stats["progresion"].pop("nivel", None)
        stats["progresion"].pop("xp", None)
        stats["progresion"].pop("rango", None)
        # Mantenemos 'clase' string en JSON para UI legacy/fallback

    # 4. Extracción de Estado y Ubicación
    if "estado" in stats:
        status_text = stats["estado"].get("rol_asignado", "Disponible")
        columns["estado_id"] = STATUS_ID_MAP.get(status_text, 1)
        # Columna legacy texto eliminada de columns para evitar error SQL
        # columns["estado"] = status_text 
        
        # Extracción de Jerarquía de Ubicación
        loc = stats["estado"].get("ubicacion", {})
        if isinstance(loc, dict):
            columns["location_system_id"] = loc.get("system_id")
            columns["location_planet_id"] = loc.get("planet_id")
            columns["location_sector_id"] = loc.get("sector_id")
            
            # Fallback legacy texto eliminado de columnas SQL
            # if "ubicacion_local" in loc:
            #      columns["ubicacion"] = loc["ubicacion_local"]
            
            # Borrar objeto ubicación del JSON (ahora vive en columnas)
            stats["estado"].pop("ubicacion", None)
        
        # Borrar rol asignado
        stats["estado"].pop("rol_asignado", None)
        
    # 5. Extracción de Comportamiento (Lealtad)
    if "comportamiento" in stats:
        if "lealtad" in stats["comportamiento"]:
            columns["loyalty"] = stats["comportamiento"]["lealtad"]
            stats["comportamiento"].pop("lealtad", None)

    return columns, stats


# Helper para migración/compatibilidad (Mantenido por seguridad)
def _ensure_v2_structure(stats_json: Dict, name: str = "") -> Dict:
    """Asegura que el JSON tenga la estructura V2, migrando si es necesario."""
    if "bio" in stats_json:
        return stats_json 
    
    return {
        "bio": {
            "nombre": name.split()[0],
            "apellido": name.split()[1] if len(name.split()) > 1 else "",
            "edad": 30,
            "sexo": "Desconocido",
            "biografia_corta": "Migrado Auto"
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
    """
    Crea un Comandante usando el esquema Híbrido V2.
    """
    from data.game_config_repository import get_current_tick

    try:
        habilidades = calculate_skills(attributes)
        current_tick = get_current_tick()
        
        # Descomponer nombre
        parts = name.split(" ", 1)
        nombre_p = parts[0]
        apellido_p = parts[1] if len(parts) > 1 else ""
        
        raza = bio_data.get("raza", "Humano")
        clase = bio_data.get("clase", "Comandante")

        # Construir objeto completo primero
        full_stats = {
            "bio": {
                "nombre": nombre_p,
                "apellido": apellido_p,
                "edad": bio_data.get("edad", 30),
                "sexo": bio_data.get("sexo", BiologicalSex.UNKNOWN.value),
                "biografia_corta": bio_data.get("biografia", f"Comandante {raza}")
            },
            "taxonomia": {
                "raza": raza,
                "transformaciones": []
            },
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
                "lealtad": 100 # Comandante siempre leal
            },
            "logistica": {
                "equipo": [],
                "slots_ocupados": 0,
                "slots_maximos": 10
            },
            "estado": {
                "estados_activos": [COMMANDER_STATUS],
                "rol_asignado": CharacterRole.COMMANDER.value,
                "accion_actual": "Iniciando mandato",
                # Inicialización de ubicación
                "ubicacion": {
                   "system_id": None, "planet_id": None, "sector_id": None, "ubicacion_local": COMMANDER_LOCATION
                }
            }
        }

        # EXTRAER Y LIMPIAR
        cols, cleaned_stats = _extract_and_clean_data(full_stats)

        new_char_data = {
            "player_id": player_id,
            "es_comandante": True,
            "recruited_at_tick": current_tick,
            "stats_json": cleaned_stats,
            
            # Columnas extraídas (Fuente de Verdad)
            "nombre": cols.get("nombre"),
            "apellido": cols.get("apellido"),
            "rango": cols.get("rango"),
            "level": cols.get("level"),
            "xp": cols.get("xp"),
            "class_id": cols.get("class_id"),
            "estado_id": cols.get("estado_id"),
            "loyalty": cols.get("loyalty", 100),
            
            # Corregido: NO enviar columnas 'estado' o 'ubicacion' (texto) ya que no existen en el nuevo esquema
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
        log_event(f"Error creando comandante V2: {e}", player_id, is_error=True)
        raise Exception("Error del sistema al guardar el comandante.")

def update_commander_profile(
    player_id: int,
    bio_data: Dict[str, Any],
    attributes: Dict[str, int]
) -> Optional[Dict[str, Any]]:
    """
    Actualiza perfil respetando Híbrido V2.
    """
    try:
        current = get_commander_by_player_id(player_id)
        if not current: return None
            
        # Reconstruir stats completos para manipular (Hydration)
        from core.models import CommanderData
        cmd_obj = CommanderData(**current)
        full_stats_model = cmd_obj.sheet
        full_stats_dict = full_stats_model.model_dump()
        
        # Modificar
        habilidades = calculate_skills(attributes)
        
        full_stats_dict["bio"]["biografia_corta"] = bio_data.get("biografia", full_stats_dict["bio"]["biografia_corta"])
        full_stats_dict["taxonomia"]["raza"] = bio_data.get("raza", full_stats_dict["taxonomia"]["raza"])
        full_stats_dict["progresion"]["clase"] = bio_data.get("clase", full_stats_dict["progresion"]["clase"])
        full_stats_dict["capacidades"]["atributos"] = attributes
        full_stats_dict["capacidades"]["habilidades"] = habilidades

        # Extraer y Limpiar
        cols, cleaned_stats = _extract_and_clean_data(full_stats_dict)

        update_payload = {
            "stats_json": cleaned_stats,
            "class_id": cols.get("class_id"),
            "nombre": cols.get("nombre"),
            "apellido": cols.get("apellido")
        }

        response = _get_db().table("characters")\
            .update(update_payload)\
            .eq("player_id", player_id)\
            .eq("es_comandante", True)\
            .execute()

        return response.data[0] if response.data else None

    except Exception as e:
        log_event(f"Error update comandante: {e}", player_id, is_error=True)
        raise Exception("Error actualizando perfil.")

def create_character(player_id: Optional[int], character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Persiste un personaje generado. Acepta full stats dictionary.
    """
    from data.game_config_repository import get_current_tick

    try:
        # Metadatos
        initial_knowledge = character_data.pop("initial_knowledge_level", None)
        tick = character_data.pop("recruited_at_tick", get_current_tick())
        
        # Limpiar campos root si existen
        stats_input = copy.deepcopy(character_data)
        stats_input.pop("player_id", None)

        # Extract & Clean
        cols, cleaned_stats = _extract_and_clean_data(stats_input)

        payload = {
            "player_id": player_id,
            "recruited_at_tick": tick,
            "stats_json": cleaned_stats,
            
            # Columnas Fuente de Verdad
            "nombre": cols.get("nombre", "Unit"),
            "apellido": cols.get("apellido", ""),
            "level": cols.get("level", 1),
            "xp": cols.get("xp", 0),
            "rango": cols.get("rango", "Recluta"),
            "class_id": cols.get("class_id", 0),
            "estado_id": cols.get("estado_id", 1),
            "loyalty": cols.get("loyalty", 50),
            "is_npc": False,
            "portrait_url": cols.get("portrait_url"),
            
            # Ubicación
            "location_system_id": cols.get("location_system_id"),
            "location_planet_id": cols.get("location_planet_id"),
            "location_sector_id": cols.get("location_sector_id")
        }

        response = _get_db().table("characters").insert(payload).execute()
        
        if response.data:
            new_char = response.data[0]
            new_char_id = new_char["id"]
            
            if player_id is not None:
                kl = initial_knowledge if initial_knowledge else KnowledgeLevel.UNKNOWN
                set_character_knowledge_level(new_char_id, player_id, kl)

            log_event(f"Generado/Reclutado: {payload['nombre']}", player_id)
            return new_char
        return None

    except Exception as e:
        log_event(f"Error reclutando: {e}", player_id, is_error=True)
        raise Exception("Error guardando personaje.")

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
    """Actualización directa a columna SQL (Fuente de Verdad)."""
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
        
        # Leer desde columna SQL (Fuente de Verdad)
        current_xp = char.get("xp", 0)
        
        # Fallback para datos muy viejos sin migrar
        if current_xp is None:
             current_xp = char.get("stats_json", {}).get("progresion", {}).get("xp", 0)

        return update_character_xp(character_id, current_xp + xp_amount, player_id)
    except Exception:
        return None

def update_character_stats(character_id: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Actualiza stats completos.
    IMPORTANTE: Separa los datos para columnas SQL y JSON limpio.
    """
    cols, cleaned_stats = _extract_and_clean_data(new_stats_json)
    
    payload = {"stats_json": cleaned_stats}
    
    # Actualizar columnas relevantes si cambiaron en el objeto de UI
    if "nombre" in cols: payload["nombre"] = cols["nombre"]
    if "apellido" in cols: payload["apellido"] = cols["apellido"]
    if "level" in cols: payload["level"] = cols["level"]
    if "xp" in cols: payload["xp"] = cols["xp"]
    if "rango" in cols: payload["rango"] = cols["rango"]
    if "class_id" in cols: payload["class_id"] = cols["class_id"]
    if "estado_id" in cols: payload["estado_id"] = cols["estado_id"]
    if "loyalty" in cols: payload["loyalty"] = cols["loyalty"]
    if "portrait_url" in cols: payload["portrait_url"] = cols["portrait_url"]

    return update_character(character_id, payload)


# --- SISTEMA DE CONOCIMIENTO (TABLA character_knowledge) ---

def get_character_knowledge_level(character_id: int, player_id: int) -> KnowledgeLevel:
    try:
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
        # Upsert
        _get_db().table("character_knowledge").upsert({
            "character_id": character_id,
            "player_id": player_id,
            "knowledge_level": level.value
        }, on_conflict="character_id, player_id").execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando conocimiento: {e}", player_id, is_error=True)
        return False