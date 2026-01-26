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
Refactorizado V13.0: Navegación estratificada, tiempos físicos entre anillos y restricciones de salto desde sectores.
Refactorizado V13.1: Fix bloqueo en validación local. Se inyecta MovementType en validación para omitir chequeos de distancia en movimientos orbitales/superficie.
Refactorizado V13.2: Reordenamiento de prioridades en determine_movement_type para evitar falsos positivos de INTER_RING en movimientos planetarios.
Refactorizado V13.3: Fix bug de llegada a Ring 0 en tránsitos locales y manejo explícito de datos de destino.
Refactorizado V13.4: Persistencia total de anillo destino en Data Layer.
Actualizado V13.5: Soporte para saltos Inter-Ring largos con costo de energía.
Actualizado V14.0: Soporte para ship_count, Starlane Boost y límites de Warp.
Actualizado V14.2: Restricción de movimientos locales para unidades en STEALTH_MODE.
Actualizado V14.3: Eliminada restricción de movimiento para STEALTH_MODE (ahora usan MAX_LOCAL_MOVES_PER_TURN y pierden sigilo al moverse).
Refactorizado V14.4: Fix cálculo de ship_count dinámico (basado en miembros) y corrección de distancia Starlane por defecto (1.0).
Refactorizado V14.5: Persistencia de STEALTH_MODE en movimientos y restricción estricta (1 movimiento local).
Refactorizado V15.2: Refuerzo detección SURFACE_ORBIT para evitar falsos INTER_RING (Fix Anillo 0).
"""

from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum
import math
import json

from core.models import UnitSchema, UnitStatus, LocationRing
from core.movement_constants import (
    TICKS_SECTOR_TO_SECTOR,
    TICKS_SURFACE_TO_ORBIT,
    TICKS_BETWEEN_RINGS_SHORT,
    INTER_RING_LONG_DISTANCE_THRESHOLD,
    INTER_RING_ENERGY_COST_PER_SHIP,
    STARLANE_DISTANCE_THRESHOLD,
    TICKS_STARLANE_SHORT,
    TICKS_STARLANE_LONG,
    STARLANE_ENERGY_BOOST_COST,
    WARP_ENERGY_COST_PER_UNIT_DISTANCE,
    WARP_TICKS_BASE,
    WARP_TICKS_PER_10_DISTANCE,
    WARP_MAX_DISTANCE,
    MOVEMENT_LOCK_ON_ORBIT_CHANGE,
    MAX_LOCAL_MOVES_PER_TURN
)
# Eliminado DISORIENTED_MAX_LOCAL_MOVES ya que V14.3 unifica el límite
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
    SURFACE_ORBIT = "surface_orbit"        # Superficie <-> Órbita (o Órbita <-> Espacio mismo anillo)
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
    V14.4: Si la distancia es None o 1.0 (default DB), fuerza el cálculo real euclidiano.
    """
    dist_val = starlane.get('distancia')
    
    # Comprobamos si es válido (distinto de None y distinto del default 1.0)
    # Usamos una tolerancia pequeña para float comparison
    is_default = False
    if dist_val is None:
        is_default = True
    else:
        try:
            if abs(float(dist_val) - 1.0) < 0.001:
                is_default = True
        except (ValueError, TypeError):
            is_default = True

    if not is_default:
        return float(dist_val)

    # Calcular desde coordenadas si el valor en DB no es confiable
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
    Refactor V13.2: Prioridad a comprobaciones de mismo planeta/sector antes que comprobaciones de anillo.
    Refactor V15.2: Refuerzo para detectar SURFACE_ORBIT aunque haya discrepancia de anillos (usando DB).
    """
    # Cambio de sistema = interestelar
    if origin_system != dest_system:
        starlane = find_starlane_between(origin_system, dest_system)
        if starlane:
            return MovementType.STARLANE
        return MovementType.WARP

    # --- LÓGICA INTRA-SISTEMA ---

    # 1. Prioridad: Mismo planeta (Movimiento Superficie/Órbita)
    if origin_planet == dest_planet and origin_planet is not None:
        # Superficie <-> Órbita (sector NULL = órbita, sector NOT NULL = superficie)
        if (origin_sector is None and dest_sector is not None) or \
           (origin_sector is not None and dest_sector is None):
            return MovementType.SURFACE_ORBIT
        # Sector a sector en superficie
        return MovementType.SECTOR_SURFACE

    # 2. Refuerzo V15.2: SURFACE_ORBIT (Entrada/Salida de órbita al anillo correspondiente)
    # Check si es movimiento entre Planeta(Órbita) y Espacio(Sin planeta) en el mismo anillo
    # Esto soluciona bug si origin_ring viene corrupto (0) pero estamos saliendo de un planeta que está en Ring 4.
    
    # Caso A: Salida de Órbita -> Espacio
    if origin_planet is not None and dest_planet is None:
        try:
            planet = get_planet_by_id(origin_planet)
            if planet and planet.get("orbital_ring") == dest_ring:
                return MovementType.SURFACE_ORBIT
        except Exception:
            pass # Fallback a lógica estándar

    # Caso B: Entrada Espacio -> Órbita
    if origin_planet is None and dest_planet is not None:
        try:
            planet = get_planet_by_id(dest_planet)
            if planet and planet.get("orbital_ring") == origin_ring:
                return MovementType.SURFACE_ORBIT
        except Exception:
            pass

    # 3. Prioridad: Mismo anillo (si no fue capturado por lógica arriba)
    if origin_ring == dest_ring:
        is_origin_orbit = origin_planet is not None
        is_dest_orbit = dest_planet is not None
        
        # Si uno está en órbita y el otro en espacio (planet_id None), es un desatraque/atraque en el mismo anillo.
        if is_origin_orbit != is_dest_orbit:
            return MovementType.SURFACE_ORBIT

    # 4. Diferente anillo = inter-ring
    # Ahora es seguro retornar esto porque ya filtramos los casos de mismo planeta.
    if origin_ring != dest_ring:
        return MovementType.INTER_RING

    # 5. Mismo sistema, mismo anillo, diferente planeta
    if origin_planet != dest_planet:
         return MovementType.INTER_RING
         
    # Caso por defecto (movimiento en espacio del mismo anillo a otro punto del mismo anillo sin planeta)
    return MovementType.INTER_RING


def is_local_movement(unit: UnitSchema, destination: DestinationData) -> bool:
    """
    Determina si un movimiento se considera 'Local' (intra-sistema).
    Tipos Locales: SECTOR_SURFACE, SURFACE_ORBIT, INTER_RING (dentro del mismo sistema).
    """
    # Si cambia de sistema, es interestelar (no local)
    if unit.location_system_id != destination.system_id:
        return False
        
    # Orbit <-> Ring en el mismo sistema es local.
    return True


def calculate_movement_cost(
    unit: UnitSchema,
    destination: DestinationData,
    movement_type: MovementType,
    use_boost: bool = False
) -> Tuple[int, int]:
    """
    Calcula ticks y costo de energía para un movimiento.
    V14.0: Soporte para use_boost en Starlane y costos basados en ship_count.
    V14.4: ship_count ahora se calcula dinámicamente basado en len(unit.members).
    """
    ticks = 0
    energy = 0
    
    # V14.4: Cálculo dinámico de ship_count (Total de entidades en la unidad)
    # Se asume mínimo 1 si la lista está vacía (aunque validaciones previas lo impiden)
    ship_count = len(unit.members) if unit.members else 1

    # V10.1: Obtener ring de origen para penalización WARP
    origin_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    if movement_type == MovementType.SECTOR_SURFACE:
        ticks = 0

    elif movement_type == MovementType.SURFACE_ORBIT:
        ticks = 0

    elif movement_type == MovementType.INTER_RING:
        # V13.0: Siempre 1 tick base
        ticks = TICKS_BETWEEN_RINGS_SHORT
        
        # V14.0: Costo de energía para saltos largos basado en ship_count real
        dist_rings = abs(origin_ring - destination.ring)
        if dist_rings > INTER_RING_LONG_DISTANCE_THRESHOLD:
            energy = INTER_RING_ENERGY_COST_PER_SHIP * ship_count

    elif movement_type == MovementType.STARLANE:
        starlane = find_starlane_between(unit.location_system_id, destination.system_id)
        if starlane:
            distance = get_starlane_distance(starlane)
            
            if distance <= STARLANE_DISTANCE_THRESHOLD:
                ticks = TICKS_STARLANE_SHORT
            else:
                # Distancia larga > 15
                if use_boost:
                    # Sobrecarga: Viaje rápido (1 tick) pero costo energético
                    ticks = TICKS_STARLANE_SHORT
                    energy = STARLANE_ENERGY_BOOST_COST * ship_count
                else:
                    # Viaje normal largo (2 ticks)
                    ticks = TICKS_STARLANE_LONG

    elif movement_type == MovementType.WARP:
        distance = calculate_euclidean_distance(unit.location_system_id, destination.system_id)

        ticks = WARP_TICKS_BASE + int(distance / 10) * WARP_TICKS_PER_10_DISTANCE
        energy = int(WARP_ENERGY_COST_PER_UNIT_DISTANCE * distance * ship_count)

        # V10.1: Penalización gravitacional - WARP desde órbita o anillo planetario
        if origin_ring > 0:
            energy = energy * 2

    return ticks, energy


# --- FUNCIONES DE VALIDACIÓN ---

def validate_movement_request(
    unit: UnitSchema,
    destination: DestinationData,
    player_id: int,
    movement_type: MovementType
) -> Tuple[bool, str]:
    """
    Valida que un movimiento sea posible.
    V14.0: Validación de distancia máxima de Warp (30.0).
    V14.2: Restricción de movimientos locales para unidades en Sigilo.
    V14.3: Eliminada restricción de sigilo (ahora usan MAX_LOCAL_MOVES_PER_TURN estándar).
    V14.5: Re-implementada restricción estricta (1 movimiento) para STEALTH_MODE.
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
        
    # --- Validaciones Específicas por Tipo (V14.0) ---
    
    if movement_type == MovementType.WARP:
        distance = calculate_euclidean_distance(unit.location_system_id, destination.system_id)
        if distance > WARP_MAX_DISTANCE:
            return False, f"Destino fuera de rango Warp (Distancia: {distance:.1f} / Max: {WARP_MAX_DISTANCE})"

    # --- V11.3 / V11.4: LOGICA DE BLOQUEO Y MOVIMIENTO LOCAL ---

    is_local = is_local_movement(unit, destination)

    # Validar bloqueo de movimiento (movement_locked)
    if unit.movement_locked:
        allow_override = False
        
        # V14.5: Lógica de límite dinámica estricta para STEALTH
        # Unidades en STEALTH solo tienen 1 movimiento antes del bloqueo.
        if unit.status == UnitStatus.STEALTH_MODE:
            local_limit = 1
        else:
            local_limit = MAX_LOCAL_MOVES_PER_TURN
        
        if is_local and unit.local_moves_count < local_limit:
            allow_override = True
        
        if not allow_override:
            return False, "La unidad no puede moverse este tick (movimiento bloqueado o sin acciones disponibles)"

    # Restricción 1: Límite de movimientos locales
    if is_local:
        # V14.5: Restricción estricta para Stealth (1 movimiento) vs Normal (2 movimientos)
        if unit.status == UnitStatus.STEALTH_MODE:
            limit_count = 1
        else:
            limit_count = MAX_LOCAL_MOVES_PER_TURN
        
        if unit.local_moves_count >= limit_count:
            return False, f"Límite de movimientos locales alcanzado ({unit.local_moves_count}/{limit_count}). Espera al próximo tick."
        
        # Validación Órbita <-> Anillo (Constraint estricto)
        if unit.location_planet_id is not None and destination.planet_id is None:
            # Salida de órbita -> Espacio
            planet = get_planet_by_id(unit.location_planet_id)
            if planet and planet.get("orbital_ring") != destination.ring:
                return False, f"Solo puedes salir al Anillo {planet.get('orbital_ring')} desde esta órbita."
                
        if unit.location_planet_id is None and destination.planet_id is not None:
             # Espacio -> Entrada en órbita
             planet = get_planet_by_id(destination.planet_id)
             if planet and planet.get("orbital_ring") != origin_ring:
                 return False, f"Solo puedes entrar en órbita desde el Anillo {planet.get('orbital_ring')}."

    # Restricción 2: Bloqueo de tránsito interestelar si ya se movió localmente
    if not is_local:
        if unit.local_moves_count > 0:
            return False, "La unidad ha realizado movimientos locales. No puede iniciar tránsito interestelar en este tick."
        
        # V13.0: Restricción física de salto (debe estar en espacio, no sector)
        if unit.location_sector_id is not None:
            return False, "Debes salir al espacio exterior para iniciar un tránsito interestelar o un salto"

    return True, ""


