# core/economy_engine.py (Completo)
"""
Motor Económico MMFR (Materials, Metals, Fuel, Resources).
Gestiona toda la lógica de cálculo económico del juego.
Refactorizado V4.2: Modelo Logarítmico y Penalización Orbital.
Actualizado V4.4: Centralización de Seguridad y Transparencia (Breakdowns).
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
import math

from data.log_repository import log_event
from data.player_repository import get_player_finances, update_player_resources, get_all_players
from data.planet_repository import (
    get_all_player_planets_with_buildings,
    get_luxury_extraction_sites_for_player,
    batch_update_planet_security, # Deprecated en V4.4 pero mantenido por compatibilidad
    batch_update_building_status,
    update_planet_asset,
    update_planet_security_data # Nueva función V4.4
)

from core.world_constants import (
    BUILDING_TYPES,
    BUILDING_SHUTDOWN_PRIORITY,
    ECONOMY_RATES,
    DISPUTED_PENALTY_MULTIPLIER,
    SECTOR_TYPE_URBAN
)
from core.models import ProductionSummary, EconomyTickResult
from core.market_engine import process_pending_market_orders
from core.rules import calculate_and_update_system_security


# --- FUNCIONES DE CÁLCULO ECONÓMICO (PURAS) ---

def calculate_planet_security(
    population: float,
    infrastructure_defense: int,
    orbital_distance: int 
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula el nivel de seguridad del planeta (0-100) y genera un desglose.
    Formula V4.2: Base (25) + (Población * 5) + Infraestructura - (2 * Anillo Orbital).
    
    Returns:
        Tuple[float, Dict]: (Valor Final, Objeto Breakdown)
    """
    if population <= 0:
        return 0.0, {"text": "Deshabitado (Población 0)", "total": 0.0}

    base = ECONOMY_RATES.get("security_base", 25.0)
    per_pop = ECONOMY_RATES.get("security_per_1b_pop", 5.0)
    
    pop_bonus = population * per_pop
    distance_penalty = 2.0 * orbital_distance
    
    raw_total = base + pop_bonus + infrastructure_defense - distance_penalty
    final_val = max(1.0, min(raw_total, 100.0)) # Clamp 1-100 si hay población
    
    # Generar Desglose
    breakdown = {
        "base": base,
        "pop_bonus": round(pop_bonus, 2),
        "infra": infrastructure_defense,
        "penalty": round(distance_penalty, 2),
        "total": round(final_val, 2),
        "text": f"Base ({base}) + Pop ({pop_bonus:.1f}) + Infra ({infrastructure_defense}) - Dist ({distance_penalty:.1f})"
    }
    
    return final_val, breakdown


def calculate_income(
    population: float,
    security: float,
    penalty_multiplier: float = 1.0
) -> int:
    """
    Calcula el ingreso de créditos.
    Formula V4.2: (RateBase * log10(Población)) * (Seguridad / 100).
    """
    rate = ECONOMY_RATES.get("income_per_pop", 150.0)
    
    # Crecimiento Logarítmico
    pop_factor = math.log10(max(1.001, population)) 
    
    efficiency = security / 100.0
    
    income = (rate * pop_factor) * efficiency * penalty_multiplier
    
    return max(0, int(income))


@dataclass
class MaintenanceResult:
    buildings_to_disable: List[Tuple[int, str]] = field(default_factory=list)
    buildings_to_enable: List[Tuple[int, str]] = field(default_factory=list)
    total_cost: Dict[str, int] = field(default_factory=dict)
    paid_buildings: List[Dict] = field(default_factory=list)


def process_building_maintenance(
    buildings: List[Dict[str, Any]],
    available_resources: Dict[str, int],
    available_pops: float
) -> MaintenanceResult:
    """
    Procesa el mantenimiento estricto de los edificios.
    """
    result = MaintenanceResult()
    current_resources = available_resources.copy()
    
    def get_priority(b: Dict) -> int:
        b_type = b.get("building_type", "")
        cat = BUILDING_TYPES.get(b_type, {}).get("category", "otros")
        return BUILDING_SHUTDOWN_PRIORITY.get(cat, 99)

    sorted_buildings = sorted(buildings, key=get_priority)
    
    for b in sorted_buildings:
        b_id = b["id"]
        b_type = b.get("building_type", "")
        b_def = BUILDING_TYPES.get(b_type, {})
        b_name = b_def.get("name", b_type)
        
        maintenance = b_def.get("maintenance", {})
        
        can_afford = True
        for res, cost in maintenance.items():
            if current_resources.get(res, 0) < cost:
                can_afford = False
                break
        
        is_active_db = b.get("is_active", True)
        
        if can_afford:
            for res, cost in maintenance.items():
                current_resources[res] -= cost
                result.total_cost[res] = result.total_cost.get(res, 0) + cost
            
            if not is_active_db:
                result.buildings_to_enable.append((b_id, b_name))
            
            b_active = b.copy()
            b_active["is_active"] = True
            result.paid_buildings.append(b_active)
            
        else:
            if is_active_db:
                result.buildings_to_disable.append((b_id, b_name))
            
    return result


