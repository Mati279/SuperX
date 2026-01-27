# data/planets/genesis.py
"""
Protocolo Génesis - Funciones de Inicialización de Planetas y Sectores.
Actualizado v7.3: Inicialización garantizada de Sectores Urbanos para Protocolo Génesis.
Actualizado v7.4: Nueva función add_initial_building() para edificio inicial en Génesis.
Actualizado v7.5.0: Implementación de Sector Orbital y Lógica de Soberanía Espacial.
Actualizado v7.6.0: Fix Crítico de IDs y Transformación de Sectores.
Actualizado v7.6.1: Fix Crítico SQL en initialize_planet_sectors (sync planet_id).
Refactor v11.0: INTEGRACIÓN DE SISTEMA DE BASES MILITARES (Tabla 'bases').
Actualizado v11.2: Fix niveles iniciales (1) en initialize_player_base.
"""

from typing import Dict, List, Any
import random

from ..log_repository import log_event
from ..world_repository import get_world_state
from core.world_constants import (
    BUILDING_TYPES,
    PLANET_MASS_CLASSES,
    SECTOR_SLOTS_CONFIG,
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_PLAIN,
    SECTOR_TYPE_MOUNTAIN,
    SECTOR_TYPE_ORBITAL,
)

from .core import _get_db
from .assets import get_planet_asset_by_id
from .sovereignty import update_planet_sovereignty


def initialize_planet_sectors(planet_id: int, biome: str, mass_class: str = 'Estándar') -> List[Dict[str, Any]]:
    """
    Garantiza que un planeta tenga sectores inicializados, INCLUYENDO LA ÓRBITA.
    Corrige IDs faltantes y transforma sectores existentes si es necesario.
    """
    try:
        db = _get_db()
        # 1. Verificar existencia
        check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
        existing_sectors = check.data if check and check.data else []

        sectors_to_create = []
        sectors_updated = False

        # A. Verificar Urbano
        urban_sector = next((s for s in existing_sectors if s.get("sector_type") == SECTOR_TYPE_URBAN), None)

        if not urban_sector:
            # CASO 1: Transformación
            if existing_sectors:
                candidate = next((s for s in existing_sectors if s.get("sector_type") != SECTOR_TYPE_ORBITAL), None)

                if candidate:
                    u_slots = SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 3)
                    try:
                        res = db.table("sectors").update({
                            "sector_type": SECTOR_TYPE_URBAN,
                            "name": "Distrito Central",
                            "max_slots": u_slots,
                        }).eq("id", candidate["id"]).execute()

                        if res and res.data:
                            candidate["sector_type"] = SECTOR_TYPE_URBAN
                            candidate["name"] = "Distrito Central"
                            candidate["max_slots"] = u_slots
                            sectors_updated = True
                    except Exception as e:
                        print(f"Error transformando sector {candidate['id']}: {e}")

            # CASO 2: Inicialización desde cero
            else:
                urban_id = (planet_id * 1000) + 1
                sectors_to_create.append({
                    "id": urban_id,
                    "planet_id": planet_id,
                    "name": "Distrito Central",
                    "sector_type": SECTOR_TYPE_URBAN,
                    "max_slots": SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_URBAN, 3),
                    "is_known": False,
                    "resource_category": "influencia"
                })

        # B. Verificar Orbital
        orbital_sector = next((s for s in existing_sectors if s.get("sector_type") == SECTOR_TYPE_ORBITAL), None)
        orbital_pending = next((s for s in sectors_to_create if s.get("sector_type") == SECTOR_TYPE_ORBITAL), None)

        if not orbital_sector and not orbital_pending:
            orbital_id = (planet_id * 1000) + 99
            sectors_to_create.append({
                "id": orbital_id,
                "planet_id": planet_id,
                "name": "Órbita Geoestacionaria",
                "sector_type": SECTOR_TYPE_ORBITAL,
                "max_slots": SECTOR_SLOTS_CONFIG.get(SECTOR_TYPE_ORBITAL, 1),
                "is_known": True,
                "resource_category": None
            })

        # C. Rellenar resto de sectores
        if not existing_sectors and sectors_to_create:
            target_count = PLANET_MASS_CLASSES.get(mass_class, 4)
            valid_types = [SECTOR_TYPE_PLAIN, SECTOR_TYPE_MOUNTAIN]

            for i in range(2, target_count + 1):
                new_id = (planet_id * 1000) + i
                sType = random.choice(valid_types)
                sectors_to_create.append({
                    "id": new_id,
                    "planet_id": planet_id,
                    "name": f"Sector {i} ({sType})",
                    "sector_type": sType,
                    "max_slots": SECTOR_SLOTS_CONFIG.get(sType, 3),
                    "is_known": False,
                    "resource_category": "materiales"
                })

        if sectors_to_create:
            res = db.table("sectors").insert(sectors_to_create).execute()
            if res and res.data:
                existing_sectors.extend(res.data)
                sectors_updated = True

        if sectors_updated:
            final_check = db.table("sectors").select("*").eq("planet_id", planet_id).execute()
            return final_check.data if final_check and final_check.data else []

        return existing_sectors

    except Exception as e:
        log_event(f"Error critical initializing sectors for planet {planet_id}: {e}", is_error=True)
        try:
            return _get_db().table("sectors").select("*").eq("planet_id", planet_id).execute().data or []
        except:
            return []


