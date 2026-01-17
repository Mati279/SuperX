# data/character_repository.py
from typing import Dict, Any, Optional
from .database import supabase
from data.log_repository import log_event
from core.rules import calculate_skills
from config.app_constants import (
    COMMANDER_RANK,
    COMMANDER_STATUS,
    COMMANDER_LOCATION
)
from core.models import BiologicalSex, CharacterRole

# Helper para migración/compatibilidad
def _ensure_v2_structure(stats_json: Dict, name: str = "") -> Dict:
    """Asegura que el JSON tenga la estructura V2, migrando si es necesario."""
    if "bio" in stats_json:
        return stats_json # Ya es V2
    
    # Migración básica de V1 -> V2
    return {
        "bio": {
            "nombre": name.split()[0],
            "apellido": name.split()[1] if len(name.split()) > 1 else "",
            "edad": 30,
            "sexo": "Desconocido",
            "biografia_corta": f"{stats_json.get('bio', {}).get('raza', 'Humano')} {stats_json.get('bio', {}).get('clase', 'Soldado')}"
        },
        "taxonomia": {"raza": stats_json.get("bio", {}).get("raza", "Humano"), "transformaciones": []},
        "progresion": {
            "nivel": stats_json.get("nivel", 1),
            "clase": stats_json.get("bio", {}).get("clase", "Novato"),
            "xp": stats_json.get("xp", 0),
            "rango": "Comandante"
        },
        "capacidades": {
            "atributos": stats_json.get("atributos", {}),
            "habilidades": stats_json.get("habilidades", {}),
            "feats": stats_json.get("feats", [])
        },
        "comportamiento": {"rasgos_personalidad": [], "relaciones": []},
        "logistica": {"equipo": [], "slots_ocupados": 0, "slots_maximos": 10},
        "estado": {
            "estados_activos": ["Disponible"],
            "sistema_actual": "Base",
            "ubicacion_local": "Mando",
            "rol_asignado": "Comandante",
            "accion_actual": "Idle"
        }
    }