# --- FUNCIÓN PRINCIPAL DE MOVIMIENTO ---

def initiate_movement(
    unit_id: int,
    destination: DestinationData,
    player_id: int,
    current_tick: int,
    use_boost: bool = False
) -> MovementResult:
    """
    Inicia el movimiento de una unidad hacia un destino.
    V14.0: Soporta use_boost para Starlanes.
    V14.5: Pasa el estado actual para persistir el sigilo en movimientos instantáneos.
    """
    # Obtener unidad
    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        return MovementResult(success=False, error_message="Unidad no encontrada")

    unit = UnitSchema.from_dict(unit_data)

    # Determinar tipo de movimiento
    origin_ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
    
    movement_type = determine_movement_type(
        origin_system=unit.location_system_id,
        origin_planet=unit.location_planet_id,
        origin_sector=unit.location_sector_id,
        origin_ring=origin_ring_val,
        dest_system=destination.system_id,
        dest_planet=destination.planet_id,
        dest_sector=destination.sector_id,
        dest_ring=destination.ring
    )

    # Validar movimiento
    is_valid, error_msg = validate_movement_request(unit, destination, player_id, movement_type)
    if not is_valid:
        return MovementResult(success=False, error_message=error_msg)

    # Calcular costos (incluyendo boost si aplica)
    ticks, energy_cost = calculate_movement_cost(unit, destination, movement_type, use_boost)

    # Validar recursos (Warp, Boost o Maniobra Larga)
    if energy_cost > 0:
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
        desc_extra = " (Boost Activado)" if use_boost else ""
        log_event(f"⚡ Energía Consumida: -{energy_cost} células (Movimiento: {movement_type.name}{desc_extra})", player_id)

    # Ejecutar movimiento
    if ticks == 0:
        # Movimiento instantáneo
        success, applied_lock = _execute_instant_movement(
            unit_id, 
            destination, 
            movement_type, 
            current_local_moves=unit.local_moves_count,
            current_status=unit.status # V14.5: Pasar estado para persistencia
        )
        
        if success:
            increment_unit_local_moves(unit_id)
            log_event(f"🚀 Unidad '{unit.name}' ha cambiado de posición (instantáneo)", player_id)
            
            return MovementResult(
                success=True,
                movement_type=movement_type,
                ticks_required=0,
                is_instant=True,
                movement_locked=applied_lock
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
        
        # Nota: start_unit_transit cambia el estado a TRANSIT, sobrescribiendo STEALTH_MODE.

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
    current_local_moves: int = 0,
    current_status: UnitStatus = UnitStatus.SPACE
) -> Tuple[bool, bool]:
    """
    Ejecuta un movimiento instantáneo (0 ticks).
    V14.5: Soporta persistencia de STEALTH_MODE.
    """
    # Determinar nuevo status
    # V14.5: Si estaba en STEALTH, se mantiene en STEALTH.
    if current_status == UnitStatus.STEALTH_MODE:
        new_status = UnitStatus.STEALTH_MODE
    else:
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
        if current_local_moves >= 1:
            update_unit_movement_lock(unit_id, locked=True)
            was_locked = True
        else:
            pass

    return success, was_locked


