# core/character_engine.py
"""
Motor de Personajes - Gestión de conocimiento, progresión y biografías.
Refactorizado para Esquema Híbrido (SQL + JSON).
Actualizado V4.3: Sistema de Niveles de Conocimiento (Unknown -> Known -> Friend).
"""
from typing import Dict, Any, Tuple, List, Optional
import random

from core.constants import (
    SKILL_POINTS_PER_LEVEL,
    AVAILABLE_FEATS,
    XP_TABLE,
    ATTRIBUTE_POINT_LEVELS,
    FEAT_LEVELS,
    BASE_ATTRIBUTE_MIN,
    BASE_ATTRIBUTE_MAX,
    MAX_ATTRIBUTE_VALUE,
    PERSONALITY_TRAITS
)
from core.models import KnowledgeLevel, SecretType
from data.log_repository import log_event


# --- Constantes de Nivel de Acceso a Biografía ---
BIO_ACCESS_UNKNOWN = "unknown"
BIO_ACCESS_KNOWN = "known"
BIO_ACCESS_DEEP = "deep"

# --- Constantes de Progresión V4.3 ---
TICKS_REQ_KNOWN_BASE = 20
TICKS_REQ_FRIEND_BASE = 50

# --- Funciones de XP y Progresión ---

def get_xp_for_level(level: int) -> int:
    """Retorna el XP acumulado necesario para un nivel dado."""
    if level <= 1:
        return 0
    return XP_TABLE.get(level, XP_TABLE.get(20, 200000))


def get_xp_required_for_next_level(current_level: int) -> int:
    """Retorna el XP necesario para el siguiente nivel."""
    next_level = min(current_level + 1, 20)
    return XP_TABLE.get(next_level, XP_TABLE.get(20, 200000))


# --- Funciones de Biografía ---

def get_visible_biography(
    stats_json: Dict[str, Any],
    knowledge_level: KnowledgeLevel = None
) -> str:
    """
    Retorna la biografía visible según el nivel de conocimiento.

    Args:
        stats_json: El diccionario stats_json del personaje.
        knowledge_level: Nivel de conocimiento del observador.

    Returns:
        Texto biográfico filtrado.
    """
    bio = stats_json.get("bio", {})

    # Determinar nivel efectivo
    if knowledge_level is None:
        # Usar el campo interno si no se especifica
        nivel_acceso = bio.get("nivel_acceso", BIO_ACCESS_UNKNOWN)
        if nivel_acceso == BIO_ACCESS_DEEP:
            knowledge_level = KnowledgeLevel.FRIEND
        elif nivel_acceso == BIO_ACCESS_KNOWN:
            knowledge_level = KnowledgeLevel.KNOWN
        else:
            knowledge_level = KnowledgeLevel.UNKNOWN

    # Obtener textos disponibles
    bio_superficial = bio.get("bio_superficial") or bio.get("biografia_corta", "Sin datos biográficos.")
    bio_conocida = bio.get("bio_conocida", "")
    bio_profunda = bio.get("bio_profunda", "")

    # Retornar según nivel
    if knowledge_level == KnowledgeLevel.FRIEND:
        # Concatenar conocida + profunda
        if bio_conocida and bio_profunda:
            return f"{bio_conocida} {bio_profunda}"
        elif bio_profunda:
            return bio_profunda
        elif bio_conocida:
            return bio_conocida
        return bio_superficial

    elif knowledge_level == KnowledgeLevel.KNOWN:
        return bio_conocida if bio_conocida else bio_superficial

    else:  # UNKNOWN
        return bio_superficial


def get_visible_feats(
    feats: List[Any],
    knowledge_level: KnowledgeLevel
) -> List[Dict[str, Any]]:
    """
    Filtra los feats según el nivel de conocimiento.
    """
    if knowledge_level in (KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND):
        # Retornar todos, normalizados a dict
        return _normalize_feats(feats)

    # UNKNOWN: Solo visibles
    normalized = _normalize_feats(feats)
    return [f for f in normalized if f.get("visible", False)]


def _normalize_feats(feats: List[Any]) -> List[Dict[str, Any]]:
    """Normaliza feats a formato Dict con campo visible."""
    result = []
    for feat in feats:
        if isinstance(feat, str):
            # Legacy: string simple, asumir no visible
            result.append({"nombre": feat, "visible": False})
        elif isinstance(feat, dict):
            result.append(feat)
    return result


def get_visible_skills(
    skills: Dict[str, int],
    knowledge_level: KnowledgeLevel,
    top_n: int = 5
) -> Dict[str, int]:
    """
    Filtra las habilidades según el nivel de conocimiento.
    """
    if knowledge_level in (KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND):
        return skills

    # UNKNOWN: Solo top N
    if not skills:
        return {}

    sorted_skills = sorted(skills.items(), key=lambda x: -x[1])[:top_n]
    return dict(sorted_skills)


