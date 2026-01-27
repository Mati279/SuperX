# data/planets/sovereignty.py (Completo)
"""
Motores de Cálculo de Soberanía, Control de Sistemas y Seguridad Galáctica.
Actualizado v9.1.0: Implementación de Seguridad de Sistema (Recálculo automático en cascada).
Actualizado v9.2.0: Reglas de Soberanía Conflictiva y Excepción de Construcción Orbital.
Actualizado v10.4: Soberanía Diferida (Filtro por built_at_tick).
Refactor v11.0: INTEGRACIÓN DE SISTEMA DE BASES MILITARES (Tabla 'bases').
Corrección v6.1: Fix crítico de tipos en seguridad (soporte Dict/Float).
Refactor V19.0: Soberanía Estricta. Solo estructuras TERMINADAS (built_at_tick <= current) otorgan control.
"""

from typing import Dict, List, Any, Optional, Tuple

from ..log_repository import log_event
from ..world_repository import get_world_state, update_system_controller, update_system_security

from .core import _get_db


def update_planet_sovereignty(planet_id: int, enemy_fleet_owner_id: Optional[int] = None):
    """
    Recalcula y actualiza la soberanía de superficie y orbital.
    Refactor V19.0: Verifica tick de finalización de estructuras para otorgar control.
    """
    try:
        db = _get_db()
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        # 0. Obtener info del planeta
        planet_info_res = db.table("planets").select("system_id, population").eq("id", planet_id).single().execute()
        if not planet_info_res or not planet_info_res.data:
            return

        system_id = planet_info_res.data.get("system_id")
        population = planet_info_res.data.get("population", 0.0)

        # 1. Obtener Bases Militares (Nueva Lógica de Soberanía Civil/Militar)
        # V19.0: Filtrar bases que ya estén completadas (created_at_tick <= current_tick)
        bases_res = db.table("bases")\
            .select("player_id, sector_id, created_at_tick")\
            .eq("planet_id", planet_id)\
            .execute()

        raw_bases = bases_res.data if bases_res and bases_res.data else []
        # Filtro estricto de finalización
        bases = [b for b in raw_bases if b.get('created_at_tick', 999999) <= current_tick]

        base_owner_id = bases[0]["player_id"] if bases else None

        # 2. Obtener Edificios (Para Outposts y Estaciones Orbitales)
        assets_res = db.table("planet_assets").select("id, player_id").eq("planet_id", planet_id).execute()

        # Si no hay bases completadas ni assets, resetear soberanía
        if not bases and (not assets_res or not assets_res.data):
            db.table("planets").update({"surface_owner_id": None, "orbital_owner_id": enemy_fleet_owner_id}).eq("id", planet_id).execute()
            if system_id:
                recalculate_system_ownership(system_id)
            return

        assets = assets_res.data if assets_res and assets_res.data else []
        player_map = {a["id"]: a["player_id"] for a in assets}
        asset_ids = list(player_map.keys())

        # Consultar edificios relevantes en planet_buildings
        buildings = []
        if asset_ids:
            # --- V10.4 / V19.0: Filtrar edificios completados ---
            buildings_res = db.table("planet_buildings")\
                .select("building_type, planet_asset_id, is_active, built_at_tick")\
                .in_("planet_asset_id", asset_ids)\
                .execute()

            raw_buildings = buildings_res.data if buildings_res and buildings_res.data else []
            # Filtro estricto de finalización
            buildings = [b for b in raw_buildings if b.get("built_at_tick", 0) <= current_tick]

        outpost_owners = set()
        orbital_station_owner = None

        for b in buildings:
            b_type = b.get("building_type")
            pid = player_map.get(b.get("planet_asset_id"))
            is_active = b.get("is_active", True)

            if b_type == "outpost":
                outpost_owners.add(pid)
            elif b_type == "orbital_station" and is_active:
                orbital_station_owner = pid

        # --- DETERMINAR SOBERANÍA DE SUPERFICIE ---
        new_surface_owner = None

        if population > 0:
            # Regla V11: Si hay población, manda la Base Militar (Tabla 'bases')
            new_surface_owner = base_owner_id
        else:
            if base_owner_id:
                new_surface_owner = base_owner_id
            elif len(outpost_owners) == 1:
                new_surface_owner = list(outpost_owners)[0]
            else:
                new_surface_owner = None

        # --- DETERMINAR SOBERANÍA ORBITAL ---
        new_orbital_owner = None
        if orbital_station_owner:
            new_orbital_owner = orbital_station_owner
        elif enemy_fleet_owner_id:
            new_orbital_owner = enemy_fleet_owner_id
        else:
            new_orbital_owner = new_surface_owner

        # Actualizar Planeta
        db.table("planets").update({
            "surface_owner_id": new_surface_owner,
            "orbital_owner_id": new_orbital_owner,
            "is_disputed": (new_surface_owner is None and len(outpost_owners) > 1)
        }).eq("id", planet_id).execute()

        # V9.0: Recalcular control del sistema en cascada
        if system_id:
            recalculate_system_ownership(system_id)

    except Exception as e:
        log_event(f"Error actualizando soberanía planet {planet_id}: {e}", is_error=True)


