# ui/faction_roster.py
"""
Comando - Vista jerárquica de personajes, tropas y unidades organizados por ubicación.
V18.0: Refactorización modular - Este archivo actúa como Page Controller.

Historial de versiones:
V11.1-V11.6: Hidratación de nombres, filtrado de sistemas, UI compacta.
V12.0: Integración de diálogo de movimiento, gestión avanzada de miembros.
V13.0-V13.5: Restricción de reclutamiento orbital, fix agrupación tránsito SCO.
V14.1: Integración del Centro de Alertas Tácticas.
V15.0-V15.3: Compatibilidad Híbrida Pydantic V2/Dict, bloqueo de seguridad en tránsito.
V16.0-V16.1: Validaciones de liderazgo, inclusión de tropas iniciales.
V17.0: Visualización de tropas sueltas en Roster.
V18.0: Refactorización modular en ui/logic, ui/components, ui/dialogs.
V18.1: Implementación de botón de Reclutamiento Rápido (No-AI).

Módulos relacionados:
- ui/logic/roster_logic.py: Helpers de acceso seguro y lógica de datos.
- ui/components/roster_widgets.py: Componentes visuales reutilizables.
- ui/dialogs/roster_dialogs.py: Diálogos modales (@st.dialog).
"""

import streamlit as st
import time
from typing import Dict, List, Any, Optional, Set

# --- Repositorios de Datos ---
from data.character_repository import get_all_player_characters
from data.unit_repository import (
    get_units_by_player,
    get_troops_by_player,
    create_troop,
)
from data.world_repository import (
    get_all_systems_from_db,
    get_planets_by_system_id,
)
from data.planet_repository import (
    get_planet_sectors_status,
    get_player_base_coordinates,
)

# --- Modelos Core ---
from core.models import CharacterStatus, KnowledgeLevel

# --- Servicios ---
from services.character_generation_service import recruit_character_with_ai, recruit_initial_crew_fast

# --- Módulos Refactorizados V18.0 ---
from ui.logic.roster_logic import (
    get_prop,
    get_assigned_entity_ids,
    hydrate_unit_members,
    get_systems_with_presence,
    build_location_index,
)
from ui.components.roster_widgets import (
    inject_compact_css,
    render_character_row,
    render_troop_row,
    render_unit_row,
    render_create_unit_button,
    render_starlanes_section,
)

# V14.1: Componentes Tácticos
from ui.components.tactical import (
    render_tactical_alert_center,
    render_debug_simulation_panel,
)


# --- FUNCIONES DE ESTRUCTURA JERÁRQUICA ---

def _render_sector_content(
    sector_id: int,
    sector_type: str,
    player_id: int,
    location_data: Dict[str, Any],
    location_index: dict,
    is_space: bool,
    assigned_char_ids: Set[int],
    assigned_troop_ids: Set[int],
    all_troops: List[Any],
    planet_id: Optional[int] = None,
    all_planet_sector_ids: Optional[Set[int]] = None
):
    """Renderiza contenido de un sector (unidades + personajes sueltos + tropas sueltas + botón crear)."""
    units = location_index["units_by_sector"].get(sector_id, [])
    chars = location_index["chars_by_sector"].get(sector_id, [])

    # V17.0: Tropas sueltas en este sector
    sector_troops = location_index.get("troops_by_sector", {}).get(sector_id, [])

    # Personajes disponibles (no asignados a unidad)
    available_chars_here = [c for c in chars if get_prop(c, "id") not in assigned_char_ids]

    # Tropas disponibles (pool global no asignado)
    available_troops_here = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

    # Determinar si hay contenido real para mostrar
    has_units = len(units) > 0
    has_chars = len(chars) > 0
    has_troops = len(sector_troops) > 0
    # El botón de crear solo es relevante si hay recursos disponibles
    can_create = len(available_chars_here) > 0

    if not has_units and not has_chars and not has_troops and not can_create:
        st.caption("Despejado.")
        return

    # Renderizar unidades primero
    for unit in units:
        render_unit_row(unit, player_id, is_space, available_chars_here, available_troops_here)

    # Renderizar personajes sueltos
    for char in chars:
        render_character_row(char, player_id, is_space)

    # V17.0: Renderizar tropas sueltas
    for troop in sector_troops:
        render_troop_row(troop, is_space)

    # Botón crear unidad (solo con disponibles no asignados)
    if can_create:
        render_create_unit_button(
            sector_id=sector_id,
            player_id=player_id,
            location_data=location_data,
            available_chars=available_chars_here,
            available_troops=available_troops_here,
            is_orbit=is_space and planet_id is not None
        )