# --- FUNCIONES DE PROCESAMIENTO DE TRÁNSITO ---

def process_transit_arrivals(current_tick: int) -> List[Dict[str, Any]]:
    """
    Procesa las llegadas de unidades en tránsito.
    V14.5: Intenta preservar STEALTH_MODE si la unidad lo tiene activo.
    """
    arrivals = []
    arriving_units = get_units_in_transit_arriving_at_tick(current_tick)

    for unit_data in arriving_units:
        unit_id = unit_data.get('id')
        unit_name = unit_data.get('name', f'Unit {unit_id}')
        player_id = unit_data.get('player_id')
        dest_system = unit_data.get('transit_destination_system_id')
        
        # Recuperar status actual para persistencia (V14.5)
        current_status_str = unit_data.get('status')
        
        # Recuperar valores específicos (V13.3 / V13.4)
        dest_json = unit_data.get('transit_destination_data')
        dest_data = {}
        if isinstance(dest_json, str):
            try:
                dest_data = json.loads(dest_json)
            except json.JSONDecodeError:
                dest_data = {}
        elif isinstance(dest_json, dict):
            dest_data = dest_json
        
        target_ring = unit_data.get('transit_destination_ring') or dest_data.get('ring', 0)
        target_planet = dest_data.get('planet_id')
        target_sector = dest_data.get('sector_id')
        
        final_system_id = dest_system if dest_system else unit_data.get('location_system_id')
        
        # Determinar nuevo status (V14.5: Persistencia de Stealth)
        if current_status_str == UnitStatus.STEALTH_MODE.value:
            new_status = UnitStatus.STEALTH_MODE
        else:
            new_status = UnitStatus.GROUND if target_sector is not None else UnitStatus.SPACE

        update_success = update_unit_location_advanced(
            unit_id=unit_id,
            system_id=final_system_id,
            planet_id=target_planet,
            sector_id=target_sector,
            ring=target_ring,
            status=new_status
        )

        success = complete_unit_transit(unit_id, current_tick)

        if success and update_success:
            dest_name = "Destino Local"
            if final_system_id:
                dest_system_data = get_system_by_id(final_system_id)
                dest_name = dest_system_data.get('name', f'Sistema {final_system_id}') if dest_system_data else f'Sistema {final_system_id}'

            arrivals.append({
                'unit_id': unit_id,
                'unit_name': unit_name,
                'player_id': player_id,
                'destination': dest_name,
                'destination_system_id': final_system_id
            })

            log_event(f"✅ Unidad '{unit_name}' ha completado su maniobra hacia {dest_name}", player_id)
        else:
            log_event(f"❌ Error completando tránsito de unidad {unit_id}", player_id, is_error=True)

    return arrivals


