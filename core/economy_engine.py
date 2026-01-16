# core/economy_engine.py
from typing import Dict, List, Any, Tuple
from data.database import supabase
from data.log_repository import log_event
from data.player_repository import get_player_finances, update_player_resources
from core.world_constants import (
    BUILDING_TYPES,
    BUILDING_SHUTDOWN_PRIORITY,
    ECONOMY_RATES,
    BROKER_PRICES
)


# --- FUNCIONES DE CÁLCULO ECONÓMICO ---

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


# --- SISTEMA DE DESACTIVACIÓN EN CASCADA ---

def cascade_shutdown_buildings(
    planet_asset_id: int,
    available_pops: int,
    buildings: List[Dict[str, Any]]
) -> Tuple[List[int], int]:
    """
    Desactiva edificios en cascada si no hay suficiente población.

    Orden de desactivación (prioridad inversa):
    1. Alta Tecnología
    2. Industria Pesada
    3. Defensa
    4. Extracción Base (crítico, se desactiva al final)

    Args:
        planet_asset_id: ID del activo planetario
        available_pops: Población disponible para asignar
        buildings: Lista de edificios del planeta

    Returns:
        Tupla: (IDs de edificios desactivados, población restante)
    """
    # Calcular requisitos totales
    total_required = sum(
        b.get("pops_required", 0)
        for b in buildings
        if b.get("is_active", True)
    )

    # Si hay suficiente población, no hacer nada
    if available_pops >= total_required:
        return ([], available_pops - total_required)

    # Ordenar edificios por prioridad de desactivación
    def get_priority(building: Dict[str, Any]) -> int:
        building_type = building.get("building_type", "")
        definition = BUILDING_TYPES.get(building_type, {})
        category = definition.get("category", "extraccion")
        return BUILDING_SHUTDOWN_PRIORITY.get(category, 999)

    sorted_buildings = sorted(
        [b for b in buildings if b.get("is_active", True)],
        key=get_priority
    )

    disabled_ids = []
    remaining_pops = available_pops

    # Desactivar edificios hasta que haya suficiente población
    for building in sorted_buildings:
        if remaining_pops >= total_required:
            break

        building_id = building["id"]
        pops_freed = building.get("pops_required", 0)

        # Desactivar edificio en DB
        try:
            supabase.table("planet_buildings").update({
                "is_active": False
            }).eq("id", building_id).execute()

            disabled_ids.append(building_id)
            remaining_pops += pops_freed
            total_required -= pops_freed

            building_name = BUILDING_TYPES.get(
                building.get("building_type", ""), {}
            ).get("name", "Edificio Desconocido")

            log_event(
                f"⚠️ Edificio desactivado por falta de POPs: {building_name}",
                building.get("player_id")
            )
        except Exception as e:
            log_event(
                f"Error desactivando edificio ID {building_id}: {e}",
                building.get("player_id"),
                is_error=True
            )

    return (disabled_ids, remaining_pops - total_required)


def reactivate_buildings_if_possible(
    planet_asset_id: int,
    available_pops: int,
    buildings: List[Dict[str, Any]]
) -> List[int]:
    """
    Reactiva edificios desactivados si hay población disponible.

    Orden inverso al shutdown: primero Extracción, luego Defensa, etc.

    Args:
        planet_asset_id: ID del activo planetario
        available_pops: Población desempleada disponible
        buildings: Lista de todos los edificios

    Returns:
        Lista de IDs de edificios reactivados
    """
    # Edificios desactivados, ordenados por prioridad inversa (extracción primero)
    def get_priority(building: Dict[str, Any]) -> int:
        building_type = building.get("building_type", "")
        definition = BUILDING_TYPES.get(building_type, {})
        category = definition.get("category", "extraccion")
        return -BUILDING_SHUTDOWN_PRIORITY.get(category, 999)

    inactive_buildings = sorted(
        [b for b in buildings if not b.get("is_active", True)],
        key=get_priority
    )

    reactivated_ids = []
    remaining_pops = available_pops

    for building in inactive_buildings:
        pops_needed = building.get("pops_required", 0)

        if remaining_pops >= pops_needed:
            building_id = building["id"]

            try:
                supabase.table("planet_buildings").update({
                    "is_active": True
                }).eq("id", building_id).execute()

                reactivated_ids.append(building_id)
                remaining_pops -= pops_needed

                building_name = BUILDING_TYPES.get(
                    building.get("building_type", ""), {}
                ).get("name", "Edificio Desconocido")

                log_event(
                    f"✅ Edificio reactivado: {building_name}",
                    building.get("player_id")
                )
            except Exception as e:
                log_event(
                    f"Error reactivando edificio ID {building_id}: {e}",
                    building.get("player_id"),
                    is_error=True
                )
        else:
            break  # No hay más población disponible

    return reactivated_ids