def _render_planet_node(
    planet: dict,
    player_id: int,
    location_index: dict,
    assigned_char_ids: Set[int],
    assigned_troop_ids: Set[int],
    all_troops: List[Any],
    is_priority: bool
):
    """Renderiza un nodo de planeta con órbita y sectores."""
    planet_id = planet["id"]
    planet_name = planet.get("name", f"Planeta {planet_id}")

    sectors = get_planet_sectors_status(planet_id, player_id)

    orbit_sector = None
    surface_sectors = []
    all_surface_sector_ids: Set[int] = set()

    # Calcular contadores
    u_count = 0
    surf_count = 0
    space_count = 0

    for s in sectors:
        sid = s["id"]
        stype = s.get("sector_type", "")

        # Unidades en este sector
        units_here = location_index["units_by_sector"].get(sid, [])
        u_count += len(units_here)

        # Personajes sueltos en este sector
        chars_here = location_index["chars_by_sector"].get(sid, [])
        c_count = len(chars_here)

        # V17.0: Tropas sueltas en este sector
        troops_here = location_index.get("troops_by_sector", {}).get(sid, [])
        t_count = len(troops_here)

        if stype == "Orbital":
            orbit_sector = s
            space_count += c_count + t_count
        else:
            surface_sectors.append(s)
            all_surface_sector_ids.add(sid)
            surf_count += c_count + t_count

    # Lógica de Visibilidad Estricta
    has_content = (u_count + surf_count + space_count) > 0

    if has_content:
        header = f"🪐 {planet_name} | 👥({u_count}) - 🪐({surf_count}) - 🌌({space_count})"
        should_expand = is_priority

        with st.expander(header, expanded=should_expand):
            if orbit_sector:
                st.markdown('<div class="comando-section-header">🌌 Órbita</div>', unsafe_allow_html=True)
                orbit_loc = {
                    "system_id": planet.get("system_id"),
                    "planet_id": planet_id,
                    "sector_id": orbit_sector["id"]
                }
                _render_sector_content(
                    sector_id=orbit_sector["id"],
                    sector_type="Orbital",
                    player_id=player_id,
                    location_data=orbit_loc,
                    location_index=location_index,
                    is_space=True,
                    assigned_char_ids=assigned_char_ids,
                    assigned_troop_ids=assigned_troop_ids,
                    all_troops=all_troops,
                    planet_id=planet_id,
                    all_planet_sector_ids=all_surface_sector_ids
                )

            if surface_sectors:
                visible_surface = []
                for s in surface_sectors:
                    sid = s["id"]
                    if location_index["units_by_sector"].get(sid) or location_index["chars_by_sector"].get(sid):
                        visible_surface.append(s)

                if visible_surface:
                    st.markdown('<div class="comando-section-header">🌍 Superficie</div>', unsafe_allow_html=True)
                    for sector in visible_surface:
                        sector_id = sector["id"]
                        sector_name = sector.get("sector_type", "Desconocido")
                        if not sector.get("is_discovered", False):
                            sector_name = f"Sector Desconocido [ID: {sector_id}]"

                        st.caption(f"**{sector_name}**")
                        surface_loc = {
                            "system_id": planet.get("system_id"),
                            "planet_id": planet_id,
                            "sector_id": sector_id
                        }
                        _render_sector_content(
                            sector_id=sector_id,
                            sector_type=sector_name,
                            player_id=player_id,
                            location_data=surface_loc,
                            location_index=location_index,
                            is_space=False,
                            assigned_char_ids=assigned_char_ids,
                            assigned_troop_ids=assigned_troop_ids,
                            all_troops=all_troops
                        )


