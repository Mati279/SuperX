# data/player_repository.py
"""
Repositorio de Jugadores.
Gestiona todas las operaciones de persistencia relacionadas con jugadores,
autenticación y recursos.
"""

from typing import Dict, Any, Optional, IO, List
import uuid
import random # Importado para generación de población aleatoria

from data.database import get_supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image
from core.exceptions import GenesisProtocolError


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


def _rollback_genesis(db, player_id: int) -> None:
    """
    Comprehensive rollback of all resources created during failed Genesis.
    Deletes in reverse order of creation to respect FK constraints.

    Args:
        db: Database client
        player_id: ID of the player to clean up
    """
    if not player_id:
        return

    print(f"Executing Genesis rollback for player ID {player_id}...")

    # 1. Delete exploration/FOW entries
    try:
        db.table("player_exploration").delete().eq("player_id", player_id).execute()
        print(f"  - Cleaned player_exploration")
    except Exception as e:
        print(f"  - Rollback warning (exploration): {e}")

    # 2. Delete characters
    try:
        db.table("characters").delete().eq("player_id", player_id).execute()
        print(f"  - Cleaned characters")
    except Exception as e:
        print(f"  - Rollback warning (characters): {e}")

    # 3. Delete planet assets
    try:
        db.table("planet_assets").delete().eq("player_id", player_id).execute()
        print(f"  - Cleaned planet_assets")
    except Exception as e:
        print(f"  - Rollback warning (planet_assets): {e}")

    # 4. Delete player record (last, as other tables may have FK to it)
    try:
        db.table("players").delete().eq("id", player_id).execute()
        print(f"  - Cleaned players")
    except Exception as e:
        print(f"  - Rollback CRITICAL (player): {e}")


# --- CONSULTAS DE JUGADORES ---

def get_all_players() -> List[Dict[str, Any]]:
    """
    Obtiene todos los jugadores registrados.
    Returns: Lista de jugadores
    """
    try:
        response = _get_db().table("players").select("id, nombre").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo lista de jugadores: {e}", is_error=True)
        return []


def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un jugador por su ID."""
    try:
        response = _get_db().table("players")\
            .select("*")\
            .eq("id", player_id)\
            .single()\
            .execute()
        return response.data
    except Exception:
        return None


def get_player_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Obtiene un jugador por su nombre."""
    try:
        response = _get_db().table("players")\
            .select("*")\
            .eq("nombre", name)\
            .single()\
            .execute()
        return response.data
    except Exception:
        return None


