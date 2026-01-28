# ui/movement_console.py (Completo)
"""
Control de Movimiento - Vista para gestionar el movimiento de unidades.
V10.1: Implementación inicial con opciones dinámicas según ubicación.
V12.0: Adaptación para uso en componente/diálogo.
V15.0: Integración de Exploración Táctica de Sectores.
V15.4: Desacople de visualización MRG a Vista Condicional.
V16.0: Integración de Construcción de Puestos de Avanzada.
V21.0: Integración de Construcción de Estaciones Orbitales y Refactor Soberanía.
V21.1: Ocultación de Exploración en sectores URBANOS (Visibilidad automática).
V21.2: Fix crítico - Conversión explícita a UnitSchema para evitar AttributeError.
V21.3: Fix validación movimientos locales (moves_this_turn -> local_moves_count).
V22.0: Refactor integral de firmas de funciones y limpieza de UI.
V22.1: Sincronización con MovementEngine V16.1 y Robustez en UI de Construcción.
V22.2: Fix Navegación Orbital - Redirección correcta de menús para sectores Orbitales.
V22.3: Fix TypeError en cálculo de distancia WARP (uso de math.sqrt in-line).
"""

import streamlit as st
import json
import math  # Import necesario para cálculo de distancias
from typing import Dict, Any, List, Optional, Tuple

# Nueva importación para gestión de estado
from ui.state import get_player_id

from data.unit_repository import get_unit_by_id
# Importaciones consolidadas de world_repository
from data.world_repository import (
    get_system_by_id,
    get_planets_by_system_id,
    get_starlanes_from_db,
    get_all_systems_from_db,
    get_world_state,
)
from data.planet_repository import get_planet_sectors_status, get_planet_by_id, has_urban_sector
from core.models import UnitSchema, UnitStatus, LocationRing
from core.movement_engine import (
    MovementType,
    DestinationData,
    MovementResult,
    estimate_travel_time,
    initiate_movement,
    find_starlane_between,
    # calculate_euclidean_distance # Eliminado: Se usa math.sqrt localmente para evitar overhead DB
)
from core.movement_constants import (
    RING_STELLAR, RING_MIN, RING_MAX, MAX_LOCAL_MOVES_PER_TURN, 
    WARP_MAX_DISTANCE
)
from core.detection_constants import DISORIENTED_MAX_LOCAL_MOVES
from services.unit_service import toggle_stealth_mode
from core.exploration_engine import resolve_sector_exploration, ExplorationResult
from core.mrg_engine import ResultType
# Importamos la VISTA de resultado (no el diálogo) para renderizarla in-place
from ui.dialogs.roster_dialogs import render_exploration_result_view
from core.construction_engine import (
    resolve_outpost_construction, 
    build_orbital_station,
    OUTPOST_COST_CREDITS, 
    OUTPOST_COST_MATERIALS,
    ORBITAL_STATION_CREDITS,
    ORBITAL_STATION_MATERIALS
)
from core.world_constants import SECTOR_TYPE_ORBITAL, SECTOR_TYPE_URBAN


def _inject_movement_css():
    """CSS para la consola de movimiento."""
    st.markdown("""
    <style>
    .movement-header {
        background: linear-gradient(135deg, rgba(69,183,209,0.15) 0%, rgba(30,40,55,0.9) 100%);
        border-left: 4px solid #45b7d1;
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 4px;
    }
    .movement-option {
        background: rgba(30, 33, 40, 0.6);
        border: 1px solid rgba(255,255,255,0.1);
        padding: 12px;
        margin: 8px 0;
        border-radius: 6px;
    }
    .movement-option:hover {
        border-color: #45b7d1;
        background: rgba(69,183,209,0.1);
    }
    .cost-display {
        font-family: 'Source Code Pro', monospace;
        padding: 8px 12px;
        background: rgba(0,0,0,0.3);
        border-radius: 4px;
        margin-top: 10px;
    }
    .cost-instant { color: #2ecc71; font-weight: bold; }
    .cost-warning { color: #f39c12; }
    .cost-danger { color: #e74c3c; }
    .location-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85em;
        margin: 2px;
    }
    .loc-surface { background: rgba(46,204,113,0.2); color: #2ecc71; }
    .loc-orbit { background: rgba(155,89,182,0.2); color: #9b59b6; }
    .loc-space { background: rgba(69,183,209,0.2); color: #45b7d1; }
    .loc-transit { background: rgba(241,196,15,0.2); color: #f1c40f; }
    .loc-stealth { background: rgba(50, 50, 50, 0.8); color: #bdc3c7; border: 1px solid #7f8c8d; }
    .resource-tag {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 5px;
        font-size: 0.85em;
        color: #e0e0e0;
    }
    </style>
    """, unsafe_allow_html=True)


