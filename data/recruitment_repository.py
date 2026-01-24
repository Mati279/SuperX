# data/recruitment_repository.py (Completo)
"""
Repositorio para gestion de candidatos de reclutamiento.
REFACTORIZADO: Ahora actúa como una interfaz sobre la tabla 'characters'
filtrando por estado 'Candidato'.
Actualizado v5.1.8: Persistencia de Conocimiento (SQL) en Investigación.
Actualizado v5.1.9: Validación de persistencia unificada.
"""

from typing import Dict, Any, List, Optional
from data.database import get_supabase
from data.log_repository import log_event
from core.models import CharacterStatus, KnowledgeLevel
from data.character_repository import update_character, get_character_by_id, set_character_knowledge_level


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSTANTES ---
CANDIDATE_LIFESPAN_TICKS = 4
CANDIDATE_STATUS_ID = 7  # ID asignado en STATUS_ID_MAP de character_repository


# --- FUNCIONES CRUD (ADAPTADAS A TABLA CHARACTERS) ---

def get_recruitment_candidates(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los personajes con estado 'Candidato' de un jugador.
    Adapta la estructura para que la UI la consuma fácilmente.

    Nota V10: Los campos location_system_id, location_planet_id, location_sector_id
    vienen directamente de las columnas SQL (Source of Truth) via select("*").
    """
    try:
        # CORRECCIÓN MMFR: Filtrar por estado_id numérico en lugar de texto
        # select("*") incluye columnas de ubicación (location_system_id, etc.)
        response = _get_db().table("characters")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("estado_id", CANDIDATE_STATUS_ID)\
            .execute()

        candidates = []
        if response.data:
            for char in response.data:
                # Adaptador: Extraer datos de recruitment_data a nivel raíz para la UI
                # Nota: location_system_id, location_planet_id, location_sector_id
                # ya están en 'char' desde las columnas SQL
                stats = char.get("stats_json", {})
                rec_data = stats.get("recruitment_data", {})
                
                # Inyectar propiedades planas para compatibilidad con UI existente
                char["costo"] = rec_data.get("costo", 100)
                char["tick_created"] = rec_data.get("tick_created", 0)
                char["is_tracked"] = rec_data.get("is_tracked", False)
                char["is_being_investigated"] = rec_data.get("is_being_investigated", False)
                char["investigation_outcome"] = rec_data.get("investigation_outcome", None)
                char["discount_applied"] = rec_data.get("discount_applied", False)
                
                candidates.append(char)
                
        # Ordenamiento manual (Python) ya que los campos están en JSON
        # Prioridad: Tracked > Created
        candidates.sort(key=lambda x: (not x["is_tracked"], x["tick_created"]))
        
        return candidates
    except Exception as e:
        log_event(f"Error obteniendo candidatos (Unified): {e}", player_id, is_error=True)
        return []


def add_candidate(player_id: int, candidate_data: Dict[str, Any], current_tick: int) -> Optional[Dict[str, Any]]:
    """
    DEPRECATED: Usar services.character_generation_service.generate_character_pool
    que llama a create_character directamente.
    Mantenido solo por compatibilidad de firma si fuera necesario.
    """
    log_event("WARNING: add_candidate llamado en deprecated mode.", player_id)
    return None


def remove_candidate(candidate_id: int) -> bool:
    """
    Elimina un candidato físicamente de la DB.
    Usado cuando expiran. Al contratar, se cambia el estado, no se borra.
    """
    try:
        # CORRECCIÓN MMFR: Filtrar por estado_id numérico
        _get_db().table("characters")\
            .delete()\
            .eq("id", candidate_id)\
            .eq("estado_id", CANDIDATE_STATUS_ID)\
            .execute()
        return True
    except Exception as e:
        log_event(f"Error eliminando candidato {candidate_id}: {e}", is_error=True)
        return False


def get_candidate_by_id(candidate_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un candidato por su ID (wrapper de character)."""
    return get_character_by_id(candidate_id)


# --- FUNCIONES DE SEGUIMIENTO (MANIPULACIÓN JSON) ---

def _update_recruitment_metadata(candidate_id: int, updates: Dict[str, Any]) -> bool:
    """Helper para actualizar campos dentro de stats_json->recruitment_data"""
    try:
        char = get_character_by_id(candidate_id)
        if not char: return False
        
        stats = char.get("stats_json", {})
        rec_data = stats.get("recruitment_data", {})
        
        # Aplicar updates
        rec_data.update(updates)
        stats["recruitment_data"] = rec_data
        
        # Guardar
        update_character(candidate_id, {"stats_json": stats})
        return True
    except Exception as e:
        log_event(f"Error actualizando metadata candidato: {e}", is_error=True)
        return False


def set_candidate_tracked(player_id: int, candidate_id: int) -> bool:
    """
    Marca un candidato como seguido. Desmarca los demás.
    """
    try:
        # 1. Obtener todos los candidatos del jugador para desmarcarlos
        candidates = get_recruitment_candidates(player_id)
        
        for cand in candidates:
            if cand["is_tracked"]:
                _update_recruitment_metadata(cand["id"], {"is_tracked": False})
        
        # 2. Marcar el nuevo
        return _update_recruitment_metadata(candidate_id, {"is_tracked": True})

    except Exception as e:
        log_event(f"Error marcando seguimiento: {e}", player_id, is_error=True)
        return False


def untrack_candidate(player_id: int, candidate_id: int) -> bool:
    """Quita el seguimiento."""
    return _update_recruitment_metadata(candidate_id, {"is_tracked": False})


def get_tracked_candidate(player_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene el candidato seguido (iterando la lista parseada)."""
    candidates = get_recruitment_candidates(player_id)
    for c in candidates:
        if c.get("is_tracked"):
            return c
    return None


# --- FUNCIONES DE LIMPIEZA ---

def clear_untracked_candidates(player_id: int) -> int:
    """
    Elimina candidatos no seguidos.
    """
    try:
        candidates = get_recruitment_candidates(player_id)
        count = 0
        for c in candidates:
            if not c.get("is_tracked") and not c.get("is_being_investigated"):
                if remove_candidate(c["id"]):
                    count += 1
        return count
    except Exception as e:
        log_event(f"Error limpiando candidatos: {e}", player_id, is_error=True)
        return 0


def expire_old_candidates(player_id: int, current_tick: int, lifespan: int = CANDIDATE_LIFESPAN_TICKS) -> int:
    """
    Elimina candidatos expirados.
    """
    try:
        candidates = get_recruitment_candidates(player_id)
        expiration_tick = current_tick - lifespan
        count = 0
        names = []
        
        for c in candidates:
            tick_created = c.get("tick_created", 0)
            if not c.get("is_tracked") and not c.get("is_being_investigated") and tick_created <= expiration_tick:
                names.append(c["nombre"])
                if remove_candidate(c["id"]):
                    count += 1
        
        if count > 0:
            log_event(f"RECLUTAMIENTO: {count} candidato(s) abandonaron la estación: {', '.join(names)}", player_id)
            
        return count

    except Exception as e:
        log_event(f"Error expirando candidatos: {e}", player_id, is_error=True)
        return 0


# --- FUNCIONES DE INVESTIGACION ---

def set_investigation_state(candidate_id: int, is_investigating: bool) -> bool:
    """
    Marca estado de investigación y seguimiento.
    """
    updates = {"is_being_investigated": is_investigating}
    if is_investigating:
        updates["is_tracked"] = True # Auto-track
        
        # Desmarcar otros trackeados (lógica simplificada: asumimos que la UI maneja el flujo principal,
        # pero idealmente deberíamos limpiar otros tracked aquí también. Lo dejamos simple por ahora).
        
    return _update_recruitment_metadata(candidate_id, updates)


def apply_investigation_result(candidate_id: int, outcome: str) -> bool:
    """
    Aplica resultado de investigación y posibles descuentos.
    Persiste el conocimiento en SQL.
    """
    updates = {
        "is_being_investigated": False,
        "investigation_outcome": outcome
    }
    
    char_obj = get_character_by_id(candidate_id)
    if not char_obj:
        return False

    player_id = char_obj.get("player_id")

    # Si la investigación fue exitosa, actualizamos la tabla de conocimiento SQL
    if outcome in ["SUCCESS", "CRIT_SUCCESS"]:
        if player_id:
            # Ahora esto funcionará correctamente gracias al fix en character_repository
            set_character_knowledge_level(candidate_id, player_id, KnowledgeLevel.KNOWN)

    if outcome == "CRIT_SUCCESS":
        updates["discount_applied"] = True
        # Nota: El costo está en recruitment_data->costo. 
        # Debemos leerlo, calcular descuento y guardar.
        original = char_obj.get("stats_json", {}).get("recruitment_data", {}).get("costo", 100)
        updates["costo"] = int(original * 0.70)

    return _update_recruitment_metadata(candidate_id, updates)


def get_investigating_target_info(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Devuelve info del candidato bajo investigación.
    """
    candidates = get_recruitment_candidates(player_id)
    for c in candidates:
        if c.get("is_being_investigated"):
            return {"target_id": c["id"], "target_name": c["nombre"], "type": "CANDIDATE"}
    return None

def get_candidate_count(player_id: int) -> int:
    return len(get_recruitment_candidates(player_id))