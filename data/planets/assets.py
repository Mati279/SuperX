# data/planets/assets.py (Completo)
"""
Gestión de Activos Planetarios (planet_assets).
Incluye colonización, población y consultas de activos del jugador.
Actualizado v7.7.1: Restauración de updates secuenciales en create_planet_asset.
Actualizado v7.7.2: Fix PGRST204 delegando 'base_tier' al default de la DB.
Actualizado v24.0: Inclusión de datos de lujo en consulta de sectores para UI.
"""

from typing import Dict, List, Any, Optional
import random
import traceback

from ..database import get_supabase
from ..log_repository import log_event
from core.world_constants import (
    BUILDING_TYPES,
    SECTOR_TYPE_URBAN,
)
from core.rules import calculate_planet_security

from .core import _get_db, get_planet_by_id


def get_planet_asset(planet_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene el activo planetario de un jugador en un planeta específico."""
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
    """Obtiene un activo planetario por su ID."""
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


def get_player_base_coordinates(player_id: int) -> Dict[str, Any]:
    """
    Obtiene las coordenadas (System, Planet, Sector) de la base principal del jugador.
    Prioriza el Sector Urbano del primer planeta colonizado.
    Helper para la refactorización de ubicación (V10).
    """
    coords = {
        "system_id": None,
        "planet_id": None,
        "sector_id": None,
        "nombre_asentamiento": None
    }

    try:
        db = _get_db()
        # 1. Obtener activos del jugador (Asumimos el primero como base principal)
        assets = get_all_player_planets(player_id)
        if not assets:
            return coords

        base_asset = assets[0]
        planet_id = base_asset.get("planet_id")

        # Extraer datos del activo y del planeta (JOIN)
        coords["planet_id"] = planet_id
        coords["nombre_asentamiento"] = base_asset.get("nombre_asentamiento", "Base Principal")

        # Datos del sistema (desde el join con planets o directo)
        planet_data = base_asset.get("planets", {})
        coords["system_id"] = planet_data.get("system_id") or base_asset.get("system_id")

        # 2. Buscar Sector Urbano para spawn preciso
        if planet_id:
            sector_res = db.table("sectors")\
                .select("id")\
                .eq("planet_id", planet_id)\
                .eq("sector_type", SECTOR_TYPE_URBAN)\
                .maybe_single()\
                .execute()

            if sector_res and sector_res.data:
                coords["sector_id"] = sector_res.data.get("id")
            else:
                # Fallback: Cualquier sector del planeta
                fallback = db.table("sectors").select("id").eq("planet_id", planet_id).limit(1).execute()
                if fallback and fallback.data:
                    coords["sector_id"] = fallback.data[0].get("id")

        return coords

    except Exception as e:
        log_event(f"Error obteniendo coordenadas base: {e}", player_id, is_error=True)
        return coords


def get_all_player_planets_with_buildings(player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene planetas del jugador con edificios y datos de sectores precargados.
    Refactor V5.7: Actualizado a 'population'.
    Fix V5.9: Corrección de nombre de columna 'sector_type'.
    Refactor V6.0: Cálculo dinámico de 'buildings_count'.
    Actualizado V11.2: Fusión de 'planet_buildings' y 'bases' para la UI.
    Actualizado V24.0: Inclusión de luxury_resource/category para proyección económica.
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

        # 1. Obtener Edificios Estándar
        buildings_response = db.table("planet_buildings")\
            .select("*")\
            .in_("planet_asset_id", asset_ids)\
            .execute()
        buildings = buildings_response.data if buildings_response and buildings_response.data else []

        # 2. Obtener Bases Militares (Tabla 'bases')
        bases_response = db.table("bases")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()
        bases = bases_response.data if bases_response and bases_response.data else []

        # 3. Obtener Sectores
        # Fix V24.0: Incluir luxury_resource y luxury_category para proyecciones de UI
        sectors_response = db.table("sectors")\
            .select("id, sector_type, planet_id, max_slots, resource_category, is_known, luxury_resource, luxury_category")\
            .in_("planet_id", planet_ids)\
            .execute()
        sectors_data = sectors_response.data if sectors_response and sectors_response.data else []

        # Mapa de sectores para acceso rápido
        sector_map = {}
        for s in sectors_data:
            if 'slots' not in s and 'max_slots' in s:
                s['slots'] = s['max_slots']
            s['buildings_count'] = 0  # Inicializar contador dinámico
            sector_map[s["id"]] = s

        buildings_by_asset: Dict[int, List[Dict]] = {}

        # A. Procesar Edificios Estándar
        for building in buildings:
            aid = building["planet_asset_id"]
            if aid not in buildings_by_asset: buildings_by_asset[aid] = []

            sec_id = building.get("sector_id")
            sector = sector_map.get(sec_id)

            # Asignar info del sector y actualizar contador
            building["sector_type"] = sector.get("sector_type") if sector else "Desconocido"
            building["sector_info"] = sector

            # Consumo Dinámico de Slots
            b_type = building.get("building_type")
            consumes_slots = BUILDING_TYPES.get(b_type, {}).get("consumes_slots", True)

            if sector and consumes_slots:
                sector['buildings_count'] += 1

            buildings_by_asset[aid].append(building)

        # B. Procesar Bases Militares (Inyección Virtual)
        # Necesitamos mapear planet_id -> asset_id
        asset_map_by_planet = {a["planet_id"]: a["id"] for a in assets}

        for base in bases:
            p_id = base.get("planet_id")
            target_asset_id = asset_map_by_planet.get(p_id)

            if target_asset_id:
                if target_asset_id not in buildings_by_asset: buildings_by_asset[target_asset_id] = []

                # Crear el objeto edificio virtual para la UI
                virtual_base = {
                    "id": base["id"],  # ID de la tabla bases (único)
                    "building_type": "military_base",  # Tipo especial para UI
                    "building_tier": base.get("tier", 1),
                    "sector_id": base["sector_id"],
                    "planet_asset_id": target_asset_id,
                    "is_active": True,
                    "built_at_tick": base.get("created_at_tick", 0),
                    "is_virtual": True  # Flag opcional para depuración
                }

                sec_id = base.get("sector_id")
                sector = sector_map.get(sec_id)
                virtual_base["sector_type"] = sector.get("sector_type") if sector else "Urbano"
                virtual_base["sector_info"] = sector

                # La base SIEMPRE consume slot
                if sector:
                    sector['buildings_count'] += 1

                buildings_by_asset[target_asset_id].append(virtual_base)

        for asset in assets:
            planet_data = asset.get("planets", {})
            asset["orbital_owner_id"] = planet_data.get("orbital_owner_id")
            asset["surface_owner_id"] = planet_data.get("surface_owner_id")
            asset["is_disputed"] = planet_data.get("is_disputed", False)
            asset["biome"] = planet_data.get("biome", "Desconocido")

            # FIX V6.2: Mapeo explícito de population para el motor económico
            asset["population"] = planet_data.get("population", 0.0)

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
    # Importación local para evitar dependencia circular
    from .sovereignty import recalculate_system_security

    try:
        db = _get_db()
        existing_assets = get_all_player_planets(player_id)
        if not existing_assets:
            if initial_population == 1.0:
                initial_population = random.uniform(1.5, 1.7)

        # --- FIX SEGURIDAD (V5.9) ---
        planet_data = get_planet_by_id(planet_id)

        initial_security = 20.0
        if planet_data:
            base_def = planet_data.get("base_defense", 10) or 10
            ring = planet_data.get("orbital_ring", 3) or 3

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
            "population": initial_population,
            "pops_activos": initial_population,
            "pops_desempleados": 0.0,
            "infraestructura_defensiva": 0
        }

        response = db.table("planet_assets").insert(asset_data).execute()

        if response and response.data:
            # --- FIX CRÍTICO V6.1: Soporte dual para Float/Dict en Security ---
            sec_value = initial_security
            sec_breakdown = {}

            if isinstance(initial_security, dict):
                sec_value = initial_security.get("total", 20.0)
                sec_breakdown = initial_security

            # Paso 1: Asignar Dueños y Población
            db.table("planets").update({
                "surface_owner_id": player_id,
                "orbital_owner_id": player_id,
                "population": initial_population
            }).eq("id", planet_id).execute()

            # Paso 2: Asignar Seguridad Calculada
            db.table("planets").update({
                "security": sec_value,
                "security_breakdown": sec_breakdown
            }).eq("id", planet_id).execute()

            # --- FAIL-SAFE DE SECTORES (V5.9) ---
            sectors_check = db.table("sectors").select("id").eq("planet_id", planet_id).execute()
            if not sectors_check.data:
                from core.world_constants import SECTOR_TYPE_URBAN
                emergency_sector = {
                    "id": (planet_id * 1000) + 1,
                    "planet_id": planet_id,
                    "name": "Sector Urbano (Emergencia)",
                    "sector_type": SECTOR_TYPE_URBAN,
                    "max_slots": 5,
                    "is_known": True
                }
                db.table("sectors").insert(emergency_sector).execute()
                log_event(f"Sector de emergencia creado para {planet_id}", player_id, is_error=True)

            log_event(f"Planeta colonizado: {settlement_name} (Seguridad inicial: {sec_value:.1f})", player_id)

            recalculate_system_security(system_id)

            return response.data[0]
        return None
    except Exception as e:
        print("\n CRITICAL ERROR IN CREATE_PLANET_ASSET:")
        traceback.print_exc()
        log_event(f"Error creando activo planetario: {e}", player_id, is_error=True)
        return None


def update_planet_asset(planet_asset_id: int, updates: Dict[str, Any]) -> bool:
    """Actualiza campos de un activo planetario."""
    try:
        response = _get_db().table("planet_assets").update(updates).eq("id", planet_asset_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando activo {planet_asset_id}: {e}", is_error=True)
        return False


def upgrade_base_tier(planet_asset_id: int, player_id: int) -> bool:
    """Mejora el tier de la base principal."""
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
    """Mejora un módulo de infraestructura."""
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


def rename_settlement(planet_asset_id: int, player_id: int, new_name: str) -> bool:
    """Permite al jugador renombrar su colonia/asentamiento."""
    if not new_name or len(new_name) < 3:
        return False

    try:
        response = _get_db().table("planet_assets").update({
            "nombre_asentamiento": new_name
        }).eq("id", planet_asset_id).eq("player_id", player_id).execute()

        if response and response.data:
            log_event(f"Asentamiento renombrado a '{new_name}'", player_id)
            return True
        return False
    except Exception as e:
        log_event(f"Error renombrando asentamiento: {e}", player_id, is_error=True)
        return False


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

        # 1. Contar edificios estándar
        buildings_res = db.table("planet_buildings")\
            .select("id, building_type")\
            .eq("planet_asset_id", planet_asset_id)\
            .execute()

        used = 0
        if buildings_res and buildings_res.data:
            for b in buildings_res.data:
                bt = b.get("building_type")
                if BUILDING_TYPES.get(bt, {}).get("consumes_slots", True):
                    used += 1

        # 2. Contar Bases Militares (Siempre usan slot)
        bases_res = db.table("bases").select("id").eq("planet_id", planet_id).execute()
        if bases_res and bases_res.data:
            used += len(bases_res.data)

        return {"total": total_slots, "used": used, "free": max(0, total_slots - used)}
    except Exception as e:
        log_event(f"Error calculando slots por sectores: {e}", is_error=True)
        return {"total": 0, "used": 0, "free": 0}