def _get_location_type(unit: UnitSchema) -> str:
    """Determina el tipo de ubicación de la unidad."""
    if unit.status == UnitStatus.TRANSIT:
        return 'transit'

    if unit.location_sector_id is not None:
        return 'surface_or_orbit'

    if unit.location_planet_id is not None:
        return 'orbit'

    ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
    if ring_val == 0:
        return 'stellar'

    return 'ring'


def _get_location_display(unit: UnitSchema) -> Dict[str, str]:
    """Obtiene información legible de la ubicación actual."""
    info = {
        'system': 'Desconocido',
        'planet': None,
        'sector': None,
        'ring': None,
        'status_text': 'Desconocido',
        'status_class': 'loc-space'
    }
    
    # Manejo visual de STEALTH
    if unit.status == UnitStatus.STEALTH_MODE:
        info['status_class'] = 'loc-stealth'

    if unit.status == UnitStatus.TRANSIT:
        # Calcular ticks reales dinámicamente para la etiqueta
        world_state = get_world_state()
        current_tick = world_state.get('current_tick', 0)
        
        real_ticks_remaining = unit.transit_ticks_remaining # Fallback
        if unit.transit_end_tick:
            real_ticks_remaining = max(0, unit.transit_end_tick - current_tick)
            
        origin_sys = get_system_by_id(unit.transit_origin_system_id)
        
        is_local_transit = unit.transit_origin_system_id == unit.transit_destination_system_id
        
        if is_local_transit:
            info['system'] = origin_sys.get('name', '?') if origin_sys else '?'
            info['status_text'] = f"Maniobra Orbital ({real_ticks_remaining} ticks)"
        else:
            dest_sys = get_system_by_id(unit.transit_destination_system_id)
            info['system'] = f"{origin_sys.get('name', '?') if origin_sys else '?'} → {dest_sys.get('name', '?') if dest_sys else '?'}"
            info['status_text'] = f"En Tránsito ({real_ticks_remaining} ticks)"
            
        info['status_class'] = 'loc-transit'
        return info

    if unit.location_system_id:
        system = get_system_by_id(unit.location_system_id)
        info['system'] = system.get('name', f'Sistema {unit.location_system_id}') if system else f'Sistema {unit.location_system_id}'

    ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
    if ring_val == 0:
        info['ring'] = 'Sector Estelar'
        if unit.status != UnitStatus.STEALTH_MODE:
            info['status_text'] = 'Sector Estelar (Espacio Profundo)'
            info['status_class'] = 'loc-space'
    else:
        info['ring'] = f'Anillo {ring_val}'

    if unit.location_planet_id:
        planet = get_planet_by_id(unit.location_planet_id)
        info['planet'] = planet.get('name', f'Planeta {unit.location_planet_id}') if planet else f'Planeta {unit.location_planet_id}'

    if unit.location_sector_id:
        if unit.location_planet_id:
            sectors = get_planet_sectors_status(unit.location_planet_id, unit.player_id)
            sector_data = next((s for s in sectors if s['id'] == unit.location_sector_id), None)
            if sector_data:
                sector_type = sector_data.get('sector_type', 'Desconocido')
                info['sector'] = sector_type
                if unit.status != UnitStatus.STEALTH_MODE:
                    if sector_type == 'Orbital':
                        info['status_text'] = f'Órbita de {info["planet"]}'
                        info['status_class'] = 'loc-orbit'
                    else:
                        info['status_text'] = f'{sector_type} - {info["planet"]}'
                        info['status_class'] = 'loc-surface'
    elif unit.location_planet_id:
         if unit.status != UnitStatus.STEALTH_MODE:
            info['status_text'] = f'Órbita de {info["planet"]}'
            info['status_class'] = 'loc-orbit'
    elif ring_val > 0:
         if unit.status != UnitStatus.STEALTH_MODE:
            info['status_text'] = f'Anillo {ring_val} - Espacio'
            info['status_class'] = 'loc-space'

    # Override texto si está en sigilo
    if unit.status == UnitStatus.STEALTH_MODE:
        info['status_text'] = 'Modo Sigilo (Ubicación Oculta)'

    return info


