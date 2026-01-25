# ui/faction_roster.py (Completo)
"""
Comando - Vista jerárquica de personajes, tropas y unidades organizados por ubicación.
V11.1: Hidratación de nombres, filtrado de sistemas, UI compacta, gestión mejorada.
V11.2: Restauración de flujo inicial "Reunir al personal".
V11.3: Reclutamiento jerárquico inicial con feedback visual mejorado.
V11.4: Filtro de seguridad para excluir candidatos (Status 7) del Roster.
V11.5: Encabezados dinámicos con métricas y visibilidad estricta de nodos vacíos.
"""

import streamlit as st
import time
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
    remove_unit_member,
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
from core.models import CommanderData, KnowledgeLevel, CharacterStatus
from ui.character_sheet import render_character_sheet
from services.character_generation_service import recruit_character_with_ai


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
        display: flex;
        align-items: center;
        justify-content: space-between;
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
    """Dialog para crear una nueva unidad con estado limpio."""
    st.subheader("Formar Nueva Unidad")

    if is_orbit:
        st.info("En órbita puedes embarcar personal de superficie.")

    # Usar keys únicas basadas en sector para evitar estado persistente
    key_prefix = f"create_{sector_id}"

    unit_name = st.text_input(
        "Nombre de la Unidad",
        value="Escuadrón Alfa",
        key=f"{key_prefix}_name"
    )

    st.markdown("**Seleccionar Miembros** (Máx 8, Mín 1 Personaje)")

    # Personajes disponibles (ya filtrados, no asignados)
    char_options = {c["id"]: f"👤 {c.get('nombre', 'Sin nombre')} (Nvl {c.get('level', 1)})" for c in available_chars}
    selected_char_ids: List[int] = st.multiselect(
        "Personajes (Líder obligatorio)",
        options=list(char_options.keys()),
        format_func=lambda x: char_options.get(x, str(x)),
        max_selections=8,
        key=f"{key_prefix}_chars"
    )

    remaining_slots = 8 - len(selected_char_ids)

    # Tropas disponibles (ya filtradas, no asignadas)
    troop_options = {t["id"]: f"🪖 {t.get('name', 'Tropa')} ({t.get('type', 'INF')})" for t in available_troops}
    selected_troop_ids: List[int] = st.multiselect(
        "Tropas",
        options=list(troop_options.keys()),
        format_func=lambda x: troop_options.get(x, str(x)),
        max_selections=max(0, remaining_slots),
        disabled=remaining_slots <= 0,
        key=f"{key_prefix}_troops"
    )

    # Métricas reactivas
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

    can_create = has_leader and 0 < total <= 8 and unit_name.strip()

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


@st.dialog("Gestionar Unidad", width="large")
def manage_unit_dialog(
    unit: dict,
    player_id: int,
    available_chars: List[dict],
    available_troops: List[dict]
):
    """Dialog para renombrar, disolver o añadir miembros a una unidad."""
    unit_id = unit["id"]
    current_name = unit.get("name", "Unidad")
    members = unit.get("members", [])
    current_count = len(members)

    st.subheader(f"Gestionar: {current_name}")

    # --- TAB 1: RENOMBRAR ---
    tab_rename, tab_add, tab_dissolve = st.tabs(["Renombrar", "Añadir Miembros", "Disolver"])

    with tab_rename:
        new_name = st.text_input("Nuevo nombre", value=current_name, key=f"rename_{unit_id}")
        if st.button(
            "Renombrar",
            use_container_width=True,
            disabled=not new_name.strip() or new_name == current_name,
            key=f"btn_rename_{unit_id}"
        ):
            if rename_unit(unit_id, new_name.strip(), player_id):
                st.success("Nombre actualizado.")
                st.rerun()
            else:
                st.error("Error al renombrar.")

    # --- TAB 2: AÑADIR MIEMBROS ---
    with tab_add:
        slots_available = 8 - current_count
        st.caption(f"Slots disponibles: {slots_available}")

        if slots_available <= 0:
            st.warning("La unidad está llena (8/8).")
        else:
            # Personajes disponibles en la ubicación
            char_opts = {c["id"]: f"👤 {c.get('nombre', '?')} (Nvl {c.get('level', 1)})" for c in available_chars}
            add_chars: List[int] = st.multiselect(
                "Añadir Personajes",
                options=list(char_opts.keys()),
                format_func=lambda x: char_opts.get(x, str(x)),
                max_selections=slots_available,
                key=f"add_chars_{unit_id}"
            )

            remaining = slots_available - len(add_chars)

            troop_opts = {t["id"]: f"🪖 {t.get('name', '?')} ({t.get('type', 'INF')})" for t in available_troops}
            add_troops: List[int] = st.multiselect(
                "Añadir Tropas",
                options=list(troop_opts.keys()),
                format_func=lambda x: troop_opts.get(x, str(x)),
                max_selections=max(0, remaining),
                disabled=remaining <= 0,
                key=f"add_troops_{unit_id}"
            )

            total_to_add = len(add_chars) + len(add_troops)
            if total_to_add > 0:
                if st.button(
                    f"Añadir {total_to_add} miembro(s)",
                    type="primary",
                    use_container_width=True,
                    key=f"btn_add_{unit_id}"
                ):
                    slot = current_count
                    for cid in add_chars:
                        add_unit_member(unit_id, "character", cid, slot)
                        slot += 1
                    for tid in add_troops:
                        add_unit_member(unit_id, "troop", tid, slot)
                        slot += 1
                    st.success(f"{total_to_add} miembro(s) añadido(s).")
                    st.rerun()

    # --- TAB 3: DISOLVER ---
    with tab_dissolve:
        st.markdown("**Disolver Unidad**")
        st.caption("Los miembros quedarán sueltos en la ubicación actual.")
        if st.button("Disolver Unidad", type="secondary", use_container_width=True, key=f"btn_dissolve_{unit_id}"):
            if delete_unit(unit_id, player_id):
                st.success("Unidad disuelta.")
                st.rerun()
            else:
                st.error("Error al disolver.")