def calculate_planet_production(active_buildings: List[Dict[str, Any]]) -> ProductionSummary:
    """
    Calcula producción SOLO de edificios activos y pagados.
    Actualizado v4.2.0: Aplica bono de +15% si está en sector Urbano.
    """
    production = ProductionSummary()

    for building in active_buildings:
        building_type = building.get("building_type")
        definition = BUILDING_TYPES.get(building_type, {})
        base_prod = definition.get("production", {})
        
        # V4.2.0: Chequear bono de sector
        sector_type = building.get("sector_type")
        multiplier = 1.15 if sector_type == SECTOR_TYPE_URBAN else 1.0

        production.materiales += int(base_prod.get("materiales", 0) * multiplier)
        production.componentes += int(base_prod.get("componentes", 0) * multiplier)
        production.celulas_energia += int(base_prod.get("celulas_energia", 0) * multiplier)
        production.influencia += int(base_prod.get("influencia", 0) * multiplier)
        production.datos += int(base_prod.get("datos", 0) * multiplier)

    return production


# --- PROCESAMIENTO DE RECURSOS DE LUJO ---

def calculate_luxury_extraction(sites: List[Dict[str, Any]]) -> Dict[str, int]:
    extracted: Dict[str, int] = {}
    for site in sites:
        if not site.get("is_active", True):
            continue
        resource_key = site.get("resource_key")
        category = site.get("resource_category")
        rate = site.get("extraction_rate", 1)
        key = f"{category}.{resource_key}"
        extracted[key] = extracted.get(key, 0) + rate
    return extracted


def merge_luxury_resources(current: Dict[str, Any], extracted: Dict[str, int]) -> Dict[str, Any]:
    result = dict(current) if current else {}
    for key, amount in extracted.items():
        parts = key.split(".")
        if len(parts) != 2: continue
        category, resource = parts
        if category not in result: result[category] = {}
        result[category][resource] = result[category].get(resource, 0) + amount
    return result


# --- ORQUESTADOR PRINCIPAL ---

