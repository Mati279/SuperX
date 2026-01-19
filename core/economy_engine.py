# core/economy_engine.py
"""
Motor Económico MMFR (Materials, Metals, Fuel, Resources).
Gestiona toda la lógica de cálculo económico del juego.

IMPORTANTE: Este módulo NO importa supabase directamente.
Todas las operaciones de DB se realizan a través de repositorios.
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field

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
    ECONOMY_RATES,
    BROKER_PRICES
)
from core.models import ProductionSummary, EconomyTickResult


# --- FUNCIONES DE CÁLCULO ECONÓMICO (PURAS - SIN SIDE EFFECTS) ---

def calculate_security_multiplier(infrastructure_defense: int) -> float:
    """
    Calcula el multiplicador de seguridad basado en infraestructura defensiva.

    Args:
        infrastructure_defense: Puntos de defensa del planeta (0-100+)

    Returns:
        Multiplicador entre security_min y security_max
    """
    rate = ECONOMY_RATES["infrastructure_security_rate"]
    min_sec = ECONOMY_RATES["security_min"]
    max_sec = ECONOMY_RATES["security_max"]

    # Cada punto de infraestructura = +1% seguridad
    security = min_sec + (infrastructure_defense * rate)

    # Clamped entre mínimo y máximo
    return max(min_sec, min(security, max_sec))


def calculate_income(
    population: int,
    security: float,
    happiness: float = 1.0
) -> int:
    """
    Calcula el ingreso de créditos de un planeta.

    Formula: Ingreso = (Población * Tasa_Base) * Seguridad * (1 + Bonus_Felicidad)

    Args:
        population: Población total del planeta
        security: Multiplicador de seguridad (0.0 - 1.2)
        happiness: Multiplicador de felicidad (0.5 - 1.5)

    Returns:
        Créditos generados este turno
    """
    base_rate = ECONOMY_RATES["income_per_pop"]
    max_happiness_bonus = ECONOMY_RATES["happiness_bonus_max"]

    # Calcular bonus de felicidad (solo si happiness > 1.0)
    happiness_bonus = 0.0
    if happiness > 1.0:
        # Felicidad de 1.5 da +50% de ingresos
        happiness_bonus = ((happiness - 1.0) / 0.5) * max_happiness_bonus

    # Fórmula completa
    income = (population * base_rate) * security * (1.0 + happiness_bonus)

    return int(income)


def calculate_building_maintenance(buildings: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calcula el consumo total de energía de todos los edificios activos.

    Args:
        buildings: Lista de edificios del planeta

    Returns:
        Diccionario con totales: {"celulas_energia": X}
    """
    total_energy = 0

    for building in buildings:
        if building.get("is_active", True):
            building_type = building.get("building_type")
            definition = BUILDING_TYPES.get(building_type, {})
            energy_cost = definition.get("energy_cost", 0)
            total_energy += energy_cost

    return {"celulas_energia": total_energy}


def calculate_planet_production(buildings: List[Dict[str, Any]]) -> ProductionSummary:
    """
    Calcula la producción total de un planeta basándose en sus edificios activos.

    Args:
        buildings: Lista de edificios del planeta

    Returns:
        ProductionSummary con recursos producidos
    """
    production = ProductionSummary()

    for building in buildings:
        if not building.get("is_active", True):
            continue

        building_type = building.get("building_type")
        definition = BUILDING_TYPES.get(building_type, {})
        building_production = definition.get("production", {})

        production.materiales += building_production.get("materiales", 0)
        production.componentes += building_production.get("componentes", 0)
        production.celulas_energia += building_production.get("celulas_energia", 0)
        production.influencia += building_production.get("influencia", 0)

    return production


# --- SISTEMA DE DESACTIVACIÓN EN CASCADA ---

@dataclass
class CascadeResult:
    """Resultado del sistema de desactivación en cascada."""
    buildings_to_disable: List[Tuple[int, str]] = field(default_factory=list)  # (id, nombre)
    buildings_to_enable: List[Tuple[int, str]] = field(default_factory=list)   # (id, nombre)
    remaining_pops: int = 0


