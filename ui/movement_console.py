# ui/movement_console.py (Completo)
"""
Control de Movimiento - Vista para gestionar el movimiento de unidades.
V10.1: Implementación inicial con opciones dinámicas según ubicación.
V12.0: Adaptación para uso en componente/diálogo.
V12.1: Reorganización de UI - Botones de acción.
V12.2: Fix de bloqueo - UI permite 2 movimientos locales.
V13.0: Refactorización de Navegación - Restricciones físicas estrictas.
V13.3: Refactor visualización SCO (Inter-Ring).
V13.5: Persistencia del diálogo tras movimiento local.
V13.6: Soporte UI para saltos largos con costo de energía.
V14.0: Soporte UI para Sobrecarga de Motores (Boost), filtrado de Warp > 30 y visualización de costos de flota.
V14.2: Panel de Modos de Unidad (Sigilo) y restricciones visuales.
V14.5: Visualización estricta de límites de movimiento para Stealth (1/1).
V14.6: Corrección de cálculo de costos (basa en miembros reales) y marcador visual Movs X/Y.
V14.7: Sincronización dinámica de ticks de viaje (Real-time calculation vs World Tick).
V15.0: Integración de Exploración Táctica de Sectores.
V15.1: Feedback persistente de exploración y gestión de fatiga.
V15.2: Integración de @st.fragment y widget MRG. Feedback simplificado.
V15.3: Fix coordenadas Warp (Cálculo 2D local y eliminación de referencia a 'z').
"""

import streamlit as st
import json
import math  # Import necesario para cálculo de distancias
from typing import Dict, Any, List, Optional, Tuple

from data.unit_repository import get_unit_by_id
from data.world_repository import (
    get_system_by_id,
    get_planets_by_system_id,
    get_starlanes_from_db,
    get_all_systems_from_db,
)
from data.planet_repository import get_planet_sectors_status, get_planet_by_id
from core.models import UnitSchema, UnitStatus, LocationRing
from core.movement_engine import (
    MovementType,
    DestinationData,
    MovementResult,
    estimate_travel_time,
    initiate_movement,
    find_starlane_between,
    calculate_euclidean_distance
)
from core.movement_constants import (
    RING_STELLAR, RING_MIN, RING_MAX, MAX_LOCAL_MOVES_PER_TURN, 
    WARP_MAX_DISTANCE
)
from core.detection_constants import DISORIENTED_MAX_LOCAL_MOVES
from data.world_repository import get_world_state
from services.unit_service import toggle_stealth_mode
from core.exploration_engine import resolve_sector_exploration, ExplorationResult
from core.mrg_engine import ResultType
from ui.mrg_resolution_widget import render_full_mrg_resolution


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
    """Opciones cuando la unidad está en órbita."""
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
        st.markdown("**⚡ Motor WARP**")
        action_container = st.container()
        
        st.caption("Salto FTL directo a otro sistema. Consume mucha energía.")

        all_systems = get_all_systems_from_db()
        
        # Corrección V15.3: Obtención segura de coordenadas 2D (sin 'z')
        origin_sys_data = get_system_by_id(system_id)
        ox = origin_sys_data.get('x', 0.0) if origin_sys_data else 0.0
        oy = origin_sys_data.get('y', 0.0) if origin_sys_data else 0.0

        warp_targets = []
        for s in all_systems:
            if s['id'] == system_id:
                continue
            
            # Cálculo directo 2D local (math.sqrt) para evitar KeyErrors
            dx = ox - s.get('x', 0.0)
            dy = oy - s.get('y', 0.0)
            dist = math.sqrt(dx**2 + dy**2)
            
            if dist <= WARP_MAX_DISTANCE:
                 warp_targets.append({
                     'id': s['id'],
                     'name': s['name'],
                     'distance': dist
                 })
        
        warp_targets.sort(key=lambda x: x['distance'])

        if warp_targets:
            warp_options = {s['id']: f"{s['name']} (Dist: {s['distance']:.1f})" for s in warp_targets}
            
            selected_warp_dest = st.selectbox(
                "Sistema destino (WARP)",
                options=list(warp_options.keys()),
                format_func=lambda x: warp_options.get(x, str(x)),
                key="select_warp_space"
            )

            if selected_warp_dest:
                estimate = estimate_travel_time(
                    system_id, 
                    selected_warp_dest, 
                    current_ring, 
                    RING_MAX, 
                    ship_count=real_ship_count
                )
                
                with action_container:
                    _render_cost_display(estimate, real_ship_count)

                    if st.button("Iniciar Salto WARP", type="primary", key="btn_warp_space", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_warp_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=RING_MAX # Warp llega al borde
                        )
                        selected_type = MovementType.WARP
        else:
            st.warning("No hay sistemas al alcance del Motor WARP (< 30.0 U).")


    if selected_dest and selected_type:
        return (selected_dest, selected_type, use_boost)
    return None


