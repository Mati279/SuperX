# ui/movement_console.py (Completo)
"""
Control de Movimiento - Vista para gestionar el movimiento de unidades.
V10.1: Implementación inicial con opciones dinámicas según ubicación.
V12.0: Adaptación para uso en componente/diálogo (eliminación de navegación de página).
V12.1: Reorganización de UI - Botones de acción movidos arriba de los selectores e iconografía actualizada.
V12.2: Fix de bloqueo - UI permite 2 movimientos locales antes de bloquear acciones.
V13.0: Refactorización de Navegación - Restricciones físicas estrictas y soporte para maniobras de acople instantáneas.

Flujo:
1. El jugador selecciona una unidad desde faction_roster (botón 🚀)
2. Se guarda unit_id en st.session_state.selected_unit_movement
3. Se muestra este componente (normalmente en un diálogo)

Reglas de Destino según Ubicación (V13.0):
- Sector Planetario (Superficie): Otro sector / Ascender a órbita.
- Órbita Planetaria: Bajar a sector / Salir al espacio exterior (Anillo Orbital). *SIN STARLANE/WARP*
- Anillo (no orbital): Mover a órbita / Otro anillo (existente) / Starlane / WARP.
- Sector Estelar (Ring 0): Anillos interiores (existentes) / Starlane / WARP.
"""