def estimate_travel_time(
    origin_system_id: int,
    dest_system_id: int,
    origin_ring: int = 0,
    dest_ring: int = 0,
    ship_count: int = 1,
    use_boost: bool = False
) -> Dict[str, Any]:
    """
    Estima el tiempo de viaje entre dos ubicaciones.
    V14.0: Soporta use_boost y retorna flags para UI (can_boost).
    """
    # Mismo sistema
    if origin_system_id == dest_system_id:
        ring_diff = abs(origin_ring - dest_ring)
        if ring_diff == 0:
            return {
                'route_type': 'local',
                'ticks': 0,
                'is_instant': True,
                'description': 'Movimiento local (instantáneo)'
            }
        
        # Inter-ring
        ticks = TICKS_BETWEEN_RINGS_SHORT
        energy_cost = 0
        
        # V14.0: Costo para saltos largos
        if ring_diff > INTER_RING_LONG_DISTANCE_THRESHOLD:
            energy_cost = INTER_RING_ENERGY_COST_PER_SHIP * ship_count
            
        return {
            'route_type': 'inter_ring',
            'ticks': ticks,
            'is_instant': False,
            'energy_cost': energy_cost,
            'description': f'Maniobra orbital ({ring_diff} anillos de distancia)'
        }

    # Buscar starlane
    starlane = find_starlane_between(origin_system_id, dest_system_id)
    if starlane:
        distance = get_starlane_distance(starlane)
        
        can_boost = False
        ticks = 0
        energy_cost = 0
        
        if distance <= STARLANE_DISTANCE_THRESHOLD:
            ticks = TICKS_STARLANE_SHORT
            desc = f'Vía Starlane (distancia: {distance:.1f})'
        else:
            # Distancia larga
            can_boost = True
            if use_boost:
                ticks = TICKS_STARLANE_SHORT
                energy_cost = STARLANE_ENERGY_BOOST_COST * ship_count
                desc = f'Vía Starlane BOOSTED (distancia: {distance:.1f})'
            else:
                ticks = TICKS_STARLANE_LONG
                desc = f'Vía Starlane (distancia: {distance:.1f})'
        
        return {
            'route_type': 'starlane',
            'starlane_id': starlane.get('id'),
            'distance': distance,
            'ticks': ticks,
            'is_instant': False,
            'energy_cost': energy_cost,
            'can_boost': can_boost,
            'boost_cost_per_ship': STARLANE_ENERGY_BOOST_COST,
            'description': desc
        }

    # Warp
    distance = calculate_euclidean_distance(origin_system_id, dest_system_id)
    
    # V14.0: Validar distancia Warp
    if distance > WARP_MAX_DISTANCE:
        return {
            'route_type': 'warp_too_far',
            'distance': distance,
            'is_valid': False,
            'description': f'Destino fuera de rango Warp ({distance:.1f} > {WARP_MAX_DISTANCE})'
        }

    ticks = WARP_TICKS_BASE + int(distance / 10) * WARP_TICKS_PER_10_DISTANCE
    energy_cost_base = int(WARP_ENERGY_COST_PER_UNIT_DISTANCE * distance * ship_count)

    # V10.1: Penalización gravitacional
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
        'is_valid': True,
        'energy_cost': energy_cost_final,
        'energy_cost_base': energy_cost_base,
        'has_gravity_penalty': warp_penalty,
        'description': desc
    }