def claim_genesis_sector(sector_id: int, player_id: int) -> bool:
    """Marca un sector como conocido para el aterrizaje inicial (Génesis)."""
    try:
        _get_db().table("sectors").update({
            "is_known": True
        }).eq("id", sector_id).execute()
        return True
    except Exception as e:
        log_event(f"Error claiming genesis sector {sector_id}: {e}", player_id, is_error=True)
        return False


def add_initial_building(
    player_id: int,
    planet_asset_id: int,
    sector_id: int,
    building_type: str = 'hq'
) -> bool:
    """Legacy: Mantenido para compatibilidad."""
    try:
        db = _get_db()
        building_def = BUILDING_TYPES.get(building_type)
        if not building_def: return False
        world = get_world_state()
        current_tick = world.get("current_tick", 1) if world else 1

        building_data = {
            "planet_asset_id": planet_asset_id,
            "player_id": player_id,
            "building_type": building_type,
            "building_tier": 1,
            "sector_id": sector_id,
            "is_active": True,
            "pops_required": building_def.get("pops_required", 0),
            "energy_consumption": building_def.get("maintenance", {}).get("celulas_energia", 0),
            "built_at_tick": current_tick
        }

        response = db.table("planet_buildings").insert(building_data).execute()
        if response and response.data:
            asset = get_planet_asset_by_id(planet_asset_id)
            if asset:
                update_planet_sovereignty(asset["planet_id"])
            return True
        return False
    except Exception as e:
        log_event(f"Error crítico en add_initial_building: {e}", player_id, is_error=True)
        return False


def initialize_player_base(player_id: int, planet_id: int, sector_id: int) -> bool:
    """
    Crea la Base Militar inicial (HQ) en la tabla 'bases'.
    Utilizado por Protocolo Génesis para despliegue gratuito.
    Actualizado V11.2: Inicialización de módulos a Nivel 1.
    """
    try:
        db = _get_db()
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        base_data = {
            "player_id": player_id,
            "planet_id": planet_id,
            "sector_id": sector_id,
            "tier": 1,
            "created_at_tick": current_tick,
            # FIX V11.2: Inicializar módulos en Nivel 1
            "module_sensor_planetary": 1,
            "module_sensor_orbital": 1,
            "module_defense_ground": 1,
            "module_bunker": 1
        }

        response = db.table("bases").insert(base_data).execute()

        if response and response.data:
            log_event(f"Base Militar establecida en sector {sector_id}", player_id)
            # Recalcular soberanía inmediatamente (La base otorga control)
            update_planet_sovereignty(planet_id)
            return True

        log_event(f"Fallo al crear Base Militar en sector {sector_id}", player_id, is_error=True)
        return False

    except Exception as e:
        log_event(f"Error crítico en initialize_player_base: {e}", player_id, is_error=True)
        return False