import streamlit as st
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
)
from core.movement_constants import RING_STELLAR, RING_MIN, RING_MAX
from data.world_repository import get_world_state


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
    </style>
    """, unsafe_allow_html=True)


def _get_location_type(unit: UnitSchema) -> str:
    """
    Determina el tipo de ubicación de la unidad.

    Returns:
        'transit' | 'surface' | 'orbit' | 'ring' | 'stellar'
    """
    if unit.status == UnitStatus.TRANSIT:
        return 'transit'

    # Si tiene sector_id, está en superficie u órbita de un planeta
    if unit.location_sector_id is not None:
        # Necesitamos verificar si el sector es orbital o de superficie
        # Por ahora asumimos que si está en un sector con planet_id, verificamos el tipo
        return 'surface_or_orbit'

    # Si tiene planet_id pero no sector_id, está en órbita genérica del planeta
    if unit.location_planet_id is not None:
        return 'orbit'

    # Si solo tiene system_id, está en espacio del sistema
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

    if unit.status == UnitStatus.TRANSIT:
        origin_sys = get_system_by_id(unit.transit_origin_system_id)
        dest_sys = get_system_by_id(unit.transit_destination_system_id)
        info['system'] = f"{origin_sys.get('name', '?') if origin_sys else '?'} → {dest_sys.get('name', '?') if dest_sys else '?'}"
        info['status_text'] = f"En Tránsito ({unit.transit_ticks_remaining} ticks)"
        info['status_class'] = 'loc-transit'
        return info

    # Sistema
    if unit.location_system_id:
        system = get_system_by_id(unit.location_system_id)
        info['system'] = system.get('name', f'Sistema {unit.location_system_id}') if system else f'Sistema {unit.location_system_id}'

    # Ring
    ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring
    if ring_val == 0:
        info['ring'] = 'Sector Estelar'
        info['status_text'] = 'Sector Estelar (Espacio Profundo)'
        info['status_class'] = 'loc-space'
    else:
        info['ring'] = f'Anillo {ring_val}'

    # Planeta
    if unit.location_planet_id:
        planet = get_planet_by_id(unit.location_planet_id)
        info['planet'] = planet.get('name', f'Planeta {unit.location_planet_id}') if planet else f'Planeta {unit.location_planet_id}'

    # Sector
    if unit.location_sector_id:
        # Determinar si es orbital o superficie
        if unit.location_planet_id:
            sectors = get_planet_sectors_status(unit.location_planet_id, unit.player_id)
            sector_data = next((s for s in sectors if s['id'] == unit.location_sector_id), None)
            if sector_data:
                sector_type = sector_data.get('sector_type', 'Desconocido')
                info['sector'] = sector_type
                if sector_type == 'Orbital':
                    info['status_text'] = f'Órbita de {info["planet"]}'
                    info['status_class'] = 'loc-orbit'
                else:
                    info['status_text'] = f'{sector_type} - {info["planet"]}'
                    info['status_class'] = 'loc-surface'
    elif unit.location_planet_id:
        info['status_text'] = f'Órbita de {info["planet"]}'
        info['status_class'] = 'loc-orbit'
    elif ring_val > 0:
        info['status_text'] = f'Anillo {ring_val} - Espacio'
        info['status_class'] = 'loc-space'

    return info


def _render_unit_info(unit: UnitSchema, location_info: Dict[str, str]):
    """Renderiza información de la unidad seleccionada."""
    st.markdown(f"""
    <div class="movement-header">
        <h4 style="margin:0">👥 {unit.name}</h4>
        <div style="margin-top:5px">
            <span class="location-badge {location_info['status_class']}">{location_info['status_text']}</span>
        </div>
        <p style="margin-top: 5px; color: #bbb; font-size: 0.9em">
            Sistema: <strong>{location_info['system']}</strong>
            {f" | Miembros: <strong>{len(unit.members)}/8</strong>" if unit.members else ""}
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
        energy_class = "cost-warning" if has_penalty else ""
        penalty_text = " (Penalización 2x)" if has_penalty else ""
        st.markdown(f"""
        <div class="cost-display">
            Tiempo: <strong>{ticks} Tick(s)</strong> |
            Energía: <span class="{energy_class}"><strong>{energy}</strong> células{penalty_text}</span>
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
    """
    Retorna lista de anillos válidos (poblados o estelar) para el sistema.
    V13.0: Solo muestra Ring 0 y anillos que contengan planetas.
    """
    planets = get_planets_by_system_id(system_id)
    populated_rings = {p.get('orbital_ring', 1) for p in planets}
    valid_rings = {0} | populated_rings
    return sorted(list(valid_rings))


def _render_surface_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType]]:
    """
    Opciones cuando la unidad está en superficie de un planeta.
    """
    st.markdown("#### Opciones de Movimiento")

    planet_id = unit.location_planet_id
    system_id = unit.location_system_id
    current_sector_id = unit.location_sector_id

    # Obtener sectores del planeta
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
                # Superficie a superficie sigue usando el ring orbital como referencia
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
        return (selected_dest, selected_type)
    return None


def _render_orbit_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType]]:
    """
    Opciones cuando la unidad está en órbita de un planeta.
    V13.0: Restricción estricta.
    - Descender a superficie.
    - Salir al espacio exterior (Solo al anillo orbital del planeta).
    - WARP/Starlane ELIMINADOS (Requieren salir al espacio exterior primero).
    """
    st.markdown("#### Opciones de Movimiento")

    planet_id = unit.location_planet_id
    system_id = unit.location_system_id
    current_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    planet = get_planet_by_id(planet_id)
    planet_name = planet.get('name', f'Planeta {planet_id}') if planet else f'Planeta {planet_id}'
    orbital_ring = planet.get('orbital_ring', current_ring) if planet else current_ring

    selected_dest = None
    selected_type = None

    # Obtener sectores del planeta
    sectors = get_planet_sectors_status(planet_id, player_id)
    surface_sectors = [s for s in sectors if s.get('sector_type') != 'Orbital']

    # V13.0: Solo 2 pestañas permitidas
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

        # V13.0: Destino fijo = Anillo orbital del planeta
        # Al salir al mismo anillo, la distancia es 0 -> Engine retorna 0 ticks/instantáneo.
        estimate = estimate_travel_time(system_id, system_id, current_ring, orbital_ring)
        
        with action_container:
            _render_cost_display(estimate)

            if st.button("Salir al Espacio Exterior", type="primary", key="btn_exit_orbit", use_container_width=True):
                selected_dest = DestinationData(
                    system_id=system_id,
                    planet_id=None,  # Ya no está en el planeta
                    sector_id=None,
                    ring=orbital_ring
                )
                # Al salir al mismo anillo, es una maniobra orbital instantánea
                selected_type = MovementType.SURFACE_ORBIT

    if selected_dest and selected_type:
        return (selected_dest, selected_type)
    return None


def _render_ring_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType]]:
    """
    Opciones cuando la unidad está en un anillo (no en órbita).
    V13.0: Selector de anillo dinámico.
    """
    st.markdown("#### Opciones de Movimiento")

    system_id = unit.location_system_id
    current_ring = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

    # Buscar planetas en el anillo actual
    planets_in_system = get_planets_by_system_id(system_id)
    planets_in_ring = [p for p in planets_in_system if p.get('orbital_ring') == current_ring]

    starlanes = _get_starlanes_from_system(system_id)

    selected_dest = None
    selected_type = None

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

                # La entrada a órbita en el mismo anillo es instantánea (0 ticks)
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
                            # Se clasifica como SURFACE_ORBIT para indicar maniobra instantánea
                            selected_type = MovementType.SURFACE_ORBIT
                    else:
                        st.warning("El planeta no tiene sector orbital definido.")
        else:
            st.info(f"No hay planetas en el Anillo {current_ring}.")

    with tab2:
        st.markdown("**🔄 Navegación Intra-Sistema**")
        action_container = st.container()

        # V13.0: Anillos dinámicos
        valid_rings = _get_valid_rings_for_selector(system_id)
        
        # Filtramos para no mostrar destino = origen en el selector
        selectable_rings = [r for r in valid_rings if r != current_ring]

        ring_labels = {0: "Sector Estelar (Ring 0)"}
        for r in range(RING_MIN, RING_MAX + 1):
            ring_labels[r] = f"Anillo {r}"

        # Mostrar indicador de posición actual
        current_label = ring_labels.get(current_ring, f"Ring {current_ring}")
        st.info(f"📍 Posición Actual: **{current_label}**")

        if selectable_rings:
            selected_ring = st.selectbox(
                "Anillo destino",
                options=selectable_rings,
                format_func=lambda x: ring_labels.get(x, f"Ring {x}"),
                key="select_ring_space"
            )

            if selected_ring is not None:
                # V13.0: estimate_travel_time ahora calcula ticks reales por distancia
                estimate = estimate_travel_time(system_id, system_id, current_ring, selected_ring)
                
                with action_container:
                    _render_cost_display(estimate)

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
                estimate = estimate_travel_time(system_id, selected_lane_dest, current_ring, 0)
                
                with action_container:
                    _render_cost_display(estimate)

                    if st.button("Iniciar Viaje por Starlane", type="primary", key="btn_starlane_space", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_lane_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                        )
                        selected_type = MovementType.STARLANE
        else:
            st.info("No hay Starlanes conectadas a este sistema.")

    with tab4:
        st.markdown("**⚡ Salto WARP**")
        action_container = st.container()

        if current_ring > 0:
            st.warning("WARP desde un anillo planetario tiene penalización de energía x2")

        all_systems = get_all_systems_from_db()
        other_systems = [s for s in all_systems if s['id'] != system_id]

        if other_systems:
            sys_options = {s['id']: s.get('name', f"Sistema {s['id']}") for s in other_systems}
            selected_warp_dest = st.selectbox(
                "Sistema destino",
                options=list(sys_options.keys()),
                format_func=lambda x: sys_options.get(x, str(x)),
                key="select_warp_space"
            )

            if selected_warp_dest:
                estimate = estimate_travel_time(
                    system_id, selected_warp_dest,
                    origin_ring=current_ring,
                    dest_ring=0,
                    ship_count=unit.ship_count
                )
                
                with action_container:
                    _render_cost_display(estimate, unit.ship_count)

                    if st.button("Iniciar Salto WARP", type="primary", key="btn_warp_space", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_warp_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                        )
                        selected_type = MovementType.WARP
        else:
            st.info("No hay otros sistemas disponibles.")

    if selected_dest and selected_type:
        return (selected_dest, selected_type)
    return None


def _render_stellar_options(
    unit: UnitSchema,
    player_id: int,
    current_tick: int
) -> Optional[Tuple[DestinationData, MovementType]]:
    """
    Opciones cuando la unidad está en el Sector Estelar (Ring 0).
    """
    st.markdown("#### Opciones de Movimiento")

    system_id = unit.location_system_id
    current_ring = 0  # Sector Estelar

    starlanes = _get_starlanes_from_system(system_id)

    selected_dest = None
    selected_type = None

    tab1, tab2, tab3 = st.tabs(["Anillos Interiores", "Starlane", "WARP"])

    with tab1:
        st.markdown("**🔄 Mover a Anillo Interior**")
        action_container = st.container()

        # V13.0: Anillos dinámicos
        valid_rings = _get_valid_rings_for_selector(system_id)
        selectable_rings = [r for r in valid_rings if r != current_ring]

        ring_labels = {}
        for r in range(RING_MIN, RING_MAX + 1):
            ring_labels[r] = f"Anillo {r}"
            
        st.info(f"📍 Posición Actual: **Sector Estelar (Ring 0)**")

        if selectable_rings:
            selected_ring = st.selectbox(
                "Anillo destino",
                options=selectable_rings,
                format_func=lambda x: ring_labels.get(x, f"Ring {x}"),
                key="select_ring_stellar"
            )

            if selected_ring is not None:
                estimate = estimate_travel_time(system_id, system_id, current_ring, selected_ring)
                
                with action_container:
                    _render_cost_display(estimate)

                    if st.button("Iniciar Maniobra", type="primary", key="btn_ring_stellar", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=system_id,
                            planet_id=None,
                            sector_id=None,
                            ring=selected_ring
                        )
                        selected_type = MovementType.INTER_RING
        else:
            st.info("No hay anillos poblados en este sistema.")

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
                estimate = estimate_travel_time(system_id, selected_lane_dest, current_ring, 0)
                
                with action_container:
                    _render_cost_display(estimate)

                    if st.button("Iniciar Viaje por Starlane", type="primary", key="btn_starlane_stellar", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_lane_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                        )
                        selected_type = MovementType.STARLANE
        else:
            st.info("No hay Starlanes conectadas a este sistema.")

    with tab3:
        st.markdown("**⚡ Salto WARP**")
        st.success("WARP desde el Sector Estelar: Costo de energía normal (sin penalización)")
        action_container = st.container()

        all_systems = get_all_systems_from_db()
        other_systems = [s for s in all_systems if s['id'] != system_id]

        if other_systems:
            sys_options = {s['id']: s.get('name', f"Sistema {s['id']}") for s in other_systems}
            selected_warp_dest = st.selectbox(
                "Sistema destino",
                options=list(sys_options.keys()),
                format_func=lambda x: sys_options.get(x, str(x)),
                key="select_warp_stellar"
            )

            if selected_warp_dest:
                estimate = estimate_travel_time(
                    system_id, selected_warp_dest,
                    origin_ring=current_ring,
                    dest_ring=0,
                    ship_count=unit.ship_count
                )
                
                with action_container:
                    _render_cost_display(estimate, unit.ship_count)

                    if st.button("Iniciar Salto WARP", type="primary", key="btn_warp_stellar", use_container_width=True):
                        selected_dest = DestinationData(
                            system_id=selected_warp_dest,
                            planet_id=None,
                            sector_id=None,
                            ring=0
                        )
                        selected_type = MovementType.WARP
        else:
            st.info("No hay otros sistemas disponibles.")

    if selected_dest and selected_type:
        return (selected_dest, selected_type)
    return None


def _render_transit_info(unit: UnitSchema):
    """Muestra información cuando la unidad está en tránsito."""
    st.warning("Esta unidad está en tránsito interestelar")

    origin_sys = get_system_by_id(unit.transit_origin_system_id)
    dest_sys = get_system_by_id(unit.transit_destination_system_id)

    origin_name = origin_sys.get('name', '???') if origin_sys else '???'
    dest_name = dest_sys.get('name', '???') if dest_sys else '???'

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Origen", origin_name)
    with col2:
        st.metric("Destino", dest_name)
    with col3:
        st.metric("Ticks Restantes", unit.transit_ticks_remaining)

    # Barra de progreso
    if unit.transit_end_tick and unit.transit_origin_system_id:
        world_state = get_world_state()
        current_tick = world_state.get('current_tick', 0)

        # Calcular progreso (aproximado)
        total_ticks = unit.transit_ticks_remaining + (current_tick - (unit.transit_end_tick - unit.transit_ticks_remaining))
        if total_ticks > 0:
            progress = 1 - (unit.transit_ticks_remaining / max(1, total_ticks))
            st.progress(min(1.0, max(0.0, progress)), text=f"Progreso del viaje: {progress*100:.0f}%")

    st.info("Los controles de movimiento estarán disponibles cuando la unidad llegue a su destino.")


def render_movement_console():
    """Punto de entrada principal - Página de Control de Movimiento."""
    from .state import get_player

    _inject_movement_css()
    
    player = get_player()
    if not player:
        st.error("Error de sesión. Por favor, inicia sesión nuevamente.")
        return

    player_id = player.id

    # Verificar si hay una unidad seleccionada
    unit_id = st.session_state.get('selected_unit_movement')

    if not unit_id:
        st.warning("No hay unidad seleccionada.")
        return

    # Cargar datos de la unidad
    unit_data = get_unit_by_id(unit_id)

    if not unit_data:
        st.error(f"No se encontró la unidad con ID {unit_id}")
        st.session_state.selected_unit_movement = None
        return

    # Verificar propiedad
    if unit_data.get('player_id') != player_id:
        st.error("No tienes control de esta unidad.")
        st.session_state.selected_unit_movement = None
        return

    # Convertir a UnitSchema
    unit = UnitSchema.from_dict(unit_data)

    # Obtener tick actual
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 0)

    # Mostrar información de la unidad
    location_info = _get_location_display(unit)
    _render_unit_info(unit, location_info)

    # --- V12.2: FIX BLOQUEO - Validar bloqueo pero permitir 2 movimientos locales ---
    if unit.movement_locked:
        if unit.local_moves_count < 2:
             st.info(f"⚠️ Unidad parcialmente fatigada. Queda **{2 - unit.local_moves_count}** movimiento local disponible este tick.")
        else:
            st.warning("🔒 Esta unidad ha alcanzado su límite de movimientos y está bloqueada hasta el próximo tick.")
            if unit.local_moves_count > 0:
                 st.caption(f"Movimientos locales realizados: {unit.local_moves_count}/2")
            return

    # Determinar tipo de ubicación y mostrar opciones correspondientes
    movement_result: Optional[Tuple[DestinationData, MovementType]] = None

    if unit.status == UnitStatus.TRANSIT:
        _render_transit_info(unit)
    else:
        # Determinar ubicación específica
        ring_val = unit.ring.value if isinstance(unit.ring, LocationRing) else unit.ring

        if unit.location_sector_id is not None and unit.location_planet_id is not None:
            # Está en un sector de un planeta - verificar si es orbital o superficie
            sectors = get_planet_sectors_status(unit.location_planet_id, player_id)
            current_sector = next((s for s in sectors if s['id'] == unit.location_sector_id), None)

            if current_sector and current_sector.get('sector_type') == 'Orbital':
                movement_result = _render_orbit_options(unit, player_id, current_tick)
            else:
                movement_result = _render_surface_options(unit, player_id, current_tick)

        elif unit.location_planet_id is not None:
            # Órbita genérica del planeta (sin sector específico)
            movement_result = _render_orbit_options(unit, player_id, current_tick)

        elif ring_val == 0:
            # Sector Estelar
            movement_result = _render_stellar_options(unit, player_id, current_tick)

        else:
            # Anillo genérico
            movement_result = _render_ring_options(unit, player_id, current_tick)

    # Ejecutar movimiento si se seleccionó un destino
    if movement_result:
        destination, movement_type = movement_result

        with st.spinner("Iniciando trayectoria..."):
            result = initiate_movement(
                unit_id=unit_id,
                destination=destination,
                player_id=player_id,
                current_tick=current_tick
            )

        if result.success:
            if result.is_instant:
                st.success(f"Movimiento completado (instantáneo)")
            else:
                st.success(f"Trayectoria iniciada. Tiempo estimado: {result.ticks_required} tick(s)")
                if result.energy_cost > 0:
                    st.info(f"Energía consumida: {result.energy_cost} células")

            # Limpiar selección y cerrar diálogo
            st.session_state.selected_unit_movement = None
            st.rerun()
        else:
            st.error(f"Error: {result.error_message}")