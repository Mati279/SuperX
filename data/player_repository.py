# data/player_repository.py
"""
Repositorio de Jugadores.
Gestiona todas las operaciones de persistencia relacionadas con jugadores,
autenticación y recursos.
"""

from typing import Dict, Any, Optional, IO, List
import uuid

from data.database import get_supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTAS DE JUGADORES ---

def get_all_players() -> List[Dict[str, Any]]:
    """
    Obtiene todos los jugadores registrados.

    Returns:
        Lista de jugadores
    """
    try:
        response = _get_db().table("players").select("id, nombre").execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo lista de jugadores: {e}", is_error=True)
        return []


def get_player_by_id(player_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene un jugador por su ID.

    Args:
        player_id: ID del jugador

    Returns:
        Datos del jugador o None
    """
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
    """
    Obtiene un jugador por su nombre.

    Args:
        name: Nombre del jugador

    Returns:
        Datos del jugador o None
    """
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
    """
    Obtiene un jugador por su token de sesión.

    Args:
        token: Token de sesión

    Returns:
        Datos del jugador o None
    """
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
    """
    Crea un nuevo token de sesión para el jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Token generado o cadena vacía si falla
    """
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
    """
    Limpia el token de sesión del jugador.

    Args:
        player_id: ID del jugador
    """
    try:
        _get_db().table("players")\
            .update({"session_token": None})\
            .eq("id", player_id)\
            .execute()
    except Exception:
        pass


# --- AUTENTICACIÓN ---

def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]:
    """
    Autentica un jugador por nombre y PIN.

    Args:
        name: Nombre del jugador
        pin: PIN en texto plano

    Returns:
        Datos del jugador si la autenticación es exitosa, None si falla
    """
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
    Crea una nueva cuenta y ejecuta el PROTOCOLO DE GÉNESIS v1.5.
    Versión: TITAN (Blindaje contra duplicados y FKs)

    Args:
        user_name: Nombre del comandante
        pin: PIN de acceso
        faction_name: Nombre de la facción
        banner_file: Archivo de banner (opcional)

    Returns:
        Datos del jugador creado

    Raises:
        ValueError: Si el nombre ya está en uso
        Exception: Si falla el registro
    """
    from core.genesis_engine import (
        find_safe_starting_node,
        generate_genesis_commander_stats,
        apply_genesis_inventory,
        initialize_fog_of_war,
        grant_genesis_ship
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

        # 2. Localización y Base
        start_system_id = find_safe_starting_node()
        planet_res = db.table("planets")\
            .select("id")\
            .eq("system_id", start_system_id)\
            .limit(1)\
            .execute()
        planet_id_val = planet_res.data[0]['id'] if planet_res.data else 1

        from data.planet_repository import create_planet_asset
        create_planet_asset(planet_id_val, start_system_id, player_id, f"Base {faction_name}", 1000)

        # 3. Comandante (Punto Crítico de Duplicados)
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
            char_res = db.table("characters").insert(char_data).execute()
            char_id = char_res.data[0]['id'] if char_res.data else None
        except Exception as e:
            err = str(e)
            # Si el error es duplicado, recuperar el existente
            if "duplicate key" in err or "23505" in err:
                print(f"⚠️ Comandante ya existente para ID {player_id}. Recuperando...")
                existing = db.table("characters")\
                    .select("id")\
                    .eq("player_id", player_id)\
                    .eq("es_comandante", True)\
                    .single()\
                    .execute()
                char_id = existing.data['id'] if existing.data else None
            else:
                raise e

        # 4. Inventario y Nave (Idempotente)
        apply_genesis_inventory(player_id)

        if char_id:
            ships = db.table("ships").select("id").eq("player_id", player_id).execute()
            if not ships.data:
                grant_genesis_ship(player_id, start_system_id, char_id)

        # 5. Niebla de Guerra
        initialize_fog_of_war(player_id, start_system_id)

        log_event("✅ Protocolo Génesis completado exitosamente.", player_id)
        return player

    except Exception as e:
        # --- ROLLBACK ATÓMICO ---
        print(f"🔥 FALLO CRÍTICO GENESIS: {e}")

        if player_id:
            print(f"🧹 Ejecutando limpieza para ID {player_id}...")
            try:
                db.table("players").delete().eq("id", player_id).execute()
            except Exception as del_err:
                print(f"❌ Falló la limpieza DB: {del_err}")

        raise Exception(f"Registro fallido: {e}")


# --- GESTIÓN DE RECURSOS ---

def get_player_finances(player_id: int) -> Dict[str, Any]:
    """
    Obtiene los recursos financieros del jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Diccionario con recursos (creditos, materiales, componentes, etc.)
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
    """
    Obtiene los créditos del jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Cantidad de créditos
    """
    finances = get_player_finances(player_id)
    return finances.get("creditos", 0)


def update_player_resources(player_id: int, updates: Dict[str, Any]) -> bool:
    """
    Actualiza los recursos del jugador.

    Args:
        player_id: ID del jugador
        updates: Diccionario con recursos a actualizar

    Returns:
        True si la actualización fue exitosa
    """
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
    """
    Actualiza los créditos del jugador.

    Args:
        player_id: ID del jugador
        new_credits: Nueva cantidad de créditos

    Returns:
        True si la actualización fue exitosa
    """
    return update_player_resources(player_id, {"creditos": new_credits})


def add_player_credits(player_id: int, amount: int) -> bool:
    """
    Añade créditos al jugador.

    Args:
        player_id: ID del jugador
        amount: Cantidad a añadir (puede ser negativo)

    Returns:
        True si la operación fue exitosa
    """
    current = get_player_credits(player_id)
    new_amount = max(0, current + amount)  # No permitir negativos
    return update_player_credits(player_id, new_amount)


def delete_player_account(player_id: int) -> bool:
    """
    Elimina permanentemente la cuenta del jugador y todos sus datos relacionados.
    Utiliza el CASCADE de la base de datos.
    
    Args:
        player_id: ID del jugador a eliminar
        
    Returns:
        True si la eliminación fue exitosa, False en caso contrario
    """
    try:
        print(f"⚠️ [DEBUG] Iniciando borrado completo de cuenta ID {player_id}")
        _get_db().table("players").delete().eq("id", player_id).execute()
        return True
    except Exception as e:
        print(f"❌ Error borrando cuenta {player_id}: {e}")
        return False