# ui/faction_roster.py
"""
Comando - Vista jerárquica de personajes, tropas y unidades organizados por ubicación.
V11.0: Rework completo con estructura colapsable Sistema -> Planeta -> Sector.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Set, Tuple

from data.character_repository import (
    get_all_player_characters,
    get_character_knowledge_level,
)
from data.unit_repository import (
    get_units_by_player,
    get_troops_by_player,
    create_unit,
    add_unit_member,
    rename_unit,
    delete_unit,
)
from data.world_repository import (
    get_all_systems_from_db,
    get_planets_by_system_id,
)
from data.planet_repository import (
    get_all_player_planets,
    get_planet_sectors_status,
)
from core.models import CommanderData, KnowledgeLevel
from ui.character_sheet import render_character_sheet


# --- CSS COMPACTO ---

def _inject_compact_css():
    """Inyecta CSS para reducir altura de filas."""
    st.markdown("""
    <style>
    .comando-entity-row {
        display: flex;
        align-items: center;
        padding: 3px 6px;
        margin: 1px 0;
        border-bottom: 1px solid #2a2a2a;
        font-size: 0.9em;
        gap: 8px;
    }
    .comando-entity-row:hover {
        background: rgba(255,255,255,0.03);
    }
    .comando-unit-header {
        background: rgba(69,183,209,0.1);
        border-left: 3px solid #45b7d1;
        padding: 4px 10px;
        margin: 4px 0;
        font-weight: 500;
    }
    .comando-section-header {
        font-size: 0.85em;
        color: #888;
        padding: 2px 0;
        margin-top: 8px;
    }
    .loc-space { color: #45b7d1; }
    .loc-ground { color: #2ecc71; }
    .loyalty-high { color: #2ecc71; }
    .loyalty-mid { color: #f1c40f; }
    .loyalty-low { color: #e74c3c; }
    div[data-testid="stExpander"] details summary {
        padding: 6px 12px;
        font-size: 0.95em;
    }
    div[data-testid="stExpander"] details > div {
        padding: 4px 8px;
    }
    </style>
    """, unsafe_allow_html=True)


# --- DIALOGS ---

@st.dialog("Ficha de Personal", width="large")
def view_character_dialog(char_dict: dict, player_id: int):
    """Modal para ver ficha completa de personaje."""
    render_character_sheet(char_dict, player_id)


@st.dialog("Crear Unidad", width="large")
def create_unit_dialog(
    sector_id: int,
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[dict],
    available_troops: List[dict],
    is_orbit: bool = False
):
    """Dialog para crear una nueva unidad."""
    st.subheader("Formar Nueva Unidad")

    if is_orbit:
        st.info("En órbita puedes embarcar personal de superficie.")

    unit_name = st.text_input("Nombre de la Unidad", value="Escuadrón Alfa")

    st.markdown("**Seleccionar Miembros** (Máx 8, Mín 1 Personaje)")

    # Personajes
    char_options = {c["id"]: f"👤 {c.get('nombre', 'Sin nombre')} (Nvl {c.get('level', 1)})" for c in available_chars}
    selected_char_ids = st.multiselect(
        "Personajes (Líder obligatorio)",
        options=list(char_options.keys()),
        format_func=lambda x: char_options.get(x, str(x)),
        max_selections=8
    )

    remaining_slots = 8 - len(selected_char_ids)

    # Tropas
    troop_options = {t["id"]: f"🪖 {t.get('name', 'Tropa')} ({t.get('type', 'INF')})" for t in available_troops}
    selected_troop_ids = st.multiselect(
        "Tropas",
        options=list(troop_options.keys()),
        format_func=lambda x: troop_options.get(x, str(x)),
        max_selections=remaining_slots,
        disabled=remaining_slots <= 0
    )

    total = len(selected_char_ids) + len(selected_troop_ids)
    has_leader = len(selected_char_ids) >= 1

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Miembros", f"{total}/8")
    with col2:
        if has_leader:
            st.success("Líder asignado")
        else:
            st.warning("Falta líder")

    if total > 8:
        st.error("Máximo 8 miembros por unidad.")

    can_create = has_leader and total <= 8 and total > 0 and unit_name.strip()

    if st.button("Crear Unidad", type="primary", disabled=not can_create, use_container_width=True):
        new_unit = create_unit(player_id, unit_name.strip(), location_data)
        if new_unit:
            unit_id = new_unit["id"]
            slot = 0
            for char_id in selected_char_ids:
                add_unit_member(unit_id, "character", char_id, slot)
                slot += 1
            for troop_id in selected_troop_ids:
                add_unit_member(unit_id, "troop", troop_id, slot)
                slot += 1
            st.success(f"Unidad '{unit_name}' creada.")
            st.rerun()
        else:
            st.error("Error al crear unidad.")


@st.dialog("Gestionar Unidad", width="small")
def manage_unit_dialog(unit: dict, player_id: int):
    """Dialog para renombrar o disolver unidad."""
    unit_id = unit["id"]
    current_name = unit.get("name", "Unidad")

    st.subheader(f"Gestionar: {current_name}")

    # Renombrar
    new_name = st.text_input("Nuevo nombre", value=current_name)
    if st.button("Renombrar", use_container_width=True, disabled=not new_name.strip() or new_name == current_name):
        if rename_unit(unit_id, new_name.strip(), player_id):
            st.success("Nombre actualizado.")
            st.rerun()
        else:
            st.error("Error al renombrar.")

    st.divider()

    # Disolver
    st.markdown("**Disolver Unidad**")
    st.caption("Los miembros quedarán sueltos en la ubicación actual.")
    if st.button("Disolver Unidad", type="secondary", use_container_width=True):
        if delete_unit(unit_id, player_id):
            st.success("Unidad disuelta.")
            st.rerun()
        else:
            st.error("Error al disolver.")


# --- HELPERS DE DATOS ---

def _get_assigned_entity_ids(units: List[dict]) -> Tuple[Set[int], Set[int]]:
    """Retorna sets de IDs de characters y troops asignados a unidades."""
    assigned_chars = set()
    assigned_troops = set()
    for unit in units:
        for member in unit.get("members", []):
            etype = member.get("entity_type")
            eid = member.get("entity_id")
            if etype == "character":
                assigned_chars.add(eid)
            elif etype == "troop":
                assigned_troops.add(eid)
    return assigned_chars, assigned_troops


def _get_player_system_ids(player_id: int) -> Set[int]:
    """Obtiene IDs de sistemas donde el jugador tiene assets."""
    assets = get_all_player_planets(player_id)
    system_ids = set()
    for asset in assets:
        planet_data = asset.get("planets", {})
        sys_id = planet_data.get("system_id") or asset.get("system_id")
        if sys_id:
            system_ids.add(sys_id)
    return system_ids


def _build_location_index(
    characters: List[dict],
    units: List[dict],
    assigned_char_ids: Set[int]
) -> Dict[str, Any]:
    """
    Construye índice de entidades por ubicación.
    Retorna dict con claves:
    - 'chars_by_sector': {sector_id: [chars]}
    - 'units_by_sector': {sector_id: [units]}
    - 'units_by_system_ring': {(system_id, ring): [units]}
    - 'units_in_transit': [units]
    """
    chars_by_sector: Dict[int, List[dict]] = {}
    units_by_sector: Dict[int, List[dict]] = {}
    units_by_system_ring: Dict[Tuple[int, int], List[dict]] = {}
    units_in_transit: List[dict] = []

    # Personajes sueltos por sector
    for char in characters:
        if char["id"] in assigned_char_ids:
            continue
        sector_id = char.get("location_sector_id")
        if sector_id:
            if sector_id not in chars_by_sector:
                chars_by_sector[sector_id] = []
            chars_by_sector[sector_id].append(char)

    # Unidades por ubicación
    for unit in units:
        status = unit.get("status", "GROUND")
        if status == "TRANSIT":
            units_in_transit.append(unit)
            continue

        sector_id = unit.get("location_sector_id")
        if sector_id:
            if sector_id not in units_by_sector:
                units_by_sector[sector_id] = []
            units_by_sector[sector_id].append(unit)
        else:
            # Unidad en espacio (ring sin planeta)
            system_id = unit.get("location_system_id")
            ring = unit.get("ring", 0)
            if system_id:
                key = (system_id, ring)
                if key not in units_by_system_ring:
                    units_by_system_ring[key] = []
                units_by_system_ring[key].append(unit)

    return {
        "chars_by_sector": chars_by_sector,
        "units_by_sector": units_by_sector,
        "units_by_system_ring": units_by_system_ring,
        "units_in_transit": units_in_transit,
    }


# --- RENDERIZADO ---

def _render_loyalty_badge(loyalty: int) -> str:
    """Retorna badge de lealtad con color."""
    if loyalty < 30:
        return f'<span class="loyalty-low">{loyalty}%</span>'
    elif loyalty < 70:
        return f'<span class="loyalty-mid">{loyalty}%</span>'
    return f'<span class="loyalty-high">{loyalty}%</span>'


def _render_character_row(char: dict, player_id: int, is_space: bool):
    """Renderiza fila de personaje suelto."""
    char_id = char["id"]
    nombre = char.get("nombre", "???")
    nivel = char.get("level", 1)
    loyalty = char.get("loyalty", 50)

    icon = "🌌" if is_space else "🌍"
    loc_class = "loc-space" if is_space else "loc-ground"
    loyalty_html = _render_loyalty_badge(loyalty)

    cols = st.columns([0.5, 4, 1.5, 1])
    with cols[0]:
        st.markdown(f'<span class="{loc_class}">{icon}</span>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"👤 **{nombre}** (Nvl {nivel})")
    with cols[2]:
        st.markdown(f"Lealtad: {loyalty_html}", unsafe_allow_html=True)
    with cols[3]:
        if st.button("📄", key=f"sheet_char_{char_id}", help="Ver ficha"):
            view_character_dialog(char, player_id)


def _render_unit_row(unit: dict, player_id: int, is_space: bool):
    """Renderiza fila de unidad con expander para miembros."""
    unit_id = unit["id"]
    name = unit.get("name", "Unidad")
    members = unit.get("members", [])
    status = unit.get("status", "GROUND")

    icon = "🌌" if is_space else "🌍"
    status_emoji = {"GROUND": "🏕️", "SPACE": "🚀", "TRANSIT": "✈️"}.get(status, "❓")

    with st.container():
        st.markdown(f'<div class="comando-unit-header">{icon} 🎖️ <strong>{name}</strong> ({len(members)}/8) {status_emoji}</div>', unsafe_allow_html=True)

        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("⚙️", key=f"manage_unit_{unit_id}", help="Gestionar unidad"):
                manage_unit_dialog(unit, player_id)

        if members:
            with st.expander(f"Miembros ({len(members)})", expanded=False):
                for m in sorted(members, key=lambda x: x.get("slot_index", 0)):
                    etype = m.get("entity_type", "?")
                    eid = m.get("entity_id")
                    slot = m.get("slot_index", 0)

                    if etype == "character":
                        member_name = m.get("name", f"Personaje #{eid}")
                        st.markdown(f"`[{slot}]` 👤 {member_name}")
                    else:
                        member_name = m.get("name", f"Tropa #{eid}")
                        st.markdown(f"`[{slot}]` 🪖 {member_name}")


def _render_create_unit_button(
    sector_id: int,
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[dict],
    available_troops: List[dict],
    is_orbit: bool = False
):
    """Renderiza botón para crear unidad si hay entidades disponibles."""
    total_available = len(available_chars) + len(available_troops)

    if total_available == 0:
        return

    if not available_chars:
        st.caption("Se requiere al menos 1 personaje para formar unidad.")
        return

    if st.button("👥 Crear Unidad", key=f"create_unit_{sector_id}", help="Formar nueva unidad"):
        create_unit_dialog(
            sector_id=sector_id,
            player_id=player_id,
            location_data=location_data,
            available_chars=available_chars,
            available_troops=available_troops,
            is_orbit=is_orbit
        )


def _render_sector_content(
    sector_id: int,
    sector_type: str,
    player_id: int,
    location_data: Dict[str, Any],
    location_index: dict,
    is_space: bool,
    planet_id: Optional[int] = None,
    all_planet_sector_ids: Optional[Set[int]] = None
):
    """Renderiza contenido de un sector (unidades + personajes sueltos + botón crear)."""
    units = location_index["units_by_sector"].get(sector_id, [])
    chars = location_index["chars_by_sector"].get(sector_id, [])

    # Para órbita: incluir entidades de superficie
    orbit_chars = []

    if is_space and all_planet_sector_ids:
        for sid in all_planet_sector_ids:
            orbit_chars.extend(location_index["chars_by_sector"].get(sid, []))

    # Renderizar unidades primero
    for unit in units:
        _render_unit_row(unit, player_id, is_space)

    # Renderizar personajes sueltos
    for char in chars:
        _render_character_row(char, player_id, is_space)

    # Botón crear unidad
    available_chars = chars + orbit_chars if is_space else chars
    _render_create_unit_button(
        sector_id=sector_id,
        player_id=player_id,
        location_data=location_data,
        available_chars=available_chars,
        available_troops=[],  # Tropas no tienen ubicación suelta
        is_orbit=is_space and planet_id is not None
    )


def _render_planet_node(
    planet: dict,
    player_id: int,
    location_index: dict,
    is_priority: bool
):
    """Renderiza un nodo de planeta con órbita y sectores."""
    planet_id = planet["id"]
    planet_name = planet.get("name", f"Planeta {planet_id}")
    orbital_ring = planet.get("orbital_ring", 1)

    # Obtener sectores del planeta
    sectors = get_planet_sectors_status(planet_id, player_id)

    # Separar órbita y superficie
    orbit_sector = None
    surface_sectors = []
    all_surface_sector_ids = set()

    for s in sectors:
        if s.get("sector_type") == "Orbital":
            orbit_sector = s
        else:
            surface_sectors.append(s)
            all_surface_sector_ids.add(s["id"])

    # Verificar si hay contenido en este planeta
    has_content = False
    if orbit_sector:
        osid = orbit_sector["id"]
        if location_index["units_by_sector"].get(osid) or location_index["chars_by_sector"].get(osid):
            has_content = True
    for ss in surface_sectors:
        ssid = ss["id"]
        if location_index["units_by_sector"].get(ssid) or location_index["chars_by_sector"].get(ssid):
            has_content = True
            break

    with st.expander(f"🪐 {planet_name} (Anillo {orbital_ring})", expanded=is_priority and has_content):
        # Órbita
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
                planet_id=planet_id,
                all_planet_sector_ids=all_surface_sector_ids
            )

        # Superficie
        if surface_sectors:
            st.markdown('<div class="comando-section-header">🌍 Superficie</div>', unsafe_allow_html=True)
            for sector in surface_sectors:
                sector_id = sector["id"]
                sector_type = sector.get("sector_type", "Desconocido")

                units_here = location_index["units_by_sector"].get(sector_id, [])
                chars_here = location_index["chars_by_sector"].get(sector_id, [])

                if units_here or chars_here:
                    st.caption(f"**{sector_type}**")
                    surface_loc = {
                        "system_id": planet.get("system_id"),
                        "planet_id": planet_id,
                        "sector_id": sector_id
                    }
                    _render_sector_content(
                        sector_id=sector_id,
                        sector_type=sector_type,
                        player_id=player_id,
                        location_data=surface_loc,
                        location_index=location_index,
                        is_space=False
                    )


def _render_system_node(
    system: dict,
    player_id: int,
    location_index: dict,
    is_priority: bool
):
    """Renderiza un nodo de sistema con sectores estelares, anillos y planetas."""
    system_id = system["id"]
    system_name = system.get("name", f"Sistema {system_id}")

    icon = "⭐" if is_priority else "🌟"

    # Obtener planetas del sistema
    planets = get_planets_by_system_id(system_id)

    # Verificar contenido en el sistema
    has_ring_content = False
    for ring in range(0, 7):
        key = (system_id, ring)
        if location_index["units_by_system_ring"].get(key):
            has_ring_content = True
            break

    has_planet_content = False
    for planet in planets:
        planet_id = planet["id"]
        sectors = get_planet_sectors_status(planet_id, player_id)
        for s in sectors:
            sid = s["id"]
            if location_index["units_by_sector"].get(sid) or location_index["chars_by_sector"].get(sid):
                has_planet_content = True
                break
        if has_planet_content:
            break

    has_content = has_ring_content or has_planet_content

    with st.expander(f"{icon} Sistema {system_name}", expanded=is_priority and has_content):
        # Sector Estelar (Ring 0)
        stellar_key = (system_id, 0)
        stellar_units = location_index["units_by_system_ring"].get(stellar_key, [])
        if stellar_units:
            st.markdown('<div class="comando-section-header">🌌 Sector Estelar</div>', unsafe_allow_html=True)
            for unit in stellar_units:
                _render_unit_row(unit, player_id, is_space=True)

        # Anillos 1-6 (espacio sin planeta específico)
        for ring in range(1, 7):
            ring_key = (system_id, ring)
            ring_units = location_index["units_by_system_ring"].get(ring_key, [])
            if ring_units:
                st.markdown(f'<div class="comando-section-header">🌌 Anillo {ring}</div>', unsafe_allow_html=True)
                for unit in ring_units:
                    _render_unit_row(unit, player_id, is_space=True)

        # Planetas ordenados por orbital_ring
        planets_sorted = sorted(planets, key=lambda p: p.get("orbital_ring", 1))
        for planet in planets_sorted:
            _render_planet_node(planet, player_id, location_index, is_priority)


def _render_starlanes_section(location_index: dict, player_id: int):
    """Renderiza sección de unidades en tránsito por starlanes."""
    units_in_transit = location_index.get("units_in_transit", [])

    if not units_in_transit:
        st.caption("No hay unidades en tránsito.")
        return

    for unit in units_in_transit:
        unit_id = unit["id"]
        name = unit.get("name", "Unidad")
        members = unit.get("members", [])
        origin = unit.get("transit_origin_system_id", "?")
        dest = unit.get("transit_destination_system_id", "?")
        ticks = unit.get("transit_ticks_remaining", 0)

        st.markdown(f"""
        <div class="comando-unit-header">
            🌌 ✈️ <strong>{name}</strong> ({len(members)}/8)
            <span style="color:#888;font-size:0.85em;margin-left:10px">
                Sistema {origin} → Sistema {dest} | {ticks} ticks restantes
            </span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("⚙️", key=f"manage_transit_{unit_id}", help="Gestionar unidad"):
                manage_unit_dialog(unit, player_id)


# --- FUNCIÓN PRINCIPAL ---

def render_comando_page():
    """Punto de entrada principal - Página de Comando."""
    from .state import get_player

    _inject_compact_css()

    st.title("Comando")

    player = get_player()
    if not player:
        st.warning("Error de sesión. Por favor, inicia sesión nuevamente.")
        return

    player_id = player.id

    # Cargar datos
    with st.spinner("Cargando estructura de comando..."):
        characters = get_all_player_characters(player_id)
        units = get_units_by_player(player_id)
        systems = get_all_systems_from_db()
        priority_system_ids = _get_player_system_ids(player_id)

        # Obtener IDs asignados
        assigned_chars, assigned_troops = _get_assigned_entity_ids(units)

        # Construir índice de ubicaciones
        location_index = _build_location_index(characters, units, assigned_chars)

    # Estadísticas rápidas
    loose_chars = len(characters) - len(assigned_chars)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Personajes", len(characters), f"{loose_chars} sueltos")
    with col2:
        st.metric("Unidades", len(units))
    with col3:
        st.metric("En Tránsito", len(location_index["units_in_transit"]))

    st.divider()

    # Ordenar sistemas: prioritarios primero
    systems_priority = [s for s in systems if s["id"] in priority_system_ids]
    systems_other = [s for s in systems if s["id"] not in priority_system_ids]

    # Renderizar sistemas prioritarios
    if systems_priority:
        for system in systems_priority:
            _render_system_node(system, player_id, location_index, is_priority=True)

    # Renderizar otros sistemas (solo si tienen contenido)
    if systems_other:
        with st.expander("Otros Sistemas", expanded=False):
            for system in systems_other:
                _render_system_node(system, player_id, location_index, is_priority=False)

    # Starlanes
    st.divider()
    with st.expander("🌌 Rutas Estelares (Starlanes)", expanded=len(location_index["units_in_transit"]) > 0):
        _render_starlanes_section(location_index, player_id)


# Alias para compatibilidad
def render_faction_roster():
    """Alias para compatibilidad con código existente."""
    render_comando_page()