def _render_unit_info(unit: UnitSchema, location_info: Dict[str, str]):
    """Renderiza información de la unidad seleccionada."""
    # V14.6: Mostrar conteo real de miembros como naves
    actual_ship_count = len(unit.members) if unit.members else 1
    ship_count_display = f" | 🚀 Naves: <strong>{actual_ship_count}</strong>"
    
    st.markdown(f"""
    <div class="movement-header">
        <h4 style="margin:0">👥 {unit.name}</h4>
        <div style="margin-top:5px">
            <span class="location-badge {location_info['status_class']}">{location_info['status_text']}</span>
        </div>
        <p style="margin-top: 5px; color: #bbb; font-size: 0.9em">
            Sistema: <strong>{location_info['system']}</strong>
            {f" | Miembros: <strong>{len(unit.members)}/8</strong>" if unit.members else ""}
            {ship_count_display}
        </p>
    </div>
    """, unsafe_allow_html=True)


def _render_cost_display(estimate: Dict[str, Any], ship_count: int = 1):
    """Renderiza la visualización de costos."""
    ticks = estimate.get('ticks', 0)
    is_instant = estimate.get('is_instant', ticks == 0)
    energy = estimate.get('energy_cost', 0)
    has_penalty = estimate.get('has_gravity_penalty', False)

    if is_instant:
        st.markdown(f"""
        <div class="cost-display">
            <span class="cost-instant">Instantáneo</span> | Sin costo de energía
        </div>
        """, unsafe_allow_html=True)
    else:
        energy_class = "cost-warning" if has_penalty or energy > 0 else ""
        penalty_text = " (Penalización 2x)" if has_penalty else ""
        
        st.markdown(f"""
        <div class="cost-display">
            Tiempo: <strong>{ticks} Tick(s)</strong> |
            Energía: <span class="{energy_class}"><strong>{energy}</strong> células{penalty_text}</span>
            <br><span style="font-size:0.8em; color:#888;">(Cálculo para {ship_count} naves)</span>
        </div>
        """, unsafe_allow_html=True)


def _get_starlanes_from_system(system_id: int) -> List[Dict[str, Any]]:
    """Obtiene starlanes conectadas a un sistema."""
    all_starlanes = get_starlanes_from_db()
    connected = []
    for lane in all_starlanes:
        if lane.get('system_a_id') == system_id:
            connected.append({
                'id': lane['id'],
                'dest_system_id': lane.get('system_b_id'),
                'distance': lane.get('distancia', 0)
            })
        elif lane.get('system_b_id') == system_id:
            connected.append({
                'id': lane['id'],
                'dest_system_id': lane.get('system_a_id'),
                'distance': lane.get('distancia', 0)
            })
    return connected


def _get_valid_rings_for_selector(system_id: int) -> List[int]:
    """Retorna lista de anillos válidos (poblados o estelar) para el sistema."""
    planets = get_planets_by_system_id(system_id)
    populated_rings = {p.get('orbital_ring', 1) for p in planets}
    valid_rings = {0} | populated_rings
    return sorted(list(valid_rings))