def run_economy_tick_for_player(player_id: int) -> EconomyTickResult:
    """
    Ejecuta el ciclo económico completo para un jugador.
    """
    result = EconomyTickResult(player_id=player_id)

    try:
        try:
            process_pending_market_orders(player_id)
        except Exception as e:
            log_event(f"Error procesando mercado en tick: {e}", player_id, is_error=True)

        planets = get_all_player_planets_with_buildings(player_id)
        if not planets:
            return result

        finances = get_player_finances(player_id)
        luxury_sites = get_luxury_extraction_sites_for_player(player_id)

        player_resources = {
            "creditos": finances.get("creditos", 0),
            "materiales": finances.get("materiales", 0),
            "componentes": finances.get("componentes", 0),
            "celulas_energia": finances.get("celulas_energia", 0),
            "influencia": finances.get("influencia", 0),
            "datos": finances.get("datos", 0)
        }
        
        building_status_updates: List[Tuple[int, bool]] = []
        systems_to_update_security = set()
        
        # 2. Procesar cada planeta
        for planet in planets:
            # A. Seguridad (V4.4: Centralizada en tabla planets con Breakdown)
            pop = float(planet.get("poblacion", 0.0))
            infra_def = planet.get("infraestructura_defensiva", 0)
            
            orbital_dist = planet.get("orbital_distance", 0) 
            if orbital_dist == 0 and "ring_index" in planet:
                orbital_dist = planet["ring_index"]

            # CALCULO PRINCIPAL DE SEGURIDAD
            security, security_breakdown = calculate_planet_security(pop, infra_def, orbital_dist)
            
            # Persistencia V4.4: Guardar en tabla PLANETS (Source of Truth)
            update_planet_security_data(planet["planet_id"], security, security_breakdown)
            
            # Sincronizar hacia planet_assets para compatibilidad UI legacy temporal
            if abs(security - planet.get("seguridad", 0)) > 0.1:
                update_planet_asset(planet["id"], {"seguridad": security})
            
            systems_to_update_security.add(planet["system_id"])
            
            # B. Estado de Disputa / Bloqueo
            orbital_owner = planet.get("orbital_owner_id")
            surface_owner = planet.get("surface_owner_id")
            is_disputed = planet.get("is_disputed", False)
            
            penalty = 1.0
            is_blockaded = False
            
            if orbital_owner is not None and orbital_owner != surface_owner:
                is_blockaded = True
                
            if is_disputed or is_blockaded:
                penalty = DISPUTED_PENALTY_MULTIPLIER # 0.3
            
            # C. Ingresos
            income = calculate_income(pop, security, penalty_multiplier=penalty)
            result.total_income += income
            
            # D. Mantenimiento
            buildings = planet.get("buildings", [])
            pops_avail = float(planet.get("pops_activos", pop))
            
            maint_res = process_building_maintenance(buildings, player_resources, pops_avail)
            
            for res, cost in maint_res.total_cost.items():
                result.maintenance_cost[res] = result.maintenance_cost.get(res, 0) + cost
                player_resources[res] -= cost 
                
            for bid, name in maint_res.buildings_to_disable:
                building_status_updates.append((bid, False))
                result.buildings_disabled.append(bid)
                log_event(f"⚠️ Edificio {name} detenido (Falta de recursos)", player_id)
                
            for bid, name in maint_res.buildings_to_enable:
                building_status_updates.append((bid, True))
                result.buildings_reactivated.append(bid)
                
            # E. Producción
            prod = calculate_planet_production(maint_res.paid_buildings)
            result.production = result.production.add(prod)

        # 3. Recursos de Lujo
        luxury_extracted = calculate_luxury_extraction(luxury_sites)
        result.luxury_extracted = luxury_extracted

        # 4. Actualizar DB
        if building_status_updates:
            batch_update_building_status(building_status_updates)
            
        # V4.4: Recalcular seguridad de sistemas afectados
        for sys_id in systems_to_update_security:
            try:
                calculate_and_update_system_security(sys_id)
            except Exception as e:
                print(f"Error actualizando seguridad sistema {sys_id}: {e}")

        # 5. Calculo Final
        final_resources = {
            "creditos": player_resources["creditos"] + result.total_income + result.production.creditos,
            "materiales": player_resources["materiales"] + result.production.materiales,
            "componentes": player_resources["componentes"] + result.production.componentes,
            "celulas_energia": player_resources["celulas_energia"] + result.production.celulas_energia,
            "influencia": player_resources["influencia"] + result.production.influencia,
            "datos": player_resources["datos"] + result.production.datos
        }
        
        if luxury_extracted:
            current_luxury = finances.get("recursos_lujo", {})
            final_resources["recursos_lujo"] = merge_luxury_resources(current_luxury, luxury_extracted)

        update_player_resources(player_id, final_resources)
        result.success = True
        
        log_event(
            f"💰 Eco Tick: +{result.total_income} Cr | Prod: {result.production.materiales} Mat",
            player_id
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        log_event(f"Error economía jugador {player_id}: {e}", player_id, is_error=True)

    return result


def run_global_economy_tick() -> List[EconomyTickResult]:
    log_event("🏛️ Iniciando fase económica global (Control V4.4)...")
    results = []
    try:
        players = get_all_players()
        for player in players:
            results.append(run_economy_tick_for_player(player["id"]))
    except Exception as e:
        log_event(f"Error global economy: {e}", is_error=True)
    return results


# --- FUNCIONES AUXILIARES PARA UI (Proyecciones) ---

def get_player_projected_economy(player_id: int) -> Dict[str, int]:
    """Calcula proyección (Delta) para UI sin modificar DB."""
    projection = {k: 0 for k in ["creditos", "materiales", "componentes", "celulas_energia", "influencia", "datos"]}
    
    try:
        planets = get_all_player_planets_with_buildings(player_id)
        
        for planet in planets:
            # Control Logic para proyección
            orbital_owner = planet.get("orbital_owner_id")
            surface_owner = planet.get("surface_owner_id")
            is_disputed = planet.get("is_disputed", False)
            penalty = 1.0
            if (orbital_owner is not None and orbital_owner != surface_owner) or is_disputed:
                penalty = DISPUTED_PENALTY_MULTIPLIER

            pop = float(planet.get("poblacion", 0.0))
            infra = planet.get("infraestructura_defensiva", 0)
            
            orbital_dist = planet.get("orbital_distance", 0)
            if orbital_dist == 0 and "ring_index" in planet:
                orbital_dist = planet["ring_index"]

            # Unpack tuple V4.4
            sec, _ = calculate_planet_security(pop, infra, orbital_dist)
            
            # Ingresos proyectados con penalización
            income = calculate_income(pop, sec, penalty_multiplier=penalty)
            projection["creditos"] += income
            
            buildings = planet.get("buildings", [])
            active_buildings = [b for b in buildings if b.get("is_active", True)]
            
            prod = calculate_planet_production(active_buildings)
            
            for b in active_buildings:
                b_type = b.get("building_type")
                maint = BUILDING_TYPES.get(b_type, {}).get("maintenance", {})
                for res, cost in maint.items():
                    projection[res] -= cost
            
            projection["materiales"] += prod.materiales
            projection["componentes"] += prod.componentes
            projection["celulas_energia"] += prod.celulas_energia
            projection["influencia"] += prod.influencia
            projection["datos"] += prod.datos
            projection["creditos"] += prod.creditos

    except Exception:
        pass
        
    return projection