# core/economy_engine.py
"""
Motor Económico MMFR (Materials, Metals, Fuel, Resources).
Gestiona toda la lógica de cálculo económico del juego.
Refactorizado: Seguridad (0-100) y Mantenimiento Estricto.

IMPORTANTE: Este módulo NO importa supabase directamente.
Todas las operaciones de DB se realizan a través de repositorios.
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
import math

from data.log_repository import log_event
from data.player_repository import get_player_finances, update_player_resources, get_all_players
from data.planet_repository import (
    get_all_player_planets_with_buildings,
    get_luxury_extraction_sites_for_player,
    batch_update_planet_security,
    batch_update_building_status,
    update_planet_asset
)

from core.world_constants import (
    BUILDING_TYPES,
    BUILDING_SHUTDOWN_PRIORITY,
    ECONOMY_RATES
)
from core.models import ProductionSummary, EconomyTickResult


# --- FUNCIONES DE CÁLCULO ECONÓMICO (PURAS) ---

def calculate_planet_security(
    population: int,
    infrastructure_defense: int
) -> float:
    """
    Calcula el nivel de seguridad del planeta (0-100).
    Formula: Base (25) + (Población / 1B * 5) + Infraestructura.
    
    Args:
        population: Población total.
        infrastructure_defense: Valor acumulado de defensa (módulos).
        
    Returns:
        float: Seguridad entre 1.0 y 100.0
    """
    base = ECONOMY_RATES.get("security_base", 25.0)
    per_pop = ECONOMY_RATES.get("security_per_1b_pop", 5.0)
    
    # Bonus por población (grandes poblaciones se defienden mejor/tienen mas milicia)
    pop_bonus = (population / 1_000_000_000) * per_pop
    
    total = base + pop_bonus + infrastructure_defense
    
    # Clamp 1-100
    return max(1.0, min(total, 100.0))


def calculate_income(
    population: int,
    security: float
) -> int:
    """
    Calcula el ingreso de créditos.
    Formula: (Pop * Tasa) * (Seguridad / 100).
    
    Args:
        population: Población total.
        security: Nivel de seguridad (0-100).
        
    Returns:
        int: Créditos generados.
    """
    rate = ECONOMY_RATES.get("income_per_pop", 0.1)
    
    # Seguridad actúa como porcentaje de eficiencia fiscal
    efficiency = security / 100.0
    
    income = (population * rate) * efficiency
    return int(income)


@dataclass
class MaintenanceResult:
    buildings_to_disable: List[Tuple[int, str]] = field(default_factory=list)
    buildings_to_enable: List[Tuple[int, str]] = field(default_factory=list)
    total_cost: Dict[str, int] = field(default_factory=dict)
    paid_buildings: List[Dict] = field(default_factory=list)


def process_building_maintenance(
    buildings: List[Dict[str, Any]],
    available_resources: Dict[str, int],
    available_pops: int
) -> MaintenanceResult:
    """
    Procesa el mantenimiento estricto de los edificios.
    Determina qué edificios se mantienen activos (pagados) y cuáles se apagan.
    
    Reglas:
    1. Se itera por prioridad (Edificios vitales primero).
    2. Si hay recursos -> Se deduce costo y activa/mantiene.
    3. Si NO hay recursos -> Se desactiva (sin coste).
    
    Args:
        buildings: Lista de edificios.
        available_resources: Recursos del jugador (Mutable copy se usa internamente).
        available_pops: Población disponible (para cascade shutdown si fuese necesario).
        
    Returns:
        MaintenanceResult con listas de cambios y coste total.
    """
    result = MaintenanceResult()
    
    # Copia de recursos para ir descontando durante la simulación
    current_resources = available_resources.copy()
    
    # Función auxiliar para obtener prioridad (Menor número = Más vital = Procesar primero)
    def get_priority(b: Dict) -> int:
        b_type = b.get("building_type", "")
        cat = BUILDING_TYPES.get(b_type, {}).get("category", "otros")
        # BUILDING_SHUTDOWN_PRIORITY: Mayor número = Se apaga primero (Menos vital)
        # Invertimos para que el sort ponga primero los vitales (priority num bajo)
        # Si 'extraccion' es 4 (se apaga primero), queremos procesarlo al FINAL si faltan recursos?
        # NO. Queremos procesar los VITALES primero para asegurar que consuman recursos.
        # Vitales (Defensa/Admin) tienen prioridad baja en SHUTDOWN_PRIORITY (0/1).
        # Así que sort ascendente está bien: 0 (Admin) va primero.
        return BUILDING_SHUTDOWN_PRIORITY.get(cat, 99)

    # Ordenar edificios: Vitales primero
    sorted_buildings = sorted(buildings, key=get_priority)
    
    # Procesar
    for b in sorted_buildings:
        b_id = b["id"]
        b_type = b.get("building_type", "")
        b_def = BUILDING_TYPES.get(b_type, {})
        b_name = b_def.get("name", b_type)
        
        # Obtener costo de mantenimiento (diccionario)
        maintenance = b_def.get("maintenance", {})
        
        # Verificar si podemos pagar TODO el mantenimiento
        can_afford = True
        for res, cost in maintenance.items():
            if current_resources.get(res, 0) < cost:
                can_afford = False
                break
        
        # Estado actual en DB
        is_active_db = b.get("is_active", True)
        
        if can_afford:
            # Pagar
            for res, cost in maintenance.items():
                current_resources[res] -= cost
                result.total_cost[res] = result.total_cost.get(res, 0) + cost
            
            # Marcar como activo para producción
            # Si estaba inactivo, lo activamos (auto-enable si hay fondos)
            if not is_active_db:
                result.buildings_to_enable.append((b_id, b_name))
            
            # Añadir a lista de pagados (para calcular producción después)
            # Creamos una copia del edificio con estado activo forzado
            b_active = b.copy()
            b_active["is_active"] = True
            result.paid_buildings.append(b_active)
            
        else:
            # No se puede pagar -> Shutdown
            if is_active_db:
                result.buildings_to_disable.append((b_id, b_name))
            
            # No añadimos a paid_buildings, por lo que no producirá
            
    return result


def calculate_planet_production(active_buildings: List[Dict[str, Any]]) -> ProductionSummary:
    """Calcula producción SOLO de edificios activos y pagados."""
    production = ProductionSummary()

    for building in active_buildings:
        # Asumimos que si está en esta lista, ya pasó el chequeo de mantenimiento
        building_type = building.get("building_type")
        definition = BUILDING_TYPES.get(building_type, {})
        building_prod = definition.get("production", {})

        production.materiales += building_prod.get("materiales", 0)
        production.componentes += building_prod.get("componentes", 0)
        production.celulas_energia += building_prod.get("celulas_energia", 0)
        production.influencia += building_prod.get("influencia", 0)

    return production


# --- PROCESAMIENTO DE RECURSOS DE LUJO (Legacy mantenido) ---

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
        # 1. Obtener datos
        planets = get_all_player_planets_with_buildings(player_id)
        if not planets:
            return result

        finances = get_player_finances(player_id)
        luxury_sites = get_luxury_extraction_sites_for_player(player_id)

        # Preparar recursos disponibles para simulación de mantenimiento
        player_resources = {
            "creditos": finances.get("creditos", 0),
            "materiales": finances.get("materiales", 0),
            "componentes": finances.get("componentes", 0),
            "celulas_energia": finances.get("celulas_energia", 0),
            "influencia": finances.get("influencia", 0)
        }
        
        security_updates: List[Tuple[int, float]] = []
        building_status_updates: List[Tuple[int, bool]] = []
        
        # 2. Procesar cada planeta
        for planet in planets:
            # A. Seguridad
            pop = planet.get("poblacion", 0)
            infra_def = planet.get("infraestructura_defensiva", 0)
            security = calculate_planet_security(pop, infra_def)
            
            # Detectar cambio para update
            old_sec = planet.get("seguridad", 25.0)
            if abs(security - old_sec) > 0.1:
                security_updates.append((planet["id"], security))
            
            # B. Ingresos
            income = calculate_income(pop, security)
            result.total_income += income
            
            # C. Mantenimiento y Estado de Edificios
            buildings = planet.get("buildings", [])
            pops_avail = planet.get("pops_activos", pop) # Simplificación
            
            maint_res = process_building_maintenance(buildings, player_resources, pops_avail)
            
            # Registrar costos y deducir de 'player_resources' localmente para siguientes planetas
            for res, cost in maint_res.total_cost.items():
                result.maintenance_cost[res] = result.maintenance_cost.get(res, 0) + cost
                player_resources[res] -= cost # Deducir real-time para no gastar lo que no tienes
                
            # Registrar cambios de estado
            for bid, name in maint_res.buildings_to_disable:
                building_status_updates.append((bid, False))
                result.buildings_disabled.append(bid)
                log_event(f"⚠️ Edificio {name} detenido (Falta de recursos)", player_id)
                
            for bid, name in maint_res.buildings_to_enable:
                building_status_updates.append((bid, True))
                result.buildings_reactivated.append(bid)
                log_event(f"✅ Edificio {name} reactivado", player_id)
                
            # D. Producción (Solo pagados)
            prod = calculate_planet_production(maint_res.paid_buildings)
            result.production = result.production.add(prod)

        # 3. Recursos de Lujo
        luxury_extracted = calculate_luxury_extraction(luxury_sites)
        result.luxury_extracted = luxury_extracted

        # 4. Actualizar DB (Batch)
        if security_updates:
            batch_update_planet_security(security_updates)
        
        if building_status_updates:
            batch_update_building_status(building_status_updates)

        # 5. Calculo Final y Update Recursos Jugador
        # Neto = Recursos Originales + Ingresos + Producción - Mantenimiento
        # Como 'player_resources' ya tiene el mantenimiento descontado iterativamente:
        # Neto = player_resources + Ingresos + Producción
        
        final_resources = {
            "creditos": player_resources["creditos"] + result.total_income + result.production.creditos,
            "materiales": player_resources["materiales"] + result.production.materiales,
            "componentes": player_resources["componentes"] + result.production.componentes,
            "celulas_energia": player_resources["celulas_energia"] + result.production.celulas_energia,
            "influencia": player_resources["influencia"] + result.production.influencia
        }
        
        if luxury_extracted:
            current_luxury = finances.get("recursos_lujo", {})
            final_resources["recursos_lujo"] = merge_luxury_resources(current_luxury, luxury_extracted)

        update_player_resources(player_id, final_resources)
        result.success = True
        
        # Log Resumen
        log_event(
            f"💰 Eco Tick: +{result.total_income} Cr | Costos: {dict(result.maintenance_cost)}",
            player_id
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        log_event(f"Error economía jugador {player_id}: {e}", player_id, is_error=True)

    return result


def run_global_economy_tick() -> List[EconomyTickResult]:
    log_event("🏛️ Iniciando fase económica global (Seguridad V2)...")
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
    projection = {k: 0 for k in ["creditos", "materiales", "componentes", "celulas_energia", "influencia"]}
    
    try:
        # Simular con recursos infinitos para ver coste teórico total
        fake_resources = {k: 999999 for k in projection}
        
        planets = get_all_player_planets_with_buildings(player_id)
        
        for planet in planets:
            # Ingresos
            pop = planet.get("poblacion", 0)
            infra = planet.get("infraestructura_defensiva", 0)
            sec = calculate_planet_security(pop, infra)
            income = calculate_income(pop, sec)
            projection["creditos"] += income
            
            # Mantenimiento y Producción
            buildings = planet.get("buildings", [])
            # Asumimos que todos los activos siguen activos para la proyección
            active_buildings = [b for b in buildings if b.get("is_active", True)]
            
            prod = calculate_planet_production(active_buildings)
            
            # Costos
            for b in active_buildings:
                b_type = b.get("building_type")
                maint = BUILDING_TYPES.get(b_type, {}).get("maintenance", {})
                for res, cost in maint.items():
                    projection[res] -= cost
            
            # Sumar producción
            projection["materiales"] += prod.materiales
            projection["componentes"] += prod.componentes
            projection["celulas_energia"] += prod.celulas_energia
            projection["influencia"] += prod.influencia
            projection["creditos"] += prod.creditos

    except Exception:
        pass
        
    return projection