def recalculate_system_ownership(system_id: int) -> Optional[int]:
    """
    Recalcula y actualiza el controlador de un sistema basado en mayoría de planetas.
    """
    try:
        db = _get_db()

        # 1. Obtener todos los planetas del sistema
        planets_res = db.table("planets").select("id, surface_owner_id").eq("system_id", system_id).execute()
        planets = planets_res.data if planets_res and planets_res.data else []

        total_planets = len(planets)

        if total_planets == 0:
            update_system_controller(system_id, None)
            return None

        # 2. Contar planetas por propietario
        owner_counts: Dict[int, int] = {}
        for planet in planets:
            owner_id = planet.get("surface_owner_id")
            if owner_id is not None:
                owner_counts[owner_id] = owner_counts.get(owner_id, 0) + 1

        # 3. Determinar si alguien tiene mayoría (> 50%)
        new_controller_id: Optional[int] = None
        majority_threshold = total_planets / 2.0

        for player_id, count in owner_counts.items():
            if count > majority_threshold:
                new_controller_id = player_id
                break

        update_system_controller(system_id, new_controller_id)

        return new_controller_id

    except Exception as e:
        log_event(f"Error recalculando propiedad del sistema {system_id}: {e}", is_error=True)
        return None


def recalculate_system_security(system_id: int) -> float:
    """
    V9.1: Recalcula el promedio de seguridad de todos los planetas del sistema
    y actualiza la tabla systems.
    """
    try:
        db = _get_db()
        response = db.table("planets")\
            .select("security")\
            .eq("system_id", system_id)\
            .execute()

        planets = response.data if response and response.data else []
        if not planets:
            update_system_security(system_id, 0.0)
            return 0.0

        total_security = sum(p.get("security", 0.0) for p in planets)
        avg_security = total_security / len(planets)

        update_system_security(system_id, avg_security)

        return avg_security
    except Exception as e:
        log_event(f"Error recalculando seguridad sistema {system_id}: {e}", is_error=True)
        return 0.0


def check_system_majority_control(system_id: int, player_id: int) -> bool:
    """Verifica si un jugador tiene control mayoritario de un sistema."""
    try:
        db = _get_db()

        all_planets_res = db.table("planets").select("id").eq("system_id", system_id).execute()
        all_planets = all_planets_res.data if all_planets_res and all_planets_res.data else []
        total_planets = len(all_planets)

        if total_planets == 0:
            return False

        my_planets_res = db.table("planets").select("id")\
            .eq("system_id", system_id)\
            .eq("surface_owner_id", player_id)\
            .execute()

        my_count = len(my_planets_res.data) if my_planets_res and my_planets_res.data else 0
        has_majority = my_count > (total_planets / 2.0)

        return has_majority

    except Exception as e:
        print(f"Error checking system control: {e}")
        return False


def batch_update_planet_security(updates: List[Tuple[int, float]]) -> bool:
    """Actualiza la seguridad en lote en la tabla 'planets' y recalcula sistemas afectados."""
    if not updates: return True
    try:
        db = _get_db()
        affected_systems = set()

        # Actualización de planetas
        for planet_id, security in updates:
            db.table("planets").update({"security": security}).eq("id", planet_id).execute()

        # V9.1: Recálculo de Sistemas Afectados
        planet_ids = [u[0] for u in updates]
        if planet_ids:
            sys_res = db.table("planets").select("system_id").in_("id", planet_ids).execute()
            if sys_res and sys_res.data:
                for row in sys_res.data:
                    sid = row.get("system_id")
                    if sid: affected_systems.add(sid)

        # Recalculamos la seguridad de cada sistema afectado
        for sid in affected_systems:
            recalculate_system_security(sid)

        return True
    except Exception as e:
        log_event(f"Error batch security update: {e}", is_error=True)
        return False


def update_planet_security_value(planet_id: int, value: float) -> bool:
    """Actualiza la seguridad física del planeta en la tabla mundial."""
    try:
        response = _get_db().table("planets").update({"security": value}).eq("id", planet_id).execute()
        return True if response else False
    except Exception as e:
        log_event(f"Error actualizando seguridad del planeta {planet_id}: {e}", is_error=True)
        return False


def update_planet_security_data(planet_id: int, security: float, breakdown: Dict[str, Any]) -> bool:
    """Actualiza la seguridad en la tabla 'planets' y recalcula la del sistema."""
    try:
        db = _get_db()
        # V6.1: Persistencia explícita de breakdown
        response = db.table("planets").update({
            "security": security,
            "security_breakdown": breakdown
        }).eq("id", planet_id).execute()

        if response:
            p_res = db.table("planets").select("system_id").eq("id", planet_id).single().execute()
            if p_res and p_res.data and p_res.data.get("system_id"):
                recalculate_system_security(p_res.data.get("system_id"))
            return True
        return False
    except Exception as e:
        log_event(f"Error actualizando seguridad planeta {planet_id}: {e}", is_error=True)
        return False