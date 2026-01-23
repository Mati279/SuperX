# data/planet_repository.py (Completo)
"""
Repositorio de Planetas y Edificios.
Gestiona activos planetarios, edificios, recursos y mejoras de base.
Refactorizado para MMFR V2: Seguridad dinámica (0-100) y Mantenimiento.
Actualizado v4.3.0: Integración completa de Planetología Avanzada (Sectores).
Actualizado v4.4.0: Persistencia de Seguridad Galáctica.
Corrección v4.4.1: Consultas seguras (maybe_single) para assets opcionales.
Actualizado v4.7.0: Estandarización de Capitales (Población Inicial).
Actualizado v4.8.1: Eliminación definitiva de 'security_breakdown' para sincronización con DB.
Refactorizado v5.3: Limpieza de redundancia 'slots' en Planeta.
Corrección v5.4: Protecciones robustas contra respuestas 'NoneType' de Supabase.
Corrección v5.5: Persistencia de 'poblacion' en tabla global 'planets'.
Corrección v5.6: Join con tabla 'planets' para obtener seguridad real.
Refactor v5.7: Estandarización de nomenclatura 'population' (Fix poblacion).
Refactor v5.8: Limpieza integral de consultas y campos expandidos.
Corrección v5.9: Fix columna 'sector_type' en tabla sectors.
Refactor v6.0: Eliminación de columna redundante 'buildings_count' en sectors (Cálculo dinámico).
Corrección v6.1: Fix crítico de tipos en seguridad (soporte Dict/Float) y persistencia de breakdown.
"""

from typing import Dict, List, Any, Optional, Tuple
import random 
from .database import get_supabase
from .log_repository import log_event
from .world_repository import get_world_state
from core.world_constants import BUILDING_TYPES, BASE_TIER_COSTS, ECONOMY_RATES
from core.rules import calculate_planet_security


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- CONSULTA DE PLANETAS (TABLA MUNDIAL) ---

