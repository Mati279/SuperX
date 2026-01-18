# data/character_repository.py
from typing import Dict, Any, Optional, List
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
    Crea un Comandante usando el esquema V2.
    """
    from data.game_config_repository import get_current_tick # Import local para evitar ciclo

    try:
        habilidades = calculate_skills(attributes)
        current_tick = get_current_tick() # Obtener tick actual
        
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
            "ubicacion": COMMANDER_LOCATION,
            "recruited_at_tick": current_tick # Persistencia del tick
        }

        response = _get_db().table("characters").insert(new_char_data).execute()
        if response.data:
            # El comandante siempre es conocido por el jugador (es él mismo) -> FRIEND
            cmd_id = response.data[0]["id"]
            set_character_knowledge_level(cmd_id, player_id, KnowledgeLevel.FRIEND)
            
            log_event(f"Nuevo comandante V2 '{name}' creado en tick {current_tick}.", player_id)
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
        current_stats = current.get("stats_json", {})
        
        habilidades = calculate_skills(attributes)
        name = current.get("nombre", "Comandante")
        
        # Update deep merge
        new_stats = _ensure_v2_structure(current_stats, name)
        
        # Update especifico
        new_stats["bio"]["biografia_corta"] = bio_data.get("biografia", new_stats["bio"]["biografia_corta"])
        new_stats["taxonomia"]["raza"] = bio_data.get("raza", new_stats["taxonomia"]["raza"])
        new_stats["progresion"]["clase"] = bio_data.get("clase", new_stats["progresion"]["clase"])
        new_stats["capacidades"]["atributos"] = attributes
        new_stats["capacidades"]["habilidades"] = habilidades

        response = _get_db().table("characters")\
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
    from data.game_config_repository import get_current_tick # Import local

    try:
        character_data["player_id"] = player_id
        
        # Inyectar tick actual si no viene en data
        if "recruited_at_tick" not in character_data:
            character_data["recruited_at_tick"] = get_current_tick()

        # Extraer nivel de conocimiento inicial si existe
        initial_knowledge = character_data.pop("initial_knowledge_level", None)

        response = _get_db().table("characters").insert(character_data).execute()
        
        if response.data:
            new_char = response.data[0]
            new_char_id = new_char["id"]
            nombre = character_data.get('nombre', 'Unit')
            
            # Persistir conocimiento inicial
            if initial_knowledge:
                set_character_knowledge_level(new_char_id, player_id, initial_knowledge)
            else:
                # REGLA DE ORO: Si no se especifica (p.ej. generación directa), 
                # por defecto es UNKNOWN.
                set_character_knowledge_level(new_char_id, player_id, KnowledgeLevel.UNKNOWN)

            log_event(f"Reclutado: {nombre}", player_id)
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

# ALIAS para compatibilidad con event_service
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
    rango = new_stats_json.get("progresion", {}).get("rango", "Recluta")
    
    return update_character(character_id, {
        "stats_json": new_stats_json,
        "rango": rango
    })

def recruit_character(player_id: int, character_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recluta un personaje con datos ya generados."""
    return create_character(player_id, character_data)


def recruit_random_character_with_ai(
    player_id: int,
    location_planet_id: Optional[int] = None,
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Genera y recluta un personaje aleatorio usando IA para nombre y biografía.
    """
    from services.character_generation_service import recruit_character_with_ai

    return recruit_character_with_ai(
        player_id=player_id,
        location_planet_id=location_planet_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )


def get_recruitment_candidates(
    player_id: int,
    pool_size: int = 3,
    location_planet_id: Optional[int] = None,
    predominant_race: Optional[str] = None,
    min_level: int = 1,
    max_level: int = 1
) -> list[Dict[str, Any]]:
    """
    Genera un pool de candidatos para reclutamiento.
    """
    from services.character_generation_service import generate_character_pool

    return generate_character_pool(
        player_id=player_id,
        pool_size=pool_size,
        location_planet_id=location_planet_id,
        predominant_race=predominant_race,
        min_level=min_level,
        max_level=max_level
    )

# --- GESTIÓN DE CONOCIMIENTO (V2: SQL TABLE) ---

def set_character_knowledge_level(
    character_id: int,
    observer_player_id: int,
    knowledge_level: KnowledgeLevel
) -> bool:
    """
    Establece el nivel de conocimiento usando la tabla relacional 'character_knowledge'.
    Realiza un UPSERT (Insertar o Actualizar).
    """
    try:
        # UPSERT en Supabase/Postgres
        data = {
            "character_id": character_id,
            "observer_player_id": observer_player_id,
            "knowledge_level": knowledge_level.value,
            "updated_at": "now()"
        }
        
        # Upsert basado en la constraint única (character_id, observer_player_id)
        response = _get_db().table("character_knowledge").upsert(data, on_conflict="character_id, observer_player_id").execute()
        
        return bool(response.data)

    except Exception as e:
        log_event(f"Error setting knowledge level (SQL): {e}", observer_player_id, is_error=True)
        return False

def get_character_knowledge_level(
    character_id: int,
    observer_player_id: int
) -> KnowledgeLevel:
    """
    Recupera el nivel de conocimiento desde la tabla SQL.
    Por defecto UNKNOWN si no existe registro.
    """
    try:
        # 1. Regla de Oro: Si es el dueño, es FRIEND automáticamente (ahorra query o sirve de fallback)
        # Nota: Idealmente esto se chequearía antes, pero necesitamos saber quién es el dueño.
        # Hacemos la query de conocimiento directa, es rápida.
        
        response = _get_db().table("character_knowledge")\
            .select("knowledge_level")\
            .eq("character_id", character_id)\
            .eq("observer_player_id", observer_player_id)\
            .maybe_single()\
            .execute()
            
        if response.data:
            return KnowledgeLevel(response.data["knowledge_level"])
            
        # 2. Fallback: Chequear si es el dueño (si no hay registro en knowledge table)
        # Esto requiere traer el personaje, lo cual puede ser costoso si solo queríamos el nivel.
        # Asumimos que si no está en la tabla de conocimiento y no preguntamos en contexto de "my_characters", es desconocido.
        # PERO, para seguridad, podemos hacer un chequeo rápido si el caller no tiene el objeto character.
        
        char = get_character_by_id(character_id)
        if char and char.get("player_id") == observer_player_id:
            # CORRECCION: Si es el dueño pero NO tiene registro en knowledge,
            # DEBE ser KNOWN (Conocido), no FRIEND.
            # (Aunque idealmente siempre debería haber registro al crearse)
            return KnowledgeLevel.KNOWN
            
        return KnowledgeLevel.UNKNOWN

    except Exception:
        return KnowledgeLevel.UNKNOWN

def get_known_characters_by_player(player_id: int) -> List[Dict[str, Any]]:
    """
    Retorna todos los personajes que el jugador conoce (KNOWN o FRIEND),
    uniendo con la tabla de characters.
    """
    try:
        # Supabase permite joins si están configurados las Foreign Keys
        # Sintaxis: characters!inner(...) hace un INNER JOIN
        response = _get_db().table("character_knowledge")\
            .select("knowledge_level, characters!inner(*)")\
            .eq("observer_player_id", player_id)\
            .execute()
            
        # Formatear salida plana si es necesario, o devolver estructura anidada
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error fetching known characters: {e}", player_id, is_error=True)
        return []