# --- PROCESAMIENTO DE RECURSOS ---

def process_planet_production(
    planet_asset: Dict[str, Any],
    buildings: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Calcula la producción total de un planeta basándose en sus edificios activos.

    Args:
        planet_asset: Datos del activo planetario
        buildings: Lista de edificios del planeta

    Returns:
        Diccionario con recursos producidos: {"materiales": X, "componentes": Y, ...}
    """
    production = {
        "materiales": 0,
        "componentes": 0,
        "celulas_energia": 0,
        "influencia": 0
    }

    for building in buildings:
        if not building.get("is_active", True):
            continue

        building_type = building.get("building_type")
        definition = BUILDING_TYPES.get(building_type, {})
        building_production = definition.get("production", {})

        for resource, amount in building_production.items():
            production[resource] = production.get(resource, 0) + amount

    return production


def apply_maintenance_costs(
    player_id: int,
    planet_asset: Dict[str, Any],
    buildings: List[Dict[str, Any]]
) -> bool:
    """
    Deduce los costos de mantenimiento (energía) de los edificios activos.

    Args:
        player_id: ID del jugador
        planet_asset: Datos del planeta
        buildings: Lista de edificios

    Returns:
        True si se pagó el mantenimiento, False si no había suficientes recursos
    """
    maintenance = calculate_building_maintenance(buildings)
    energy_cost = maintenance.get("celulas_energia", 0)

    if energy_cost == 0:
        return True

    # Obtener recursos actuales del jugador
    finances = get_player_finances(player_id)
    current_energy = finances.get("celulas_energia", 0)

    if current_energy < energy_cost:
        log_event(
            f"⚠️ Energía insuficiente para mantenimiento en {planet_asset.get('nombre_asentamiento')}. "
            f"Requerido: {energy_cost}, Disponible: {current_energy}",
            player_id
        )
        return False

    # Deducir energía
    update_player_resources(player_id, {
        "celulas_energia": current_energy - energy_cost
    })

    return True


def process_luxury_resource_extraction(player_id: int) -> Dict[str, int]:
    """
    Procesa la extracción de recursos de lujo de todos los sitios activos del jugador.

    Args:
        player_id: ID del jugador

    Returns:
        Diccionario con recursos extraídos por categoría
    """
    try:
        # Obtener todos los sitios de extracción activos
        response = supabase.table("luxury_extraction_sites")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("is_active", True)\
            .execute()

        sites = response.data if response.data else []

        if not sites:
            return {}

        # Acumular producción
        extracted = {}

        for site in sites:
            resource_key = site.get("resource_key")
            category = site.get("resource_category")
            rate = site.get("extraction_rate", 1)

            key = f"{category}.{resource_key}"
            extracted[key] = extracted.get(key, 0) + rate

        # Actualizar recursos del jugador en JSONB
        if extracted:
            _update_luxury_resources(player_id, extracted)

        return extracted

    except Exception as e:
        log_event(f"Error procesando extracción de lujo: {e}", player_id, is_error=True)
        return {}


def _update_luxury_resources(player_id: int, extracted: Dict[str, int]):
    """
    Actualiza el campo recursos_lujo JSONB del jugador.

    Args:
        player_id: ID del jugador
        extracted: Diccionario con claves "categoria.recurso" y cantidades
    """
    try:
        # Obtener el JSONB actual
        response = supabase.table("players")\
            .select("recursos_lujo")\
            .eq("id", player_id)\
            .single()\
            .execute()

        current_luxury = response.data.get("recursos_lujo", {}) if response.data else {}

        # Sumar nuevos valores
        for key, amount in extracted.items():
            parts = key.split(".")
            if len(parts) != 2:
                continue

            category, resource = parts

            if category not in current_luxury:
                current_luxury[category] = {}

            current_luxury[category][resource] = \
                current_luxury[category].get(resource, 0) + amount

        # Actualizar DB
        supabase.table("players").update({
            "recursos_lujo": current_luxury
        }).eq("id", player_id).execute()

    except Exception as e:
        log_event(f"Error actualizando recursos de lujo: {e}", player_id, is_error=True)


# --- ORQUESTADOR PRINCIPAL ---

def run_economy_tick_for_player(player_id: int):
    """
    Ejecuta el ciclo económico completo para un jugador.

    Orden de ejecución:
    1. Procesar cada planeta del jugador
    2. Calcular ingresos por población
    3. Verificar requisitos de POPs y desactivar/reactivar edificios
    4. Calcular producción de edificios activos
    5. Aplicar mantenimiento
    6. Extraer recursos de lujo
    7. Actualizar recursos del jugador
    """
    try:
        # 1. Obtener todos los planetas del jugador
        response = supabase.table("planet_assets")\
            .select("*")\
            .eq("player_id", player_id)\
            .execute()

        planets = response.data if response.data else []

        if not planets:
            # Jugador sin planetas colonizados
            return

        # Acumuladores globales
        total_income = 0
        total_production = {
            "materiales": 0,
            "componentes": 0,
            "celulas_energia": 0,
            "influencia": 0
        }

        # 2. Procesar cada planeta
        for planet in planets:
            planet_id = planet["id"]
            population = planet.get("poblacion", 0)
            infrastructure = planet.get("infraestructura_defensiva", 0)
            happiness = planet.get("felicidad", 1.0)

            # Calcular seguridad
            security = calculate_security_multiplier(infrastructure)

            # Actualizar seguridad en DB
            supabase.table("planet_assets").update({
                "seguridad": security
            }).eq("id", planet_id).execute()

            # Calcular ingresos
            income = calculate_income(population, security, happiness)
            total_income += income

            # 3. Obtener edificios del planeta
            buildings_response = supabase.table("planet_buildings")\
                .select("*")\
                .eq("planet_asset_id", planet_id)\
                .execute()

            buildings = buildings_response.data if buildings_response.data else []

            # 4. Gestión de POPs
            pops_activos = planet.get("pops_activos", population)
            pops_desempleados = planet.get("pops_desempleados", 0)
            available_pops = pops_activos + pops_desempleados

            # Desactivación en cascada si es necesario
            disabled, remaining = cascade_shutdown_buildings(
                planet_id, available_pops, buildings
            )

            # Intentar reactivar edificios si hay POPs disponibles
            if remaining > 0:
                reactivate_buildings_if_possible(planet_id, remaining, buildings)

            # 5. Calcular producción
            production = process_planet_production(planet, buildings)

            for resource, amount in production.items():
                total_production[resource] = total_production.get(resource, 0) + amount

            # 6. Aplicar mantenimiento
            apply_maintenance_costs(player_id, planet, buildings)

        # 7. Extraer recursos de lujo
        luxury_extracted = process_luxury_resource_extraction(player_id)

        # 8. Actualizar recursos del jugador
        finances = get_player_finances(player_id)

        updates = {
            "creditos": finances.get("creditos", 0) + total_income,
            "materiales": finances.get("materiales", 0) + total_production.get("materiales", 0),
            "componentes": finances.get("componentes", 0) + total_production.get("componentes", 0),
            "celulas_energia": finances.get("celulas_energia", 0) + total_production.get("celulas_energia", 0),
            "influencia": finances.get("influencia", 0) + total_production.get("influencia", 0)
        }

        update_player_resources(player_id, updates)

        # Log resumen
        log_event(
            f"💰 Economía procesada: +{total_income} CI | "
            f"Producción: M:{total_production['materiales']} "
            f"C:{total_production['componentes']} "
            f"E:{total_production['celulas_energia']} "
            f"I:{total_production['influencia']}",
            player_id
        )

        if luxury_extracted:
            luxury_summary = ", ".join([f"{k}:{v}" for k, v in luxury_extracted.items()])
            log_event(f"💎 Recursos de lujo extraídos: {luxury_summary}", player_id)

    except Exception as e:
        log_event(f"Error crítico en economía del jugador {player_id}: {e}", player_id, is_error=True)


def run_global_economy_tick():
    """
    Ejecuta el tick económico para TODOS los jugadores activos.
    Se llama desde time_engine._phase_macroeconomics()
    """
    log_event("running fase económica global (MMFR)...")

    try:
        # Obtener todos los jugadores
        response = supabase.table("players").select("id").execute()
        players = response.data if response.data else []

        for player in players:
            player_id = player["id"]
            run_economy_tick_for_player(player_id)

        log_event("✅ Fase económica completada.")

    except Exception as e:
        log_event(f"Error crítico en tick económico global: {e}", is_error=True)
