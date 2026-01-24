# data/player_repository.py (Completo)
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
        # FIX V10: Capturamos el resultado completo (dict) en lugar de solo bool
        genesis_result = genesis_protocol(player_id)
        
        # Soporte retrocompatible (por si genesis devuelve solo bool en versiones viejas)
        is_success = genesis_result if isinstance(genesis_result, bool) else genesis_result.get("success", False)
        
        if not is_success:
            raise GenesisProtocolError("El protocolo Genesis devolvió False.", {"player_id": player_id})

        # Extraer contexto de ubicación del Genesis
        genesis_ctx = genesis_result if isinstance(genesis_result, dict) else {}
        loc_system = genesis_ctx.get("system_id")
        loc_planet = genesis_ctx.get("planet_id")
        loc_sector = genesis_ctx.get("sector_id")

        # 3. Comandante (Responsabilidad del Repo, el engine solo maneja mundo/assets)
        stats = generate_genesis_commander_stats(user_name)
        
        # FIX SCHEMA V2: Inyectar ubicación en JSON y en Columnas SQL
        if "estado" not in stats: stats["estado"] = {}
        
        # Estructura completa de ubicación para JSON
        stats["estado"]["ubicacion"] = {
            "system_id": loc_system,
            "planet_id": loc_planet,
            "sector_id": loc_sector,
            "ubicacion_local": "Puesto de Mando"
        }

        char_data = {
            "player_id": player_id,
            "nombre": user_name,
            "rango": "Comandante",
            "es_comandante": True,
            # Schema V2 changes:
            "class_id": 99,       # 99 = Comandante
            "level": stats['nivel'],
            "xp": stats['xp'],
            "estado_id": 1,       # 1 = Disponible
            "stats_json": stats,
            
            # FIX: Inyección de columnas de ubicación SQL (Source of Truth)
            "location_system_id": loc_system,
            "location_planet_id": loc_planet,
            "location_sector_id": loc_sector
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
    """
    Elimina permanentemente la cuenta del jugador y TODOS sus datos asociados (Deep Wipe).
    Evita dejar registros huérfanos que contaminen futuras partidas.
    """
    db = _get_db()
    print(f"⚠️ [DEBUG] Iniciando borrado completo en cascada para cuenta ID {player_id}")
    
    try:
        # 1. Borrar Conocimiento de Tripulación (Evita que el nuevo usuario "herede" conocimiento)
        try:
            db.table("character_knowledge").delete().eq("player_id", player_id).execute()
            print("  - Tabla 'character_knowledge' limpiada.")
        except Exception as e:
             print(f"  - Warning: Fallo al limpiar 'character_knowledge': {e}")

        # 2. Borrar Exploración (Niebla de Guerra)
        try:
            db.table("player_exploration").delete().eq("player_id", player_id).execute()
            print("  - Tabla 'player_exploration' limpiada.")
        except Exception as e:
            print(f"  - Warning: Fallo al limpiar 'player_exploration': {e}")
            
        # 3. Borrar Logs (Historial de eventos)
        try:
            db.table("logs").delete().eq("player_id", player_id).execute()
            print("  - Tabla 'logs' limpiada.")
        except Exception as e:
            print(f"  - Warning: Fallo al limpiar 'logs': {e}")

        # 4. Borrar Activos Planetarios (Bases)
        try:
            db.table("planet_assets").delete().eq("player_id", player_id).execute()
            print("  - Tabla 'planet_assets' limpiada.")
        except Exception as e:
             print(f"  - Warning: Fallo al limpiar 'planet_assets': {e}")

        # 5. Borrar Personajes (Tripulación)
        # Nota: character_knowledge puede referenciar a estos ID, por eso se borra knowledge primero.
        try:
            db.table("characters").delete().eq("player_id", player_id).execute()
            print("  - Tabla 'characters' limpiada.")
        except Exception as e:
            print(f"  - Warning: Fallo al limpiar 'characters': {e}")

        # 6. Finalmente, borrar al Jugador
        db.table("players").delete().eq("id", player_id).execute()
        print(f"✅ Cuenta ID {player_id} eliminada exitosamente.")
        return True
        
    except Exception as e:
        print(f"❌ Error CRÍTICO borrando cuenta {player_id}: {e}")
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
        # FIX V10: Capturar resultado como Dict
        genesis_result = genesis_protocol(player_id)
        is_success = genesis_result if isinstance(genesis_result, bool) else genesis_result.get("success", False)
        
        if not is_success:
            raise Exception("Genesis Protocol failed during reset")

        # Contexto de ubicación
        genesis_ctx = genesis_result if isinstance(genesis_result, dict) else {}
        loc_system = genesis_ctx.get("system_id")
        loc_planet = genesis_ctx.get("planet_id")
        loc_sector = genesis_ctx.get("sector_id")

        # 2. Re-crear Comandante (Responsabilidad del Repo)
        stats = generate_genesis_commander_stats(player.get('nombre', 'Comandante'))
        
        # FIX SCHEMA V2: Inyectar ubicación completa
        if "estado" not in stats: stats["estado"] = {}
        stats["estado"]["ubicacion"] = {
            "system_id": loc_system,
            "planet_id": loc_planet,
            "sector_id": loc_sector,
            "ubicacion_local": "Puesto de Mando"
        }
        
        char_data = {
            "player_id": player_id,
            "nombre": player.get('nombre', 'Comandante'),
            "rango": "Comandante",
            "es_comandante": True,
            # Schema V2 changes:
            "class_id": 99,       # 99 = Comandante
            "level": stats['nivel'],
            "xp": stats['xp'],
            "estado_id": 1,       # 1 = Disponible
            "stats_json": stats,
            
            # FIX: Columnas SQL de ubicación
            "location_system_id": loc_system,
            "location_planet_id": loc_planet,
            "location_sector_id": loc_sector
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