def _render_stellar_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType, bool]]:
    """Opciones cuando la unidad está en el Sector Estelar (Ring 0)."""
    st.markdown("#### Opciones de Movimiento")
    st.info("🌌 Estás en el Sector Estelar Central (Ring 0).")

    system_id = unit.location_system_id
    current_ring = 0
    real_ship_count = len(unit.members) if unit.members else 1

    starlanes = _get_starlanes_from_system(system_id)
    
    selected_dest = None
    selected_type = None
    use_boost = False

    tab1, tab2 = st.tabs(["Navegación Intra-Sistema", "Starlane"])

    with tab1:
        st.markdown("**🔄 Ir a un Anillo**")
        action_container = st.container()

        valid_rings = _get_valid_rings_for_selector(system_id)
        selectable_rings = [r for r in valid_rings if r != 0]

        if selectable_rings:
            selected_ring = st.selectbox(
                "Anillo destino",
                options=selectable_rings,
                format_func=lambda x: f"Anillo {x}",
                key="select_ring_stellar"
            )

            if selected_ring:
                estimate = estimate_travel_time(
                    system_id, 
                    system_id, 
                    origin_ring=0, 
                    dest_ring=selected_ring,
                    ship_count=real_ship_count
                )
                
                with action_container:
                    _render_cost_display(estimate, real_ship_count)
                    
                    if st.button("Iniciar Maniobra", type="primary", key="btn_ring_stellar", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=None,
                            sector_id=None,
                            ring=selected_ring
                        )
                        selected_type = MovementType.INTER_RING
        else:
            st.info("Este sistema no tiene anillos explorables.")

    with tab2:
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
                key="select_starlane_stellar"
            )

            if selected_lane_dest:
                # Checkbox para Boost
                boost_check = st.checkbox("🔥 Sobrecarga de Motores (Boost)", key="boost_check_stellar")

                estimate = estimate_travel_time(
                    system_id, 
                    selected_lane_dest, 
                    origin_ring=0, 
                    dest_ring=0,
                    ship_count=real_ship_count,
                    use_boost=boost_check
                )
                
                with action_container:
                    if estimate.get('can_boost') and not boost_check:
                         st.info("💡 Ruta larga detectada. Puedes usar Sobrecarga de Motores para reducir el tiempo.")
                         
                    _render_cost_display(estimate, real_ship_count)

                    if st.button("Iniciar Viaje por Starlane", type="primary", key="btn_starlane_stellar", use_container_width=True):
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

    if selected_dest and selected_type:
        return (selected_dest, selected_type, use_boost)
    return None


def _render_transit_info(unit: UnitSchema):
    """Muestra información cuando la unidad está en tránsito."""
    st.info("🚀 La unidad está actualmente en tránsito.")
    
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 0)
    
    # Calcular ticks restantes reales
    ticks_remaining = 0
    if unit.transit_end_tick:
        ticks_remaining = max(0, unit.transit_end_tick - current_tick)
        
    st.write(f"**Destino:** Sistema {unit.transit_destination_system_id}")
    st.write(f"**Llegada estimada:** En {ticks_remaining} tick(s)")
    
    # Barra de progreso (simulada)
    if unit.transit_start_tick and unit.transit_end_tick:
        total = unit.transit_end_tick - unit.transit_start_tick
        if total > 0:
            elapsed = current_tick - unit.transit_start_tick
            progress = min(1.0, max(0.0, elapsed / total))
            st.progress(progress)