def _render_surface_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType, bool]]:
    """
    Opciones cuando la unidad está en superficie de un planeta.
    Returns: (Destination, Type, UseBoost)
    """
    st.markdown("#### Opciones de Movimiento")

    planet_id = unit.location_planet_id
    system_id = unit.location_system_id
    current_sector_id = unit.location_sector_id

    sectors = get_planet_sectors_status(planet_id, player_id)
    surface_sectors = [s for s in sectors if s.get('sector_type') != 'Orbital' and s['id'] != current_sector_id]
    orbit_sector = next((s for s in sectors if s.get('sector_type') == 'Orbital'), None)

    planet = get_planet_by_id(planet_id)
    planet_name = planet.get('name', f'Planeta {planet_id}') if planet else f'Planeta {planet_id}'
    orbital_ring = planet.get('orbital_ring', 1) if planet else 1

    selected_dest = None
    selected_type = None

    tab1, tab2 = st.tabs(["Mover en Superficie", "Ascender a Órbita"])

    with tab1:
        st.markdown(f"**🌍 Mover a otro Sector de {planet_name}**")
        action_container = st.container()

        if surface_sectors:
            sector_options = {}
            for s in surface_sectors:
                if s.get('is_discovered', False):
                    sector_options[s['id']] = s.get('sector_type', f"Sector {s['id']}")
                else:
                    sector_options[s['id']] = f"Sector Desconocido [ID: {s['id']}]"

            selected_sector = st.selectbox(
                "Sector destino",
                options=list(sector_options.keys()),
                format_func=lambda x: sector_options.get(x, str(x)),
                key="move_surface_sector"
            )

            if selected_sector:
                estimate = estimate_travel_time(system_id, system_id, orbital_ring, orbital_ring)
                
                with action_container:
                    _render_cost_display(estimate)
                    if st.button("Mover a Sector", type="primary", key="btn_move_sector", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=planet_id,
                            sector_id=selected_sector,
                            ring=orbital_ring
                        )
                        selected_type = MovementType.SECTOR_SURFACE
        else:
            st.info("No hay otros sectores disponibles en este planeta.")

    with tab2:
        st.markdown(f"**🚀 Ascender a Órbita de {planet_name}**")
        
        # Validación de seguridad: Si ya estamos en el sector orbital, no mostrar esta opción o deshabilitarla
        is_already_in_orbit_sector = orbit_sector and current_sector_id == orbit_sector['id']
        
        if is_already_in_orbit_sector:
             st.info("ℹ️ La unidad ya se encuentra posicionada en el sector orbital.")
        
        else:
            action_container = st.container()
            
            if orbit_sector:
                st.caption("Salida de atmósfera hacia espacio orbital.")
                estimate = estimate_travel_time(system_id, system_id, orbital_ring, orbital_ring)
                
                with action_container:
                    _render_cost_display(estimate)

                    if st.button("Ascender a Órbita", type="primary", key="btn_ascend_orbit", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=planet_id,
                            sector_id=orbit_sector['id'],
                            ring=orbital_ring
                        )
                        selected_type = MovementType.SURFACE_ORBIT
            else:
                st.warning("Este planeta no tiene sector orbital definido.")

    if selected_dest and selected_type:
        return (selected_dest, selected_type, False)
    return None


def _render_orbit_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType, bool]]:
    """Opciones cuando la unidad está en órbita (Sector Orbital o ubicación genérica de órbita)."""
    st.markdown("#### Opciones de Movimiento")

    planet_id = unit.location_planet_id
    system_id = unit.location_system_id
    current_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    planet = get_planet_by_id(planet_id)
    planet_name = planet.get('name', f'Planeta {planet_id}') if planet else f'Planeta {planet_id}'
    orbital_ring = planet.get('orbital_ring', current_ring) if planet else current_ring

    selected_dest = None
    selected_type = None

    sectors = get_planet_sectors_status(planet_id, player_id)
    # Excluir 'Orbital' para las opciones de descenso
    surface_sectors = [s for s in sectors if s.get('sector_type') != 'Orbital']

    tab1, tab2 = st.tabs(["Descender", "Salir al espacio exterior"])

    with tab1:
        st.markdown(f"**🌍 Descender a Superficie de {planet_name}**")
        action_container = st.container()
        
        if surface_sectors:
            sector_options = {}
            for s in surface_sectors:
                if s.get('is_discovered', False):
                    sector_options[s['id']] = s.get('sector_type', f"Sector {s['id']}")
                else:
                    sector_options[s['id']] = f"Sector Desconocido [ID: {s['id']}]"

            selected_sector = st.selectbox(
                "Sector destino",
                options=list(sector_options.keys()),
                format_func=lambda x: sector_options.get(x, str(x)),
                key="descend_sector"
            )

            if selected_sector:
                estimate = estimate_travel_time(system_id, system_id, orbital_ring, orbital_ring)
                
                with action_container:
                    _render_cost_display(estimate)

                    if st.button("Descender", type="primary", key="btn_descend", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=planet_id,
                            sector_id=selected_sector,
                            ring=orbital_ring
                        )
                        selected_type = MovementType.SURFACE_ORBIT
        else:
            st.info("No hay sectores de superficie en este planeta.")

    with tab2:
        st.markdown(f"**🚀 Salir al Anillo {orbital_ring}**")
        st.caption("Desacoplar de la órbita para navegar en el espacio del sistema.")
        
        action_container = st.container()

        estimate = estimate_travel_time(system_id, system_id, current_ring, orbital_ring)
        
        with action_container:
            _render_cost_display(estimate)

            if st.button("Salir al Espacio Exterior", type="primary", key="btn_exit_orbit", use_container_width=True):
                # Destino: Mismo sistema/anillo, pero SIN planeta ni sector asignado (Espacio profundo del anillo)
                selected_dest = DestinationData(
                    system_id=system_id,
                    planet_id=None,
                    sector_id=None,
                    ring=orbital_ring
                )
                selected_type = MovementType.SURFACE_ORBIT

    if selected_dest and selected_type:
        return (selected_dest, selected_type, False)
    return None


