# core/movement_engine.py (Completo)
"""
Motor de Movimiento V10.0.
Gestiona:
1. Cálculo de tiempos de viaje
2. Validación de rutas
3. Iniciación y resolución de tránsitos
4. Costos de Warp
Actualizado V11.3: Lógica de Movimiento Local y restricciones diarias (local_moves_count).
Refactorizado V11.4: Fix bloqueo prematuro en movimientos locales (permite 2 movimientos antes de lock).
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
    get_units_in_transit_arriving_at_tick,
    increment_unit_local_moves
)
from data.world_repository import get_system_by_id, get_starlanes_from_db
from data.planet_repository import get_planet_by_id
from data.player_repository import get_player_finances, update_player_resources
from data.log_repository import log_event


class MovementType(Enum):
    """Tipos de movimiento posibles."""
    SECTOR_SURFACE = "sector_surface"      # Entre sectores en superficie
    SURFACE_ORBIT = "surface_orbit"        # Superficie <-> Órbita
    INTER_RING = "inter_ring"              # Entre anillos planetarios o Espacio <-> Órbita
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

    # Mismo sistema, diferente anillo = inter-ring (o salir de órbita a espacio del anillo)
    if origin_ring != dest_ring:
        return MovementType.INTER_RING

    # Mismo anillo...
    
    # ...y planeta pero diferente sector
    if origin_planet == dest_planet and origin_planet is not None:
        # Superficie <-> Órbita (sector NULL = órbita, sector NOT NULL = superficie)
        if (origin_sector is None and dest_sector is not None) or \
           (origin_sector is not None and dest_sector is None):
            return MovementType.SURFACE_ORBIT
        # Sector a sector en superficie
        return MovementType.SECTOR_SURFACE

    # Mismo sistema, mismo anillo, diferente planeta (o entrar/salir órbita en mismo anillo)
    # Ej: Espacio Ring 1 -> Órbita Planeta en Ring 1
    if origin_planet != dest_planet:
         return MovementType.INTER_RING
         
    # Caso por defecto (movimiento en espacio del mismo anillo)
    return MovementType.INTER_RING


def is_local_movement(unit: UnitSchema, destination: DestinationData) -> bool:
    """
    Determina si un movimiento se considera 'Local' (intra-sistema).
    Tipos Locales: SECTOR_SURFACE, SURFACE_ORBIT, INTER_RING (dentro del mismo sistema).
    """
    # Si cambia de sistema, es interestelar (no local)
    if unit.location_system_id != destination.system_id:
        return False
        
    return True


def calculate_movement_cost(
    unit: UnitSchema,
    destination: DestinationData,
    movement_type: MovementType
) -> Tuple[int, int]:
    """
    Calcula ticks y costo de energía para un movimiento.

    Reglas de Negocio V10.1:
    - SECTOR_SURFACE, SURFACE_ORBIT, INTER_RING: Tiempo = 0 (instantáneo)
    - WARP desde Orbit o Ring > 0: Costo de energía x2 (penalización gravitacional)
    - WARP desde Sector Estelar (Ring 0): Costo normal

    Returns:
        Tuple[int, int]: (ticks_required, energy_cost)
    """
    ticks = 0
    energy = 0

    # V10.1: Obtener ring de origen para penalización WARP
    origin_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    if movement_type == MovementType.SECTOR_SURFACE:
        # V10.1: Movimiento intra-planeta = instantáneo
        ticks = 0

    elif movement_type == MovementType.SURFACE_ORBIT:
        # V10.1: Superficie <-> Órbita = instantáneo
        ticks = 0

    elif movement_type == MovementType.INTER_RING:
        # V10.1: Movimiento entre anillos dentro del mismo sistema = instantáneo
        ticks = 0

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

        # V10.1: Penalización gravitacional - WARP desde órbita o anillo planetario
        # Si el origen NO es Sector Estelar (Ring 0), el costo de energía se duplica
        if origin_ring > 0:
            energy = energy * 2

    return ticks, energy


# --- FUNCIONES DE VALIDACIÓN ---

def validate_movement_request(
    unit: UnitSchema,
    destination: DestinationData,
    player_id: int
) -> Tuple[bool, str]:
    """
    Valida que un movimiento sea posible.
    V11.3: Implementa restricciones de local_moves_count.
    V11.4: Permite movimientos locales si local_moves_count < 2 aunque movement_locked sea True.

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Validar propiedad de la unidad
    if unit.player_id != player_id:
        return False, "No tienes control de esta unidad"

    # Validar que no está en tránsito
    if unit.status == UnitStatus.TRANSIT:
        return False, "La unidad ya está en tránsito"

    # Validar que tiene al menos un miembro
    if len(unit.members) == 0:
        return False, "La unidad está vacía, no puede moverse"

    # Validar que el destino es diferente al origen
    origin_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
    if (unit.location_system_id == destination.system_id and
        unit.location_planet_id == destination.planet_id and
        unit.location_sector_id == destination.sector_id and
        origin_ring == destination.ring):
        return False, "El destino es igual al origen"

    # --- V11.3 / V11.4: LOGICA DE BLOQUEO Y MOVIMIENTO LOCAL ---

    is_local = is_local_movement(unit, destination)

    # Validar bloqueo de movimiento (movement_locked)
    # V11.4: Si está bloqueada, SOLO permitimos si es movimiento local Y aún tiene cupo (count < 2)
    if unit.movement_locked:
        allow_override = False
        if is_local and unit.local_moves_count < 2:
            allow_override = True
        
        if not allow_override:
            return False, "La unidad no puede moverse este tick (movimiento bloqueado o sin acciones disponibles)"

    # Restricción 1: Límite de movimientos locales (Max 2)
    if is_local:
        if unit.local_moves_count >= 2:
            return False, f"Límite de movimientos locales alcanzado ({unit.local_moves_count}/2). Espera al próximo tick."
        
        # Validación Órbita <-> Anillo (Constraint estricto)
        # Si se mueve de Órbita a Anillo (espacio), el anillo destino debe ser el anillo orbital del planeta
        if unit.location_planet_id is not None and destination.planet_id is None:
            # Salida de órbita -> Espacio
            planet = get_planet_by_id(unit.location_planet_id)
            if planet and planet.get("orbital_ring") != destination.ring:
                return False, f"Solo puedes salir al Anillo {planet.get('orbital_ring')} desde esta órbita."
                
        # Si se mueve de Anillo (espacio) a Órbita, el anillo de origen debe ser el anillo orbital del planeta
        if unit.location_planet_id is None and destination.planet_id is not None:
             # Espacio -> Entrada en órbita
             planet = get_planet_by_id(destination.planet_id)
             if planet and planet.get("orbital_ring") != origin_ring:
                 return False, f"Solo puedes entrar en órbita desde el Anillo {planet.get('orbital_ring')}."

    # Restricción 2: Bloqueo de tránsito interestelar si ya se movió localmente
    if not is_local:
        if unit.local_moves_count > 0:
            return False, "La unidad ha realizado movimientos locales. No puede iniciar tránsito interestelar en este tick."

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
    V11.3: Incrementa local_moves_count si es movimiento local.

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

    # Validar movimiento (incluye restricciones V11.3 y V11.4)
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
        # Movimiento instantáneo (superficie <-> órbita o local)
        # V11.4: Pasamos el contador actual para decidir si bloquear
        success, applied_lock = _execute_instant_movement(
            unit_id, 
            destination, 
            movement_type, 
            current_local_moves=unit.local_moves_count
        )
        
        if success:
            # V11.3: Incrementar contador de movimientos locales
            increment_unit_local_moves(unit_id)
            
            log_event(f"🚀 Unidad '{unit.name}' ha cambiado de posición (instantáneo)", player_id)
            return MovementResult(
                success=True,
                movement_type=movement_type,
                ticks_required=0,
                is_instant=True,
                movement_locked=applied_lock # Refleja si realmente se bloqueó
            )
        return MovementResult(success=False, error_message="Error ejecutando movimiento instantáneo")
    else:
        # Movimiento con duración (Interestelar)
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
    movement_type: MovementType,
    current_local_moves: int = 0
) -> Tuple[bool, bool]:
    """
    Ejecuta un movimiento instantáneo (0 ticks).
    Usado para superficie <-> órbita y movimientos locales.
    
    V11.4: Lógica de bloqueo inteligente.
    Solo aplica movement_locked=True si se alcanza el límite de movimientos locales (2).
    
    Returns:
        Tuple[bool, bool]: (success, was_locked)
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
    
    was_locked = False
    if success and MOVEMENT_LOCK_ON_ORBIT_CHANGE:
        # V11.4: Regla de 2 movimientos.
        # Si current_local_moves es 0, este es el 1er movimiento -> NO lockear (permite el 2do).
        # Si current_local_moves es 1, este es el 2do movimiento -> LOCK.
        # Si current_local_moves >= 2, ya debería haber sido validado antes, pero por seguridad -> LOCK.
        
        if current_local_moves >= 1:
            update_unit_movement_lock(unit_id, locked=True)
            was_locked = True
        else:
            # Asegurarse que no esté lockeado (por si acaso viene true de otro lado, aunque update_unit_movement_lock normalmente solo pone true o false)
            # En este caso, solo queremos poner True si es el ultimo, si es el primero lo dejamos como este (que debería ser False).
            pass

    return success, was_locked


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
    dest_ring: int = 0,
    ship_count: int = 1
) -> Dict[str, Any]:
    """
    Estima el tiempo de viaje entre dos ubicaciones.
    Útil para la UI y planificación.

    V10.1: Actualizado con nuevas reglas de negocio:
    - Movimientos intra-sistema = instantáneos (0 ticks)
    - WARP desde Ring > 0 = penalización 2x energía

    Args:
        origin_system_id: Sistema de origen
        dest_system_id: Sistema destino
        origin_ring: Anillo de origen (para penalización WARP)
        dest_ring: Anillo destino
        ship_count: Número de naves (para cálculo de energía)

    Returns:
        Dict con información de la ruta y tiempo estimado
    """
    # Mismo sistema - V10.1: Todos instantáneos
    if origin_system_id == dest_system_id:
        ring_diff = abs(origin_ring - dest_ring)
        if ring_diff == 0:
            return {
                'route_type': 'local',
                'ticks': 0,
                'is_instant': True,
                'description': 'Movimiento local (instantáneo)'
            }
        # V10.1: Inter-ring ahora es instantáneo
        return {
            'route_type': 'inter_ring',
            'ticks': 0,
            'is_instant': True,
            'description': f'Movimiento entre anillos ({ring_diff} anillos) - Instantáneo'
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
            'is_instant': False,
            'description': f'Vía Starlane (distancia: {distance:.1f})'
        }

    # Warp
    distance = calculate_euclidean_distance(origin_system_id, dest_system_id)
    ticks = WARP_TICKS_BASE + int(distance / 10) * WARP_TICKS_PER_10_DISTANCE
    energy_cost_base = int(WARP_ENERGY_COST_PER_UNIT_DISTANCE * distance * ship_count)

    # V10.1: Penalización gravitacional si origen no es Sector Estelar
    warp_penalty = origin_ring > 0
    energy_cost_final = energy_cost_base * 2 if warp_penalty else energy_cost_base

    desc = f'Salto Warp (distancia: {distance:.1f}, energía: {energy_cost_final})'
    if warp_penalty:
        desc += ' ⚠️ Penalización gravitacional x2'

    return {
        'route_type': 'warp',
        'distance': distance,
        'ticks': ticks,
        'is_instant': False,
        'energy_cost': energy_cost_final,
        'energy_cost_base': energy_cost_base,
        'has_gravity_penalty': warp_penalty,
        'description': desc
    }