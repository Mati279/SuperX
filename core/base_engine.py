# core/base_engine.py
"""
Motor de Bases.
Maneja la construcción, mejora y gestión de módulos de bases militares.

Reglas:
- Las bases se construyen en sectores urbanos bajo soberanía del jugador.
- Niveles 1-4.
- Cada módulo se mejora hasta (nivel_base * 2).
- Módulos nuevos arrancan en (nivel_base + 1).
- Tiempo de mejora de base = nivel_destino + 1 ticks.

v1.0.0: Implementación inicial del sistema de bases.
"""

from typing import Dict, Any, Optional, List, Tuple
from data.database import get_supabase
from data.player_repository import get_player_finances, update_player_resources
from data.planet_repository import (
    get_planet_asset_by_id,
    get_planet_by_id,
    get_planet_sectors_status,
    update_planet_asset
)
from data.log_repository import log_event
from data.world_repository import get_world_state
from core.world_constants import (
    BASE_CONSTRUCTION_COST,
    BASE_UPGRADE_COSTS,
    BASE_MODULES,
    BASE_MODULES_BY_TIER,
    BASE_EXTRA_SLOTS,
    SECTOR_TYPE_URBAN,
    get_base_upgrade_time,
    get_max_module_level,
    get_initial_module_level
)


def _get_db():
    """Obtiene el cliente de Supabase."""
    return get_supabase()


# --- VALIDACIONES ---

def can_build_base_in_sector(sector_id: int, player_id: int) -> Tuple[bool, str]:
    """
    Verifica si un jugador puede construir una base en un sector.

    Requisitos:
    1. El sector debe ser de tipo Urbano.
    2. El sector no debe tener ya una base.
    3. El sector debe estar bajo soberanía del jugador (planeta doblegado).

    Returns:
        Tuple[bool, str]: (puede_construir, mensaje_error)
    """
    db = _get_db()

    try:
        # 1. Obtener datos del sector
        sector_res = db.table("sectors").select("*, planets(surface_owner_id)")\
            .eq("id", sector_id).single().execute()

        if not sector_res or not sector_res.data:
            return False, "Sector no encontrado."

        sector = sector_res.data

        # 2. Verificar tipo de sector
        if sector.get("sector_type") != SECTOR_TYPE_URBAN:
            return False, f"Solo se pueden construir bases en sectores urbanos. Este sector es: {sector.get('sector_type')}"

        # 3. Verificar que no haya base existente
        planet_id = sector.get("planet_id")
        bases_res = db.table("bases")\
            .select("id")\
            .eq("sector_id", sector_id)\
            .execute()

        if bases_res and bases_res.data and len(bases_res.data) > 0:
            return False, "Este sector ya tiene una base construida."

        # 4. Verificar soberanía (planeta doblegado)
        planet_data = sector.get("planets", {})
        surface_owner = planet_data.get("surface_owner_id")

        if surface_owner != player_id:
            return False, "Solo puedes construir bases en sectores bajo tu soberanía."

        return True, "OK"

    except Exception as e:
        return False, f"Error de validación: {e}"


def can_upgrade_base(base_id: int, player_id: int) -> Tuple[bool, str]:
    """
    Verifica si una base puede ser mejorada.

    Requisitos:
    1. La base debe pertenecer al jugador.
    2. La base no debe estar en proceso de mejora.
    3. La base debe ser nivel < 4.
    4. El jugador debe tener recursos suficientes.

    Returns:
        Tuple[bool, str]: (puede_mejorar, mensaje_error)
    """
    db = _get_db()

    try:
        # 1. Obtener datos de la base
        base_res = db.table("bases").select("*").eq("id", base_id).single().execute()

        if not base_res or not base_res.data:
            return False, "Base no encontrada."

        base = base_res.data

        # 2. Verificar propiedad
        if base.get("player_id") != player_id:
            return False, "Esta base no te pertenece."

        # 3. Verificar que no esté en mejora
        if base.get("upgrade_in_progress", False):
            remaining = base.get("upgrade_completes_at_tick", 0) - get_world_state().get("current_tick", 0)
            return False, f"Base en proceso de mejora. Faltan {remaining} ciclos."

        # 4. Verificar nivel máximo
        current_tier = base.get("tier", 1)
        if current_tier >= 4:
            return False, "La base ya está al nivel máximo (Nv.4)."

        # 5. Verificar recursos
        target_tier = current_tier + 1
        costs = BASE_UPGRADE_COSTS.get(target_tier, {})
        finances = get_player_finances(player_id)

        if finances.get("creditos", 0) < costs.get("creditos", 0):
            return False, f"Créditos insuficientes. Necesitas {costs.get('creditos', 0)}C."

        if finances.get("materiales", 0) < costs.get("materiales", 0):
            return False, f"Materiales insuficientes. Necesitas {costs.get('materiales', 0)} Mat."

        return True, "OK"

    except Exception as e:
        return False, f"Error de validación: {e}"