# --- HELPERS DE DATOS ---

def _get_assigned_entity_ids(units: List[dict]) -> Tuple[Set[int], Set[int]]:
    """Retorna sets de IDs de characters y troops asignados a unidades."""
    assigned_chars: Set[int] = set()
    assigned_troops: Set[int] = set()
    for unit in units:
        for member in unit.get("members", []):
            etype = member.get("entity_type")
            eid = member.get("entity_id")
            if etype == "character":
                assigned_chars.add(eid)
            elif etype == "troop":
                assigned_troops.add(eid)
    return assigned_chars, assigned_troops


def _hydrate_unit_members(
    units: List[dict],
    char_map: Dict[int, str],
    troop_map: Dict[int, str]
) -> List[dict]:
    """Inyecta nombres reales en los miembros de cada unidad."""
    for unit in units:
        for member in unit.get("members", []):
            eid = member.get("entity_id")
            etype = member.get("entity_type")
            if etype == "character":
                member["name"] = char_map.get(eid, f"Personaje {eid}")
            elif etype == "troop":
                member["name"] = troop_map.get(eid, f"Tropa {eid}")
    return units


def _get_systems_with_presence(
    location_index: dict,
    characters: List[dict],
    assigned_char_ids: Set[int]
) -> Set[int]:
    """Obtiene IDs de sistemas donde hay presencia del jugador."""
    system_ids: Set[int] = set()

    # Desde unidades por sector
    for sector_id, unit_list in location_index["units_by_sector"].items():
        for u in unit_list:
            sid = u.get("location_system_id")
            if sid:
                system_ids.add(sid)

    # Desde unidades por ring
    for (sys_id, ring), unit_list in location_index["units_by_system_ring"].items():
        if unit_list:
            system_ids.add(sys_id)

    # Desde personajes sueltos
    for char in characters:
        if char["id"] not in assigned_char_ids:
            sys_id = char.get("location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # Desde chars_by_sector (inferir sistema desde planeta)
    for sector_id, char_list in location_index["chars_by_sector"].items():
        for c in char_list:
            sys_id = c.get("location_system_id")
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
            chars_by_sector.setdefault(sector_id, []).append(char)

    # Unidades por ubicación
    for unit in units:
        status = unit.get("status", "GROUND")
        if status == "TRANSIT":
            units_in_transit.append(unit)
            continue

        sector_id = unit.get("location_sector_id")
        if sector_id:
            units_by_sector.setdefault(sector_id, []).append(unit)
        else:
            system_id = unit.get("location_system_id")
            ring = unit.get("ring", 0)
            if system_id:
                key = (system_id, ring)
                units_by_system_ring.setdefault(key, []).append(unit)

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


def _render_unit_row(
    unit: dict,
    player_id: int,
    is_space: bool,
    available_chars: List[dict],
    available_troops: List[dict]
):
    """Renderiza unidad con header expandible: nombre + botón gestión en misma fila."""
    unit_id = unit["id"]
    name = unit.get("name", "Unidad")
    members = unit.get("members", [])
    status = unit.get("status", "GROUND")

    icon = "🌌" if is_space else "🌍"
    status_emoji = {"GROUND": "🏕️", "SPACE": "🚀", "TRANSIT": "✈️"}.get(status, "❓")

    # Header compacto con expander
    with st.expander(f"{icon} 🎖️ **{name}** ({len(members)}/8) {status_emoji}", expanded=False):
        # Botón gestión en la parte superior del contenido expandido
        col_info, col_btn = st.columns([4, 1])
        with col_btn:
            if st.button("⚙️", key=f"manage_unit_{unit_id}", help="Gestionar unidad"):
                manage_unit_dialog(unit, player_id, available_chars, available_troops)

        # Lista de miembros
        if members:
            st.caption("Composición:")
            for m in sorted(members, key=lambda x: x.get("slot_index", 0)):
                etype = m.get("entity_type", "?")
                slot = m.get("slot_index", 0)
                member_name = m.get("name", "???")

                if etype == "character":
                    st.markdown(f"`[{slot}]` 👤 {member_name}")
                else:
                    st.markdown(f"`[{slot}]` 🪖 {member_name}")
        else:
            st.caption("Sin miembros asignados.")


def _render_create_unit_button(
    sector_id: int,
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[dict],
    available_troops: List[dict],
    is_orbit: bool = False
):
    """Renderiza botón para crear unidad si hay entidades disponibles."""
    if not available_chars:
        if available_troops:
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
    assigned_char_ids: Set[int],
    assigned_troop_ids: Set[int],
    all_troops: List[dict],
    planet_id: Optional[int] = None,
    all_planet_sector_ids: Optional[Set[int]] = None
):
    """Renderiza contenido de un sector (unidades + personajes sueltos + botón crear)."""
    units = location_index["units_by_sector"].get(sector_id, [])
    chars = location_index["chars_by_sector"].get(sector_id, [])

    # Validación rápida: si no hay nada y no se puede crear unidad (o no hay gente), no renderizar nada?
    # El prompt pide "si un sector está vacío, no renderice nada".
    
    # Para órbita: incluir entidades de superficie para crear unidad
    orbit_chars: List[dict] = []
    if is_space and all_planet_sector_ids:
        for sid in all_planet_sector_ids:
            orbit_chars.extend(location_index["chars_by_sector"].get(sid, []))

    # Personajes disponibles (no asignados a unidad)
    available_chars_here = [c for c in (chars + orbit_chars if is_space else chars)
                           if c["id"] not in assigned_char_ids]

    # Tropas no tienen ubicación suelta, pero si las hubiera, filtrar no asignadas
    available_troops_here = [t for t in all_troops if t["id"] not in assigned_troop_ids]
    
    # Determinar si hay contenido real para mostrar
    has_units = len(units) > 0
    has_chars = len(chars) > 0
    # El botón de crear solo es relevante si hay recursos disponibles
    can_create = len(available_chars_here) > 0

    if not has_units and not has_chars and not can_create:
        return

    # Renderizar unidades primero
    for unit in units:
        _render_unit_row(unit, player_id, is_space, available_chars_here, available_troops_here)

    # Renderizar personajes sueltos
    for char in chars:
        _render_character_row(char, player_id, is_space)

    # Botón crear unidad (solo con disponibles no asignados)
    if can_create:
        _render_create_unit_button(
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
    all_troops: List[dict],
    is_priority: bool
):
    """Renderiza un nodo de planeta con órbita y sectores."""
    planet_id = planet["id"]
    planet_name = planet.get("name", f"Planeta {planet_id}")
    orbital_ring = planet.get("orbital_ring", 1)

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

        if stype == "Orbital":
            orbit_sector = s
            space_count += c_count
        else:
            surface_sectors.append(s)
            all_surface_sector_ids.add(sid)
            surf_count += c_count

    # Lógica de Visibilidad Estricta
    has_content = (u_count + surf_count + space_count) > 0
    
    if has_content:
        header = f"🪐 {planet_name} | 👥({u_count}) - 🪐({surf_count}) - 🌌({space_count})"
        # is_priority ayuda a decidir si arranca expandido, pero si tiene contenido lo mostramos
        should_expand = is_priority
        
        with st.expander(header, expanded=should_expand):
            if orbit_sector:
                # Verificar si el orbital tiene contenido específico
                osid = orbit_sector["id"]
                u_orb = len(location_index["units_by_sector"].get(osid, []))
                c_orb = len(location_index["chars_by_sector"].get(osid, []))
                
                # Renderizar solo si hay algo
                if u_orb > 0 or c_orb > 0:
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
                # Filtrar sectores de superficie con contenido
                visible_surface = []
                for s in surface_sectors:
                    sid = s["id"]
                    if location_index["units_by_sector"].get(sid) or location_index["chars_by_sector"].get(sid):
                        visible_surface.append(s)
                
                if visible_surface:
                    st.markdown('<div class="comando-section-header">🌍 Superficie</div>', unsafe_allow_html=True)
                    for sector in visible_surface:
                        sector_id = sector["id"]
                        sector_type = sector.get("sector_type", "Desconocido")

                        # No need to check emptiness again, loop filtered it, but _render_sector_content double checks
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
    all_troops: List[dict],
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

    # 1. Unidades en espacio (Estrella + Anillos)
    for r in range(7):
        key = (system_id, r)
        units = location_index["units_by_system_ring"].get(key, [])
        sys_u_count += len(units)
        # Nota: Los personajes sueltos en espacio profundo sin sector específico no se están indexando en 'chars_by_sector'
        # ni 'units_by_system_ring' en la lógica actual de _build_location_index para chars.
        # Asumimos que los chars en espacio están en tránsito (otro nodo) o en sectores orbitales (Planetas).

    # 2. Contenido de Planetas
    for planet in planets:
        # Nota: Llamamos a la DB aquí. Es necesario para el resumen.
        p_sectors = get_planet_sectors_status(planet["id"], player_id)
        for s in p_sectors:
            sid = s["id"]
            stype = s.get("sector_type", "")
            
            u_here = len(location_index["units_by_sector"].get(sid, []))
            c_here = len(location_index["chars_by_sector"].get(sid, []))
            
            sys_u_count += u_here
            
            if stype == "Orbital":
                sys_space_count += c_here
            else:
                sys_surf_count += c_here

    # Lógica de Visibilidad Estricta
    has_content = (sys_u_count + sys_space_count + sys_surf_count) > 0

    if has_content:
        header = f"{icon} Sistema {system_name} | 👥({sys_u_count}) - 🪐({sys_surf_count}) - 🌌({sys_space_count})"
        
        with st.expander(header, expanded=is_priority):
            # Sector Estelar (Ring 0)
            stellar_key = (system_id, 0)
            stellar_units = location_index["units_by_system_ring"].get(stellar_key, [])
            if stellar_units:
                st.markdown('<div class="comando-section-header">🌌 Sector Estelar</div>', unsafe_allow_html=True)
                available_chars_space: List[dict] = []
                available_troops_space = [t for t in all_troops if t["id"] not in assigned_troop_ids]
                for unit in stellar_units:
                    _render_unit_row(unit, player_id, is_space=True,
                                    available_chars=available_chars_space,
                                    available_troops=available_troops_space)

            # Anillos 1-6
            for ring in range(1, 7):
                ring_key = (system_id, ring)
                ring_units = location_index["units_by_system_ring"].get(ring_key, [])
                if ring_units:
                    st.markdown(f'<div class="comando-section-header">🌌 Anillo {ring}</div>', unsafe_allow_html=True)
                    for unit in ring_units:
                        _render_unit_row(unit, player_id, is_space=True,
                                        available_chars=[],
                                        available_troops=[t for t in all_troops if t["id"] not in assigned_troop_ids])

            # Planetas ordenados
            planets_sorted = sorted(planets, key=lambda p: p.get("orbital_ring", 1))
            for planet in planets_sorted:
                # El nodo planeta hará su propia verificación de visibilidad
                _render_planet_node(planet, player_id, location_index,
                                   assigned_char_ids, assigned_troop_ids, all_troops, is_priority)