def _render_system_node(
    system: dict,
    player_id: int,
    location_index: dict,
    assigned_char_ids: Set[int],
    assigned_troop_ids: Set[int],
    all_troops: List[Any],
    is_priority: bool
):
    """Renderiza un nodo de sistema con sectores estelares, anillos y planetas."""
    system_id = system["id"]
    system_name = system.get("name", f"Sistema {system_id}")

    icon = "⭐" if is_priority else "🌟"
    planets = get_planets_by_system_id(system_id)

    # --- Pre-cálculo de contadores del Sistema ---
    sys_u_count = 0
    sys_space_count = 0
    sys_surf_count = 0

    # 1. Unidades y Personajes en espacio (Estrella + Anillos)
    chars_by_ring = location_index.get("chars_by_system_ring", {})
    troops_by_ring = location_index.get("troops_by_system_ring", {})

    for r in range(7):
        key = (system_id, r)
        units = location_index["units_by_system_ring"].get(key, [])
        chars = chars_by_ring.get(key, [])
        troops = troops_by_ring.get(key, [])

        sys_u_count += len(units)
        sys_space_count += len(chars) + len(troops)  # V17.0: Sumar tropas sueltas

    # 2. Contenido de Planetas
    for planet in planets:
        p_sectors = get_planet_sectors_status(planet["id"], player_id)
        for s in p_sectors:
            sid = s["id"]
            stype = s.get("sector_type", "")

            u_here = len(location_index["units_by_sector"].get(sid, []))
            c_here = len(location_index["chars_by_sector"].get(sid, []))
            t_here = len(location_index.get("troops_by_sector", {}).get(sid, []))

            sys_u_count += u_here

            if stype == "Orbital":
                sys_space_count += c_here + t_here
            else:
                sys_surf_count += c_here + t_here

    # Lógica de Visibilidad Estricta
    has_content = (sys_u_count + sys_space_count + sys_surf_count) > 0

    if has_content:
        header = f"{icon} Sistema {system_name} | 👥({sys_u_count}) - 🪐({sys_surf_count}) - 🌌({sys_space_count})"

        with st.expander(header, expanded=is_priority):
            # Sector Estelar (Ring 0)
            stellar_key = (system_id, 0)
            stellar_units = location_index["units_by_system_ring"].get(stellar_key, [])
            stellar_chars = location_index.get("chars_by_system_ring", {}).get(stellar_key, [])
            stellar_troops = location_index.get("troops_by_system_ring", {}).get(stellar_key, [])

            if stellar_units or stellar_chars or stellar_troops:
                st.markdown('<div class="comando-section-header">🌌 Sector Estelar</div>', unsafe_allow_html=True)
                available_chars_space: List[dict] = []
                available_troops_space = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

                # Render Units
                for unit in stellar_units:
                    render_unit_row(unit, player_id, is_space=True,
                                    available_chars=available_chars_space,
                                    available_troops=available_troops_space)
                # Render Chars
                for char in stellar_chars:
                    render_character_row(char, player_id, is_space=True)
                # V17.0: Render Troops
                for troop in stellar_troops:
                    render_troop_row(troop, is_space=True)

                # --- NUEVO V15.3: Botón Crear Unidad en Espacio Profundo (Ring 0) ---
                if stellar_chars:
                    # Generar ID único negativo para evitar colisión con sector_ids reales
                    pseudo_sector_id = -(system_id * 10000)
                    loc_data = {"system_id": system_id, "ring": 0, "sector_id": None}
                    # Tropas disponibles (Pool global no asignado, según lógica existente)
                    avail_troops = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

                    render_create_unit_button(
                        sector_id=pseudo_sector_id,
                        player_id=player_id,
                        location_data=loc_data,
                        available_chars=stellar_chars,
                        available_troops=avail_troops,
                        is_orbit=True
                    )

            # Anillos 1-6
            for ring in range(1, 7):
                ring_key = (system_id, ring)
                ring_units = location_index["units_by_system_ring"].get(ring_key, [])
                ring_chars = location_index.get("chars_by_system_ring", {}).get(ring_key, [])
                ring_troops = location_index.get("troops_by_system_ring", {}).get(ring_key, [])

                if ring_units or ring_chars or ring_troops:
                    st.markdown(f'<div class="comando-section-header">🌌 Anillo {ring}</div>', unsafe_allow_html=True)
                    # Render Units
                    for unit in ring_units:
                        render_unit_row(unit, player_id, is_space=True,
                                        available_chars=[],
                                        available_troops=[t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids])
                    # Render Chars
                    for char in ring_chars:
                        render_character_row(char, player_id, is_space=True)
                    # V17.0: Render Troops
                    for troop in ring_troops:
                        render_troop_row(troop, is_space=True)

                    # --- NUEVO V15.3: Botón Crear Unidad en Anillo (Ring 1-6) ---
                    if ring_chars:
                        pseudo_sector_id = -(system_id * 10000 + ring)
                        loc_data = {"system_id": system_id, "ring": ring, "sector_id": None}
                        avail_troops = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

                        render_create_unit_button(
                            sector_id=pseudo_sector_id,
                            player_id=player_id,
                            location_data=loc_data,
                            available_chars=ring_chars,
                            available_troops=avail_troops,
                            is_orbit=True
                        )

            # Planetas ordenados
            planets_sorted = sorted(planets, key=lambda p: p.get("orbital_ring", 1))
            for planet in planets_sorted:
                _render_planet_node(planet, player_id, location_index,
                                    assigned_char_ids, assigned_troop_ids, all_troops, is_priority)


