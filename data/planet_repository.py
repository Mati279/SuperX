# data/planet_repository.py
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
Refactorizado para MMFR V2: Seguridad dinámica (0-100) y Mantenimiento.
Actualizado v4.3.0: Integración completa de Planetología Avanzada (Sectores).
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
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados para el tick económico.
    Actualizado v4.3.0: Mapeo robusto de sectores y soporte para visualización de Planetología.
    """
    try:
        db = _get_db()
        # 1. Obtener Activos Planetarios + Datos de Control (Foreign Key a planets)
        planets_response = db.table("planet_assets")\
            .select("*, planets(orbital_owner_id, surface_owner_id, is_disputed)")\
            .eq("player_id", player_id)\
            .execute()

        planets = planets_response.data if planets_response.data else []
        if not planets: return []

        planet_ids = [p["planet_id"] for p in planets] 
        asset_ids = [p["id"] for p in planets]         

        # 2. Obtener Edificios
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response.data else []

        # 3. Obtener Sectores (para mapear localización de edificios)
        sectors_response = db.table("sectors")\
            .select("id, type, planet_id, slots, buildings_count")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response.data else []
        
        # Crear mapa de ID Sector -> Datos completos para enriquecimiento
        sector_map = {s["id"]: s for s in sectors_data}

        # 4. Organizar edificios por activo y enriquecer con sector
        buildings_by_asset: Dict[int, List[Dict]] = {}
        for building in buildings:
            pid = building["planet_asset_id"]
            if pid not in buildings_by_asset: buildings_by_asset[pid] = []
            
            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id) if sec_id else None
            
            building["sector_type"] = sector["type"] if sector else "Desconocido"
            building["sector_info"] = sector # Info extra para UI
            
            buildings_by_asset[pid].append(building)

        # 5. Ensamblar resultado final
        for planet in planets:
            planet_data = planet.get("planets", {})
            if planet_data:
                planet["orbital_owner_id"] = planet_data.get("orbital_owner_id")
                planet["surface_owner_id"] = planet_data.get("surface_owner_id")
                planet["is_disputed"] = planet_data.get("is_disputed", False)
            else:
                planet["orbital_owner_id"] = None
                planet["surface_owner_id"] = player_id
                planet["is_disputed"] = False

            planet["buildings"] = buildings_by_asset.get(planet["id"], [])
            # Incluir sectores filtrados para este planeta específico
            planet["sectors"] = [s for s in sectors_data if s["planet_id"] == planet["planet_id"]]

        return planets
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
    """Crea una colonia con seguridad inicial basada en población (MMFR V2)."""
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
            "seguridad": initial_security, 
            "infraestructura_defensiva": 0,
            "base_tier": 1
        }
        
        response = _get_db().table("planet_assets").insert(asset_data).execute()
        
        if response.data:
            _get_db().table("planets").update({"surface_owner_id": player_id}).eq("id", planet_id).execute()
            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {initial_security:.1f})", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y MÓDULOS (MÓDULO 20) ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    """
    Calcula slots totales y usados basados en la Planetología Avanzada (Sectores).
    Actualizado V4.3: Elimina dependencia de base_tier y suma slots de sectores.
    """
    try:
        db = _get_db()
        # 1. Obtener planet_id asociado al activo
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return {"total": 0, "used": 0, "free": 0}
        planet_id = asset.get("planet_id")
        
        # 2. Sumar capacidad total de todos los sectores del planeta
        sectors_res = db.table("sectors").select("slots").eq("planet_id", planet_id).execute()
        total_slots = sum(s["slots"] for s in sectors_res.data) if sectors_res.data else 0
        
        # 3. Contar edificios físicos en este activo planetario
        buildings_res = db.table("planet_buildings").select("id", count="exact").eq("planet_asset_id", planet_asset_id).execute()
        used = buildings_res.count if buildings_res.count is not None else 0
        
        return {
            "total": total_slots,
            "used": used,
            "free": max(0, total_slots - used)
        }
    except Exception as e:
        log_event(f"Error calculando slots de sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}


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
    """
    Construye una estructura validando slots de sectores y sincronizando el estado.
    V4.3.0: Soporta asignación manual o automática por tipo de sector (Prioridad Urbano).
    """
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        # 1. Obtener información del activo y planeta
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # 2. Selección y Validación de Sector
        target_sector = None
        if sector_id:
            # Validación manual de sector
            sec_res = db.table("sectors").select("*").eq("id", sector_id).single().execute()
            if not sec_res.data:
                log_event(f"Sector {sector_id} inexistente.", player_id, is_error=True)
                return None
            target_sector = sec_res.data
            if target_sector["buildings_count"] >= target_sector["slots"]:
                log_event(f"Sector {target_sector['type']} lleno.", player_id, is_error=True)
                return None
        else:
            # Auto-asignación: Buscar primer hueco disponible
            sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
            sectors = sectors_res.data if sectors_res.data else []
            
            # Prioridad: 1. Urbano con espacio, 2. Otros con espacio
            urban_sectors = [s for s in sectors if s["type"] == 'Urbano' and s["buildings_count"] < s["slots"]]
            other_sectors = [s for s in sectors if s["type"] != 'Urbano' and s["buildings_count"] < s["slots"]]
            
            if urban_sectors:
                target_sector = urban_sectors[0]
            elif other_sectors:
                target_sector = other_sectors[0]
            else:
                log_event("No hay espacio en ningún sector del planeta.", player_id, is_error=True)
                return None

        # 3. Validación de HQ único por activo
        if building_type == 'hq':
            existing = db.table("planet_buildings").select("id").eq("planet_asset_id", planet_asset_id).eq("building_type", "hq").execute()
            if existing.data: 
                log_event("La colonia ya posee un Cuartel General.", player_id, is_error=True)
                return None

        # 4. Obtener tick actual para registro temporal
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        # 5. Insertar edificio
        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": tier,
            "sector_id": target_sector["id"],
            "is_active": True,
            "pops_required": definition.get("pops_required", 0),
            "energy_consumption": 0, 
            "built_at_tick": current_tick 
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response.data:
            # 6. Sincronización: Incrementar contador en la tabla 'sectors'
            db.table("sectors").update({
                "buildings_count": target_sector["buildings_count"] + 1
            }).eq("id", target_sector["id"]).execute()
            
            log_event(f"Edificio '{definition['name']}' construido en Sector {target_sector['type']}.", player_id)
            return response.data[0]
            
        return None
    except Exception as e:
        log_event(f"Error en construcción por sectores: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    """Elimina un edificio y libera el slot en su sector correspondiente."""
    try:
        db = _get_db()
        # 1. Identificar sector antes de borrar
        b_res = db.table("planet_buildings").select("sector_id").eq("id", building_id).single().execute()
        if not b_res.data: 
            log_event(f"No se encontró el edificio {building_id} para demoler.", player_id, is_error=True)
            return False
        
        sector_id = b_res.data.get("sector_id")
        
        # 2. Borrar registro del edificio
        db.table("planet_buildings").delete().eq("id", building_id).execute()
        
        # 3. Decrementar contador en el sector
        if sector_id:
            sec_res = db.table("sectors").select("buildings_count").eq("id", sector_id).single().execute()
            if sec_res.data:
                new_count = max(0, sec_res.data["buildings_count"] - 1)
                db.table("sectors").update({"buildings_count": new_count}).eq("id", sector_id).execute()
        
        log_event(f"Edificio {building_id} demolido. Slot liberado en sector.", player_id)
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