@st.fragment
def render_movement_console():
    """Punto de entrada principal - Página de Control de Movimiento."""
    from .state import get_player

    _inject_movement_css()
    
    player = get_player()
    if not player:
        st.error("Error de sesión. Por favor, inicia sesión nuevamente.")
        return

    player_id = player.id
    unit_id = st.session_state.get('selected_unit_movement')

    if not unit_id:
        st.warning("No hay unidad seleccionada.")
        return

    unit_data = get_unit_by_id(unit_id)
    if not unit_data:
        st.error(f"No se encontró la unidad con ID {unit_id}")
        st.session_state.selected_unit_movement = None
        return

    if unit_data.get('player_id') != player_id:
        st.error("No tienes control de esta unidad.")
        st.session_state.selected_unit_movement = None
        return

    unit = UnitSchema.from_dict(unit_data)
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 0)

    location_info = _get_location_display(unit)
    _render_unit_info(unit, location_info)
    
    # --- V14.2: SECCIÓN DE MODOS DE LA UNIDAD ---
    if unit.status != UnitStatus.TRANSIT:
        st.markdown("### 🎛️ Modos de la Unidad")
        
        mode_cols = st.columns([2, 1])
        with mode_cols[0]:
            is_stealth = unit.status == UnitStatus.STEALTH_MODE
            btn_label = "Desactivar Sigilo 📡" if is_stealth else "Activar Sigilo 🥷"
            btn_type = "secondary" if is_stealth else "primary"
            
            if st.button(btn_label, type=btn_type, key="toggle_stealth_btn", use_container_width=True):
                result = toggle_stealth_mode(unit_id, player_id)
                if result["success"]:
                    st.toast(f"Modo actualizado: {result['new_status']}")
                    st.rerun()
                else:
                    st.error(result["error"])
        
        if is_stealth:
            st.caption("🔒 En modo sigilo, los movimientos locales están restringidos a 1 por tick.")

    # --- V15.2: Feedback Visual Persistente (Exploración) ---
    if 'last_exploration_result' in st.session_state:
        res = st.session_state.last_exploration_result
        if res.unit_id == unit.id: # Solo mostrar si corresponde a la unidad actual
            if res.success:
                # Éxito: Mostrar detalles de recursos
                sec_name = res.details.get('name', f"Sector {res.sector_id}")
                res_cat = res.details.get('resource_category', 'Desconocido')
                lux_res = res.details.get('luxury_resource', 'Desconocido')
                
                st.success(f"📍 **Exploración Exitosa**\n\nSector {sec_name} cartografiado. Recursos: {res_cat}, {lux_res}")
            else:
                # Fallo: Diferenciar crítico de normal
                is_critical = res.mrg_result.result_type in [ResultType.CRITICAL_FAILURE, ResultType.TOTAL_FAILURE]
                
                if is_critical:
                    st.error("❌ **FALLO CRÍTICO**: La unidad se ha perdido, pierde sus acciones por el resto del turno.")
                else:
                    st.error("⚠️ **Exploración fallida**: Datos no concluyentes.")
            
            # Widget de resolución MRG en el fragmento
            render_full_mrg_resolution(res.mrg_result)

    # --- V14.6: Lógica de Límites de Movimiento (Visualización Estricta) ---
    if unit.status == UnitStatus.STEALTH_MODE:
        limit_count = 1
    else:
        limit_count = MAX_LOCAL_MOVES_PER_TURN
    
    # Texto para mostrar en la UI
    limit_txt = f"Acciones: {unit.local_moves_count}/{limit_count}"

    if unit.movement_locked:
        st.warning(f"🔒 Movimiento/Acciones Bloqueadas ({limit_txt}). Espera al siguiente tick.")
        if unit.local_moves_count > 0:
             st.caption(f"Acciones realizadas: {unit.local_moves_count}/{limit_count}")
        return

    # Visualización de fatiga/estado antes de las opciones
    if unit.local_moves_count > 0:
         remaining = limit_count - unit.local_moves_count
         st.info(f"⚠️ Unidad parcialmente fatigada. {limit_txt} (Restantes: {remaining})")

    # --- V15.0: SECCIÓN DE ACCIONES TÁCTICAS (Exploración) ---
    if unit.status != UnitStatus.TRANSIT and unit.location_sector_id and unit.location_planet_id:
        sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
        current_sector = next((s for s in sectors if s['id'] == unit.location_sector_id), None)

        if current_sector and not current_sector.get('is_discovered', False):
            st.markdown("### 🔭 Acciones Tácticas")
            
            # V15.1: Deshabilitar si no hay acciones
            can_explore = unit.local_moves_count < limit_count
            
            if can_explore:
                st.info(f"Este sector no ha sido cartografiado. Realiza una exploración para revelar recursos y amenazas. (Consume 1 Acción)")
                if st.button("📡 Explorar Sector Actual", type="primary", use_container_width=True):
                    with st.spinner("Escaneando terreno..."):
                        try:
                            result = resolve_sector_exploration(unit_id, unit.location_sector_id, player_id)
                            # Guardar resultado en sesión para persistencia visual
                            st.session_state.last_exploration_result = result
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error crítico en exploración: {e}")
            else:
                st.warning(f"🚫 Acciones agotadas ({unit.local_moves_count}/{limit_count}). No se puede explorar este turno.")

    movement_result: Optional[Tuple[DestinationData, MovementType, bool]] = None

    if unit.status == UnitStatus.TRANSIT:
        _render_transit_info(unit)
    else:
        ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

        if unit.location_sector_id is not None and unit.location_planet_id is not None:
            sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
            current_sector = next((s for s in sectors if s['id'] == unit.location_sector_id), None)

            if current_sector and current_sector.get('sector_type') == 'Orbital':
                movement_result = _render_orbit_options(unit, player_id, current_tick)
            else:
                movement_result = _render_surface_options(unit, player_id, current_tick)

        elif unit.location_planet_id is not None:
            movement_result = _render_orbit_options(unit, player_id, current_tick)

        elif ring_val == 0:
            movement_result = _render_stellar_options(unit, player_id, current_tick)

        else:
            movement_result = _render_ring_options(unit, player_id, current_tick)

    if movement_result:
        destination, movement_type, use_boost = movement_result

        with st.spinner("Iniciando trayectoria..."):
            result = initiate_movement(
                unit_id=unit_id,
                destination=destination,
                player_id=player_id,
                current_tick=current_tick,
                use_boost=use_boost
            )

        if result.success:
            if result.is_instant:
                st.success(f"Movimiento completado (instantáneo)")
            else:
                st.success(f"Trayectoria iniciada. Tiempo estimado: {result.ticks_required} tick(s)")
                if result.energy_cost > 0:
                    st.info(f"Energía consumida: {result.energy_cost} células")

            # Persistencia de diálogo si es local y quedan movimientos
            should_close = True
            
            if movement_type not in [MovementType.WARP, MovementType.STARLANE]:
                updated_unit_data = get_unit_by_id(unit_id)
                if updated_unit_data:
                    updated_unit = UnitSchema.from_dict(updated_unit_data)
                    # V14.5: Usar límite dinámico estricto para decidir si cerrar
                    if updated_unit.status == UnitStatus.STEALTH_MODE:
                        limit_count = 1
                    else:
                        limit_count = MAX_LOCAL_MOVES_PER_TURN
                    
                    if updated_unit.local_moves_count < limit_count:
                        should_close = False
                        remaining = limit_count - updated_unit.local_moves_count
                        st.toast(f"✅ Posición actualizada. Acciones restantes: {remaining}")

            if should_close:
                st.session_state.selected_unit_movement = None
            
            # Limpiar resultado de exploración anterior al moverse
            if 'last_exploration_result' in st.session_state:
                del st.session_state.last_exploration_result
                
            st.rerun()
        else:
            st.error(f"Error: {result.error_message}")