# --- FUNCIÓN PRINCIPAL ---

def render_comando_page():
    """Punto de entrada principal - Página de Comando."""
    from ui.state import get_player

    inject_compact_css()

    st.title("Comando")

    player = get_player()
    if not player:
        st.warning("Error de sesión. Por favor, inicia sesión nuevamente.")
        return

    player_id = player.id

    # Cargar datos
    with st.spinner("Cargando estructura de comando..."):
        all_characters = get_all_player_characters(player_id)

        # FILTRO DE SEGURIDAD V11.4/11.5:
        roster_characters = [c for c in all_characters if get_prop(c, "status_id") != CharacterStatus.CANDIDATE.value]

        # --- NUEVO: Flujo inicial de reclutamiento ---
        non_commander_count = sum(1 for c in roster_characters if not get_prop(c, "es_comandante", False))

        if non_commander_count == 0:
            st.info("La facción se está estableciendo. Necesitas personal para operar.")
            
            # Layout para los botones de reclutamiento inicial
            c1, c2 = st.columns(2)
            
            with c1:
                if st.button("Reunir al personal (Estándar con IA)", type="primary", use_container_width=True):
                    # Configuración jerárquica: 1x L5, 2x L3, 4x L1
                    recruitment_config = [
                        (5, KnowledgeLevel.KNOWN, "Oficial de Mando"),
                        (3, KnowledgeLevel.KNOWN, "Oficial Técnico"),
                        (3, KnowledgeLevel.KNOWN, "Oficial Táctico"),
                        (1, KnowledgeLevel.UNKNOWN, "Recluta"),
                        (1, KnowledgeLevel.UNKNOWN, "Recluta"),
                        (1, KnowledgeLevel.UNKNOWN, "Recluta"),
                        (1, KnowledgeLevel.UNKNOWN, "Recluta")
                    ]

                    success_count = 0
                    total_ops = len(recruitment_config)

                    # --- V16.1: Obtener coordenadas base para las tropas ---
                    base_coords = get_player_base_coordinates(player_id)
                    loc_data = {
                        "system_id": base_coords.get("system_id"),
                        "planet_id": base_coords.get("planet_id"),
                        "sector_id": base_coords.get("sector_id"),
                        "ring": 0
                    }

                    with st.status("Estableciendo cadena de mando...", expanded=True) as status:
                        # 1. Reclutar Personajes
                        for idx, (level, k_level, label) in enumerate(recruitment_config):
                            status.update(label=f"Reclutando {label} (Nivel {level}) - [{idx+1}/{total_ops}]...")
                            try:
                                recruit_character_with_ai(
                                    player_id=player_id,
                                    min_level=level,
                                    max_level=level,
                                    initial_knowledge_level=k_level
                                )
                                st.write(f"✅ {label} reclutado exitosamente.")
                                success_count += 1
                            except Exception as e:
                                st.write(f"❌ Error reclutando {label}: {e}")
                                print(f"Error en reclutamiento inicial ({label}): {e}")

                        # 2. Generar Tropas Básicas (Infantería)
                        if success_count > 0:
                            status.update(label="Desplegando guarnición de infantería...", state="running")
                            troops_created = 0
                            for i in range(1, 5):
                                t_name = f"Escuadrón de Infantería {i}"
                                try:
                                    new_troop = create_troop(
                                        player_id=player_id,
                                        name=t_name,
                                        troop_type="INFANTRY",
                                        level=1,
                                        location_data=loc_data
                                    )
                                    if new_troop:
                                        st.write(f"✅ {t_name} desplegado en base.")
                                        troops_created += 1
                                    else:
                                        st.write(f"⚠️ Fallo al desplegar {t_name}.")
                                except Exception as e:
                                    st.write(f"❌ Error crítico en despliegue de tropa: {e}")

                        if success_count > 0:
                            status.update(label="¡Personal reunido! Iniciando sistemas...", state="complete", expanded=False)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            status.update(label="Fallo crítico en el reclutamiento.", state="error")
                            st.error("No se pudo establecer la facción. Intenta nuevamente.")

            with c2:
                if st.button("⚡ Reclutamiento Rápido (No-AI)", type="secondary", use_container_width=True, help="Genera 7 unidades de nivel 1 de forma instantánea sin historias complejas."):
                    with st.spinner("⚡ Ejecutando leva forzosa de personal..."):
                        recruit_initial_crew_fast(player_id, count=7)
                        st.success("Dotación inicial desplegada.")
                        time.sleep(0.5)
                        st.rerun()

            return

        # Si hay personal, continuar con carga normal
        troops = get_troops_by_player(player_id)
        units = get_units_by_player(player_id)
        systems = get_all_systems_from_db()

        # Mapas de nombres para hidratación
        char_map: Dict[int, str] = {get_prop(c, "id"): get_prop(c, "nombre", f"Personaje {get_prop(c, 'id')}") for c in all_characters}
        troop_map: Dict[int, str] = {get_prop(t, "id"): get_prop(t, "name", f"Tropa {get_prop(t, 'id')}") for t in troops}

        # Hidratar nombres de miembros
        units = hydrate_unit_members(units, char_map, troop_map)

        # Obtener IDs asignados
        assigned_chars, assigned_troops = get_assigned_entity_ids(units)

        # Construir índice de ubicaciones USANDO ROSTER FILTRADO
        # V17.0: Incluir tropas para visualización de tropas sueltas
        location_index = build_location_index(
            roster_characters, units, assigned_chars,
            troops=troops, assigned_troop_ids=assigned_troops
        )

        # Obtener sistemas con presencia del jugador USANDO ROSTER FILTRADO
        systems_with_presence = get_systems_with_presence(location_index, roster_characters, assigned_chars)

    # Estadísticas rápidas
    roster_loose_chars = len(roster_characters) - len([cid for cid in assigned_chars if any(get_prop(c, "id") == cid for c in roster_characters)])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Personajes", len(all_characters), f"{roster_loose_chars} sueltos (Roster)")
    with col2:
        st.metric("Unidades", len(units))
    with col3:
        st.metric("En Tránsito", len(location_index["units_in_transit"]))

    # V14.1: Centro de Alertas Tácticas
    if units:
        with st.expander("📡 Centro de Alertas Tácticas", expanded=False):
            render_tactical_alert_center(player_id, units, show_header=False)

    st.divider()

    # Filtrar solo sistemas con presencia
    systems_to_show = [s for s in systems if s["id"] in systems_with_presence]

    if not systems_to_show and not location_index["units_in_transit"]:
        st.info("No hay personal desplegado en ningún sistema. Recluta personajes y forma unidades.")
        return

    # Renderizar sistemas con presencia
    for system in systems_to_show:
        is_priority = True  # Todos los que se muestran tienen presencia
        _render_system_node(
            system, player_id, location_index,
            assigned_chars, assigned_troops, troops, is_priority
        )

    # Starlanes
    if location_index["units_in_transit"]:
        st.divider()
        with st.expander("🌌 Rutas Estelares (Starlanes)", expanded=True):
            render_starlanes_section(location_index, player_id, [], [])

    # V14.1: Panel de Debug para Simulación de Detección
    st.divider()
    render_debug_simulation_panel(player_id, units)


# Alias para compatibilidad
def render_faction_roster():
    """Alias para compatibilidad con código existente."""
    render_comando_page()