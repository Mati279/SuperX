# data/player_repository.py
from typing import Dict, Any, Optional, IO
import uuid
from data.database import supabase
from data.log_repository import log_event
from utils.security import hash_password, verify_password
from utils.helpers import encode_image

# --- IMPORTACIONES DEL MOTOR GÉNESIS ---
from core.genesis_engine import (
    find_safe_starting_node, 
    generate_genesis_commander_stats, 
    apply_genesis_inventory,
    initialize_fog_of_war,
    grant_genesis_ship
)

def get_player_by_name(name: str) -> Optional[Dict[str, Any]]:
    try:
        response = supabase.table("players").select("*").eq("nombre", name).single().execute()
        return response.data
    except Exception:
        return None

def get_player_by_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Valida un token de sesión y devuelve el jugador asociado."""
    if not token: return None
    try:
        response = supabase.table("players").select("*").eq("session_token", token).single().execute()
        return response.data
    except Exception:
        return None

def create_session_token(player_id: int) -> str:
    """Genera un nuevo token, lo guarda en DB y lo devuelve."""
    new_token = str(uuid.uuid4())
    try:
        supabase.table("players").update({"session_token": new_token}).eq("id", player_id).execute()
        return new_token
    except Exception as e:
        log_event(f"Error al crear sesión: {e}", is_error=True)
        return ""

def clear_session_token(player_id: int) -> None:
    """Elimina el token de sesión de la base de datos."""
    try:
        supabase.table("players").update({"session_token": None}).eq("id", player_id).execute()
    except Exception as e:
        log_event(f"Error al cerrar sesión: {e}", is_error=True)

def authenticate_player(name: str, pin: str) -> Optional[Dict[str, Any]]:
    player = get_player_by_name(name)
    if player and verify_password(player['pin'], pin):
        return player
    return None

def register_player_account(
    user_name: str, 
    pin: str, 
    faction_name: str, 
    banner_file: Optional[IO[bytes]]
) -> Optional[Dict[str, Any]]:
    """
    Crea una nueva cuenta y ejecuta el PROTOCOLO DE GÉNESIS v1.5.
    """
    if get_player_by_name(user_name):
        log_event(f"Intento de registro con nombre duplicado: {user_name}", is_error=True)
        raise ValueError("El nombre de Comandante ya está en uso.")

    banner_url = f"data:image/png;base64,{encode_image(banner_file)}" if banner_file else None
    
    # 1. Crear el registro base del jugador
    new_player_data = {
        "nombre": user_name,
        "pin": hash_password(pin),
        "faccion_nombre": faction_name,
        "banner_url": banner_url,
        # Recursos en 0, se llenan en el paso de inventario
    }
    
    try:
        response = supabase.table("players").insert(new_player_data).execute()
        if not response.data:
            raise Exception("No se pudo crear el registro de jugador.")
            
        player = response.data[0]
        player_id = player['id']
        
        log_event(f"Iniciando Protocolo Génesis v1.5 para {user_name}...", player_id)

        # -----------------------------------------------------
        # PROTOCOLO GÉNESIS v1.5
        # -----------------------------------------------------

        # 2. Localización Inicial (Topología de Seguridad)
        start_system_id = find_safe_starting_node()
        log_event(f"Nodo de inserción seguro calculado: Sistema ID {start_system_id}", player_id)
        
        # Buscar planeta válido en el sistema para la base
        planet_res = supabase.table("planets").select("id").eq("system_id", start_system_id).limit(1).execute()
        # Si no hay planeta (sistema vacío o anomalía), fallback al ID 1 o error controlado
        planet_id = planet_res.data[0]['id'] if planet_res.data else 1 

        # 3. Crear Asentamiento (Outpost Scale S)
        from data.planet_repository import create_planet_asset
        create_planet_asset(
            planet_id=planet_id, 
            system_id=start_system_id, 
            player_id=player_id, 
            settlement_name=f"Puesto {faction_name}",
            initial_population=1000 # Escala S
        )

        # 4. Generar Comandante (Nivel 6)
        stats = generate_genesis_commander_stats(user_name)
        char_data = {
            "player_id": player_id,
            "nombre": user_name,
            "rango": "Comandante",
            "clase": "Operaciones",
            "nivel": stats['nivel'],
            "xp": stats['xp'],
            "ubicacion": "Puesto de Mando",
            "estado": "Disponible",
            "stats_json": stats
        }
        char_res = supabase.table("characters").insert(char_data).execute()
        char_id = char_res.data[0]['id'] if char_res.data else None

        # 5. Inventario MMFR
        apply_genesis_inventory(player_id)

        # 6. Activo Aeroespacial (Nave)
        if char_id:
            grant_genesis_ship(player_id, start_system_id, char_id)

        # 7. Niebla de Guerra
        initialize_fog_of_war(player_id, start_system_id)
        
        log_event("✅ Protocolo Génesis completado. Infiltración exitosa.", player_id)
        return player

    except Exception as e:
        log_event(f"Fallo Crítico en Génesis: {e}", is_error=True)
        raise Exception(f"Error en el sistema de registro: {e}")

# --- Funciones de Gestión Económica (MMFR) ---

def get_player_finances(player_id: int) -> Dict[str, int]:
    try:
        response = supabase.table("players")\
            .select("creditos, materiales, componentes, celulas_energia, influencia")\
            .eq("id", player_id).single().execute()
        
        if response.data:
            return response.data
        return {
            "creditos": 0, "materiales": 0, "componentes": 0, 
            "celulas_energia": 0, "influencia": 0
        }
    except Exception as e:
        log_event(f"Error al obtener finanzas para ID {player_id}: {e}", player_id, is_error=True)
        return {
            "creditos": 0, "materiales": 0, "componentes": 0, 
            "celulas_energia": 0, "influencia": 0
        }

def get_player_credits(player_id: int) -> int:
    finances = get_player_finances(player_id)
    return finances.get("creditos", 0)

def update_player_resources(player_id: int, updates: Dict[str, int]) -> bool:
    try:
        supabase.table("players").update(updates).eq("id", player_id).execute()
        # Log simplificado
        log_event(f"Suministros actualizados: {list(updates.keys())}", player_id)
        return True
    except Exception as e:
        log_event(f"Error actualizando recursos ID {player_id}: {e}", player_id, is_error=True)
        return False

def update_player_credits(player_id: int, new_credits: int) -> bool:
    return update_player_resources(player_id, {"creditos": new_credits})