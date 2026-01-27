# core/economy_engine.py (Completo)
"""
Motor Económico MMFR (Materials, Metals, Fuel, Resources).
Gestiona toda la lógica de cálculo económico del juego.
Refactorizado V4.2: Modelo Logarítmico y Penalización Orbital.
Actualizado V4.4: Centralización de Seguridad y Transparencia (Breakdowns).
Corrección V5.6: Estandarización de Modelos usando 'core.rules.calculate_planet_security'.
Corrección V5.7: Estandarización de Fórmula Fiscal usando 'core.rules.calculate_fiscal_income'.
Corrección V5.8: Fix crítico de nomenclatura 'poblacion' a 'population'.
Actualizado V6.3: Implementación de Restricciones de Soberanía y Bloqueos.
Actualizado V6.4: Penalización por Bloqueo Orbital Enemigo en Producción Industrial.
Actualizado V8.0: Control del Sistema (Nivel Estelar) - Bonos de Sistema y Producción Estelar.
Actualizado V9.0: Logística de Transporte Automático (Unidades en Tránsito).
Refactorizado V20.0: Bloqueo total de ingresos en planetas DISPUTADOS.
Refactorizado V23.0: Soporte para Tiers de Edificios (1.1x) y Extracción de Lujo Automática en Tier 2.
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
import math

from data.database import get_supabase
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
# V9.0: Importar repositorio de unidades para coste logístico
from data.unit_repository import get_troops_in_transit_count

from core.world_constants import (
    BUILDING_TYPES,
    BUILDING_SHUTDOWN_PRIORITY,
    ECONOMY_RATES,
    DISPUTED_PENALTY_MULTIPLIER,
    SECTOR_TYPE_URBAN,
    SECTOR_TYPE_STELLAR
)
from core.models import ProductionSummary, EconomyTickResult
from core.market_engine import process_pending_market_orders
# Importamos la lógica centralizada (V5.6 + V5.7)
from core.rules import (
    calculate_and_update_system_security, 
    calculate_planet_security as rules_calculate_planet_security,
    calculate_fiscal_income
)


# --- FUNCIONES DE CÁLCULO ECONÓMICO (PURAS) ---

def calculate_planet_security(
    population: float,
    infrastructure_defense: int,
    orbital_distance: int 
) -> Tuple[float, Dict[str, Any]]:
    """
    Calcula el nivel de seguridad del planeta (0-100) y genera un desglose.
    Wrapper alrededor de core.rules.calculate_planet_security para mantener compatibilidad
    con la firma que retorna (float, dict) y generar el breakdown visual.
    
    Actualización Estandarización: Refleja Base 30 y Pop Mult 3.
    """
    if population <= 0:
        return 0.0, {"text": "Deshabitado (Población 0)", "total": 0.0}

    # Valores base para el desglose (ESTANDARIZADOS)
    # Deben coincidir con core.rules y core.world_constants
    base = 30.0 # Base fija estándar
    
    # Llamada a la lógica centralizada
    # Nota: rules_calculate_planet_security ignora el base_stat pasado, pero lo enviamos por consistencia
    final_val = rules_calculate_planet_security(
        base_stat=int(base),
        pop_count=population,
        infrastructure_defense=infrastructure_defense,
        orbital_ring=orbital_distance
    )
    
    # Reconstrucción del Breakdown para UI (Transparencia)
    per_pop = 3.0 # Nuevo multiplicador estandarizado
    pop_bonus = population * per_pop
    distance_penalty = 1.0 * orbital_distance # RING_PENALTY es 1
    
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
    Formula V4.2/V5.7: Delegado a core.rules.calculate_fiscal_income para asegurar
    que se usa el logaritmo de la población TOTAL (unidades), no billones.
    """
    rate = ECONOMY_RATES.get("income_per_pop", 150.0)
    
    # Delegación a Source of Truth (core.rules)
    # Esto asegura que log10(1 Billon) sea 9.0, no 0.0
    base_income = calculate_fiscal_income(rate, population, security)
    
    final_income = base_income * penalty_multiplier
    
    return max(0, int(final_income))


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


