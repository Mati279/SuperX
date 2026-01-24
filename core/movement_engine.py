# core/movement_engine.py
"""
Motor de Movimiento V10.0.
Gestiona:
1. Cálculo de tiempos de viaje
2. Validación de rutas
3. Iniciación y resolución de tránsitos
4. Costos de Warp
"""

from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum
import math

from core.models import UnitSchema, UnitStatus, LocationRing
from core.movement_constants import (
    TICKS_SECTOR_TO_SECTOR,
    TICKS_SURFACE_TO_ORBIT,
    TICKS_BETWEEN_RINGS_SHORT,
    TICKS_BETWEEN_RINGS_LONG,
    RING_THRESHOLD_FOR_LONG_TRAVEL,
    STARLANE_DISTANCE_THRESHOLD,
    TICKS_STARLANE_SHORT,
    TICKS_STARLANE_LONG,
    WARP_ENERGY_COST_PER_UNIT_DISTANCE,
    WARP_TICKS_BASE,
    WARP_TICKS_PER_10_DISTANCE,
    MOVEMENT_LOCK_ON_ORBIT_CHANGE
)
from data.unit_repository import (
    get_unit_by_id,
    start_unit_transit,
    complete_unit_transit,
    update_unit_location_advanced,
    update_unit_movement_lock,
    get_units_in_transit_arriving_at_tick
)
from data.world_repository import get_system_by_id, get_starlanes_from_db
from data.player_repository import get_player_finances, update_player_resources
from data.log_repository import log_event


class MovementType(Enum):
    """Tipos de movimiento posibles."""
    SECTOR_SURFACE = "sector_surface"      # Entre sectores en superficie
    SURFACE_ORBIT = "surface_orbit"        # Superficie <-> Órbita
    INTER_RING = "inter_ring"              # Entre anillos planetarios
    STARLANE = "starlane"                  # Vía starlane
    WARP = "warp"                          # Salto warp (sin starlane)


@dataclass
class MovementResult:
    """Resultado de una orden de movimiento."""
    success: bool
    movement_type: Optional[MovementType] = None
    ticks_required: int = 0
    energy_cost: int = 0
    is_instant: bool = False
    movement_locked: bool = False
    error_message: str = ""


@dataclass
class DestinationData:
    """Datos del destino de un movimiento."""
    system_id: Optional[int] = None
    planet_id: Optional[int] = None
    sector_id: Optional[int] = None
    ring: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_id": self.system_id,
            "planet_id": self.planet_id,
            "sector_id": self.sector_id,
            "ring": self.ring
        }


# --- FUNCIONES DE CÁLCULO DE DISTANCIAS ---

def calculate_euclidean_distance(system_a_id: int, system_b_id: int) -> float:
    """
    Calcula la distancia euclidiana entre dos sistemas.
    Retorna infinito si alguno de los sistemas no existe.
    """
    sys_a = get_system_by_id(system_a_id)
    sys_b = get_system_by_id(system_b_id)

    if not sys_a or not sys_b:
        return float('inf')

    dx = sys_a.get('x', 0) - sys_b.get('x', 0)
    dy = sys_a.get('y', 0) - sys_b.get('y', 0)
    return math.sqrt(dx**2 + dy**2)


def find_starlane_between(system_a_id: int, system_b_id: int) -> Optional[Dict[str, Any]]:
    """
    Busca starlane directa entre dos sistemas.
    Retorna la starlane si existe, None si no hay conexión directa.
    """
    starlanes = get_starlanes_from_db()
    for lane in starlanes:
        if (lane.get('system_a_id') == system_a_id and lane.get('system_b_id') == system_b_id) or \
           (lane.get('system_a_id') == system_b_id and lane.get('system_b_id') == system_a_id):
            return lane
    return None


def get_starlane_distance(starlane: Dict[str, Any]) -> float:
    """
    Obtiene la distancia de una starlane.
    Si no tiene campo 'distancia', la calcula desde las coordenadas de los sistemas.
    """
    if 'distancia' in starlane and starlane['distancia'] is not None:
        return float(starlane['distancia'])

    # Calcular desde coordenadas
    return calculate_euclidean_distance(
        starlane.get('system_a_id'),
        starlane.get('system_b_id')
    )