# --- CONSTRUCCIÓN DE BASES ---

def build_base(sector_id: int, player_id: int) -> Dict[str, Any]:
    """
    Construye una nueva base Nv.1 en un sector urbano.

    Args:
        sector_id: ID del sector donde construir.
        player_id: ID del jugador.

    Returns:
        Dict con resultado de la operación.
    """
    db = _get_db()

    # 1. Validar construcción
    can_build, error_msg = can_build_base_in_sector(sector_id, player_id)
    if not can_build:
        return {"success": False, "error": error_msg}

    # 2. Verificar recursos
    finances = get_player_finances(player_id)
    cost_c = BASE_CONSTRUCTION_COST.get("creditos", 1000)
    cost_m = BASE_CONSTRUCTION_COST.get("materiales", 110)

    if finances.get("creditos", 0) < cost_c:
        return {"success": False, "error": f"Créditos insuficientes. Necesitas {cost_c}C."}

    if finances.get("materiales", 0) < cost_m:
        return {"success": False, "error": f"Materiales insuficientes. Necesitas {cost_m} Mat."}

    try:
        # 3. Obtener planet_id del sector
        sector_res = db.table("sectors").select("planet_id").eq("id", sector_id).single().execute()
        planet_id = sector_res.data.get("planet_id") if sector_res and sector_res.data else None

        if not planet_id:
            return {"success": False, "error": "No se pudo determinar el planeta del sector."}

        # 4. Descontar recursos
        new_credits = finances.get("creditos", 0) - cost_c
        new_materials = finances.get("materiales", 0) - cost_m

        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # 5. Obtener tick actual
        world = get_world_state()
        current_tick = world.get("current_tick", 1)

        # 6. Crear base con módulos iniciales
        # Tiempo de construcción de base Nv.1 = 2 ticks (1+1)
        construction_time = get_base_upgrade_time(1)
        completes_at = current_tick + construction_time

        # Módulos iniciales (Nv.1 desbloquea: sensor_planetary, sensor_orbital, defense_ground, bunker)
        # Los módulos arrancan en nivel 2 (nivel_base + 1 = 1 + 1)
        initial_module_level = get_initial_module_level(1)

        base_data = {
            "player_id": player_id,
            "planet_id": planet_id,
            "sector_id": sector_id,
            "tier": 1,
            "upgrade_in_progress": True,
            "upgrade_completes_at_tick": completes_at,
            # Módulos iniciales
            "module_sensor_planetary": initial_module_level,
            "module_sensor_orbital": initial_module_level,
            "module_defense_ground": initial_module_level,
            "module_bunker": initial_module_level,
            # Módulos de niveles superiores (bloqueados)
            "module_defense_aa": 0,
            "module_defense_missile": 0,
            "module_energy_shield": 0,
            "module_planetary_shield": 0,
            "created_at_tick": current_tick
        }

        response = db.table("bases").insert(base_data).execute()

        if response and response.data:
            base_id = response.data[0].get("id")
            log_event(
                f"Iniciada construcción de Base Nv.1 en sector {sector_id}. "
                f"Completará en {construction_time} ciclos.",
                player_id
            )

            return {
                "success": True,
                "message": f"Base en construcción. Estará lista en {construction_time} ciclos.",
                "base_id": base_id,
                "completes_at_tick": completes_at
            }

        return {"success": False, "error": "Error al crear la base en la base de datos."}

    except Exception as e:
        log_event(f"Error crítico construyendo base: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}


def upgrade_base(base_id: int, player_id: int) -> Dict[str, Any]:
    """
    Mejora una base existente al siguiente nivel.

    Args:
        base_id: ID de la base a mejorar.
        player_id: ID del jugador.

    Returns:
        Dict con resultado de la operación.
    """
    db = _get_db()

    # 1. Validar mejora
    can_upgrade, error_msg = can_upgrade_base(base_id, player_id)
    if not can_upgrade:
        return {"success": False, "error": error_msg}

    try:
        # 2. Obtener datos de la base
        base_res = db.table("bases").select("*").eq("id", base_id).single().execute()
        base = base_res.data

        current_tier = base.get("tier", 1)
        target_tier = current_tier + 1

        # 3. Obtener costos y descontar recursos
        costs = BASE_UPGRADE_COSTS.get(target_tier, {})
        finances = get_player_finances(player_id)

        new_credits = finances.get("creditos", 0) - costs.get("creditos", 0)
        new_materials = finances.get("materiales", 0) - costs.get("materiales", 0)

        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # 4. Calcular tiempo de mejora
        world = get_world_state()
        current_tick = world.get("current_tick", 1)
        upgrade_time = get_base_upgrade_time(target_tier)
        completes_at = current_tick + upgrade_time

        # 5. Actualizar base (marcar mejora en progreso)
        update_data = {
            "upgrade_in_progress": True,
            "upgrade_completes_at_tick": completes_at,
            "upgrade_target_tier": target_tier
        }

        db.table("bases").update(update_data).eq("id", base_id).execute()

        log_event(
            f"Iniciada mejora de base a Nv.{target_tier}. "
            f"Coste: {costs.get('creditos', 0)}C, {costs.get('materiales', 0)} Mat. "
            f"Completará en {upgrade_time} ciclos.",
            player_id
        )

        return {
            "success": True,
            "message": f"Mejora a Nv.{target_tier} iniciada. Estará lista en {upgrade_time} ciclos.",
            "target_tier": target_tier,
            "completes_at_tick": completes_at
        }

    except Exception as e:
        log_event(f"Error crítico mejorando base: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}


def complete_base_upgrade(base_id: int) -> bool:
    """
    Completa la mejora de una base cuando el tick de finalización se alcanza.
    Desbloquea nuevos módulos según el nivel alcanzado.

    Esta función es llamada por el TimeEngine en la fase correspondiente.

    Args:
        base_id: ID de la base a completar.

    Returns:
        bool: True si se completó correctamente.
    """
    db = _get_db()

    try:
        # 1. Obtener datos de la base
        base_res = db.table("bases").select("*").eq("id", base_id).single().execute()

        if not base_res or not base_res.data:
            return False

        base = base_res.data
        target_tier = base.get("upgrade_target_tier", base.get("tier", 1) + 1)
        player_id = base.get("player_id")

        # 2. Preparar actualización
        update_data = {
            "tier": target_tier,
            "upgrade_in_progress": False,
            "upgrade_completes_at_tick": None,
            "upgrade_target_tier": None
        }

        # 3. Desbloquear nuevos módulos si corresponde
        new_modules = BASE_MODULES_BY_TIER.get(target_tier, [])
        initial_level = get_initial_module_level(target_tier)

        for module_key in new_modules:
            column_name = f"module_{module_key}"
            # Solo inicializar si el módulo estaba en 0 (bloqueado)
            if base.get(column_name, 0) == 0:
                update_data[column_name] = initial_level

        # 4. Aplicar actualización
        db.table("bases").update(update_data).eq("id", base_id).execute()

        # 5. Aplicar slots extra si corresponde
        extra_slots = BASE_EXTRA_SLOTS.get(target_tier, 0)
        if extra_slots > 0:
            sector_id = base.get("sector_id")
            _add_extra_slots_to_sector(sector_id, extra_slots)

        log_event(
            f"Base mejorada a Nv.{target_tier}. "
            f"Nuevos módulos desbloqueados: {', '.join(new_modules) if new_modules else 'Ninguno'}. "
            f"Slots extra: +{extra_slots}.",
            player_id
        )

        return True

    except Exception as e:
        print(f"Error completando mejora de base {base_id}: {e}")
        return False


def _add_extra_slots_to_sector(sector_id: int, extra_slots: int) -> bool:
    """Añade slots extra a un sector (por mejora de base)."""
    db = _get_db()

    try:
        # Obtener slots actuales
        sector_res = db.table("sectors").select("max_slots").eq("id", sector_id).single().execute()

        if not sector_res or not sector_res.data:
            return False

        current_slots = sector_res.data.get("max_slots", 3)
        new_slots = current_slots + extra_slots

        db.table("sectors").update({"max_slots": new_slots}).eq("id", sector_id).execute()

        return True

    except Exception as e:
        print(f"Error añadiendo slots extra al sector {sector_id}: {e}")
        return False


# --- GESTIÓN DE MÓDULOS ---

def upgrade_module(base_id: int, module_key: str, player_id: int) -> Dict[str, Any]:
    """
    Mejora un módulo de una base.

    Reglas:
    - El módulo debe estar desbloqueado (nivel > 0).
    - El nivel máximo es (nivel_base * 2).

    Args:
        base_id: ID de la base.
        module_key: Clave del módulo (ej: "sensor_planetary").
        player_id: ID del jugador.

    Returns:
        Dict con resultado de la operación.
    """
    db = _get_db()

    # 1. Validar que el módulo existe en la configuración
    if module_key not in BASE_MODULES:
        return {"success": False, "error": f"Módulo desconocido: {module_key}"}

    module_def = BASE_MODULES[module_key]
    column_name = f"module_{module_key}"

    try:
        # 2. Obtener datos de la base
        base_res = db.table("bases").select("*").eq("id", base_id).single().execute()

        if not base_res or not base_res.data:
            return {"success": False, "error": "Base no encontrada."}

        base = base_res.data

        # 3. Verificar propiedad
        if base.get("player_id") != player_id:
            return {"success": False, "error": "Esta base no te pertenece."}

        # 4. Verificar que la base no esté en mejora
        if base.get("upgrade_in_progress", False):
            return {"success": False, "error": "No puedes mejorar módulos mientras la base está en mejora."}

        # 5. Verificar nivel actual del módulo
        current_level = base.get(column_name, 0)

        if current_level == 0:
            return {"success": False, "error": f"Módulo '{module_def['name']}' no está desbloqueado. Mejora la base."}

        # 6. Verificar nivel máximo
        base_tier = base.get("tier", 1)
        max_level = get_max_module_level(base_tier)

        if current_level >= max_level:
            return {
                "success": False,
                "error": f"Módulo al nivel máximo ({max_level}) para base Nv.{base_tier}. Mejora la base primero."
            }

        # 7. Calcular coste de mejora
        cost_base = module_def.get("cost_base", {})
        cost_per_level = module_def.get("cost_per_level", {})

        # Coste = base + (nivel_actual * coste_por_nivel)
        cost_c = cost_base.get("creditos", 0) + (current_level * cost_per_level.get("creditos", 0))
        cost_m = cost_base.get("materiales", 0) + (current_level * cost_per_level.get("materiales", 0))

        # 8. Verificar recursos
        finances = get_player_finances(player_id)

        if finances.get("creditos", 0) < cost_c:
            return {"success": False, "error": f"Créditos insuficientes. Necesitas {cost_c}C."}

        if finances.get("materiales", 0) < cost_m:
            return {"success": False, "error": f"Materiales insuficientes. Necesitas {cost_m} Mat."}

        # 9. Descontar recursos
        new_credits = finances.get("creditos", 0) - cost_c
        new_materials = finances.get("materiales", 0) - cost_m

        update_player_resources(player_id, {
            "creditos": new_credits,
            "materiales": new_materials
        })

        # 10. Mejorar módulo
        new_level = current_level + 1
        db.table("bases").update({column_name: new_level}).eq("id", base_id).execute()

        log_event(
            f"Módulo '{module_def['name']}' mejorado a nivel {new_level}. "
            f"Coste: {cost_c}C, {cost_m} Mat.",
            player_id
        )

        return {
            "success": True,
            "message": f"'{module_def['name']}' mejorado a nivel {new_level}.",
            "new_level": new_level,
            "max_level": max_level
        }

    except Exception as e:
        log_event(f"Error mejorando módulo: {e}", player_id, is_error=True)
        return {"success": False, "error": f"Error del sistema: {e}"}


# --- CONSULTAS ---

def get_base_by_id(base_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene los datos completos de una base por ID."""
    db = _get_db()

    try:
        response = db.table("bases").select("*").eq("id", base_id).single().execute()
        return response.data if response and response.data else None
    except Exception:
        return None


def get_base_by_sector(sector_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene la base de un sector, si existe."""
    db = _get_db()

    try:
        response = db.table("bases").select("*").eq("sector_id", sector_id).maybe_single().execute()
        return response.data if response and response.data else None
    except Exception:
        return None


def get_player_bases(player_id: int) -> List[Dict[str, Any]]:
    """Obtiene todas las bases de un jugador."""
    db = _get_db()

    try:
        response = db.table("bases")\
            .select("*, sectors(name, sector_type), planets(name)")\
            .eq("player_id", player_id)\
            .execute()
        return response.data if response and response.data else []
    except Exception:
        return []


def get_bases_pending_completion(current_tick: int) -> List[Dict[str, Any]]:
    """
    Obtiene bases cuya mejora debe completarse en el tick actual.
    Usado por el TimeEngine.
    """
    db = _get_db()

    try:
        response = db.table("bases")\
            .select("*")\
            .eq("upgrade_in_progress", True)\
            .lte("upgrade_completes_at_tick", current_tick)\
            .execute()
        return response.data if response and response.data else []
    except Exception:
        return []


def get_base_module_status(base_id: int) -> Dict[str, Any]:
    """
    Obtiene el estado detallado de todos los módulos de una base.

    Returns:
        Dict con información de cada módulo: nivel actual, máximo, bloqueado, etc.
    """
    base = get_base_by_id(base_id)

    if not base:
        return {}

    base_tier = base.get("tier", 1)
    max_module_level = get_max_module_level(base_tier)

    modules_status = {}

    for module_key, module_def in BASE_MODULES.items():
        column_name = f"module_{module_key}"
        current_level = base.get(column_name, 0)
        unlock_tier = module_def.get("unlock_tier", 1)

        is_unlocked = current_level > 0
        is_maxed = current_level >= max_module_level
        can_unlock_at_tier = unlock_tier if not is_unlocked else None

        # Calcular coste de siguiente mejora
        next_cost = None
        if is_unlocked and not is_maxed:
            cost_base = module_def.get("cost_base", {})
            cost_per_level = module_def.get("cost_per_level", {})
            next_cost = {
                "creditos": cost_base.get("creditos", 0) + (current_level * cost_per_level.get("creditos", 0)),
                "materiales": cost_base.get("materiales", 0) + (current_level * cost_per_level.get("materiales", 0))
            }

        modules_status[module_key] = {
            "name": module_def.get("name"),
            "description": module_def.get("desc"),
            "current_level": current_level,
            "max_level": max_module_level,
            "is_unlocked": is_unlocked,
            "is_maxed": is_maxed,
            "unlock_tier": unlock_tier,
            "can_unlock_at_tier": can_unlock_at_tier,
            "next_upgrade_cost": next_cost,
            "effect": module_def.get("effect", {})
        }

    return modules_status


def get_sector_eligible_for_base(planet_id: int, player_id: int) -> List[Dict[str, Any]]:
    """
    Obtiene los sectores elegibles para construir una base en un planeta.

    Returns:
        Lista de sectores urbanos sin base y bajo soberanía del jugador.
    """
    db = _get_db()

    try:
        # 1. Verificar soberanía del planeta
        planet = get_planet_by_id(planet_id)
        if not planet or planet.get("surface_owner_id") != player_id:
            return []

        # 2. Obtener sectores urbanos
        sectors_res = db.table("sectors")\
            .select("id, name, sector_type, max_slots")\
            .eq("planet_id", planet_id)\
            .eq("sector_type", SECTOR_TYPE_URBAN)\
            .execute()

        if not sectors_res or not sectors_res.data:
            return []

        sectors = sectors_res.data

        # 3. Filtrar sectores que ya tienen base
        sector_ids = [s["id"] for s in sectors]

        bases_res = db.table("bases")\
            .select("sector_id")\
            .in_("sector_id", sector_ids)\
            .execute()

        occupied_sectors = set()
        if bases_res and bases_res.data:
            occupied_sectors = {b["sector_id"] for b in bases_res.data}

        # 4. Retornar solo sectores elegibles
        eligible = [s for s in sectors if s["id"] not in occupied_sectors]

        return eligible

    except Exception:
        return []
