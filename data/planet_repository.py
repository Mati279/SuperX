# data/planet_repository.py
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
"""

from typing import Dict, List, Any, Optional, Tuple
from data.database import get_supabase
from data.log_repository import log_event
from core.world_constants import BUILDING_TYPES, BASE_TIER_COSTS


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- GESTIÓN DE ACTIVOS PLANETARIOS ---

def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .single()\
            .execute()
        return response.data if response.data else None
    except Exception as e:
        log_event(f"Error obteniendo activo planetario: {e}", player_id, is_error=True)
        return None


def get_planet_asset_by_id(planet_asset_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("id", planet_asset_id)\
            .single()\
            .execute()
        return response.data if response.data else None
    except Exception:
        return None


def get_all_player_planets(player_id: int) -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del jugador: {e}", player_id, is_error=True)
        return []


def create_planet_asset(
    planet_id: int,
    system_id: int,
    player_id: int,
    settlement_name: str = "Colonia Principal",
    initial_population: int = 1000
) -> Optional[Dict[str, Any]]:
    try:
        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            "poblacion": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0,
            "seguridad": 1.0,
            "infraestructura_defensiva": 0,
            "felicidad": 1.0,
            "base_tier": 1  # Inicializar Tier 1
        }
        response = _get_db().table("planet_assets").insert(asset_data).execute()
        if response.data:
            log_event(f"Planeta colonizado: {settlement_name}", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y MÓDULOS (MÓDULO 20) ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    """
    Calcula slots totales y usados según Tier de la base (Regla 20.5).
    Tier 1: 5 slots, Tier 2: 8 slots.
    """
    asset = get_planet_asset_by_id(planet_asset_id)
    if not asset:
        return {"total": 0, "used": 0, "free": 0}
    
    tier = asset.get('base_tier', 1)
    
    # Regla Módulo 20.5
    if tier == 1:
        total_slots = 5
    elif tier == 2:
        total_slots = 8
    else:
        # Progresión lineal implícita para Tiers > 2 (ej: +3 por nivel)
        total_slots = 8 + ((tier - 2) * 3)
        
    # Contar edificios construidos
    buildings = get_planet_buildings(planet_asset_id)
    used = len(buildings)
    
    return {"total": total_slots, "used": used, "free": total_slots - used}


def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool:
    """Intenta mejorar el Tier de la Base Principal."""
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return False
        
        current_tier = asset.get('base_tier', 1)
        if current_tier >= 4:
            return False # Max tier
            
        # NOTA: Aquí se debería agregar la validación y descuento de recursos
        # usando BASE_TIER_COSTS y player_repository.update_player_resources.
        # Por ahora actualizamos directo.
        
        _get_db().table("planet_assets").update({
            "base_tier": current_tier + 1
        }).eq("id", planet_asset_id).execute()
        
        log_event(f"Base Principal mejorada a Tier {current_tier + 1}", player_id)
        return True
    except Exception as e:
        log_event(f"Error upgrade base: {e}", player_id, is_error=True)
        return False


def upgrade_infrastructure_module(planet_asset_id: int, module_key: str, player_id: int) -> str:
    """
    Mejora un módulo de infraestructura (sensores/defensa).
    Aplica regla de Overclock (Nivel Modulo <= Nivel Base + 1).
    """
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return "Asset no encontrado"
        
        base_tier = asset.get('base_tier', 1)
        current_level = asset.get(f"module_{module_key}", 0)
        
        # Regla de Overclock 20.2
        max_allowed = base_tier + 1
        
        if current_level >= max_allowed:
            return f"Límite Tecnológico alcanzado. Mejora la Base a Tier {base_tier + 1} primero."
            
        # Actualizar
        _get_db().table("planet_assets").update({
            f"module_{module_key}": current_level + 1
        }).eq("id", planet_asset_id).execute()
        
        log_event(f"Módulo {module_key} mejorado a nivel {current_level + 1}", player_id)
        return "OK"
    except Exception as e:
        log_event(f"Error upgrade module: {e}", player_id, is_error=True)
        return f"Error: {e}"


# --- GESTIÓN DE EDIFICIOS ---

def get_planet_buildings(planet_asset_id: int) -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_buildings")\
            .select("*")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo edificios: {e}", is_error=True)
        return []


def build_structure(
    planet_asset_id: int,
    player_id: int,
    building_type: str,
    tier: int = 1
) -> Optional[Dict[str, Any]]:
    """Construye un nuevo edificio si hay slots y es válido."""
    if building_type not in BUILDING_TYPES:
        return None

    definition = BUILDING_TYPES[building_type]
    
    # Validar Slots
    slots = get_base_slots_info(planet_asset_id)
    if slots['free'] <= 0:
        log_event("No hay slots de construcción disponibles.", player_id, is_error=True)
        return None

    try:
        db = _get_db()
        
        # Verificar edificios únicos (como HQ)
        if building_type == 'hq':
            existing = db.table("planet_buildings").select("id").eq("planet_asset_id", planet_asset_id).eq("building_type", "hq").execute()
            if existing.data:
                return None

        # Crear edificio
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "is_active": True,
            "pops_required": definition.get("pops_required", 0),
            "energy_consumption": definition.get("energy_cost", 0),
            "built_at_tick": 1 # Placeholder tick
        }

        response = db.table("planet_buildings").insert(building_data).execute()

        if response.data:
            log_event(f"Edificio construido: {definition['name']}", player_id)
            return response.data[0]
        return None

    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    try:
        _get_db().table("planet_buildings").delete().eq("id", building_id).execute()
        log_event(f"Edificio ID {building_id} demolido.", player_id)
        return True
    except Exception as e:
        log_event(f"Error demoliendo edificio: {e}", player_id, is_error=True)
        return False