# --- FUNCIONES DE CÁLCULO DE MOVIMIENTO ---

def determine_movement_type(
    origin_system: Optional[int],
    origin_planet: Optional[int],
    origin_sector: Optional[int],
    origin_ring: int,
    dest_system: Optional[int],
    dest_planet: Optional[int],
    dest_sector: Optional[int],
    dest_ring: int
) -> MovementType:
    """
    Determina el tipo de movimiento basado en origen y destino.
    """
    # Cambio de sistema = interestelar
    if origin_system != dest_system:
        starlane = find_starlane_between(origin_system, dest_system)
        if starlane:
            return MovementType.STARLANE
        return MovementType.WARP

    # Mismo sistema, diferente anillo = inter-ring
    if origin_ring != dest_ring:
        return MovementType.INTER_RING

    # Mismo anillo y planeta pero diferente sector
    if origin_planet == dest_planet:
        # Superficie <-> Órbita (sector NULL = órbita, sector NOT NULL = superficie)
        if (origin_sector is None and dest_sector is not None) or \
           (origin_sector is not None and dest_sector is None):
            return MovementType.SURFACE_ORBIT
        # Sector a sector en superficie
        return MovementType.SECTOR_SURFACE

    # Mismo sistema, mismo anillo, diferente planeta
    return MovementType.INTER_RING


def calculate_movement_cost(
    unit: UnitSchema,
    destination: DestinationData,
    movement_type: MovementType
) -> Tuple[int, int]:
    """
    Calcula ticks y costo de energía para un movimiento.

    Returns:
        Tuple[int, int]: (ticks_required, energy_cost)
    """
    ticks = 0
    energy = 0

    if movement_type == MovementType.SECTOR_SURFACE:
        ticks = TICKS_SECTOR_TO_SECTOR

    elif movement_type == MovementType.SURFACE_ORBIT:
        ticks = TICKS_SURFACE_TO_ORBIT  # 0 (instantáneo)

    elif movement_type == MovementType.INTER_RING:
        origin_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
        dest_ring = destination.ring
        ring_diff = abs(origin_ring - dest_ring)
        ticks = TICKS_BETWEEN_RINGS_SHORT if ring_diff <= RING_THRESHOLD_FOR_LONG_TRAVEL else TICKS_BETWEEN_RINGS_LONG

    elif movement_type == MovementType.STARLANE:
        starlane = find_starlane_between(unit.location_system_id, destination.system_id)
        if starlane:
            distance = get_starlane_distance(starlane)
            ticks = TICKS_STARLANE_SHORT if distance <= STARLANE_DISTANCE_THRESHOLD else TICKS_STARLANE_LONG

    elif movement_type == MovementType.WARP:
        distance = calculate_euclidean_distance(unit.location_system_id, destination.system_id)
        ship_count = unit.ship_count  # Propiedad del modelo

        ticks = WARP_TICKS_BASE + int(distance / 10) * WARP_TICKS_PER_10_DISTANCE
        energy = int(WARP_ENERGY_COST_PER_UNIT_DISTANCE * distance * ship_count)

    return ticks, energy


# --- FUNCIONES DE VALIDACIÓN ---