def get_commander_by_player_id(player_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("characters").select("*").eq("player_id", player_id).eq("es_comandante", True).single().execute()
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
    Crea un Comandante usando el esquema V2.
    """
    try:
        habilidades = calculate_skills(attributes)
        
        # Construir estructura V2 manualmente ya que recibimos piezas sueltas del wizard
        raza = bio_data.get("raza", "Humano")
        clase = bio_data.get("clase", "Comandante")
        
        # Descomponer nombre
        parts = name.split(" ", 1)
        nombre_p = parts[0]
        apellido_p = parts[1] if len(parts) > 1 else ""

        stats_json = {
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
                "feats": ["Liderazgo Táctico"] # Feat base de comandante
            },
            "comportamiento": {
                "rasgos_personalidad": ["Liderazgo"],
                "relaciones": []
            },
            "logistica": {
                "equipo": [],
                "slots_ocupados": 0,
                "slots_maximos": 10
            },
            "estado": {
                "estados_activos": [COMMANDER_STATUS],
                "sistema_actual": "Sistema Inicial",
                "ubicacion_local": COMMANDER_LOCATION,
                "rol_asignado": CharacterRole.COMMANDER.value,
                "accion_actual": "Iniciando mandato"
            }
        }

        new_char_data = {
            "player_id": player_id,
            "nombre": name,
            "rango": COMMANDER_RANK,
            "es_comandante": True,
            "stats_json": stats_json,
            "estado": COMMANDER_STATUS,
            "ubicacion": COMMANDER_LOCATION
        }

        response = supabase.table("characters").insert(new_char_data).execute()
        if response.data:
            log_event(f"Nuevo comandante V2 '{name}' creado.", player_id)
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
    Actualiza perfil (Paso 3 Wizard) respetando V2.
    """
    try:
        # Recuperar actual para preservar IDs o estructura si existiera
        current = get_commander_by_player_id(player_id)
        if not current:
            return None # No debería pasar en flujo normal
            
        # Reconstruir stats_json completo con los nuevos datos
        # Nota: Como es update, podríamos querer fusionar, pero el wizard suele ser "set definitivo" inicial.
        # Reutilizamos lógica de create pero actualizando
        
        current_stats = current.get("stats_json", {})
        # Si es V1, esto sobrescribirá a V2
        
        habilidades = calculate_skills(attributes)
        name = current.get("nombre", "Comandante")
        parts = name.split(" ", 1)
        
        # Update deep merge
        new_stats = _ensure_v2_structure(current_stats, name)
        
        # Update especifico
        new_stats["bio"]["biografia_corta"] = bio_data.get("biografia", new_stats["bio"]["biografia_corta"])
        new_stats["taxonomia"]["raza"] = bio_data.get("raza", new_stats["taxonomia"]["raza"])
        new_stats["progresion"]["clase"] = bio_data.get("clase", new_stats["progresion"]["clase"])
        new_stats["capacidades"]["atributos"] = attributes
        new_stats["capacidades"]["habilidades"] = habilidades

        response = supabase.table("characters")\
            .update({"stats_json": new_stats})\
            .eq("player_id", player_id)\
            .eq("es_comandante", True)\
            .execute()

        if response.data:
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error update comandante: {e}", player_id, is_error=True)
        raise Exception("Error actualizando perfil.")

def create_character(player_id: int, character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Persiste un personaje generado por character_engine (que ya viene en formato V2/DB ready).
    """
    try:
        # El engine ya devuelve {nombre, rango, estado, stats_json, ...}
        # Solo necesitamos inyectar player_id
        character_data["player_id"] = player_id
        
        response = supabase.table("characters").insert(character_data).execute()
        
        if response.data:
            nombre = character_data.get('nombre', 'Unit')
            log_event(f"Reclutado: {nombre}", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error reclutando: {e}", player_id, is_error=True)
        raise Exception("Error guardando personaje.")

def get_all_characters_by_player_id(player_id: int) -> list[Dict[str, Any]]:
    try:
        response = supabase.table("characters").select("*").eq("player_id", player_id).execute()
        return response.data if response.data else []
    except Exception:
        return []

def update_character(character_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("characters").update(data).eq("id", character_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        log_event(f"Error update char {character_id}: {e}", is_error=True)
        raise Exception("Error actualizando datos.")

def get_character_by_id(character_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("characters").select("*").eq("id", character_id).single().execute()
        return response.data
    except Exception:
        return None

def update_character_xp(character_id: int, new_xp: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    try:
        char = get_character_by_id(character_id)
        if not char: return None

        stats = _ensure_v2_structure(char.get("stats_json", {}), char.get("nombre", ""))
        
        # Update path seguro
        stats["progresion"]["xp"] = new_xp
        
        return update_character(character_id, {"stats_json": stats})
    except Exception as e:
        log_event(f"Error XP update: {e}", player_id, is_error=True)
        return None

def add_xp_to_character(character_id: int, xp_amount: int, player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    try:
        char = get_character_by_id(character_id)
        if not char: return None
        
        stats = _ensure_v2_structure(char.get("stats_json", {}), char.get("nombre", ""))
        current = stats["progresion"]["xp"]
        
        return update_character_xp(character_id, current + xp_amount, player_id)
    except Exception:
        return None

def update_character_stats(character_id: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    return update_character(character_id, {"stats_json": new_stats_json})

def update_character_level(character_id: int, new_level: int, new_stats_json: Dict[str, Any], player_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    # Sync columna Rango si cambia
    rango = new_stats_json.get("progresion", {}).get("rango", "Recluta")
    
    return update_character(character_id, {
        "stats_json": new_stats_json,
        "rango": rango
    })

def recruit_character(player_id: int, character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return create_character(player_id, character_data)