def get_planet_by_id(planet_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene información de un planeta de la tabla mundial 'planets'.
    Actualizado V5.8: Recuperación explícita de population y breakdown.
    """
    try:
        response = _get_db().table("planets")\
            .select("id, name, system_id, biome, mass_class, orbital_ring, is_habitable, surface_owner_id, orbital_owner_id, is_disputed, security, population, security_breakdown, base_defense")\
            .eq("id", planet_id)\
            .single()\
            .execute()
        return response.data if response and response.data else None
    except Exception:
        return None


# --- GESTIÓN DE ACTIVOS PLANETARIOS ---

def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    try:
        response = _get_db().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .maybe_single()\
            .execute()
        return response.data if response and response.data else None
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
        return response.data if response and response.data else None
    except Exception:
        return None


def get_all_player_planets(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene todos los activos planetarios del jugador.
    Fix V5.6: JOIN con 'planets' para obtener 'security' (Source of Truth).
    Refactor V5.7: Actualizado a 'population'.
    """
    try:
        response = _get_db().table("planet_assets")\
            .select("*, planets(security, population, system_id, name)")\
            .eq("player_id", player_id)\
            .execute()
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo planetas del jugador: {e}", player_id, is_error=True)
        return []


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados.
    Refactor V5.7: Actualizado a 'population'.
    Fix V5.9: Corrección de nombre de columna 'sector_type'.
    Refactor V6.0: Cálculo dinámico de 'buildings_count'.
    """
    try:
        db = _get_db()
        planets_response = db.table("planet_assets")\
            .select("*, planets(orbital_owner_id, surface_owner_id, is_disputed, biome, security, population)")\
            .eq("player_id", player_id)\
            .execute()

        if not planets_response or not planets_response.data:
            return []
            
        assets = planets_response.data
        planet_ids = [a["planet_id"] for a in assets]
        asset_ids = [a["id"] for a in assets]

        # Obtener Edificios
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response and buildings_response.data else []

        # Obtener Sectores (Sin buildings_count)
        sectors_response = db.table("sectors")\
            .select("id, sector_type, planet_id, max_slots, resource_category, is_known")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response and sectors_response.data else []
        
        # Corrección de campo legacy 'slots' -> 'max_slots' e inicializar count
        sector_map = {}
        for s in sectors_data:
            if 'slots' not in s and 'max_slots' in s:
                s['slots'] = s['max_slots']
            s['buildings_count'] = 0 # Inicializar contador dinámico
            sector_map[s["id"]] = s
        
        buildings_by_asset: Dict[int, List[Dict]] = {}
        for building in buildings:
            aid = building["planet_asset_id"]
            if aid not in buildings_by_asset: buildings_by_asset[aid] = []
            
            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id)
            
            # Asignar info del sector y actualizar contador
            building["sector_type"] = sector.get("sector_type") if sector else "Desconocido"
            building["sector_info"] = sector
            
            if sector:
                sector['buildings_count'] += 1
            
            buildings_by_asset[aid].append(building)

        for asset in assets:
            planet_data = asset.get("planets", {})
            asset["orbital_owner_id"] = planet_data.get("orbital_owner_id")
            asset["surface_owner_id"] = planet_data.get("surface_owner_id")
            asset["is_disputed"] = planet_data.get("is_disputed", False)
            asset["biome"] = planet_data.get("biome", "Desconocido")
            # Ensure planet data is accessible
            if "security" in planet_data: asset["security_from_planet"] = planet_data["security"]

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
        db = _get_db()
        existing_assets = get_all_player_planets(player_id)
        if not existing_assets:
            # Boost para la primera colonia
            initial_population = random.uniform(1.5, 1.7)

        # --- FIX SEGURIDAD (V5.9) ---
        # Obtener datos reales del planeta para calcular seguridad correcta
        planet_data = get_planet_by_id(planet_id)
        
        initial_security = 20.0 # Fallback seguro
        if planet_data:
            base_def = planet_data.get("base_defense", 10) or 10
            ring = planet_data.get("orbital_ring", 3) or 3
            
            # Usamos la regla centralizada con flag de propiedad
            initial_security = calculate_planet_security(
                base_stat=base_def,
                pop_count=initial_population,
                infrastructure_defense=0,
                orbital_ring=ring,
                is_player_owned=True 
            )

        asset_data = {
            "planet_id": planet_id,
            "system_id": system_id,
            "player_id": player_id,
            "nombre_asentamiento": settlement_name,
            # Refactor V5.7: population en lugar de poblacion
            "population": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0,
            "infraestructura_defensiva": 0,
            "base_tier": 1
        }
        
        response = db.table("planet_assets").insert(asset_data).execute()
        
        if response and response.data:
            # --- FIX CRÍTICO V6.1: Soporte dual para Float/Dict en Security ---
            sec_value = initial_security
            sec_breakdown = {}
            
            if isinstance(initial_security, dict):
                sec_value = initial_security.get("total", 20.0)
                sec_breakdown = initial_security
            
            # Sincronizar tabla PLANETS con desglose explícito
            db.table("planets").update({
                "surface_owner_id": player_id,
                "security": sec_value,
                "security_breakdown": sec_breakdown,
                "population": initial_population
            }).eq("id", planet_id).execute()
            
            # --- FAIL-SAFE DE SECTORES (V5.9) ---
            # Verificar si existen sectores. Si no, crear uno de emergencia.
            sectors_check = db.table("sectors").select("id").eq("planet_id", planet_id).execute()
            if not sectors_check.data:
                # Crear sector de emergencia
                emergency_sector = {
                    "id": (planet_id * 1000) + 1,
                    "planet_id": planet_id,
                    "name": "Sector Urbano (Emergencia)",
                    "sector_type": "Urbano", 
                    "max_slots": 5,
                    "is_known": True
                    # V6.0: Eliminado 'buildings_count'
                }
                db.table("sectors").insert(emergency_sector).execute()
                log_event(f"Sector de emergencia creado para {planet_id}", player_id, is_error=True)

            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {sec_value:.1f})", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


# --- GESTIÓN DE BASE Y SECTORES ---

def get_base_slots_info(planet_asset_id: int) -> Dict[str, int]:
    """Calcula slots totales sumando los de todos los sectores del planeta."""
    try:
        db = _get_db()
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return {"total": 0, "used": 0, "free": 0}
        
        planet_id = asset.get("planet_id")
        total_slots = 0
        try:
            sectors_res = db.table("sectors").select("max_slots").eq("planet_id", planet_id).execute()
            if sectors_res and sectors_res.data:
                total_slots = sum(s["max_slots"] for s in sectors_res.data)
        except:
            sectors_res = db.table("sectors").select("slots").eq("planet_id", planet_id).execute()
            if sectors_res and sectors_res.data:
                total_slots = sum(s["slots"] for s in sectors_res.data)
        
        buildings_res = db.table("planet_buildings").select("id", count="exact").eq("planet_asset_id", planet_asset_id).execute()
        used = buildings_res.count if buildings_res and buildings_res.count is not None else 0
        
        return {"total": total_slots, "used": used, "free": max(0, total_slots - used)}
    except Exception as e:
        log_event(f"Error calculando slots por sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}


def get_planet_sectors_status(planet_id: int) -> List[Dict[str, Any]]:
    """Consulta el estado actual de los sectores de un planeta, calculando ocupación dinámica."""
    try:
        db = _get_db()
        # 1. Obtener Sectores
        response = db.table("sectors")\
            .select("id, sector_type, max_slots, resource_category, is_known")\
            .eq("planet_id", planet_id)\
            .execute()
        
        sectors = response.data if response and response.data else []
        if not sectors: return []
        
        sector_ids = [s["id"] for s in sectors]

        # 2. Contar edificios dinámicamente
        b_response = db.table("planet_buildings")\
            .select("sector_id")\
            .in_("sector_id", sector_ids)\
            .execute()
        
        buildings = b_response.data if b_response and b_response.data else []
        counts = {}
        for b in buildings:
            sid = b.get("sector_id")
            if sid: counts[sid] = counts.get(sid, 0) + 1

        # 3. Mapear resultados
        for s in sectors:
            s['slots'] = s.get('max_slots', 2)
            s['buildings_count'] = counts.get(s["id"], 0)
            
        return sectors
    except Exception:
        return []


def get_sector_details(sector_id: int) -> Optional[Dict[str, Any]]:
    """Retorna información detallada de un sector y sus edificios."""
    try:
        db = _get_db()
        response = db.table("sectors").select("*").eq("id", sector_id).single().execute()
        if not response or not response.data: return None
        
        sector = response.data
        if 'max_slots' in sector:
            sector['slots'] = sector['max_slots']

        buildings_res = db.table("planet_buildings")\
            .select("building_type, building_tier")\
            .eq("sector_id", sector_id)\
            .execute()
        
        names = []
        if buildings_res and buildings_res.data:
            for b in buildings_res.data:
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
        
        response = _get_db().table("planet_assets").update({
            "base_tier": current_tier + 1
        }).eq("id", planet_asset_id).execute()
        
        if response:
            log_event(f"Base Principal mejorada a Tier {current_tier + 1}", player_id)
            return True
        return False
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
            
        response = _get_db().table("planet_assets").update({
            f"module_{module_key}": current_level + 1
        }).eq("id", planet_asset_id).execute()
        
        if response:
            log_event(f"Módulo {module_key} mejorado a nivel {current_level + 1}", player_id)
            return "OK"
        return "Error en la base de datos"
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
        return response.data if response and response.data else []
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
    """Construye validando espacio en sectores de manera dinámica."""
    if building_type not in BUILDING_TYPES: return None
    definition = BUILDING_TYPES[building_type]
    db = _get_db()

    try:
        asset = get_planet_asset_by_id(planet_asset_id)
        if not asset: return None
        planet_id = asset["planet_id"]

        # 1. Recuperar Sectores y Edificios para calcular espacio
        sectors_res = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        sectors = sectors_res.data if sectors_res and sectors_res.data else []
        if not sectors:
            log_event("No hay sectores en el planeta.", player_id, is_error=True)
            return None

        # Contar edificios existentes
        buildings_res = db.table("planet_buildings").select("sector_id").eq("planet_asset_id", planet_asset_id).execute()
        existing_buildings = buildings_res.data if buildings_res and buildings_res.data else []
        
        sector_counts = {}
        for b in existing_buildings:
            sid = b.get("sector_id")
            if sid: sector_counts[sid] = sector_counts.get(sid, 0) + 1

        # Preparar sectores con contadores
        for s in sectors:
            if 'max_slots' in s: s['slots'] = s['max_slots']
            s['buildings_count'] = sector_counts.get(s["id"], 0) # Count dinámico

        # 2. Selección de Sector Objetivo
        target_sector = None
        if sector_id:
            # Buscar en la lista ya traída para tener el count actualizado
            matches = [s for s in sectors if s["id"] == sector_id]
            if matches: target_sector = matches[0]
        else:
            urban = [s for s in sectors if s.get("sector_type") == 'Urbano' and s["buildings_count"] < s["slots"]]
            others = [s for s in sectors if s["buildings_count"] < s["slots"]]
            target_sector = urban[0] if urban else (others[0] if others else None)

        if not target_sector or target_sector["buildings_count"] >= target_sector["slots"]:
            log_event("No hay espacio en sectores disponibles.", player_id, is_error=True)
            return None

        # 3. Insertar Edificio
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
        if response and response.data:
            # V6.0: Eliminada actualización redundante a tabla 'sectors' (buildings_count)
            log_event(f"Construido {definition['name']} en {target_sector.get('sector_type', 'Sector')}", player_id)
            return response.data[0]
        return None
    except Exception as e:
        log_event(f"Error construyendo edificio: {e}", player_id, is_error=True)
        return None


def demolish_building(building_id: int, player_id: int) -> bool:
    """Demuele y decrementa el contador del sector (Implícito)."""
    try:
        db = _get_db()
        # Verificar propiedad
        b_res = db.table("planet_buildings").select("id").eq("id", building_id).single().execute()
        if not b_res or not b_res.data: return False
        
        # Eliminar
        db.table("planet_buildings").delete().eq("id", building_id).execute()
        
        # V6.0: Eliminada actualización redundante a tabla 'sectors'
        
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
        return response.data if response and response.data else []
    except Exception as e:
        log_event(f"Error obteniendo sitios: {e}", player_id, is_error=True)
        return []


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    """Actualiza la seguridad en lote en la tabla 'planets'."""
    if not updates: return True
    try:
        db = _get_db()
        for planet_id, security in updates:
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
            res = db.table("planet_buildings").update({"is_active": is_active}).eq("id", building_id).execute()
            if res: success += 1
            else: failed += 1
        except Exception: failed += 1
    return (success, failed)


def update_planet_asset(planet_asset_id: int, updates: Dict[str, Any]) -> bool:
    try:
        response = _get_db().table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando activo {planet_asset_id}: {e}", is_error=True)
        return False

# --- V4.3: CONTROL DEL SISTEMA ESTELAR ---

def check_system_majority_control(system_id: int, faction_id: int) -> bool:
    """Verifica si una facción tiene 'Control de Sistema'."""
    try:
        db = _get_db()
        
        all_planets_res = db.table("planets").select("id").eq("system_id", system_id).execute()
        all_planets = all_planets_res.data if all_planets_res and all_planets_res.data else []
        total_planets = len(all_planets)
        
        if total_planets == 0:
            return False
            
        my_planets_res = db.table("planets").select("id")\
            .eq("system_id", system_id)\
            .eq("surface_owner_id", faction_id)\
            .execute()
            
        my_count = len(my_planets_res.data) if my_planets_res and my_planets_res.data else 0
        has_majority = my_count > (total_planets / 2.0)
        
        return has_majority

    except Exception as e:
        print(f"Error checking system control: {e}")
        return False

# --- V4.4: SEGURIDAD GALÁCTICA ---

def update_planet_security_value(planet_id: int, value: float) -> bool:
    """Actualiza la seguridad física del planeta en la tabla mundial."""
    try:
        response = _get_db().table("planets").update({"security": value}).eq("id", planet_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad del planeta {planet_id}: {e}", is_error=True)
        return False

def update_planet_security_data(planet_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """Actualiza la seguridad en la tabla 'planets'."""
    try:
        # V6.1: Persistencia explícita de breakdown
        response = _get_db().table("planets").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", planet_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad planeta {planet_id}: {e}", is_error=True)
        return False

def get_all_colonized_system_ids() -> List[int]:
    try:
        response = _get_db().table("planets")\
            .select("system_id")\
            .not_.is_("surface_owner_id", "null")\
            .execute()
            
        if not response or not response.data:
            return []
            
        system_ids = list(set([p["system_id"] for p in response.data if p.get("system_id")]))
        return system_ids
    except Exception as e:
        log_event(f"Error obteniendo sistemas colonizados: {e}", is_error=True)
        return []