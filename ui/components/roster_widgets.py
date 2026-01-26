# ui/components/roster_widgets.py
"""
Componentes visuales reutilizables para el Roster de Facción.
Contiene: CSS injection, badges, filas de personajes/tropas/unidades.
Extraído de ui/faction_roster.py V17.0.
"""

import json
import streamlit as st
from typing import Dict, List, Any, Optional, Set

from ui.logic.roster_logic import (
    get_prop,
    sort_key_by_prop,
    calculate_unit_display_capacity,
)
from ui.dialogs.roster_dialogs import (
    view_character_dialog,
    movement_dialog,
    create_unit_dialog,
    manage_unit_dialog,
)
from services.unit_service import toggle_stealth_mode
from core.exploration_engine import resolve_sector_exploration
from data.planet_repository import build_structure, get_planet_sectors_status
from core.world_constants import SECTOR_TYPE_ORBITAL


# --- CSS COMPACTO ---

def inject_compact_css():
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


# --- RENDERIZADO ---

def render_loyalty_badge(loyalty: int) -> str:
    """Retorna badge de lealtad con color."""
    if loyalty < 30:
        return f'<span class="loyalty-low">{loyalty}%</span>'
    elif loyalty < 70:
        return f'<span class="loyalty-mid">{loyalty}%</span>'
    return f'<span class="loyalty-high">{loyalty}%</span>'


def render_character_row(char: Any, player_id: int, is_space: bool):
    """Renderiza fila de personaje suelto."""
    char_id = get_prop(char, "id")
    nombre = get_prop(char, "nombre", "???")
    nivel = get_prop(char, "level", 1)
    loyalty = get_prop(char, "loyalty", 50)

    icon = "🌌" if is_space else "🌍"
    loc_class = "loc-space" if is_space else "loc-ground"
    loyalty_html = render_loyalty_badge(loyalty)

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


def render_troop_row(troop: Any, is_space: bool):
    """V17.0: Renderiza fila de tropa suelta."""
    troop_id = get_prop(troop, "id")
    name = get_prop(troop, "name", "Tropa Sin Nombre")
    level = get_prop(troop, "level", 1)
    troop_type = get_prop(troop, "type", "INFANTRY")

    icon = "🌌" if is_space else "🌍"
    loc_class = "loc-space" if is_space else "loc-ground"

    cols = st.columns([0.5, 5.5, 1])
    with cols[0]:
        st.markdown(f'<span class="{loc_class}">{icon}</span>', unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"🪖 **{name}** ({troop_type}, Nvl {level})")
    with cols[2]:
        st.caption(f"ID: {troop_id}")


def _render_unit_skills(unit: Any):
    """
    V17.1: Renderiza las habilidades colectivas de una unidad en formato compacto.
    Muestra las 5 habilidades con iconos, valores y tooltips detallados con desglose.
    """
    # Extraer habilidades de la unidad
    skill_deteccion = get_prop(unit, "skill_deteccion", 0)
    skill_radares = get_prop(unit, "skill_radares", 0)
    skill_exploracion = get_prop(unit, "skill_exploracion", 0)
    skill_sigilo = get_prop(unit, "skill_sigilo", 0)
    skill_evasion = get_prop(unit, "skill_evasion_sensores", 0)

    # Solo mostrar si hay al menos una habilidad > 0
    if skill_deteccion == 0 and skill_radares == 0 and skill_exploracion == 0 and skill_sigilo == 0 and skill_evasion == 0:
        return

    # V17.1: Construir tooltips detallados con desglose de fórmula
    members = get_prop(unit, "members", [])
    tooltips = _build_skill_tooltips(members)

    st.caption("Habilidades Colectivas:")

    # Renderizar en 5 columnas compactas
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("👁️ Detección", skill_deteccion, help=tooltips.get("deteccion", "INT + VOL"))
    with c2:
        st.metric("📡 Radares", skill_radares, help=tooltips.get("radares", "INT + VOL"))
    with c3:
        st.metric("🔭 Exploración", skill_exploracion, help=tooltips.get("exploracion", "INT + AGI"))
    with c4:
        st.metric("🥷 Sigilo", skill_sigilo, help=tooltips.get("sigilo", "AGI + VOL"))
    with c5:
        st.metric("🛡️ Evasión", skill_evasion, help=tooltips.get("evasion_sensores", "TEC + INT"))