def _render_ring_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType, bool]]:
    """
    Opciones cuando la unidad está en un anillo.
    V14.0: Filtro Warp > 30 y opción Boost para Starlanes.
    V14.6: Uso de miembros reales para cálculo de flota.
    """
    st.markdown("#### Opciones de Movimiento")

    system_id = unit.location_system_id
    current_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    # V14.6: Calcular naves basado en miembros reales
    real_ship_count = len(unit.members) if unit.members else 1

    planets_in_system = get_planets_by_system_id(system_id)
    planets_in_ring = [p for p in planets_in_system if p.get('orbital_ring') == current_ring]

    starlanes = _get_starlanes_from_system(system_id)

    selected_dest = None
    selected_type = None
    use_boost = False

    tab1, tab2, tab3, tab4 = st.tabs(["Órbita Planeta", "Navegación Intra-Sistema", "Starlane", "WARP"])

    with tab1:
        st.markdown("**🪐 Entrar en Órbita de Planeta**")
        action_container = st.container()

        if planets_in_ring:
            planet_options = {p['id']: p.get('name', f"Planeta {p['id']}") for p in planets_in_ring}
            selected_planet = st.selectbox(
                "Planeta destino",
                options=list(planet_options.keys()),
                format_func=lambda x: planet_options.get(x, str(x)),
                key="select_planet_orbit"
            )

            if selected_planet:
                sectors = get_planet_sectors_status(selected_planet, player_id)
                orbit_sector = next((s for s in sectors if s.get('sector_type') == 'Orbital'), None)

                estimate = estimate_travel_time(system_id, system_id, current_ring, current_ring)
                
                with action_container:
                    _render_cost_display(estimate)

                    if orbit_sector:
                        if st.button("Entrar en Órbita", type="primary", key="btn_enter_orbit", use_container_width=True):
                            selected_dest = DestinationData(
                                system_id=system_id,
                                planet_id=selected_planet,
                                sector_id=orbit_sector['id'],
                                ring=current_ring
                            )
                            selected_type = MovementType.SURFACE_ORBIT
                    else:
                        st.warning("El planeta no tiene sector orbital definido.")
        else:
            st.info(f"No hay planetas en el Anillo {current_ring}.")

    with tab2:
        st.markdown("**🔄 Navegación Intra-Sistema**")
        action_container = st.container()

        valid_rings = _get_valid_rings_for_selector(system_id)
        selectable_rings = [r for r in valid_rings if r != current_ring]

        ring_labels = {0: "Sector Estelar (Ring 0)"}
        for r in range(RING_MIN, RING_MAX + 1):
            ring_labels[r] = f"Anillo {r}"

        st.info(f"📍 Posición Actual: **{ring_labels.get(current_ring, f'Ring {current_ring}')}**")

        if selectable_rings:
            selected_ring = st.selectbox(
                "Anillo destino",
                options=selectable_rings,
                format_func=lambda x: ring_labels.get(x, f"Ring {x}"),
                key="select_ring_space"
            )

            if selected_ring is not None:
                estimate = estimate_travel_time(
                    system_id, 
                    system_id, 
                    origin_ring=current_ring, 
                    dest_ring=selected_ring,
                    ship_count=real_ship_count
                )
                
                with action_container:
                    _render_cost_display(estimate, real_ship_count)
                    
                    if st.button("Iniciar Maniobra", type="primary", key="btn_ring_space", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=None,
                            sector_id=None,
                            ring=selected_ring
                        )
                        selected_type = MovementType.INTER_RING
        else:
            st.info("No hay otros anillos de interés en este sistema.")

    with tab3:
        st.markdown("**🛤️ Usar Starlane**")
        action_container = st.container()

        if starlanes:
            lane_options = {}
            for lane in starlanes:
                dest_sys = get_system_by_id(lane['dest_system_id'])
                dest_name = dest_sys.get('name', f"Sistema {lane['dest_system_id']}") if dest_sys else f"Sistema {lane['dest_system_id']}"
                lane_options[lane['dest_system_id']] = f"{dest_name} (dist: {lane['distance']:.1f})"

            selected_lane_dest = st.selectbox(
                "Sistema destino",
                options=list(lane_options.keys()),
                format_func=lambda x: lane_options.get(x, str(x)),
                key="select_starlane_space"
            )

            if selected_lane_dest:
                # Checkbox para Boost
                boost_check = st.checkbox("🔥 Sobrecarga de Motores (Boost)", key="boost_check_space")
                
                estimate = estimate_travel_time(
                    system_id, 
                    selected_lane_dest, 
                    current_ring, 
                    0, 
                    ship_count=real_ship_count,
                    use_boost=boost_check
                )
                
                with action_container:
                    if estimate.get('can_boost') and not boost_check:
                         st.info("💡 Ruta larga detectada. Puedes usar Sobrecarga de Motores para reducir el tiempo.")
                    
                    _render_cost_display(estimate, real_ship_count)

                    if st.button("Iniciar Viaje por Starlane", type="primary", key="btn_starlane_space", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_lane_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                        )
                        selected_type = MovementType.STARLANE
                        use_boost = boost_check
        else:
            st.info("No hay Starlanes conectadas a este sistema.")

    with tab4:
        st.markdown("**🌌 Salto WARP (Sin Starlane)**")
        action_container = st.container()
        
        all_systems = get_all_systems_from_db()
        # Filtrar solo sistemas a distancia válida (WARP_MAX_DISTANCE)
        valid_warp_targets = []
        
        current_sys = get_system_by_id(system_id)
        
        if current_sys:
             for s in all_systems:
                 if s['id'] == system_id:
                     continue
                 
                 # FIX V22.3: Cálculo in-line de distancia euclidiana
                 # Se elimina el uso incorrecto de calculate_euclidean_distance(x,y,x,y)
                 # Usamos math.sqrt directamente con coordenadas para evitar llamadas extra a DB
                 dist = math.sqrt(
                     (s.get('x', 0) - current_sys.get('x', 0))**2 + 
                     (s.get('y', 0) - current_sys.get('y', 0))**2
                 )
                 
                 if dist <= WARP_MAX_DISTANCE:
                     valid_warp_targets.append({
                         'id': s['id'],
                         'name': s['name'],
                         'dist': dist
                     })
        
        if valid_warp_targets:
            warp_options = {s['id']: f"{s['name']} (Dist: {s['dist']:.1f})" for s in valid_warp_targets}
            
            selected_warp_dest = st.selectbox(
                "Sistema destino (Warp)",
                options=list(warp_options.keys()),
                format_func=lambda x: warp_options.get(x, str(x)),
                key="select_warp_space"
            )
            
            if selected_warp_dest:
                st.info(f"Distancia de Salto: {warp_options[selected_warp_dest].split('Dist: ')[1]}")
                
                if st.button("Iniciar Salto WARP", type="primary", key="btn_warp_space", use_container_width=True):
                     selected_dest = DestinationData(
                            system_id=selected_warp_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                     )
                     selected_type = MovementType.WARP # Corrección: WARP_JUMP -> WARP
        else:
            st.warning("No hay sistemas dentro del rango de salto WARP.")

    if selected_dest and selected_type:
        return (selected_dest, selected_type, use_boost)
    return None