def calculate_planet_production(active_buildings: List[Dict[str, Any]], penalty_multiplier: float = 1.0) -> ProductionSummary:
    """
    Calcula producción SOLO de edificios activos y pagados.
    Actualizado v4.2.0: Aplica bono de +15% si está en sector Urbano.
    Actualizado V6.4: Aplica penalización por bloqueo (penalty_multiplier).
    Actualizado V23.0: Aplica bono de Tier 2 (1.1x).
    """
    production = ProductionSummary()

    for building in active_buildings:
        building_type = building.get("building_type")
        building_tier = building.get("building_tier", 1)
        
        definition = BUILDING_TYPES.get(building_type, {})
        base_prod = definition.get("production", {})
        
        # V4.2.0: Chequear bono de sector
        sector_type = building.get("sector_type")
        multiplier = 1.15 if sector_type == SECTOR_TYPE_URBAN else 1.0
        
        # V23.0: Chequear bono de Tier (10% extra si Tier >= 2)
        if building_tier >= 2:
            multiplier *= 1.1

        # V6.4: Penalización global por bloqueo
        multiplier *= penalty_multiplier

        production.materiales += int(base_prod.get("materiales", 0) * multiplier)
        production.componentes += int(base_prod.get("componentes", 0) * multiplier)
        production.celulas_energia += int(base_prod.get("celulas_energia", 0) * multiplier)
        production.influencia += int(base_prod.get("influencia", 0) * multiplier)
        production.datos += int(base_prod.get("datos", 0) * multiplier)

    return production


# --- V8.0: PROCESAMIENTO DE BONOS DE SISTEMA (ESTRUCTURAS ESTELARES) ---

@dataclass
class SystemBonuses:
    """V8.0: Contenedor de bonos aplicables a nivel de sistema."""
    fiscal_multiplier: float = 1.0        # Multiplicador de ingresos fiscales
    maintenance_multiplier: float = 1.0   # Multiplicador de costes de mantenimiento
    security_flat: float = 0.0            # Bono plano de seguridad a todos los planetas
    material_multiplier: float = 1.0      # Multiplicador de producción de materiales
    data_multiplier: float = 1.0          # Multiplicador de producción de datos
    mitigate_ring_penalty: bool = False   # Mitiga penalización por anillo orbital
    defense_bonus: int = 0                # Bono de defensa del sistema
    detection_range: int = 0              # Rango de detección adicional
    ftl_speed_bonus: float = 0.0          # Bono de velocidad FTL


def calculate_system_bonuses(stellar_buildings: List[Dict[str, Any]]) -> SystemBonuses:
    """
    V8.0: Calcula los bonos acumulados de las estructuras estelares activas.

    Args:
        stellar_buildings: Lista de edificios estelares activos (con is_active=True).

    Returns:
        SystemBonuses con todos los modificadores aplicables.
    """
    bonuses = SystemBonuses()

    for building in stellar_buildings:
        if not building.get("is_active", True):
            continue

        building_type = building.get("building_type", "")
        definition = BUILDING_TYPES.get(building_type, {})
        system_bonus = definition.get("system_bonus", {})

        # Acumular bonos multiplicativos (se multiplican entre sí)
        if "fiscal_multiplier" in system_bonus:
            bonuses.fiscal_multiplier *= system_bonus["fiscal_multiplier"]
        if "maintenance_multiplier" in system_bonus:
            bonuses.maintenance_multiplier *= system_bonus["maintenance_multiplier"]
        if "material_multiplier" in system_bonus:
            bonuses.material_multiplier *= system_bonus["material_multiplier"]
        if "data_multiplier" in system_bonus:
            bonuses.data_multiplier *= system_bonus["data_multiplier"]
        if "ftl_speed_bonus" in system_bonus:
            bonuses.ftl_speed_bonus += system_bonus["ftl_speed_bonus"]

        # Acumular bonos aditivos
        if "security_flat" in system_bonus:
            bonuses.security_flat += system_bonus["security_flat"]
        if "defense" in system_bonus:
            bonuses.defense_bonus += system_bonus["defense"]
        if "detection_range" in system_bonus:
            bonuses.detection_range += system_bonus["detection_range"]

        # Flags booleanos (OR)
        if system_bonus.get("mitigate_ring_penalty", False):
            bonuses.mitigate_ring_penalty = True

    return bonuses