# --- Funciones de Secretos ---

def reveal_secret_on_friend(
    character_id: int,
    player_id: int,
    char_data: Dict[str, Any]
) -> Tuple[SecretType, str, Dict[str, Any]]:
    """
    Revela un secreto aleatorio al alcanzar nivel FRIEND y aplica el efecto.
    Refactorizado para manejar columnas SQL como fuente de verdad.

    Args:
        character_id: ID del personaje
        player_id: ID del jugador observador
        char_data: Diccionario COMPLETO del personaje (cols SQL + stats_json)

    Returns:
        Tuple de (tipo_secreto, mensaje, stats_json_actualizados)
    """
    from data.character_repository import update_character

    # Seleccionar tipo de secreto aleatorio
    secret_type = random.choice(list(SecretType))
    
    # Extraer stats_json (siempre necesario para flags y atributos)
    stats_json = char_data.get("stats_json", {})
    if not stats_json:
        stats_json = {}

    # --- REFACTOR: LECTURA HÍBRIDA (SQL First) ---
    # Leemos nivel desde columna SQL, fallback a JSON
    nivel_actual = char_data.get("level")
    if nivel_actual is None:
        nivel_actual = stats_json.get("progresion", {}).get("nivel", 1)
        
    char_name = char_data.get("nombre") or stats_json.get("bio", {}).get("nombre", "Personaje")

    msg = ""
    update_payload = {} # Diccionario para enviar a update_character

    if secret_type == SecretType.PROFESSIONAL:
        # +XP fijo según nivel (nivel * 100)
        xp_bonus = nivel_actual * 100
        
        # Leer XP actual (SQL First)
        current_xp = char_data.get("xp")
        if current_xp is None:
            current_xp = stats_json.get("progresion", {}).get("xp", 0)
            
        new_xp = current_xp + xp_bonus
        
        # Preparar actualización DUAL (SQL + JSON) para consistencia
        update_payload["xp"] = new_xp
        
        if "progresion" not in stats_json:
            stats_json["progresion"] = {}
        stats_json["progresion"]["xp"] = new_xp
        
        msg = f"🎓 SECRETO PROFESIONAL: {char_name} revela técnicas de entrenamiento avanzadas. +{xp_bonus} XP."

    elif secret_type == SecretType.PERSONAL:
        # +2 Voluntad (Atributo sigue viviendo en JSON->Capacidades)
        # Buscar en V2 (capacidades->atributos) o V1 (atributos)
        attributes_container = stats_json.get("capacidades", {}).get("atributos")
        if attributes_container is None:
             # Fallback o crear estructura V2
             if "capacidades" not in stats_json: stats_json["capacidades"] = {}
             if "atributos" not in stats_json["capacidades"]: stats_json["capacidades"]["atributos"] = {}
             attributes_container = stats_json["capacidades"]["atributos"]

        # Si estaba vacio, inicializar (aunque raro en este punto)
        current_vol = attributes_container.get("voluntad", 5)
        new_vol = min(20, current_vol + 2)  # Cap en 20
        
        attributes_container["voluntad"] = new_vol
        msg = f"💚 SECRETO PERSONAL: {char_name} encuentra un sentido de pertenencia contigo. +2 Voluntad."

    elif secret_type == SecretType.CRITICAL:
        # Flag de misión personal (JSON Logic)
        if "comportamiento" not in stats_json:
            stats_json["comportamiento"] = {}
        stats_json["comportamiento"]["mision_personal_disponible"] = True
        msg = f"⚠️ SECRETO CRÍTICO: {char_name} revela algo importante de su pasado. Se desbloquea una misión personal."

    # Guardar flag de secreto revelado (JSON Logic)
    if "secreto_revelado" not in stats_json:
        stats_json["secreto_revelado"] = {}
    stats_json["secreto_revelado"] = {
        "tipo": secret_type.value,
        "revelado_tick": None  # Se llena desde el caller con el tick actual si es necesario
    }

    # Empaquetar stats_json en el payload
    update_payload["stats_json"] = stats_json

    # Actualizar en DB
    # Nota: update_character maneja kwargs mapeando a columnas si existen
    update_character(character_id, update_payload)

    return secret_type, msg, stats_json