def render_movement_console(unit_id: int):
    """
    Renderiza la consola de movimiento y acciones tácticas para una unidad.
    """
    # 1. Validación de Sesión y Unidad
    player_id = get_player_id()
    
    if not player_id:
        st.error("Sesión no válida.")
        return

    # FIX: La función devuelve un dict, pero usamos notación de objeto en el resto del código
    unit_dict = get_unit_by_id(unit_id)

    # Validamos usando acceso de diccionario
    if not unit_dict or unit_dict.get('player_id') != player_id:
        st.error("Unidad no encontrada o acceso denegado.")
        return
        
    # Convertimos a Pydantic Model para soportar notación de punto (unit.location_system_id, etc.)
    try:
        unit = UnitSchema(**unit_dict)
    except Exception as e:
        st.error(f"Error procesando datos de la unidad: {e}")
        return

    # Inyectar CSS
    _inject_movement_css()

    # 2. Renderizado de Cabecera
    loc_type = _get_location_type(unit)
    loc_info = _get_location_display(unit)
    _render_unit_info(unit, loc_info)

    # 3. Estado de Movimiento
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 0)
    
    if unit.status == UnitStatus.TRANSIT:
        st.info("🚀 La unidad está actualmente en tránsito.")
        return
        
    if unit.status == UnitStatus.CONSTRUCTING:
        st.info(f"🚧 La unidad está realizando operaciones de construcción (Finaliza en Tick {unit_dict.get('construction_end_tick', '?')}).")
        return

    # 4. Acciones Tácticas (Exploración, Construcción, Sigilo)
    st.divider()
    
    with st.expander("🛠️ Acciones Tácticas", expanded=True):
        col1, col2 = st.columns(2)
        
        # A) Exploración
        can_explore = False
        explore_label = "Explorar"
        
        if unit.location_sector_id:
            # Check si el sector ya está explorado
            is_orbital = loc_info.get('sector') == SECTOR_TYPE_ORBITAL
            sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
            sector_data = next((s for s in sectors if s['id'] == unit.location_sector_id), None)
            
            if sector_data:
                # Regla V21.1: Si es URBANO, la exploración no está disponible (Visible por defecto)
                is_urban = sector_data.get('sector_type') == SECTOR_TYPE_URBAN
                
                # Permitir re-explorar orbital para actualizar datos
                # Y solo mostrar opción si NO es urbano (o si es urbano pero no descubierto, aunque urbano suele ser known)
                if not is_urban and (is_orbital or not sector_data.get('is_explored_by_player')):
                    can_explore = True
                    explore_label = "Escanear Órbita" if is_orbital else "Explorar Sector"
        
        with col1:
             # Refactor: Pasar sector actual a resolve_sector_exploration
             if st.button(f"🔭 {explore_label}", disabled=not can_explore, use_container_width=True, help="Realizar reconocimiento del sector actual"):
                 result = resolve_sector_exploration(unit_id, unit.location_sector_id, player_id)
                 if result:
                     # Renderizar resultado visual in-place
                     render_exploration_result_view(result)
                     # Forzar recarga ligera para actualizar vista
                     st.rerun()

        # B) Sigilo
        is_stealth = unit.status == UnitStatus.STEALTH_MODE
        stealth_label = "Desactivar Sigilo" if is_stealth else "Activar Sigilo"
        stealth_btn_type = "secondary" if is_stealth else "primary"
        
        with col2:
            if st.button(f"👻 {stealth_label}", type=stealth_btn_type, use_container_width=True):
                # Refactor: Firma nueva toggle_stealth_mode(unit_id, player_id) y manejo de dict
                res = toggle_stealth_mode(unit_id, player_id)
                if res.get('success'):
                    st.toast(res.get('message', "Estado de sigilo actualizado."))
                    st.rerun()
                else:
                    st.error(res.get('error', "Error al cambiar sigilo."))
        
        # C) Construcción Táctica (Puestos de Avanzada / Estaciones Orbitales)
        st.markdown("---")
        c_col1, c_col2 = st.columns(2)
        
        # Validar Puesto de Avanzada
        # Solo en superficie, terreno válido, sin propiedad previa y si NO hay ciudades (V21.0)
        can_build_outpost = False
        outpost_reason = ""
        
        if unit.location_sector_id and loc_info.get('sector') != SECTOR_TYPE_ORBITAL:
            # Verificar si hay ciudades en el planeta (Nueva Soberanía V21.0)
            if has_urban_sector(unit.location_planet_id):
                outpost_reason = "Planeta con centros urbanos. Requiere conquista militar."
            else:
                # Reglas clásicas para planetas salvajes
                sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
                current_sector = next((s for s in sectors if s['id'] == unit.location_sector_id), None)
                
                if current_sector:
                    # Validar si está ocupado
                    is_occupied = current_sector.get('buildings_count', 0) > 0
                    # Validar terreno (ej: no Inhóspito, no Urbano - aunque urbano ya filtrado arriba)
                    terrain = current_sector.get('sector_type')
                    valid_terrains = ["Llanura", "Montañoso"]
                    is_terrain_ok = terrain in valid_terrains
                    
                    if is_occupied:
                        outpost_reason = "Sector ya ocupado."
                    elif not is_terrain_ok:
                        outpost_reason = "Terreno no apto para construcción."
                    else:
                        can_build_outpost = True

        # Validar Estación Orbital (V21.0)
        can_build_orbital = False
        orbital_reason = ""
        
        if unit.location_sector_id and loc_info.get('sector') == SECTOR_TYPE_ORBITAL:
             sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
             orbit_sector = next((s for s in sectors if s['sector_type'] == SECTOR_TYPE_ORBITAL), None)
             
             if orbit_sector:
                 is_occupied = orbit_sector.get('buildings_count', 0) > 0
                 if is_occupied:
                     orbital_reason = "Órbita ya controlada."
                 else:
                     can_build_orbital = True

        with c_col1:
            # Botón Puesto de Avanzada
            if can_build_outpost:
                if st.button("🏗️ Construir Puesto", use_container_width=True, help=f"Costo: {OUTPOST_COST_CREDITS} CR / {OUTPOST_COST_MATERIALS} MAT"):
                    # Refactor: Pasar sector explícitamente
                    result = resolve_outpost_construction(unit_id, unit.location_sector_id, player_id)
                    if result.get('success'):
                        st.success(result.get('message', 'Construcción iniciada.'))
                        st.rerun()
                    else:
                        st.error(result.get('message', result.get('error', 'Error desconocido')))
            elif unit.location_sector_id and loc_info.get('sector') != SECTOR_TYPE_ORBITAL:
                 st.button("🏗️ Construir Puesto", disabled=True, use_container_width=True, help=outpost_reason)

        with c_col2:
            # Botón Estación Orbital
            if can_build_orbital:
                 if st.button("🛰️ Estación Orbital", use_container_width=True, help=f"Costo: {ORBITAL_STATION_CREDITS} CR / {ORBITAL_STATION_MATERIALS} MAT"):
                    # Refactor: Pasar sector explícitamente
                    result = build_orbital_station(unit_id, unit.location_sector_id, player_id)
                    if result.get('success'):
                        st.success(result.get('message', 'Construcción Orbital iniciada.'))
                        st.rerun()
                    else:
                        st.error(result.get('message', result.get('error', 'Error desconocido')))
            elif unit.location_sector_id and loc_info.get('sector') == SECTOR_TYPE_ORBITAL:
                  st.button("🛰️ Estación Orbital", disabled=True, use_container_width=True, help=orbital_reason)

    st.divider()

    # 5. Opciones de Movimiento Dinámicas
    selection = None
    
    # Determinar contexto especial para Órbita (Sector Orbital)
    is_orbital_sector = loc_info.get('sector') == SECTOR_TYPE_ORBITAL
    
    if loc_type == 'surface_or_orbit':
        # FIX V22.2: Si es específicamente un Sector Orbital, usamos el menú de órbita
        if is_orbital_sector:
             selection = _render_orbit_options(unit, player_id, current_tick)
        else:
             selection = _render_surface_options(unit, player_id, current_tick)
        
    elif loc_type == 'orbit':
        # Estamos en órbita genérica (sin sector asignado - legacy o error, pero manejado)
        selection = _render_orbit_options(unit, player_id, current_tick)
        
    elif loc_type == 'ring' or loc_type == 'stellar':
        # Estamos en espacio
        selection = _render_ring_options(unit, player_id, current_tick)

    # 6. Procesar Selección de Movimiento
    if selection:
        dest_data, move_type, use_boost = selection
        
        # Validar penalización de movimiento local si está desorientada
        allowed_moves = DISORIENTED_MAX_LOCAL_MOVES if unit.disoriented else MAX_LOCAL_MOVES_PER_TURN
        
        # Validación de movimientos locales usando move_type para filtrar WARP/STARLANE
        # Corrección: WARP_JUMP -> WARP (enum correcto en el motor)
        if unit.local_moves_count >= allowed_moves and move_type not in [MovementType.WARP, MovementType.STARLANE]:
             limit_msg = "desorientación" if unit.disoriented else "límite estándar"
             st.warning(f"⚠️ La unidad ha alcanzado el límite de movimientos locales por turno ({limit_msg}).")
             return

        # Refactor: initiate_movement con firma nueva (sin move_type, con player_id y current_tick)
        # Se elimina explícitamente cualquier parámetro extra, el motor calcula el tipo.
        result = initiate_movement(unit_id, dest_data, player_id, current_tick, use_boost=use_boost)
        
        if result.success:
            st.success(f"Movimiento iniciado: {result.message}")
            st.rerun()
        else:
            st.error(f"Error de movimiento: {result.message}")