def calculate_stellar_production(
    stellar_buildings: List[Dict[str, Any]],
    system_bonuses: SystemBonuses
) -> ProductionSummary:
    """
    V8.0: Calcula la producción directa de las estructuras estelares.

    Args:
        stellar_buildings: Lista de edificios estelares activos.
        system_bonuses: Bonos calculados del sistema (para aplicar multiplicadores).

    Returns:
        ProductionSummary con los recursos producidos.
    """
    production = ProductionSummary()

    for building in stellar_buildings:
        if not building.get("is_active", True):
            continue

        building_type = building.get("building_type", "")
        definition = BUILDING_TYPES.get(building_type, {})
        base_prod = definition.get("production", {})

        # Aplicar producción base con multiplicadores del sistema
        production.materiales += int(
            base_prod.get("materiales", 0) * system_bonuses.material_multiplier
        )
        production.componentes += int(base_prod.get("componentes", 0))
        production.celulas_energia += int(base_prod.get("celulas_energia", 0))
        production.influencia += int(base_prod.get("influencia", 0))
        production.datos += int(
            base_prod.get("datos", 0) * system_bonuses.data_multiplier
        )

    return production


def process_stellar_building_maintenance(
    stellar_buildings: List[Dict[str, Any]],
    available_resources: Dict[str, int],
    maintenance_multiplier: float = 1.0
) -> MaintenanceResult:
    """
    V8.0: Procesa el mantenimiento de edificios estelares.
    Similar a process_building_maintenance pero para estructuras estelares.

    Args:
        stellar_buildings: Lista de edificios estelares.
        available_resources: Recursos disponibles del jugador.
        maintenance_multiplier: Multiplicador de coste (ej: 0.9 si hay logistics_hub).

    Returns:
        MaintenanceResult con edificios pagados y costes.
    """
    result = MaintenanceResult()
    current_resources = available_resources.copy()

    def get_priority(b: Dict) -> int:
        b_type = b.get("building_type", "")
        cat = BUILDING_TYPES.get(b_type, {}).get("category", "otros")
        return BUILDING_SHUTDOWN_PRIORITY.get(cat, 99)

    sorted_buildings = sorted(stellar_buildings, key=get_priority)

    for b in sorted_buildings:
        b_id = b["id"]
        b_type = b.get("building_type", "")
        b_def = BUILDING_TYPES.get(b_type, {})
        b_name = b_def.get("name", b_type)

        maintenance = b_def.get("maintenance", {})

        can_afford = True
        adjusted_costs = {}
        for res, cost in maintenance.items():
            adjusted_cost = int(cost * maintenance_multiplier)
            adjusted_costs[res] = adjusted_cost
            if current_resources.get(res, 0) < adjusted_cost:
                can_afford = False
                break

        is_active_db = b.get("is_active", True)

        if can_afford:
            for res, cost in adjusted_costs.items():
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


# --- PROCESAMIENTO DE RECURSOS DE LUJO ---

def calculate_luxury_extraction(sites: List[Dict[str, Any]]) -> Dict[str, int]:
    """Calcula extracción base de sitios dedicados."""
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


# --- V8.0: FUNCIONES DE ACCESO A EDIFICIOS ESTELARES ---