def validate_movement_request(
    unit: UnitSchema,
    destination: DestinationData,
    player_id: int
) -> Tuple[bool, str]:
    """
    Valida que un movimiento sea posible.

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Validar propiedad de la unidad
    if unit.player_id != player_id:
        return False, "No tienes control de esta unidad"

    # Validar que no está en tránsito
    if unit.status == UnitStatus.TRANSIT:
        return False, "La unidad ya está en tránsito"

    # Validar que no está bloqueada por movimiento reciente
    if unit.movement_locked:
        return False, "La unidad no puede moverse este tick (movimiento bloqueado)"

    # Validar que tiene al menos un miembro
    if len(unit.members) == 0:
        return False, "La unidad está vacía, no puede moverse"

    # Validar que el destino es diferente al origen
    if (unit.location_system_id == destination.system_id and
        unit.location_planet_id == destination.planet_id and
        unit.location_sector_id == destination.sector_id and
        unit.ring.value == destination.ring):
        return False, "El destino es igual al origen"

    return True, ""


# --- FUNCIÓN PRINCIPAL DE MOVIMIENTO ---

def initiate_movement(
    unit_id: int,
    destination: DestinationData,
    player_id: int,
    current_tick: int
) -> MovementResult:
    """
    Inicia el movimiento de una unidad hacia un destino.
    Valida recursos, actualiza estado a TRANSIT si aplica.

    Args:
        unit_id: ID de la unidad a mover
        destination: Datos del destino
        player_id: ID del jugador que ordena el movimiento
        current_tick: Tick actual del juego

    Returns:
        MovementResult con el resultado de la operación
    """
    # Obtener unidad
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return MovementResult(success=False, error_message="Unidad no encontrada")

    unit = UnitSchema.from_dict(unit_data)

    # Validar movimiento
    is_valid, error_msg = validate_movement_request(unit, destination, player_id)
    if not is_valid:
        return MovementResult(success=False, error_message=error_msg)

    # Determinar tipo de movimiento
    movement_type = determine_movement_type(
        origin_system=unit.location_system_id,
        origin_planet=unit.location_planet_id,
        origin_sector=unit.location_sector_id,
        origin_ring=unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring,
        dest_system=destination.system_id,
        dest_planet=destination.planet_id,
        dest_sector=destination.sector_id,
        dest_ring=destination.ring
    )

    # Calcular costos
    ticks, energy_cost = calculate_movement_cost(unit, destination, movement_type)

    # Validar recursos para Warp
    if movement_type == MovementType.WARP and energy_cost > 0:
        finances = get_player_finances(player_id)
        current_energy = finances.get('celulas_energia', 0) if finances else 0
        if current_energy < energy_cost:
            return MovementResult(
                success=False,
                error_message=f"Energía insuficiente. Necesitas {energy_cost} células, tienes {current_energy}."
            )
        # Deducir energía
        update_player_resources(player_id, {
            'celulas_energia': current_energy - energy_cost
        })
        log_event(f"⚡ Warp: -{energy_cost} células de energía", player_id)

    # Ejecutar movimiento
    if ticks == 0:
        # Movimiento instantáneo (superficie <-> órbita)
        success = _execute_instant_movement(unit_id, destination, movement_type)
        if success:
            log_event(f"🚀 Unidad '{unit.name}' ha cambiado de posición (instantáneo)", player_id)
            return MovementResult(
                success=True,
                movement_type=movement_type,
                ticks_required=0,
                is_instant=True,
                movement_locked=MOVEMENT_LOCK_ON_ORBIT_CHANGE
            )
        return MovementResult(success=False, error_message="Error ejecutando movimiento instantáneo")
    else:
        # Movimiento con duración
        starlane = None
        starlane_id = None
        if movement_type == MovementType.STARLANE:
            starlane = find_starlane_between(unit.location_system_id, destination.system_id)
            starlane_id = starlane.get('id') if starlane else None

        success = start_unit_transit(
            unit_id=unit_id,
            destination_data=destination.to_dict(),
            ticks_required=ticks,
            current_tick=current_tick,
            starlane_id=starlane_id,
            movement_type=movement_type.value
        )

        if success:
            log_event(f"🚀 Unidad '{unit.name}' iniciando tránsito ({ticks} ticks)", player_id)
            return MovementResult(
                success=True,
                movement_type=movement_type,
                ticks_required=ticks,
                energy_cost=energy_cost
            )
        return MovementResult(success=False, error_message="Error iniciando tránsito")


def _execute_instant_movement(
    unit_id: int,
    destination: DestinationData,
    movement_type: MovementType
) -> bool:
    """
    Ejecuta un movimiento instantáneo (0 ticks).
    Usado para superficie <-> órbita.
    """
    # Determinar nuevo status
    new_status = UnitStatus.GROUND if destination.sector_id is not None else UnitStatus.SPACE

    # Actualizar ubicación
    success = update_unit_location_advanced(
        unit_id=unit_id,
        system_id=destination.system_id,
        planet_id=destination.planet_id,
        sector_id=destination.sector_id,
        ring=destination.ring,
        status=new_status
    )

    if success and MOVEMENT_LOCK_ON_ORBIT_CHANGE:
        update_unit_movement_lock(unit_id, locked=True)

    return success


# --- FUNCIONES DE PROCESAMIENTO DE TRÁNSITO ---

def process_transit_arrivals(current_tick: int) -> List[Dict[str, Any]]:
    """
    Procesa las llegadas de unidades en tránsito.
    Llamado durante la fase de Decremento del tick.

    Returns:
        Lista de diccionarios con información de cada llegada
    """
    arrivals = []

    # Obtener unidades que llegan en este tick
    arriving_units = get_units_in_transit_arriving_at_tick(current_tick)

    for unit_data in arriving_units:
        unit_id = unit_data.get('id')
        unit_name = unit_data.get('name', f'Unit {unit_id}')
        player_id = unit_data.get('player_id')
        dest_system = unit_data.get('transit_destination_system_id')

        # Completar tránsito
        success = complete_unit_transit(unit_id, current_tick)

        if success:
            # Obtener nombre del sistema destino
            dest_system_data = get_system_by_id(dest_system)
            dest_name = dest_system_data.get('name', f'Sistema {dest_system}') if dest_system_data else f'Sistema {dest_system}'

            arrivals.append({
                'unit_id': unit_id,
                'unit_name': unit_name,
                'player_id': player_id,
                'destination': dest_name,
                'destination_system_id': dest_system
            })

            log_event(f"✅ Unidad '{unit_name}' ha llegado a {dest_name}", player_id)
        else:
            log_event(f"❌ Error completando tránsito de unidad {unit_id}", player_id, is_error=True)

    return arrivals


def estimate_travel_time(
    origin_system_id: int,
    dest_system_id: int,
    origin_ring: int = 0,
    dest_ring: int = 0
) -> Dict[str, Any]:
    """
    Estima el tiempo de viaje entre dos ubicaciones.
    Útil para la UI y planificación.

    Returns:
        Dict con información de la ruta y tiempo estimado
    """
    # Mismo sistema
    if origin_system_id == dest_system_id:
        ring_diff = abs(origin_ring - dest_ring)
        if ring_diff == 0:
            return {
                'route_type': 'local',
                'ticks': 0,
                'description': 'Movimiento local'
            }
        ticks = TICKS_BETWEEN_RINGS_SHORT if ring_diff <= RING_THRESHOLD_FOR_LONG_TRAVEL else TICKS_BETWEEN_RINGS_LONG
        return {
            'route_type': 'inter_ring',
            'ticks': ticks,
            'description': f'Movimiento entre anillos ({ring_diff} anillos)'
        }

    # Buscar starlane
    starlane = find_starlane_between(origin_system_id, dest_system_id)
    if starlane:
        distance = get_starlane_distance(starlane)
        ticks = TICKS_STARLANE_SHORT if distance <= STARLANE_DISTANCE_THRESHOLD else TICKS_STARLANE_LONG
        return {
            'route_type': 'starlane',
            'starlane_id': starlane.get('id'),
            'distance': distance,
            'ticks': ticks,
            'description': f'Vía Starlane (distancia: {distance:.1f})'
        }

    # Warp
    distance = calculate_euclidean_distance(origin_system_id, dest_system_id)
    ticks = WARP_TICKS_BASE + int(distance / 10) * WARP_TICKS_PER_10_DISTANCE
    energy_cost = int(WARP_ENERGY_COST_PER_UNIT_DISTANCE * distance)  # Por nave

    return {
        'route_type': 'warp',
        'distance': distance,
        'ticks': ticks,
        'energy_cost_per_ship': energy_cost,
        'description': f'Salto Warp (distancia: {distance:.1f}, energía: {energy_cost}/nave)'
    }