def get_player_by_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Obtiene un jugador por su token de sesión."""
    if not token:
        return None
    try:
        response = _get_db().table("players")\
            .select("*")\
            .eq("session_token", token)\
            .single()\
            .execute()
        return response.data
    except Exception:
        return None


# --- GESTIÓN DE SESIONES ---

def create_session_token(player_id: int) -> str:
    new_token = str(uuid.uuid4())
    try:
        _get_db().table("players")\
            .update({"session_token": new_token})\
            .eq("id", player_id)\
            .execute()
        return new_token
    except Exception:
        return ""


def clear_session_token(player_id: int) -> None:
    try:
        _get_db().table("players")\
            .update({"session_token": None})\
            .eq("id", player_id)\
            .execute()
    except Exception:
        pass


# --- AUTENTICACIÓN ---

def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]:
    player = get_player_by_name(name)
    if player and verify_password(player['pin'], pin):
        return player
    return None


# --- REGISTRO DE JUGADORES ---

def register_player_account(
    user_name: str,
    pin: str,
    faction_name: str,
    banner_file: Optional[IO[bytes]]
) -> Optional[Dict[str, Any]]:
    """
    Crea una nueva cuenta y ejecuta el PROTOCOLO DE GÉNESIS v2.0 (Vía Engine).
    Versión: TITAN Refactorizado (Delega a genesis_protocol)
    """
    # Importación local para evitar ciclos y usar el protocolo centralizado
    from core.genesis_engine import (
        genesis_protocol,
        generate_genesis_commander_stats
    )

    if get_player_by_name(user_name):
        raise ValueError("El nombre de Comandante ya está en uso.")

    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    player_id = None
    db = _get_db()

    try:
        # 1. Crear el registro base del jugador
        new_player_data = {
            "nombre": user_name,
            "pin": hash_password(pin),
            "faccion_nombre": faction_name,
            "banner_url": banner_url,
        }

        response = db.table("players").insert(new_player_data).execute()
        if not response.data:
            raise Exception("DB Error: No se pudo crear jugador.")

        player = response.data[0]
        player_id = player['id']

        print(f"🚀 Iniciando Génesis para {user_name} ID: {player_id}")

        # 2. Ejecutar Protocolo Génesis (Delegado al Engine)
        # Esto maneja: Ubicación segura, Selección Aleatoria de Planeta, 
        # Población (MMFR), Inventario Inicial y Niebla de Guerra.
        genesis_success = genesis_protocol(player_id)
        
        if not genesis_success:
            raise GenesisProtocolError("El protocolo Genesis devolvió False.", {"player_id": player_id})

        # 3. Comandante (Responsabilidad del Repo, el engine solo maneja mundo/assets)
        stats = generate_genesis_commander_stats(user_name)
        char_data = {
            "player_id": player_id,
            "nombre": user_name,
            "rango": "Comandante",
            "es_comandante": True,
            "clase": "Operaciones",
            "nivel": stats['nivel'],
            "xp": stats['xp'],
            "ubicacion": "Puesto de Mando",
            "estado": "Disponible",
            "stats_json": stats
        }

        try:
            db.table("characters").insert(char_data).execute()
        except Exception as e:
            err = str(e)
            # Si el error es duplicado, recuperar el existente (idempotencia)
            if "duplicate key" in err or "23505" in err:
                print(f"⚠️ Comandante ya existente para ID {player_id}. Recuperando...")
            else:
                raise e

        log_event("✅ Registro de cuenta y Génesis completados exitosamente.", player_id)
        return player

    except Exception as e:
        # --- COMPREHENSIVE ROLLBACK ---
        print(f"GENESIS CRITICAL FAILURE: {e}")
        log_event(f"Genesis Protocol FAILED: {e}", player_id, is_error=True)

        if player_id:
            _rollback_genesis(db, player_id)

        raise GenesisProtocolError(f"Registration failed: {e}", {"player_id": player_id})


# --- GESTIÓN DE RECURSOS ---

def get_player_finances(player_id: int) -> Dict[str, Any]:
    """
    Obtiene los recursos financieros del jugador.
    """
    try:
        response = _get_db().table("players")\
            .select("creditos, materiales, componentes, celulas_energia, influencia, recursos_lujo")\
            .eq("id", player_id)\
            .single()\
            .execute()

        if response.data:
            return response.data

        return _default_finances()
    except Exception:
        return _default_finances()


def get_player_resources(player_id: int) -> Dict[str, Any]:
    """
    ALIAS para compatibilidad con UI.
    Redirige a get_player_finances.
    """
    return get_player_finances(player_id)


def _default_finances() -> Dict[str, Any]:
    """Retorna valores por defecto de finanzas."""
    return {
        "creditos": 0,
        "materiales": 0,
        "componentes": 0,
        "celulas_energia": 0,
        "influencia": 0,
        "recursos_lujo": {}
    }


def get_player_credits(player_id: int) -> int:
    """Obtiene los créditos del jugador."""
    finances = get_player_finances(player_id)
    return finances.get("creditos", 0)


def update_player_resources(player_id: int, updates: Dict[str, Any]) -> bool:
    """Actualiza los recursos del jugador."""
    try:
        _get_db().table("players")\
            .update(updates)\
            .eq("id", player_id)\
            .execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando recursos ID {player_id}: {e}", player_id, is_error=True)
        return False


def update_player_credits(player_id: int, new_credits: int) -> bool:
    """Actualiza los créditos del jugador."""
    return update_player_resources(player_id, {"creditos": new_credits})


def add_player_credits(player_id: int, amount: int) -> bool:
    """Añade créditos al jugador."""
    current = get_player_credits(player_id)
    new_amount = max(0, current + amount)  # No permitir negativos
    return update_player_credits(player_id, new_amount)


def delete_player_account(player_id: int) -> bool:
    """Elimina permanentemente la cuenta del jugador."""
    try:
        print(f"⚠️ [DEBUG] Iniciando borrado completo de cuenta ID {player_id}")
        _get_db().table("players").delete().eq("id", player_id).execute()
        return True
    except Exception as e:
        print(f"❌ Error borrando cuenta {player_id}: {e}")
        return False


def reset_player_progress(player_id: int) -> bool:
    """
    Realiza un 'Soft Reset' de la cuenta del jugador.
    Elimina progreso, activos, personajes y exploración, pero MANTIENE la cuenta (ID, nombre, pass).
    Luego re-ejecuta el Protocolo Génesis.

    Args:
        player_id: ID del jugador a reiniciar.
    
    Returns:
        bool: True si el reinicio fue exitoso.
    """
    # Imports locales
    from core.genesis_engine import (
        genesis_protocol,
        generate_genesis_commander_stats
    )

    db = _get_db()
    print(f"🔄 [RESET] Iniciando reinicio de cuenta para jugador {player_id}")

    try:
        # 0. Obtener datos clave antes de limpiar (necesitamos nombre y facción)
        player = get_player_by_id(player_id)
        if not player:
            print("❌ Jugador no encontrado para reset.")
            return False
            
        # --- FASE 1: WIPE (Limpieza Profunda) ---
        
        # A. Limpiar Exploración
        db.table("player_exploration").delete().eq("player_id", player_id).execute()
        
        # B. Limpiar Activos Planetarios (Bases)
        db.table("planet_assets").delete().eq("player_id", player_id).execute()
        
        # C. Limpiar Personajes (Incluido el Comandante anterior)
        db.table("characters").delete().eq("player_id", player_id).execute()
        
        # D. Limpiar Logs (Opcional)
        try:
            db.table("logs").delete().eq("player_id", player_id).execute()
        except Exception:
            pass

        # E. Resetear Recursos y Estado en tabla players
        db.table("players").update({
            "creditos": 0,
            "materiales": 0,
            "componentes": 0,
            "celulas_energia": 0,
            "influencia": 0,
            "recursos_lujo": {}
        }).eq("id", player_id).execute()

        print(f"✅ [RESET] Fase de limpieza completada para {player_id}")

        # --- FASE 2: RE-GÉNESIS (Reconstrucción Vía Engine) ---

        # 1. Ejecutar Protocolo Génesis Centralizado
        genesis_success = genesis_protocol(player_id)
        if not genesis_success:
            raise Exception("Genesis Protocol failed during reset")

        # 2. Re-crear Comandante (Responsabilidad del Repo)
        stats = generate_genesis_commander_stats(player.get('nombre', 'Comandante'))
        char_data = {
            "player_id": player_id,
            "nombre": player.get('nombre', 'Comandante'),
            "rango": "Comandante",
            "es_comandante": True,
            "clase": "Operaciones",
            "nivel": stats['nivel'],
            "xp": stats['xp'],
            "ubicacion": "Puesto de Mando",
            "estado": "Disponible",
            "stats_json": stats
        }
        db.table("characters").insert(char_data).execute()

        # Finalización
        log_event("🔄 CUENTA REINICIADA: Protocolo Génesis re-ejecutado.", player_id)
        print(f"✅ [RESET] Protocolo completado exitosamente para {player_id}")
        return True

    except Exception as e:
        log_event(f"CRITICAL ERROR RESET ACCOUNT: {e}", player_id, is_error=True)
        print(f"❌ Error crítico en Reset Account: {e}")
        return False