def _build_skill_tooltips(members: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    V17.1: Construye tooltips detallados para cada habilidad de unidad.
    Muestra la fórmula y el desglose de contribución de cada miembro.
    """
    LEADER_WEIGHT = 4
    skill_keys = ["deteccion", "radares", "exploracion", "sigilo", "evasion_sensores"]
    skill_formulas = {
        "deteccion": "INT + VOL",
        "radares": "INT + VOL",
        "exploracion": "INT + AGI",
        "sigilo": "AGI + VOL",
        "evasion_sensores": "TEC + INT"
    }

    # Filtrar solo personajes (tropas no contribuyen a habilidades colectivas)
    characters = [m for m in members if m.get("entity_type") == "character"]

    if not characters:
        return {k: f"Sin personajes. Fórmula: {skill_formulas[k]}" for k in skill_keys}

    # Identificar líder
    leader = None
    others = []
    for char in characters:
        if char.get("is_leader", False):
            leader = char
        else:
            others.append(char)

    # Si no hay líder explícito, el primero asume el rol
    if leader is None:
        leader = characters[0]
        others = characters[1:]

    tooltips = {}

    for skill_key in skill_keys:
        lines = [f"Fórmula: (Líder×4 + Miembros) / (4 + N)"]
        lines.append(f"Base: {skill_formulas[skill_key]}")
        lines.append("─" * 25)

        # Obtener valor del líder
        leader_details = leader.get("details", {})
        leader_habilidades = leader_details.get("habilidades", {})
        leader_value = leader_habilidades.get(skill_key, 20)
        leader_name = leader.get("name", "Líder")
        leader_rango = leader_details.get("rango", "")

        leader_display = f"{leader_name}"
        if leader_rango:
            leader_display += f" ({leader_rango})"

        lines.append(f"[Líder] {leader_display}: {leader_value} × 4 = {leader_value * LEADER_WEIGHT}")

        # Sumar contribuciones de otros miembros
        others_sum = 0
        for other in others:
            other_details = other.get("details", {})
            other_habilidades = other_details.get("habilidades", {})
            other_value = other_habilidades.get(skill_key, 20)
            other_name = other.get("name", "Miembro")
            others_sum += other_value
            lines.append(f"[Miembro] {other_name}: {other_value}")

        # Calcular resultado
        weighted_sum = (leader_value * LEADER_WEIGHT) + others_sum
        total_weight = LEADER_WEIGHT + len(others)
        result = round(weighted_sum / total_weight) if total_weight > 0 else 0

        lines.append("─" * 25)
        lines.append(f"Resultado: {weighted_sum} / {total_weight} = {result}")

        tooltips[skill_key] = "\n".join(lines)

    return tooltips


def _get_sector_action_context(
    unit: Any,
    player_id: int
) -> Dict[str, Any]:
    """
    V18.0: Obtiene el contexto del sector para habilitar/deshabilitar acciones.
    Retorna info sobre: sector_type, is_discovered, has_outpost.
    """
    sector_id = get_prop(unit, "location_sector_id")
    planet_id = get_prop(unit, "location_planet_id")

    context = {
        "sector_id": sector_id,
        "sector_type": None,
        "is_orbital": False,
        "is_discovered": False,
        "has_outpost": False,
        "can_explore": False,
        "can_build_outpost": False,
        "planet_asset_id": None  # Necesario para build_structure
    }

    if not sector_id or not planet_id:
        return context

    try:
        # Obtener sectores del planeta con estado de descubrimiento
        sectors = get_planet_sectors_status(planet_id, player_id)

        # Buscar el sector actual
        current_sector = None
        for s in sectors:
            if s.get("id") == sector_id:
                current_sector = s
                break

        if not current_sector:
            return context

        sector_type = current_sector.get("sector_type")
        is_orbital = sector_type == SECTOR_TYPE_ORBITAL
        is_discovered = current_sector.get("is_discovered", False)

        context["sector_type"] = sector_type
        context["is_orbital"] = is_orbital
        context["is_discovered"] = is_discovered

        # Verificar si ya tiene outpost (consultar edificios del sector)
        from data.database import get_supabase
        db = get_supabase()

        # Buscar planet_asset_id del jugador para este planeta
        asset_res = db.table("planet_assets")\
            .select("id")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player_id)\
            .maybe_single()\
            .execute()

        if asset_res and asset_res.data:
            context["planet_asset_id"] = asset_res.data.get("id")

        # Verificar si hay outpost en el sector
        outpost_res = db.table("planet_buildings")\
            .select("id")\
            .eq("sector_id", sector_id)\
            .eq("building_type", "outpost")\
            .maybe_single()\
            .execute()

        context["has_outpost"] = bool(outpost_res and outpost_res.data)

        # Determinar acciones disponibles
        # Explorar: sector_id válido, NO es orbital
        context["can_explore"] = (sector_id is not None) and (not is_orbital)

        # Puesto de avanzada: sector descubierto, no tiene outpost, no es orbital
        context["can_build_outpost"] = (
            is_discovered and
            not context["has_outpost"] and
            not is_orbital and
            context["planet_asset_id"] is not None
        )

    except Exception as e:
        print(f"Error obteniendo contexto de sector: {e}")

    return context


def render_unit_row(
    unit: Any,
    player_id: int,
    is_space: bool,
    available_chars: List[Any],
    available_troops: List[Any]
):
    """
    V18.0: Nueva estructura de fila de unidad.
    - Cabecera Estática: Icono + Nombre + Badge capacidad
    - Botonera Continua: Movimiento, Gestionar, Sigilo, Explorar, Puesto de Avanzada
    - Menú Desplegable: Personal con fichas de personaje
    """
    unit_id = get_prop(unit, "id")
    name = get_prop(unit, "name", "Unidad")
    members = get_prop(unit, "members", [])
    status = get_prop(unit, "status", "GROUND")
    local_moves = get_prop(unit, "local_moves_count", 0)

    # V16.0: Calcular capacidad dinámica y estado de riesgo
    is_at_risk = get_prop(unit, "is_at_risk", False)
    max_capacity = calculate_unit_display_capacity(members)
    current_count = len(members)

    # Icono de entorno
    icon = "🌌" if is_space else "🌍"

    # Badge de capacidad
    capacity_display = f"{current_count}/{max_capacity}"
    risk_indicator = " ⚠️" if is_at_risk else ""

    # Verificar si está en modo sigilo
    is_stealth = status == "STEALTH_MODE"
    is_transit = status == "TRANSIT"

    # Obtener contexto del sector para botones condicionales
    sector_context = _get_sector_action_context(unit, player_id)

    # ═══════════════════════════════════════════════════════════════
    # CABECERA ESTÁTICA (Fila de Control)
    # ═══════════════════════════════════════════════════════════════
    header_cols = st.columns([0.4, 3, 1])

    with header_cols[0]:
        st.markdown(f"**{icon}**")

    with header_cols[1]:
        # Nombre + Badge de capacidad
        stealth_badge = " 🥷" if is_stealth else ""
        transit_badge = " ✈️" if is_transit else ""
        st.markdown(f"🎖️ **{name}** `[{capacity_display}]`{stealth_badge}{transit_badge}{risk_indicator}")

    with header_cols[2]:
        # Mostrar estado de movimientos
        if local_moves < 2:
            st.caption(f"Movs: {local_moves}/2")
        else:
            st.caption("🛑 Sin Movs")

    # ═══════════════════════════════════════════════════════════════
    # BOTONERA CONTINUA (Acciones Rápidas)
    # ═══════════════════════════════════════════════════════════════
    btn_cols = st.columns([1, 1, 1, 1, 1])

    # 🚀 Botón de Movimiento
    with btn_cols[0]:
        if is_transit:
            st.button("✈️", key=f"move_transit_{unit_id}", disabled=True, help="En tránsito")
        elif local_moves >= 2:
            st.button("🚀", key=f"move_lock_{unit_id}", disabled=True, help="Sin movimientos")
        else:
            if st.button("🚀", key=f"move_{unit_id}", help="Control de Movimiento"):
                st.session_state.selected_unit_movement = unit_id
                movement_dialog()

    # ⚙ Botón de Gestionar
    with btn_cols[1]:
        if st.button("⚙️", key=f"manage_{unit_id}", help="Gestionar unidad"):
            manage_unit_dialog(unit, player_id, available_chars, available_troops)

    # 🐱‍👤 Botón de Modo Sigilo
    with btn_cols[2]:
        stealth_disabled = is_transit
        stealth_type = "primary" if is_stealth else "secondary"
        stealth_help = "Desactivar Sigilo" if is_stealth else "Activar Modo Sigilo"

        if stealth_disabled:
            st.button("🐱‍👤", key=f"stealth_disabled_{unit_id}", disabled=True, help="No disponible en tránsito")
        else:
            if st.button("🐱‍👤", key=f"stealth_{unit_id}", help=stealth_help, type=stealth_type):
                result = toggle_stealth_mode(unit_id, player_id)
                if result.get("success"):
                    st.success(f"Sigilo: {result.get('new_status')}")
                    st.rerun()
                else:
                    st.error(result.get("error", "Error al cambiar modo sigilo"))

    # 🔭 Botón de Explorar (Condicional)
    with btn_cols[3]:
        can_explore = sector_context.get("can_explore", False) and not is_transit
        sector_id = sector_context.get("sector_id")

        if not can_explore or sector_id is None:
            st.button("🔭", key=f"explore_disabled_{unit_id}", disabled=True, help="Exploración no disponible")
        else:
            if st.button("🔭", key=f"explore_{unit_id}", help="Explorar Sector"):
                try:
                    result = resolve_sector_exploration(unit_id, sector_id, player_id)
                    if result.success:
                        st.success(f"Exploración exitosa: {result.narrative}")
                    else:
                        st.warning(f"Exploración fallida: {result.narrative}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en exploración: {e}")

    # 🏛 Botón de Puesto de Avanzada (Condicional)
    with btn_cols[4]:
        can_build = sector_context.get("can_build_outpost", False) and not is_transit
        planet_asset_id = sector_context.get("planet_asset_id")

        if not can_build or planet_asset_id is None:
            help_text = "Requiere sector descubierto sin outpost"
            if sector_context.get("has_outpost"):
                help_text = "Ya existe un puesto en este sector"
            st.button("🏛", key=f"outpost_disabled_{unit_id}", disabled=True, help=help_text)
        else:
            if st.button("🏛", key=f"outpost_{unit_id}", help="Construir Puesto de Avanzada"):
                try:
                    result = build_structure(
                        planet_asset_id=planet_asset_id,
                        player_id=player_id,
                        building_type="outpost",
                        sector_id=sector_context.get("sector_id")
                    )
                    if result:
                        st.success("Puesto de Avanzada construido")
                        st.rerun()
                    else:
                        st.error("No se pudo construir el puesto")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ═══════════════════════════════════════════════════════════════
    # MENÚ DESPLEGABLE DE PERSONAL (Expander)
    # ═══════════════════════════════════════════════════════════════
    with st.expander("👥 Personal", expanded=False):
        # V16.0: Mostrar advertencia si está en riesgo
        if is_at_risk:
            st.warning("⚠️ Unidad en riesgo: territorio hostil o excede capacidad del líder.")

        # V17.0: Habilidades Colectivas de Unidad
        _render_unit_skills(unit)

        # Lista de miembros
        if members:
            st.caption("Composición:")
            sorted_members = sorted(members, key=sort_key_by_prop("slot_index", 0))

            for m in sorted_members:
                etype = get_prop(m, "entity_type", "?")
                slot = get_prop(m, "slot_index", 0)
                member_name = get_prop(m, "name", "???")
                is_leader = get_prop(m, "is_leader", False)
                leader_icon = "⭐ " if is_leader else ""

                # Fila de miembro con botón de ficha para personajes
                if etype == "character":
                    char_cols = st.columns([4, 1])
                    with char_cols[0]:
                        st.markdown(f"`[{slot}]` {leader_icon}👤 {member_name}")
                    with char_cols[1]:
                        # 📄 Botón de Ficha de Personaje
                        char_id = get_prop(m, "entity_id")
                        char_details = get_prop(m, "details", {})
                        if st.button("📄", key=f"sheet_{unit_id}_{char_id}", help="Ver ficha de personaje"):
                            # Construir objeto de personaje para el diálogo
                            char_data = {
                                "id": char_id,
                                "nombre": member_name,
                                **char_details
                            }
                            view_character_dialog(char_data, player_id)
                else:
                    st.markdown(f"`[{slot}]` 🪖 {member_name}")
        else:
            st.caption("Sin miembros asignados.")


def render_create_unit_button(
    sector_id: int,
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[Any],
    available_troops: List[Any],
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


def render_starlanes_section(
    location_index: dict,
    player_id: int,
    available_chars: List[Any],
    available_troops: List[Any]
):
    """Renderiza sección de unidades en tránsito por starlanes."""
    units_in_transit = location_index.get("units_in_transit", [])

    if not units_in_transit:
        return

    for unit in units_in_transit:
        unit_id = get_prop(unit, "id")
        name = get_prop(unit, "name", "Unidad")
        members = get_prop(unit, "members", [])
        origin = get_prop(unit, "transit_origin_system_id", "?")
        dest = get_prop(unit, "transit_destination_system_id", "?")
        ticks = get_prop(unit, "transit_ticks_remaining", 0)

        # V16.0: Capacidad dinámica
        max_capacity = calculate_unit_display_capacity(members)
        capacity_display = f"({len(members)}/{max_capacity})"

        with st.expander(f"🌌 ✈️ **{name}** {capacity_display} | Sistema {origin} → {dest} | {ticks} ticks", expanded=False):
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("⚙️", key=f"manage_transit_{unit_id}", help="Gestionar unidad"):
                    manage_unit_dialog(unit, player_id, [], [])

            # V17.0: Habilidades Colectivas de Unidad
            _render_unit_skills(unit)

            if members:
                st.caption("Composición:")
                # Fix V15.0: Sort seguro para Pydantic Models y Dicts
                sorted_members = sorted(members, key=sort_key_by_prop("slot_index", 0))

                for m in sorted_members:
                    # Fix V15.0: Acceso seguro
                    etype = get_prop(m, "entity_type", "?")
                    slot = get_prop(m, "slot_index", 0)
                    member_name = get_prop(m, "name", "???")
                    # V16.0: Indicador de líder
                    is_leader = get_prop(m, "is_leader", False)
                    leader_icon = "⭐ " if is_leader else ""
                    icon_e = "👤" if etype == "character" else "🪖"
                    st.markdown(f"`[{slot}]` {leader_icon}{icon_e} {member_name}")