def calculate_cascade_shutdown(
    available_pops: int,
    buildings: List[Dict[str, Any]]
) -> CascadeResult:
    """
    Calcula qué edificios deben desactivarse/reactivarse basándose en POPs disponibles.
    Esta función es PURA - no realiza cambios en DB.

    Orden de desactivación (prioridad inversa):
    1. Alta Tecnología
    2. Industria Pesada
    3. Defensa
    4. Extracción Base (crítico, se desactiva al final)

    Args:
        available_pops: Población disponible para asignar
        buildings: Lista de edificios del planeta

    Returns:
        CascadeResult con listas de edificios a activar/desactivar
    """
    result = CascadeResult()

    # Separar edificios activos e inactivos
    active_buildings = [b for b in buildings if b.get("is_active", True)]
    inactive_buildings = [b for b in buildings if not b.get("is_active", True)]

    # Calcular requisitos totales de edificios activos
    total_required = sum(
        b.get("pops_required", 0)
        for b in active_buildings
    )

    # Si hay suficiente población, intentar reactivar edificios
    if available_pops >= total_required:
        remaining = available_pops - total_required
        result.remaining_pops = remaining

        # Intentar reactivar edificios (ordenados por prioridad inversa: extracción primero)
        def get_reactivation_priority(building: Dict[str, Any]) -> int:
            building_type = building.get("building_type", "")
            definition = BUILDING_TYPES.get(building_type, {})
            category = definition.get("category", "extraccion")
            return -BUILDING_SHUTDOWN_PRIORITY.get(category, 999)

        sorted_inactive = sorted(inactive_buildings, key=get_reactivation_priority)

        for building in sorted_inactive:
            pops_needed = building.get("pops_required", 0)
            if remaining >= pops_needed:
                building_name = BUILDING_TYPES.get(
                    building.get("building_type", ""), {}
                ).get("name", "Edificio Desconocido")
                result.buildings_to_enable.append((building["id"], building_name))
                remaining -= pops_needed

        result.remaining_pops = remaining
        return result

    # Si no hay suficiente población, desactivar edificios
    def get_shutdown_priority(building: Dict[str, Any]) -> int:
        building_type = building.get("building_type", "")
        definition = BUILDING_TYPES.get(building_type, {})
        category = definition.get("category", "extraccion")
        return BUILDING_SHUTDOWN_PRIORITY.get(category, 999)

    sorted_active = sorted(active_buildings, key=get_shutdown_priority)

    remaining_pops = available_pops

    for building in sorted_active:
        if remaining_pops >= total_required:
            break

        building_id = building["id"]
        pops_freed = building.get("pops_required", 0)

        building_name = BUILDING_TYPES.get(
            building.get("building_type", ""), {}
        ).get("name", "Edificio Desconocido")

        result.buildings_to_disable.append((building_id, building_name))
        remaining_pops += pops_freed
        total_required -= pops_freed

    result.remaining_pops = max(0, remaining_pops - total_required)
    return result


# --- PROCESAMIENTO DE RECURSOS DE LUJO ---