def update_character_access_level(
    character_id: int,
    new_level: str
) -> bool:
    """
    Actualiza el nivel de acceso interno del personaje (campo nivel_acceso en bio).
    Usado por event_service para actualización directa.
    """
    from data.character_repository import get_character_by_id, update_character

    char = get_character_by_id(character_id)
    if not char:
        return False

    stats = char.get("stats_json", {})
    if "bio" not in stats:
        stats["bio"] = {}

    stats["bio"]["nivel_acceso"] = new_level

    result = update_character(character_id, {"stats_json": stats})
    return result is not None


# --- Función Principal de Progresión Pasiva (V4.3) ---

def process_passive_knowledge_updates(player_id: int, current_tick: int) -> List[str]:
    """
    Se ejecuta cada Tick. Revisa todos los personajes de la facción.
    Aplica la fórmula dinámica basada en Presencia para subir nivel.
    Revela secretos al alcanzar nivel FRIEND.
    """
    from data.character_repository import (
        get_all_player_characters,
        set_character_knowledge_level,
        get_character_knowledge_level,
        update_character
    )

    updates_log = []
    # get_all_player_characters devuelve dicts híbridos (cols SQL + stats_json)
    characters = get_all_player_characters(player_id)

    for char in characters:
        # Saltar comandantes (siempre son FRIEND implícito)
        if char.get("es_comandante", False):
            continue

        char_id = char["id"]
        # Obtener nivel actual desde DB o stats
        current_level_enum = get_character_knowledge_level(char_id, player_id)

        # Si ya es FRIEND, no hay más progreso pasivo
        if current_level_enum == KnowledgeLevel.FRIEND:
            continue
            
        # Extraer Stats y Atributos
        stats = char.get("stats_json", {})
        attributes = {}
        if "capacidades" in stats and "atributos" in stats["capacidades"]:
            attributes = stats["capacidades"]["atributos"]
        elif "atributos" in stats:
            attributes = stats["atributos"]
            
        presence = attributes.get('presencia', 10) # Default 10

        # Obtener progreso acumulado
        progress_ticks = stats.get('knowledge_progress_ticks', 0)
        progress_ticks += 1
        stats['knowledge_progress_ticks'] = progress_ticks
        
        new_level = None

        # --- LÓGICA DE TRANSICIÓN V4.3 ---
        
        # 1. UNKNOWN -> KNOWN
        if current_level_enum == KnowledgeLevel.UNKNOWN:
            # Fórmula: Base (20) - (Presencia - 10)
            # Presencia 15 (+5) -> Req = 20 - 5 = 15.
            # Presencia 5 (-5) -> Req = 20 - (-5) = 25.
            req_ticks = TICKS_REQ_KNOWN_BASE - (presence - 10)
            req_ticks = max(5, req_ticks) # Seguridad
            
            if progress_ticks >= req_ticks:
                new_level = KnowledgeLevel.KNOWN
                # Generar bio_conocida si no existe
                if 'bio_conocida' not in stats.get('bio', {}):
                    if 'bio' not in stats: stats['bio'] = {}
                    stats['bio']['bio_conocida'] = "Biografía detallada generada por IA."

        # 2. KNOWN -> FRIEND
        elif current_level_enum == KnowledgeLevel.KNOWN:
            # Fórmula: Base (50) + Penalización si Presencia < 10
            penalty = max(0, 10 - presence)
            req_ticks = TICKS_REQ_FRIEND_BASE + penalty
            
            if progress_ticks >= req_ticks:
                new_level = KnowledgeLevel.FRIEND

        # --- APLICAR CAMBIOS ---
        if new_level:
            char_name = char.get("nombre", "Unidad")
            
            # Resetear contador para el nuevo nivel
            stats['knowledge_progress_ticks'] = 0
            
            # Actualizar DB
            update_character(char_id, {"stats_json": stats})
            success = set_character_knowledge_level(char_id, player_id, new_level)
            
            if success:
                if new_level == KnowledgeLevel.KNOWN:
                    msg = f"ℹ️ Conocimiento actualizado: Has pasado suficiente tiempo con **{char_name}** para conocer sus capacidades."
                    updates_log.append(msg)
                    log_event(msg, player_id)
                    update_character_access_level(char_id, BIO_ACCESS_KNOWN)

                elif new_level == KnowledgeLevel.FRIEND:
                    msg = f"🤝 Vínculo fortalecido: **{char_name}** ahora confía plenamente en ti."
                    updates_log.append(msg)
                    log_event(msg, player_id)
                    update_character_access_level(char_id, BIO_ACCESS_DEEP)

                    # Revelar secreto
                    secret_type, secret_msg, _ = reveal_secret_on_friend(
                        char_id,
                        player_id,
                        char
                    )
                    updates_log.append(secret_msg)
                    log_event(secret_msg, player_id)
        else:
            # Solo actualizar contador de progreso en DB
            update_character(char_id, {"stats_json": stats})

    return updates_log