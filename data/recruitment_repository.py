# data/recruitment_repository.py
"""
Repositorio para gestion de candidatos de reclutamiento.
Maneja persistencia en DB, seguimiento, investigacion y expiracion.
"""

from typing import Dict, Any, List, Optional
from data.database import get_supabase
from data.log_repository import log_event


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSTANTES ---
CANDIDATE_LIFESPAN_TICKS = 4
DEFAULT_POOL_SIZE = 3


# --- FUNCIONES CRUD ---

def get_recruitment_candidates(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los candidatos de reclutamiento de un jugador.
    Ordenados por: seguidos primero, luego por fecha de creacion.
    """
    try:
        response = _get_db().table("recruitment_candidates")\
            .select("*")\
            .eq("player_id", player_id)\
            .order("is_tracked", desc=True)\
            .order("created_at", desc=False)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo candidatos: {e}", player_id, is_error=True)
        return []


def add_candidate(
    player_id: int,
    candidate_data: Dict[str, Any],
    current_tick: int
) -> Optional[Dict[str, Any]]:
    """
    Agrega un nuevo candidato al roster de reclutamiento.

    Args:
        player_id: ID del jugador
        candidate_data: Datos del candidato (debe incluir nombre, stats_json, costo)
        current_tick: Tick actual para calcular expiracion

    Returns:
        Candidato creado o None si falla
    """
    try:
        data = {
            "player_id": player_id,
            "nombre": candidate_data.get("nombre", "Desconocido"),
            "stats_json": candidate_data.get("stats_json", {}),
            "costo": candidate_data.get("costo", 100),
            "tick_created": current_tick,
            "is_tracked": False,
            "is_being_investigated": False,
            "investigation_outcome": None,
            "discount_applied": False
        }

        response = _get_db().table("recruitment_candidates").insert(data).execute()

        if response.data:
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error agregando candidato: {e}", player_id, is_error=True)
        return None


def remove_candidate(candidate_id: int) -> bool:
    """
    Elimina un candidato del roster (al ser reclutado o por expiracion).
    """
    try:
        _get_db().table("recruitment_candidates")\
            .delete()\
            .eq("id", candidate_id)\
            .execute()
        return True
    except Exception as e:
        log_event(f"Error eliminando candidato {candidate_id}: {e}", is_error=True)
        return False


def get_candidate_by_id(candidate_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un candidato por su ID."""
    try:
        response = _get_db().table("recruitment_candidates")\
            .select("*")\
            .eq("id", candidate_id)\
            .maybe_single()\
            .execute()
        return response.data
    except Exception:
        return None


# --- FUNCIONES DE SEGUIMIENTO ---

def set_candidate_tracked(player_id: int, candidate_id: int) -> bool:
    """
    Marca un candidato como seguido. Solo puede haber uno seguido por jugador.
    Automaticamente quita el seguimiento de cualquier otro candidato.

    Args:
        player_id: ID del jugador
        candidate_id: ID del candidato a seguir

    Returns:
        True si se actualizo correctamente
    """
    try:
        db = _get_db()

        # 1. Quitar seguimiento de todos los candidatos del jugador
        db.table("recruitment_candidates")\
            .update({"is_tracked": False})\
            .eq("player_id", player_id)\
            .execute()

        # 2. Marcar el nuevo candidato como seguido
        db.table("recruitment_candidates")\
            .update({"is_tracked": True})\
            .eq("id", candidate_id)\
            .eq("player_id", player_id)\
            .execute()

        return True

    except Exception as e:
        log_event(f"Error marcando seguimiento: {e}", player_id, is_error=True)
        return False


def untrack_candidate(player_id: int, candidate_id: int) -> bool:
    """Quita el seguimiento de un candidato especifico."""
    try:
        _get_db().table("recruitment_candidates")\
            .update({"is_tracked": False})\
            .eq("id", candidate_id)\
            .eq("player_id", player_id)\
            .execute()
        return True
    except Exception:
        return False


def get_tracked_candidate(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene el candidato actualmente seguido por el jugador.
    Solo puede haber uno.
    """
    try:
        response = _get_db().table("recruitment_candidates")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_tracked", True)\
            .maybe_single()\
            .execute()
        return response.data
    except Exception:
        return None


# --- FUNCIONES DE LIMPIEZA ---

def clear_untracked_candidates(player_id: int) -> int:
    """
    Elimina todos los candidatos NO seguidos de un jugador.
    Usado cuando se solicita "Buscar Nuevos".

    Returns:
        Numero de candidatos eliminados
    """
    try:
        # Obtener IDs de candidatos no seguidos
        response = _get_db().table("recruitment_candidates")\
            .select("id")\
            .eq("player_id", player_id)\
            .eq("is_tracked", False)\
            .execute()

        if not response.data:
            return 0

        count = len(response.data)
        ids_to_delete = [c["id"] for c in response.data]

        # Eliminar
        _get_db().table("recruitment_candidates")\
            .delete()\
            .in_("id", ids_to_delete)\
            .execute()

        return count

    except Exception as e:
        log_event(f"Error limpiando candidatos: {e}", player_id, is_error=True)
        return 0


def expire_old_candidates(player_id: int, current_tick: int, lifespan: int = CANDIDATE_LIFESPAN_TICKS) -> int:
    """
    Elimina candidatos expirados (que superaron el tiempo de vida).
    No elimina candidatos seguidos ni los que estan siendo investigados.

    Args:
        player_id: ID del jugador
        current_tick: Tick actual
        lifespan: Ticks de vida de un candidato (default 4)

    Returns:
        Numero de candidatos expirados
    """
    try:
        # Calcular tick de corte
        expiration_tick = current_tick - lifespan

        # Obtener candidatos expirados (no seguidos, no investigados)
        response = _get_db().table("recruitment_candidates")\
            .select("id, nombre")\
            .eq("player_id", player_id)\
            .eq("is_tracked", False)\
            .eq("is_being_investigated", False)\
            .lte("tick_created", expiration_tick)\
            .execute()

        if not response.data:
            return 0

        count = len(response.data)
        ids_to_delete = [c["id"] for c in response.data]
        nombres = [c["nombre"] for c in response.data]

        # Eliminar
        _get_db().table("recruitment_candidates")\
            .delete()\
            .in_("id", ids_to_delete)\
            .execute()

        # Log
        if count > 0:
            log_event(f"RECLUTAMIENTO: {count} candidato(s) abandonaron la estacion: {', '.join(nombres)}", player_id)

        return count

    except Exception as e:
        log_event(f"Error expirando candidatos: {e}", player_id, is_error=True)
        return 0


# --- FUNCIONES DE INVESTIGACION ---

def set_investigation_state(candidate_id: int, is_investigating: bool) -> bool:
    """
    Marca/desmarca un candidato como siendo investigado.
    Si se inicia investigacion, tambien se marca como seguido automaticamente.
    """
    try:
        update_data = {"is_being_investigated": is_investigating}

        # Si inicia investigacion, marcar como seguido
        if is_investigating:
            # Primero obtener el player_id
            candidate = get_candidate_by_id(candidate_id)
            if candidate:
                # Quitar seguimiento de otros
                _get_db().table("recruitment_candidates")\
                    .update({"is_tracked": False})\
                    .eq("player_id", candidate["player_id"])\
                    .neq("id", candidate_id)\
                    .execute()

                update_data["is_tracked"] = True

        _get_db().table("recruitment_candidates")\
            .update(update_data)\
            .eq("id", candidate_id)\
            .execute()

        return True

    except Exception as e:
        log_event(f"Error actualizando estado investigacion: {e}", is_error=True)
        return False


def apply_investigation_result(candidate_id: int, outcome: str) -> bool:
    """
    Aplica el resultado de una investigacion a un candidato.

    Args:
        candidate_id: ID del candidato
        outcome: 'SUCCESS', 'CRIT_SUCCESS', 'FAIL', 'CRIT_FAIL'

    Returns:
        True si se actualizo correctamente
    """
    try:
        update_data = {
            "is_being_investigated": False,
            "investigation_outcome": outcome
        }

        # Si es exito critico, aplicar descuento
        if outcome == "CRIT_SUCCESS":
            update_data["discount_applied"] = True

            # Obtener candidato para actualizar costo
            candidate = get_candidate_by_id(candidate_id)
            if candidate:
                original_cost = candidate.get("costo", 100)
                discounted_cost = int(original_cost * 0.70)  # 30% descuento
                update_data["costo"] = discounted_cost

        _get_db().table("recruitment_candidates")\
            .update(update_data)\
            .eq("id", candidate_id)\
            .execute()

        return True

    except Exception as e:
        log_event(f"Error aplicando resultado investigacion: {e}", is_error=True)
        return False


def get_investigating_candidate(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene el candidato que esta siendo investigado actualmente.
    """
    try:
        response = _get_db().table("recruitment_candidates")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_being_investigated", True)\
            .maybe_single()\
            .execute()
        return response.data
    except Exception:
        return None


def get_candidate_count(player_id: int) -> int:
    """Obtiene el numero de candidatos de un jugador."""
    try:
        response = _get_db().table("recruitment_candidates")\
            .select("id", count="exact")\
            .eq("player_id", player_id)\
            .execute()
        return response.count if response.count else 0
    except Exception:
        return 0