def get_stellar_buildings_for_system(system_id: int, player_id: int) -> List[Dict[str, Any]]:
    """
    V8.0: Obtiene los edificios estelares de un sistema controlados por un jugador.
    """
    try:
        from data.world_repository import get_stellar_buildings_by_system
        return get_stellar_buildings_by_system(system_id, player_id)
    except ImportError:
        # El repositorio aún no tiene esta función implementada
        return []
    except Exception:
        return []


# --- ORQUESTADOR PRINCIPAL ---

def run_economy_tick_for_player(player_id: int) -> EconomyTickResult:
    """
    Ejecuta el ciclo económico completo para un jugador.
    Actualizado V8.0: Soporte para bonos de sistema y estructuras estelares.
    Actualizado V9.0: Soporte para Logística de Transporte (Unidades en tránsito).
    Refactor V20.0: Bloqueo de ingresos en estados disputados.
    Refactor V23.0: Extracción de lujo por edificios Tier 2.
    """
    result = EconomyTickResult(player_id=player_id)
    db = get_supabase()

    try:
        try:
            process_pending_market_orders(player_id)
        except Exception as e:
            log_event(f"Error procesando mercado en tick: {e}", player_id, is_error=True)

        planets = get_all_player_planets_with_buildings(player_id)
        # Nota: Incluso si no hay planetas, puede haber unidades en tránsito o edificios estelares.
        # Continuamos la ejecución aunque 'planets' esté vacío, pero necesitamos cargar finanzas.
        
        finances = get_player_finances(player_id)
        if not finances:
             # Si no hay finanzas, no hay jugador válido (edge case)
             return result

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

        # --- V8.0: FASE 1 - Agrupar planetas por sistema y calcular bonos estelares ---
        systems_planets: Dict[int, List[Dict]] = {}
        all_active_tier_2_sectors = [] # Para recursos de lujo V23.0

        # Obtener lista de IDs de sistema únicos (planetas + assets conocidos)
        for planet in planets:
            sys_id = planet.get("system_id")
            if sys_id not in systems_planets:
                systems_planets[sys_id] = []
            systems_planets[sys_id].append(planet)

        # Cache de bonos por sistema (evita recalcular para cada planeta)
        system_bonuses_cache: Dict[int, SystemBonuses] = {}
        stellar_production_total = ProductionSummary()

        # --- V8.0: FASE 2 - Procesar estructuras estelares por sistema ---
        for sys_id in systems_planets.keys():
            # Obtener edificios estelares del jugador en este sistema
            stellar_buildings = get_stellar_buildings_for_system(sys_id, player_id)

            if stellar_buildings:
                # Calcular bonos del sistema
                system_bonuses = calculate_system_bonuses(stellar_buildings)
                system_bonuses_cache[sys_id] = system_bonuses

                # Procesar mantenimiento de edificios estelares
                stellar_maint = process_stellar_building_maintenance(
                    stellar_buildings,
                    player_resources,
                    maintenance_multiplier=system_bonuses.maintenance_multiplier
                )

                # Registrar costes de mantenimiento estelar
                for res, cost in stellar_maint.total_cost.items():
                    result.maintenance_cost[res] = result.maintenance_cost.get(res, 0) + cost
                    player_resources[res] -= cost

                # Registrar edificios desactivados/reactivados
                for bid, name in stellar_maint.buildings_to_disable:
                    building_status_updates.append((bid, False))
                    result.buildings_disabled.append(bid)
                    log_event(f"⚠️ Estructura estelar {name} detenida (Falta de recursos)", player_id)

                for bid, name in stellar_maint.buildings_to_enable:
                    building_status_updates.append((bid, True))
                    result.buildings_reactivated.append(bid)

                # Calcular producción de estructuras estelares
                stellar_prod = calculate_stellar_production(
                    stellar_maint.paid_buildings,
                    system_bonuses
                )
                stellar_production_total = stellar_production_total.add(stellar_prod)
            else:
                # Sin estructuras estelares, bonos por defecto
                system_bonuses_cache[sys_id] = SystemBonuses()

        # --- V8.0: FASE 3 - Procesar cada planeta con bonos de sistema aplicados ---
        for planet in planets:
            sys_id = planet.get("system_id")
            system_bonuses = system_bonuses_cache.get(sys_id, SystemBonuses())

            # A. Seguridad (V4.4: Centralizada en tabla planets con Breakdown)
            pop = float(planet.get("population", 0.0))
            infra_def = planet.get("infraestructura_defensiva", 0)

            orbital_dist = planet.get("orbital_distance", 0)
            if orbital_dist == 0 and "ring_index" in planet:
                orbital_dist = planet["ring_index"]

            # CALCULO PRINCIPAL DE SEGURIDAD
            security, security_breakdown = calculate_planet_security(pop, infra_def, orbital_dist)

            # V8.0: Aplicar bono de seguridad plano de surveillance_network
            security += system_bonuses.security_flat
            security = min(100.0, security)  # Cap a 100
            if system_bonuses.security_flat > 0:
                security_breakdown["stellar_bonus"] = system_bonuses.security_flat
                security_breakdown["total"] = round(security, 2)
                security_breakdown["text"] += f" + Estelar ({system_bonuses.security_flat:.1f})"

            # Persistencia V4.4: Guardar en tabla PLANETS (Source of Truth)
            update_planet_security_data(planet["planet_id"], security, security_breakdown)

            # Sincronizar hacia planet_assets para compatibilidad UI legacy temporal
            if abs(security - planet.get("seguridad", 0)) > 0.1:
                update_planet_asset(planet["id"], {"seguridad": security})

            systems_to_update_security.add(planet["system_id"])

            # B. Estado de Disputa / Bloqueo y Soberanía (V6.3/V6.4)
            orbital_owner = planet.get("orbital_owner_id")
            surface_owner = planet.get("surface_owner_id")
            is_disputed = planet.get("is_disputed", False)

            penalty = 1.0
            is_blockaded = False

            # Regla de Soberanía V6.3:
            # Si no soy el surface owner, mis ingresos y producción son 0.
            is_sovereign = (surface_owner == player_id)

            # Regla de Bloqueo Orbital (V6.4):
            # Si hay un dueño orbital diferente al dueño de superficie (yo) -> Bloqueo
            if orbital_owner is not None and orbital_owner != player_id:
                is_blockaded = True
            
            # --- REFACTOR V20.0: Bloqueo Total en Disputa ---
            if is_disputed:
                penalty = 0.0 # Ingreso CERO si está disputado
            elif is_blockaded:
                penalty = DISPUTED_PENALTY_MULTIPLIER # Penalización parcial si solo bloqueo orbital

            # Si no soy soberano, penalización total (0 ingresos)
            if not is_sovereign:
                penalty = 0.0

            # C. Ingresos
            # V8.0: Aplicar multiplicador fiscal de trade_beacon
            fiscal_multiplier = system_bonuses.fiscal_multiplier * penalty
            income = calculate_income(pop, security, penalty_multiplier=fiscal_multiplier)
            result.total_income += income

            # D. Mantenimiento
            buildings = planet.get("buildings", [])
            pops_avail = float(planet.get("pops_activos", pop))

            # V8.0: Aplicar reducción de mantenimiento de logistics_hub
            maint_res = process_building_maintenance(buildings, player_resources, pops_avail)

            # V8.0: Aplicar multiplicador de mantenimiento del sistema
            for res, cost in maint_res.total_cost.items():
                adjusted_cost = int(cost * system_bonuses.maintenance_multiplier)
                result.maintenance_cost[res] = result.maintenance_cost.get(res, 0) + adjusted_cost
                player_resources[res] -= adjusted_cost

            for bid, name in maint_res.buildings_to_disable:
                building_status_updates.append((bid, False))
                result.buildings_disabled.append(bid)
                log_event(f"⚠️ Edificio {name} detenido (Falta de recursos)", player_id)

            for bid, name in maint_res.buildings_to_enable:
                building_status_updates.append((bid, True))
                result.buildings_reactivated.append(bid)

            # E. Producción
            if is_sovereign:
                # V6.4: Aplicar penalización de bloqueo a producción también
                prod = calculate_planet_production(maint_res.paid_buildings, penalty_multiplier=penalty)

                # V8.0: Aplicar multiplicadores de material_multiplier y data_multiplier
                prod.materiales = int(prod.materiales * system_bonuses.material_multiplier)
                prod.datos = int(prod.datos * system_bonuses.data_multiplier)

                result.production = result.production.add(prod)

                # V23.0: Recolectar IDs de sector de edificios Tier 2 pagados para extracción de lujo
                for pb in maint_res.paid_buildings:
                    if pb.get("building_tier", 1) >= 2 and pb.get("sector_id"):
                         all_active_tier_2_sectors.append(pb["sector_id"])

        # V8.0: Añadir producción estelar al total
        result.production = result.production.add(stellar_production_total)

        # 3. Recursos de Lujo (Legacy + Tier 2 V23.0)
        luxury_extracted = calculate_luxury_extraction(luxury_sites)
        
        # V23.0: Procesar Extracción de Lujo de Edificios Tier 2
        if all_active_tier_2_sectors:
            try:
                # Fetch en lote de recursos de lujo de los sectores relevantes
                sectors_res = db.table("sectors")\
                    .select("id, luxury_resource, luxury_category")\
                    .in_("id", all_active_tier_2_sectors)\
                    .not_.is_("luxury_resource", "null")\
                    .execute()
                
                if sectors_res.data:
                    for s in sectors_res.data:
                        cat = s.get("luxury_category")
                        res_name = s.get("luxury_resource")
                        if cat and res_name:
                            key = f"{cat}.{res_name}"
                            luxury_extracted[key] = luxury_extracted.get(key, 0) + 1
            except Exception as e:
                log_event(f"Error procesando extracción de lujo Tier 2: {e}", player_id, is_error=True)

        result.luxury_extracted = luxury_extracted

        # --- V9.0: COSTO LOGÍSTICA DE TRANSPORTE (Unidades en Tránsito) ---
        troops_in_transit = get_troops_in_transit_count(player_id)
        transit_cost = troops_in_transit * 5  # Costo fijo por tropa en espacio
        
        if transit_cost > 0:
            if player_resources["creditos"] >= transit_cost:
                player_resources["creditos"] -= transit_cost
                result.maintenance_cost["creditos"] = result.maintenance_cost.get("creditos", 0) + transit_cost
                log_event(f"🚀 Logística de Flota: -{transit_cost} Cr ({troops_in_transit} tropas en tránsito).", player_id)
            else:
                paid = player_resources["creditos"]
                player_resources["creditos"] = 0
                result.maintenance_cost["creditos"] = result.maintenance_cost.get("creditos", 0) + paid
                log_event(f"⚠️ FALLO LOGÍSTICO: Fondos insuficientes para transporte de tropas.", player_id, is_error=True)

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
    """
    Calcula proyección (Delta) para UI sin modificar DB.
    Actualizado V8.0: Incluye bonos de sistema y producción estelar.
    Actualizado V9.0: Incluye costo de logística de transporte proyectado.
    """
    projection = {k: 0 for k in ["creditos", "materiales", "componentes", "celulas_energia", "influencia", "datos"]}

    try:
        planets = get_all_player_planets_with_buildings(player_id)

        # V8.0: Agrupar por sistema y pre-calcular bonos
        systems_planets: Dict[int, List[Dict]] = {}
        for planet in planets:
            sys_id = planet.get("system_id")
            if sys_id not in systems_planets:
                systems_planets[sys_id] = []
            systems_planets[sys_id].append(planet)

        # Cache de bonos por sistema
        system_bonuses_cache: Dict[int, SystemBonuses] = {}

        for sys_id in systems_planets.keys():
            stellar_buildings = get_stellar_buildings_for_system(sys_id, player_id)
            if stellar_buildings:
                system_bonuses = calculate_system_bonuses(stellar_buildings)
                system_bonuses_cache[sys_id] = system_bonuses

                # V8.0: Proyectar producción estelar
                active_stellar = [b for b in stellar_buildings if b.get("is_active", True)]
                stellar_prod = calculate_stellar_production(active_stellar, system_bonuses)
                projection["materiales"] += stellar_prod.materiales
                projection["celulas_energia"] += stellar_prod.celulas_energia
                projection["datos"] += stellar_prod.datos
                projection["componentes"] += stellar_prod.componentes
                projection["influencia"] += stellar_prod.influencia

                # V8.0: Proyectar mantenimiento estelar
                for b in active_stellar:
                    b_type = b.get("building_type")
                    maint = BUILDING_TYPES.get(b_type, {}).get("maintenance", {})
                    for res, cost in maint.items():
                        adjusted_cost = int(cost * system_bonuses.maintenance_multiplier)
                        projection[res] -= adjusted_cost
            else:
                system_bonuses_cache[sys_id] = SystemBonuses()

        for planet in planets:
            sys_id = planet.get("system_id")
            system_bonuses = system_bonuses_cache.get(sys_id, SystemBonuses())

            # Control Logic para proyección
            orbital_owner = planet.get("orbital_owner_id")
            surface_owner = planet.get("surface_owner_id")
            is_disputed = planet.get("is_disputed", False)

            penalty = 1.0
            is_blockaded = False

            is_sovereign = (surface_owner == player_id)

            if orbital_owner is not None and orbital_owner != player_id:
                is_blockaded = True

            # Refactor V20.0
            if is_disputed:
                penalty = 0.0
            elif is_blockaded:
                penalty = DISPUTED_PENALTY_MULTIPLIER

            if not is_sovereign:
                penalty = 0.0

            pop = float(planet.get("population", 0.0))
            infra = planet.get("infraestructura_defensiva", 0)

            orbital_dist = planet.get("orbital_distance", 0)
            if orbital_dist == 0 and "ring_index" in planet:
                orbital_dist = planet["ring_index"]

            # Unpack tuple V4.4
            sec, _ = calculate_planet_security(pop, infra, orbital_dist)

            # V8.0: Aplicar bono de seguridad estelar
            sec += system_bonuses.security_flat
            sec = min(100.0, sec)

            # Ingresos proyectados con penalización
            fiscal_multiplier = system_bonuses.fiscal_multiplier * penalty
            income = calculate_income(pop, sec, penalty_multiplier=fiscal_multiplier)
            projection["creditos"] += income

            buildings = planet.get("buildings", [])
            active_buildings = [b for b in buildings if b.get("is_active", True)]

            # Solo sumar producción si es soberano
            if is_sovereign:
                prod = calculate_planet_production(active_buildings, penalty_multiplier=penalty)
                projection["materiales"] += int(prod.materiales * system_bonuses.material_multiplier)
                projection["componentes"] += prod.componentes
                projection["celulas_energia"] += prod.celulas_energia
                projection["influencia"] += prod.influencia
                projection["datos"] += int(prod.datos * system_bonuses.data_multiplier)
                projection["creditos"] += prod.creditos

            # Mantenimiento siempre se resta (Costo operativo)
            for b in active_buildings:
                b_type = b.get("building_type")
                maint = BUILDING_TYPES.get(b_type, {}).get("maintenance", {})
                for res, cost in maint.items():
                    adjusted_cost = int(cost * system_bonuses.maintenance_multiplier)
                    projection[res] -= adjusted_cost

        # V9.0: Proyectar costo logístico de transporte
        troops_in_transit = get_troops_in_transit_count(player_id)
        transit_cost = troops_in_transit * 5
        projection["creditos"] -= transit_cost

    except Exception:
        pass

    return projection