def _render_starlanes_section(
    location_index: dict,
    player_id: int,
    available_chars: List[dict],
    available_troops: List[dict]
):
    """Renderiza sección de unidades en tránsito por starlanes."""
    units_in_transit = location_index.get("units_in_transit", [])

    if not units_in_transit:
        # Si no hay unidades en tránsito, esta sección ni debería llamarse desde el main loop si queremos strict visibility total
        # pero la función padre lo controla con if location_index["units_in_transit"]
        return

    for unit in units_in_transit:
        unit_id = unit["id"]
        name = unit.get("name", "Unidad")
        members = unit.get("members", [])
        origin = unit.get("transit_origin_system_id", "?")
        dest = unit.get("transit_destination_system_id", "?")
        ticks = unit.get("transit_ticks_remaining", 0)

        with st.expander(f"🌌 ✈️ **{name}** ({len(members)}/8) | Sistema {origin} → {dest} | {ticks} ticks", expanded=False):
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("⚙️", key=f"manage_transit_{unit_id}", help="Gestionar unidad"):
                    manage_unit_dialog(unit, player_id, [], [])

            if members:
                st.caption("Composición:")
                for m in sorted(members, key=lambda x: x.get("slot_index", 0)):
                    etype = m.get("entity_type", "?")
                    slot = m.get("slot_index", 0)
                    member_name = m.get("name", "???")
                    icon_e = "👤" if etype == "character" else "🪖"
                    st.markdown(f"`[{slot}]` {icon_e} {member_name}")


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
        all_characters = get_all_player_characters(player_id)
        
        # FILTRO DE SEGURIDAD V11.4/11.5:
        # Usamos 'all_characters' para métricas globales (incluye candidatos).
        # Usamos 'roster_characters' para la visualización en mapa (excluye candidatos).
        roster_characters = [c for c in all_characters if c.get("status_id") != CharacterStatus.CANDIDATE.value]
        
        # --- NUEVO: Flujo inicial de reclutamiento ---
        # Verificar sobre roster_characters para ver si hay personal activo
        non_commander_count = sum(1 for c in roster_characters if not c.get("es_comandante", False))
        
        # Si no hay nadie en el roster (salvo quizás el comandante si cuenta), pero vamos a asumir que
        # si la lista está vacía o solo tiene al jugador (si fuera el caso)
        # La lógica original usaba 'characters', que ahora es 'all_characters'.
        # Si hay candidatos pero no roster activo, quizás querramos mostrar el botón.
        # Mantenemos lógica: si no hay personal activo (excluyendo comandante), sugerimos reclutar.
        
        if non_commander_count == 0:
            st.info("La facción se está estableciendo. Necesitas personal para operar.")
            col_center = st.columns([1, 2, 1])
            with col_center[1]:
                if st.button("Reunir al personal", type="primary", use_container_width=True):
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

                    # Feedback visual y bloqueo con st.status
                    with st.status("Estableciendo cadena de mando...", expanded=True) as status:
                        for idx, (level, k_level, label) in enumerate(recruitment_config):
                            status.update(label=f"Reclutando {label} (Nivel {level}) - [{idx+1}/{total_ops}]...")
                            try:
                                # recruit_character_with_ai usa el context interno para hallar la base
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
                        
                        if success_count > 0:
                            status.update(label="¡Personal reunido! Iniciando sistemas...", state="complete", expanded=False)
                            time.sleep(0.5) # Pausa estética breve
                            st.rerun()
                        else:
                            status.update(label="Fallo crítico en el reclutamiento.", state="error")
                            st.error("No se pudo establecer la facción. Intenta nuevamente.")
            return

        # Si hay personal, continuar con carga normal
        troops = get_troops_by_player(player_id)
        units = get_units_by_player(player_id)
        systems = get_all_systems_from_db()

        # Mapas de nombres para hidratación (usando todos para que no falle si una unidad tiene un candidato asignado por error)
        char_map: Dict[int, str] = {c["id"]: c.get("nombre", f"Personaje {c['id']}") for c in all_characters}
        troop_map: Dict[int, str] = {t["id"]: t.get("name", f"Tropa {t['id']}") for t in troops}

        # Hidratar nombres de miembros
        units = _hydrate_unit_members(units, char_map, troop_map)

        # Obtener IDs asignados
        assigned_chars, assigned_troops = _get_assigned_entity_ids(units)

        # Construir índice de ubicaciones USANDO ROSTER FILTRADO
        location_index = _build_location_index(roster_characters, units, assigned_chars)

        # Obtener sistemas con presencia del jugador USANDO ROSTER FILTRADO
        systems_with_presence = _get_systems_with_presence(location_index, roster_characters, assigned_chars)

    # Estadísticas rápidas
    # Personajes: Muestra Total (incluyendo candidatos)
    # Sueltos: Muestra Solo Roster sueltos (los candidatos no deberían estar en el mapa)
    roster_loose_chars = len(roster_characters) - len([cid for cid in assigned_chars if any(c["id"] == cid for c in roster_characters)])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Personajes", len(all_characters), f"{roster_loose_chars} sueltos (Roster)")
    with col2:
        st.metric("Unidades", len(units))
    with col3:
        st.metric("En Tránsito", len(location_index["units_in_transit"]))

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
            _render_starlanes_section(location_index, player_id, [], [])


# Alias para compatibilidad
def render_faction_roster():
    """Alias para compatibilidad con código existente."""
    render_comando_page()