def calculate_luxury_extraction(sites: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Calcula la extracción de recursos de lujo.
    Esta función es PURA - no realiza cambios en DB.

    Args:
        sites: Lista de sitios de extracción activos

    Returns:
        Diccionario con claves "categoria.recurso" y cantidades
    """
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


def merge_luxury_resources(
    current: Dict[str, Any],
    extracted: Dict[str, int]
) -> Dict[str, Any]:
    """
    Combina recursos de lujo actuales con los recién extraídos.

    Args:
        current: JSONB actual de recursos_lujo
        extracted: Nuevos recursos extraídos

    Returns:
        Diccionario actualizado de recursos de lujo
    """
    result = dict(current) if current else {}

    for key, amount in extracted.items():
        parts = key.split(".")
        if len(parts) != 2:
            continue

        category, resource = parts

        if category not in result:
            result[category] = {}

        result[category][resource] = result[category].get(resource, 0) + amount

    return result


# --- PROCESADOR DE PLANETA (INDIVIDUAL) ---

@dataclass
class PlanetTickResult:
    """Resultado del procesamiento de un planeta."""
    planet_id: int
    income: int = 0
    production: ProductionSummary = field(default_factory=ProductionSummary)
    security_update: Optional[Tuple[int, float]] = None
    buildings_disabled: List[Tuple[int, str]] = field(default_factory=list)
    buildings_enabled: List[Tuple[int, str]] = field(default_factory=list)
    maintenance_paid: bool = True


def process_planet_tick(
    planet: Dict[str, Any],
    player_energy: int
) -> PlanetTickResult:
    """
    Procesa el tick económico de un planeta individual.
    Esta función es mayormente PURA - calcula pero no persiste.

    Args:
        planet: Datos del planeta con edificios precargados
        player_energy: Energía disponible del jugador

    Returns:
        PlanetTickResult con todos los cálculos
    """
    result = PlanetTickResult(planet_id=planet["id"])

    # Datos del planeta
    population = planet.get("poblacion", 0)
    infrastructure = planet.get("infraestructura_defensiva", 0)
    happiness = planet.get("felicidad", 1.0)
    buildings = planet.get("buildings", [])

    # 1. Calcular seguridad
    security = calculate_security_multiplier(infrastructure)
    if security != planet.get("seguridad", 1.0):
        result.security_update = (planet["id"], security)

    # 2. Calcular ingresos
    result.income = calculate_income(population, security, happiness)

    # 3. Gestión de POPs
    pops_activos = planet.get("pops_activos", population)
    pops_desempleados = planet.get("pops_desempleados", 0)
    available_pops = pops_activos + pops_desempleados

    cascade = calculate_cascade_shutdown(available_pops, buildings)
    result.buildings_disabled = cascade.buildings_to_disable
    result.buildings_enabled = cascade.buildings_to_enable

    # 4. Recalcular edificios activos después del cascade
    active_building_ids = {b["id"] for b in buildings if b.get("is_active", True)}

    # Remover los que se desactivarán
    for bid, _ in cascade.buildings_to_disable:
        active_building_ids.discard(bid)

    # Agregar los que se reactivarán
    for bid, _ in cascade.buildings_to_enable:
        active_building_ids.add(bid)

    # Filtrar edificios activos finales
    final_active_buildings = [b for b in buildings if b["id"] in active_building_ids]

    # 5. Calcular producción
    result.production = calculate_planet_production(final_active_buildings)

    # 6. Calcular mantenimiento
    maintenance = calculate_building_maintenance(final_active_buildings)
    energy_cost = maintenance.get("celulas_energia", 0)

    if energy_cost > player_energy:
        result.maintenance_paid = False

    return result


# --- ORQUESTADOR PRINCIPAL ---

def run_economy_tick_for_player(player_id: int) -> EconomyTickResult:
    """
    Ejecuta el ciclo económico completo para un jugador.
    Optimizado para reducir queries a la DB.

    Orden de ejecución:
    1. Obtener todos los datos necesarios en queries batch
    2. Calcular todos los cambios (funciones puras)
    3. Aplicar cambios en batch

    Args:
        player_id: ID del jugador

    Returns:
        EconomyTickResult con el resumen de la operación
    """
    result = EconomyTickResult(player_id=player_id)

    try:
        # 1. Obtener datos en batch
        planets = get_all_player_planets_with_buildings(player_id)

        if not planets:
            return result  # Jugador sin planetas

        finances = get_player_finances(player_id)
        luxury_sites = get_luxury_extraction_sites_for_player(player_id)

        # 2. Procesar cada planeta
        security_updates: List[Tuple[int, float]] = []
        building_status_updates: List[Tuple[int, bool]] = []
        total_energy_available = finances.get("celulas_energia", 0)

        for planet in planets:
            planet_result = process_planet_tick(planet, total_energy_available)

            # Acumular resultados
            result.total_income += planet_result.income
            result.production = result.production.add(planet_result.production)

            # Recolectar actualizaciones
            if planet_result.security_update:
                security_updates.append(planet_result.security_update)

            for bid, name in planet_result.buildings_disabled:
                building_status_updates.append((bid, False))
                result.buildings_disabled.append(bid)
                log_event(f"⚠️ Edificio desactivado por falta de POPs: {name}", player_id)

            for bid, name in planet_result.buildings_enabled:
                building_status_updates.append((bid, True))
                result.buildings_reactivated.append(bid)
                log_event(f"✅ Edificio reactivado: {name}", player_id)

        # 3. Calcular recursos de lujo
        luxury_extracted = calculate_luxury_extraction(luxury_sites)
        result.luxury_extracted = luxury_extracted

        # 4. Aplicar cambios en batch
        if security_updates:
            batch_update_planet_security(security_updates)

        if building_status_updates:
            batch_update_building_status(building_status_updates)

        # 5. Actualizar recursos del jugador
        new_resources = {
            "creditos": finances.get("creditos", 0) + result.total_income,
            "materiales": finances.get("materiales", 0) + result.production.materiales,
            "componentes": finances.get("componentes", 0) + result.production.componentes,
            "celulas_energia": finances.get("celulas_energia", 0) + result.production.celulas_energia,
            "influencia": finances.get("influencia", 0) + result.production.influencia
        }

        # Actualizar recursos de lujo si hay extracción
        if luxury_extracted:
            current_luxury = finances.get("recursos_lujo", {})
            new_resources["recursos_lujo"] = merge_luxury_resources(current_luxury, luxury_extracted)

        update_player_resources(player_id, new_resources)

        # 6. Log resumen
        log_event(
            f"💰 Economía procesada: +{result.total_income} CI | "
            f"Producción: M:{result.production.materiales} "
            f"C:{result.production.componentes} "
            f"E:{result.production.celulas_energia} "
            f"I:{result.production.influencia}",
            player_id
        )

        if luxury_extracted:
            luxury_summary = ", ".join([f"{k}:{v}" for k, v in luxury_extracted.items()])
            log_event(f"💎 Recursos de lujo extraídos: {luxury_summary}", player_id)

        result.success = True

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        log_event(f"Error crítico en economía del jugador {player_id}: {e}", player_id, is_error=True)

    return result


def run_global_economy_tick() -> List[EconomyTickResult]:
    """
    Ejecuta el tick económico para TODOS los jugadores activos.
    Se llama desde time_engine._phase_macroeconomics()

    Returns:
        Lista de resultados por jugador
    """
    log_event("🏛️ Iniciando fase económica global (MMFR)...")

    results: List[EconomyTickResult] = []

    try:
        # Obtener todos los jugadores
        players = get_all_players()

        for player in players:
            player_id = player["id"]
            result = run_economy_tick_for_player(player_id)
            results.append(result)

        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        log_event(f"✅ Fase económica completada. Jugadores: {successful} OK, {failed} errores.")

    except Exception as e:
        log_event(f"Error crítico en tick económico global: {e}", is_error=True)

    return results


# --- FUNCIONES AUXILIARES PARA UI ---

def get_planet_economy_summary(planet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Genera un resumen económico de un planeta para mostrar en UI.

    Args:
        planet: Datos del planeta con edificios

    Returns:
        Diccionario con resumen para UI
    """
    buildings = planet.get("buildings", [])
    population = planet.get("poblacion", 0)
    infrastructure = planet.get("infraestructura_defensiva", 0)
    happiness = planet.get("felicidad", 1.0)

    security = calculate_security_multiplier(infrastructure)
    income = calculate_income(population, security, happiness)
    production = calculate_planet_production(buildings)
    maintenance = calculate_building_maintenance(buildings)

    active_buildings = sum(1 for b in buildings if b.get("is_active", True))
    total_buildings = len(buildings)

    return {
        "income": income,
        "security": security,
        "production": production.to_dict(),
        "maintenance": maintenance,
        "active_buildings": active_buildings,
        "total_buildings": total_buildings,
        "population": population,
        "happiness": happiness
    }


def get_player_projected_economy(player_id: int) -> Dict[str, int]:
    """
    Calcula la proyección de ingresos y gastos del próximo turno (Delta).
    Esta función es Read-Only y se usa para el HUD.

    Args:
        player_id: ID del jugador

    Returns:
        Diccionario con deltas: {creditos, materiales, componentes, celulas_energia, influencia}
    """
    projection = {
        "creditos": 0,
        "materiales": 0,
        "componentes": 0,
        "celulas_energia": 0,
        "influencia": 0
    }

    try:
        planets = get_all_player_planets_with_buildings(player_id)
        
        for planet in planets:
            # 1. Seguridad
            infrastructure = planet.get("infraestructura_defensiva", 0)
            security = calculate_security_multiplier(infrastructure)
            
            # 2. Ingresos (Créditos)
            pop = planet.get("poblacion", 0)
            happiness = planet.get("felicidad", 1.0)
            income = calculate_income(pop, security, happiness)
            projection["creditos"] += income

            # 3. Producción y Mantenimiento
            buildings = planet.get("buildings", [])
            # Usamos los edificios tal como están en DB (is_active)
            prod_summary = calculate_planet_production(buildings)
            maintenance = calculate_building_maintenance(buildings)

            projection["materiales"] += prod_summary.materiales
            projection["componentes"] += prod_summary.componentes
            projection["influencia"] += prod_summary.influencia
            
            # Energía = Producción - Consumo
            energy_produced = prod_summary.celulas_energia
            energy_consumed = maintenance.get("celulas_energia", 0)
            projection["celulas_energia"] += (energy_produced - energy_consumed)

    except Exception as e:
        # En caso de error, logueamos pero retornamos 0s para no romper el HUD
        log_event(f"Error en proyección económica HUD: {e}", player_id, is_error=True)

    return projection