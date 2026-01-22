# data/planet_repository.py (Completo)
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
Refactorizado para MMFR V2: Seguridad dinámica (0-100) y Mantenimiento.
Actualizado v4.3.0: Integración completa de Planetología Avanzada (Sectores).
Actualizado v4.4.0: Persistencia de Seguridad Galáctica y Desgloses.
Corrección v4.4.1: Consultas seguras (maybe_single) para assets opcionales.
"""

from typing import Dict, List, Any, Optional, Tuple
from .database import get_supabase
from .log_repository import log_event
from .world_repository import get_world_state
from core.world_constants import BUILDING_TYPES, BASE_TIER_COSTS, ECONOMY_RATES


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTA DE PLANETAS (TABLA MUNDIAL) ---

def get_planet_by_id(planet_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene información de un planeta de la tabla mundial 'planets'."""
    try:
        response = _get_db().table("planets")\
            .select("id, name, system_id, biome, mass_class, orbital_ring, is_habitable, surface_owner_id, orbital_owner_id, is_disputed, security, security_breakdown")\
            .eq("id", planet_id)\
            .single()\
            .execute()
        return response.data if response.data else None
    except Exception:
        return None


# --- GESTIÓN DE ACTIVOS PLANETARIOS ---

def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    try:
        # V4.4.1: Usamos maybe_single() para evitar errores cuando no hay colonia
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .maybe_single()\
            .execute()
        return response.data 
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
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados.
    Actualizado v4.3.0: Mapeo robusto de sectores para visualización en UI.
    """
    try:
        db = _get_db()
        planets_response = db.table("planet_assets")\
            .select("*, planets(orbital_owner_id, surface_owner_id, is_disputed, biome)")\
            .eq("player_id", player_id)\
            .execute()

        assets = planets_response.data if planets_response.data else []
        if not assets: return []

        planet_ids = [a["planet_id"] for a in assets]
        asset_ids = [a["id"] for a in assets]

        # Obtener Edificios
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response.data else []

        # Obtener Sectores
        sectors_response = db.table("sectors")\
            .select("id, type, planet_id, slots, buildings_count")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response.data else []
        
        sector_map = {s["id"]: s for s in sectors_data}

        buildings_by_asset: Dict[int, List[Dict]] = {}
        for building in buildings:
            aid = building["planet_asset_id"]
            if aid not in buildings_by_asset: buildings_by_asset[aid] = []
            
            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id) if sec_id else None
            
            building["sector_type"] = sector["type"] if sector else "Desconocido"
            building["sector_info"] = sector
            
            buildings_by_asset[aid].append(building)

        for asset in assets:
            planet_data = asset.get("planets", {})
            asset["orbital_owner_id"] = planet_data.get("orbital_owner_id")
            asset["surface_owner_id"] = planet_data.get("surface_owner_id")
            asset["is_disputed"] = planet_data.get("is_disputed", False)
            asset["biome"] = planet_data.get("biome", "Desconocido")

            asset["buildings"] = buildings_by_asset.get(asset["id"], [])
            asset["sectors"] = [s for s in sectors_data if s["planet_id"] == asset["planet_id"]]

        return assets
    except Exception as e:
        log_event(f"Error obteniendo planetas full data: {e}", player_id, is_error=True)
        return []


def create_planet_asset(
    planet_id: int,
    system_id: int,
    player_id: int,
    settlement_name: str = "Colonia Principal",
    initial_population: float = 1.0 
) -> Optional[Dict[str, Any]]:
    """Crea una colonia con seguridad inicial basada en población."""
    try:
        base_sec = ECONOMY_RATES.get("security_base", 25.0)
        per_pop = ECONOMY_RATES.get("security_per_1b_pop", 5.0)
        
        pop_bonus = initial_population * per_pop
        initial_security = base_sec + pop_bonus
        initial_security = max(1.0, min(initial_security, 100.0))

        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            "poblacion": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0,
            # "seguridad": initial_security, <-- ELIMINADO V4.4
            "infraestructura_defensiva": 0,
            "base_tier": 1
        }
        
        response = _get_db().table("planet_assets").insert(asset_data).execute()
        
        if response.data:
            # V4.4: Actualizar seguridad en la tabla PLANETS
            _get_db().table("planets").update({
                "surface_owner_id": player_id,
                "security": initial_security
            }).eq("id", planet_id).execute()
            
            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {initial_security:.1f})", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y SECTORES (MÓDULO 20 / V4.3) ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    """Calcula slots totales sumando los de todos los sectores del planeta."""
    try:
        db = _get_db()
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return {"total": 0, "used": 0, "free": 0}
        
        planet_id = asset.get("planet_id")
        sectors_res = db.table("sectors").select("slots").eq("planet_id", planet_id).execute()
        total_slots = sum(s["slots"] for s in sectors_res.data) if sectors_res.data else 0
        
        buildings_res = db.table("planet_buildings").select("id", count="exact").eq("planet_asset_id", planet_asset_id).execute()
        used = buildings_res.count if buildings_res.count is not None else 0
        
        return {"total": total_slots, "used": used, "free": max(0, total_slots - used)}
    except Exception as e:
        log_event(f"Error calculando slots por sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}


def get_planet_sectors_status(planet_id: int) -> List[Dict[str, Any]]:
    """Consulta el estado actual de los sectores de un planeta."""
    try:
        response = _get_db().table("sectors")\
            .select("id, type, slots, buildings_count, resource_type, is_known")\
            .eq("planet_id", planet_id)\
            .execute()
        return response.data if response.data else []
    except Exception:
        return []


def get_sector_details(sector_id: int) -> Optional[Dict[str, Any]]:
    """Retorna información detallada de un sector y sus edificios."""
    try:
        db = _get_db()
        response = db.table("sectors").select("*").eq("id", sector_id).single().execute()
        if not response.data: return None
        
        sector = response.data
        buildings_res = db.table("planet_buildings")\
            .select("building_type, building_tier")\
            .eq("sector_id", sector_id)\
            .execute()
        
        # Enriquecer nombres de edificios desde constantes
        names = []
        for b in (buildings_res.data or []):
            name = BUILDING_TYPES.get(b["building_type"], {}).get("name", "Estructura")
            names.append(f"{name} (T{b['building_tier']})")
        
        sector["buildings_list"] = names
        return sector
    except Exception:
        return None


def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool:
    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return False
        current_tier = asset.get('base_tier', 1)
        if current_tier >= 4: return False 
        
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
    tier: int = 1,
    sector_id: Optional[int] = None 
) -> Optional[Dict[str, Any]]:
    """Construye validando espacio en sectores y sincronizando el contador."""
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # 1. Selección de Sector
        target_sector = None
        if sector_id:
            sec_res = db.table("sectors").select("*").eq("id", sector_id).single().execute()
            target_sector = sec_res.data
        else:
            # Auto-asignación (Prioridad Urbano)
            sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
            sectors = sectors_res.data or []
            urban = [s for s in sectors if s["type"] == 'Urbano' and s["buildings_count"] < s["slots"]]
            others = [s for s in sectors if s["buildings_count"] < s["slots"]]
            target_sector = urban[0] if urban else (others[0] if others else None)

        if not target_sector or target_sector["buildings_count"] >= target_sector["slots"]:
            log_event("No hay espacio en sectores disponibles.", player_id, is_error=True)
            return None

        # 2. Insertar
        world = get_world_state()
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "sector_id": target_sector["id"],
            "is_active": True,
            "built_at_tick": world.get("current_tick", 1)
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response.data:
            # 3. Sincronización
            db.table("sectors").update({
                "buildings_count": target_sector["buildings_count"] + 1
            }).eq("id", target_sector["id"]).execute()
            
            log_event(f"Construido {definition['name']} en {target_sector['type']}", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    """Demuele y decrementa el contador del sector."""
    try:
        db = _get_db()
        b_res = db.table("planet_buildings").select("sector_id").eq("id", building_id).single().execute()
        if not b_res.data: return False
        
        sid = b_res.data.get("sector_id")
        db.table("planet_buildings").delete().eq("id", building_id).execute()
        
        if sid:
            s_res = db.table("sectors").select("buildings_count").eq("id", sid).single().execute()
            if s_res.data:
                db.table("sectors").update({"buildings_count": max(0, s_res.data["buildings_count"] - 1)}).eq("id", sid).execute()
        
        log_event(f"Edificio {building_id} demolido.", player_id)
        return True
    except Exception as e:
        log_event(f"Error demoliendo: {e}", player_id, is_error=True)
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
        log_event(f"Error obteniendo sitios: {e}", player_id, is_error=True)
        return []


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    """
    Actualiza la seguridad en lote.
    V4.4: Redirigido a la tabla 'planets'. Se espera que 'updates' sea (planet_id, security).
    """
    if not updates: return True
    try:
        db = _get_db()
        for planet_id, security in updates:
            # Nota: Originalmente el primer elemento era asset_id si venía de get_all_player_planets
            # Pero en la lógica V4.4 de economy_engine se pasa (planet['id'], security) donde planet['id'] es el PLANET ID
            db.table("planets").update({"security": security}).eq("id", planet_id).execute()
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

# --- V4.3: CONTROL DEL SISTEMA ESTELAR ---

def check_system_majority_control(system_id: int, faction_id: int) -> bool:
    """
    Verifica si una facción tiene 'Control de Sistema' según V4.3.
    Regla: Poseer > 50% de los planetas habitados/habitables del sistema.
    """
    try:
        db = _get_db()
        
        # 1. Contar total de planetas relevantes en el sistema
        all_planets_res = db.table("planets").select("id").eq("system_id", system_id).execute()
        all_planets = all_planets_res.data if all_planets_res.data else []
        total_planets = len(all_planets)
        
        if total_planets == 0:
            return False
            
        # 2. Contar planetas controlados por la facción (Jugador/Facción)
        # Verificamos planetas donde 'surface_owner_id' coincida con la facción (o player asociado)
        # Nota: Asumimos que faction_id es equivalente a player_id para propiedad directa
        # o que hay lógica de alianza. Para simplificar, usamos surface_owner_id.
        
        my_planets_res = db.table("planets").select("id")\
            .eq("system_id", system_id)\
            .eq("surface_owner_id", faction_id)\
            .execute()
            
        my_count = len(my_planets_res.data) if my_planets_res.data else 0
        
        # 3. Verificar mayoría simple (> 50%)
        has_majority = my_count > (total_planets / 2.0)
        
        return has_majority

    except Exception as e:
        print(f"Error checking system control: {e}")
        return False

# --- V4.4: SEGURIDAD GALÁCTICA ---

def update_planet_security_value(planet_id: int, value: float) -> bool:
    """Actualiza la seguridad física del planeta en la tabla mundial."""
    try:
        _get_db().table("planets").update({"security": value}).eq("id", planet_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando seguridad del planeta {planet_id}: {e}", is_error=True)
        return False

def update_planet_security_data(planet_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """
    Actualiza la seguridad y el desglose detallado (breakdown) en la tabla 'planets'.
    """
    try:
        _get_db().table("planets").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", planet_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando seguridad detallada planeta {planet_id}: {e}", is_error=True)
        return False

def get_all_colonized_system_ids() -> List[int]:
    """Retorna una lista única de IDs de sistemas que tienen al menos un planeta colonizado."""
    try:
        # Buscamos planetas que tengan surface_owner_id definido
        response = _get_db().table("planets")\
            .select("system_id")\
            .not_.is_("surface_owner_id", "null")\
            .execute()
            
        if not response.data:
            return []
            
        # Extraemos IDs únicos
        system_ids = list(set([p["system_id"] for p in response.data if p.get("system_id")]))
        return system_ids
    except Exception as e:
        log_event(f"Error obteniendo sistemas colonizados: {e}", is_error=True)
        return []