# data/planet_repository.py
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
Refactorizado para MMFR V2: Seguridad dinámica (0-100) y Mantenimiento.
"""

from typing import Dict, List, Any, Optional, Tuple
from .database import get_supabase
from .log_repository import log_event
from core.world_constants import BUILDING_TYPES, BASE_TIER_COSTS, ECONOMY_RATES


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTA DE PLANETAS (TABLA MUNDIAL) ---

def get_planet_by_id(planet_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene información de un planeta de la tabla mundial 'planets'."""
    try:
        response = _get_db().table("planets")\
            .select("*")\
            .eq("id", planet_id)\
            .single()\
            .execute()
        return response.data if response.data else None
    except Exception:
        return None


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


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """Obtiene planetas del jugador con edificios precargados para el tick económico."""
    try:
        planets_response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()

        planets = planets_response.data if planets_response.data else []
        if not planets: return []

        planet_ids = [p["id"] for p in planets]
        buildings_response = _get_db().table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", planet_ids)\
            .execute()

        buildings = buildings_response.data if buildings_response.data else []
        buildings_by_planet: Dict[int, List[Dict]] = {}
        for building in buildings:
            pid = building["planet_asset_id"]
            if pid not in buildings_by_planet: buildings_by_planet[pid] = []
            buildings_by_planet[pid].append(building)

        for planet in planets:
            planet["buildings"] = buildings_by_planet.get(planet["id"], [])

        return planets
    except Exception as e:
        log_event(f"Error obteniendo planetas con edificios: {e}", player_id, is_error=True)
        return []


def create_planet_asset(
    planet_id: int,
    system_id: int,
    player_id: int,
    settlement_name: str = "Colonia Principal",
    initial_population: float = 1.0 # Default actualizado a escala float (1.0 = 1B)
) -> Optional[Dict[str, Any]]:
    """Crea una colonia con seguridad inicial basada en población (MMFR V2)."""
    try:
        # Cálculo de seguridad inicial (Scale 0-100)
        # Fórmula V2: Base + (Población * Tasa)
        # Nota: Population ya es un float en escala de billones.
        base_sec = ECONOMY_RATES.get("security_base", 25.0)
        per_pop = ECONOMY_RATES.get("security_per_1b_pop", 5.0)
        
        pop_bonus = initial_population * per_pop
        initial_security = base_sec + pop_bonus
        
        # Clamp 1-100
        initial_security = max(1.0, min(initial_security, 100.0))

        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            "poblacion": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0, # Float explícito
            "seguridad": initial_security, 
            "infraestructura_defensiva": 0,
            "base_tier": 1
        }
        # Nota: La columna 'felicidad' ha sido eliminada de la estructura
        
        response = _get_db().table("planet_assets").insert(asset_data).execute()
        if response.data:
            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {initial_security:.1f})", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y MÓDULOS (MÓDULO 20) ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    asset = get_planet_asset_by_id(planet_asset_id)
    if not asset: return {"total": 0, "used": 0, "free": 0}
    tier = asset.get('base_tier', 1)
    
    if tier == 1: total_slots = 5
    elif tier == 2: total_slots = 8
    else: total_slots = 8 + ((tier - 2) * 3)
        
    buildings = get_planet_buildings(planet_asset_id)
    used = len(buildings)
    return {"total": total_slots, "used": used, "free": total_slots - used}


def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool:
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return False
        current_tier = asset.get('base_tier', 1)
        if current_tier >= 4: return False 
        
        # Aquí se debería validar recursos del jugador antes de actualizar
        # (Lógica pendiente de integración completa con player_repository)
        
        _get_db().table("planet_assets").update({
            "base_tier": current_tier + 1
        }).eq("id", planet_asset_id).execute()
        
        log_event(f"Base Principal mejorada a Tier {current_tier + 1}", player_id)
        return True
    except Exception as e:
        log_event(f"Error upgrade base: {e}", player_id, is_error=True)
        return False


def upgrade_infrastructure_module(planet_asset_id: int, module_key: str, player_id: int) -> str:
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return "Asset no encontrado"
        
        base_tier = asset.get('base_tier', 1)
        current_level = asset.get(f"module_{module_key}", 0)
        
        # Regla de Overclock 20.2
        max_allowed = base_tier + 1
        if current_level >= max_allowed:
            return f"Límite Tecnológico. Mejora la Base a Tier {base_tier + 1}."
            
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
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    
    slots = get_base_slots_info(planet_asset_id)
    if slots['free'] <= 0:
        log_event("No hay slots disponibles.", player_id, is_error=True)
        return None

    try:
        db = _get_db()
        if building_type == 'hq':
            existing = db.table("planet_buildings").select("id").eq("planet_asset_id", planet_asset_id).eq("building_type", "hq").execute()
            if existing.data: return None

        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "is_active": True,
            "pops_required": definition.get("pops_required", 0),
            "energy_consumption": 0, # Deprecado, usamos 'maintenance' en constantes
            "built_at_tick": 1 
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


def get_luxury_extraction_sites_for_player(player_id: int) -> List[Dict[str, Any]]:
    try:
        response = _get_db().table("luxury_extraction_sites")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_active", True)\
            .execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios de extracción: {e}", player_id, is_error=True)
        return []


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    if not updates: return True
    try:
        db = _get_db()
        for planet_id, security in updates:
            db.table("planet_assets").update({"seguridad": security}).eq("id", planet_id).execute()
        return True
    except Exception as e:
        log_event(f"Error batch security update: {e}", is_error=True)
        return False


def batch_update_building_status(updates: List[Tuple[int, bool]]) -> Tuple[int, int]:
    if not updates: return (0, 0)
    success, failed = 0, 0
    db = _get_db()
    for building_id, is_active in updates:
        try:
            db.table("planet_buildings").update({"is_active": is_active}).eq("id", building_id).execute()
            success += 1
        except Exception: failed += 1
    return (success, failed)


def update_planet_asset(planet_asset_id: int, updates: Dict[str, Any]) -> bool:
    try:
        _get_db().table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando activo {planet_asset_id}: {e}", is_error=True)
        return False