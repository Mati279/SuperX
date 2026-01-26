# ui/dialogs/roster_dialogs.py
"""
Diálogos modales para el Roster de Facción.
Contiene: view_character_dialog, movement_dialog, create_unit_dialog, manage_unit_dialog.
Extraído de ui/faction_roster.py V17.0.
"""

import streamlit as st
from typing import Dict, List, Any

from data.unit_repository import (
    create_unit,
    add_unit_member,
    remove_unit_member,
    rename_unit,
    delete_unit,
)
from core.models import UnitStatus
from ui.character_sheet import render_character_sheet
from ui.movement_console import render_movement_console
from ui.logic.roster_logic import (
    get_prop,
    set_prop,
    sort_key_by_prop,
    calculate_unit_display_capacity,
    get_leader_capacity,
    BASE_CAPACITY,
    MAX_CAPACITY,
)


# --- DIALOGS ---

@st.dialog("Ficha de Personal", width="large")
def view_character_dialog(char: Any, player_id: int):
    """Modal para ver ficha completa de personaje."""
    # Convertir a dict si es modelo para el renderizador legacy
    char_dict = char.model_dump() if hasattr(char, 'model_dump') else char
    render_character_sheet(char_dict, player_id)


@st.dialog("Control de Movimiento", width="large")
def movement_dialog():
    """Modal para control de movimiento."""
    render_movement_console()


@st.dialog("Crear Unidad", width="large")
def create_unit_dialog(
    sector_id: int,
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[Any],
    available_troops: List[Any],
    is_orbit: bool = False
):
    """
    V16.0: Dialog para crear una nueva unidad con selección obligatoria de líder.
    La capacidad máxima depende de la habilidad de Liderazgo del líder seleccionado.
    """
    st.subheader("Formar Nueva Unidad")

    # Usar keys únicas basadas en sector para evitar estado persistente
    key_prefix = f"create_{sector_id}"

    # Verificar que haya personajes disponibles para liderar
    if not available_chars:
        st.warning("No hay personajes disponibles en esta ubicación para liderar una unidad.")
        if available_troops:
            st.info("Las tropas requieren al menos un personaje como líder.")
        return

    unit_name = st.text_input(
        "Nombre de la Unidad",
        value="Escuadrón Alfa",
        key=f"{key_prefix}_name"
    )

    # --- V16.0: PASO 1 - Selección obligatoria de Líder ---
    st.markdown("**1. Seleccionar Líder** (Obligatorio)")

    # Helper para obtener ID, Nombre y Label
    def _char_opt(obj):
        oid = get_prop(obj, "id")
        oname = get_prop(obj, "nombre") or get_prop(obj, "name") or "Sin nombre"
        lvl = get_prop(obj, "level", 1)
        return oid, f"👤 {oname} (Nvl {lvl})"

    def _troop_opt(obj):
        oid = get_prop(obj, "id")
        oname = get_prop(obj, "name") or "Sin nombre"
        ttype = get_prop(obj, "type", "INF")
        lvl = get_prop(obj, "level", 1)
        return oid, f"🪖 {oname} ({ttype}, Nvl {lvl})"

    # Crear mapa de personajes disponibles con datos
    char_map = {}  # id -> objeto completo
    char_options = {}  # id -> label para display
    for c in available_chars:
        cid, clabel = _char_opt(c)
        char_map[cid] = c
        char_options[cid] = clabel

    # Selectbox para líder (obligatorio)
    leader_options = [None] + list(char_options.keys())
    leader_format = lambda x: "-- Seleccionar Líder --" if x is None else char_options.get(x, str(x))

    selected_leader_id = st.selectbox(
        "Líder de la Unidad ⭐",
        options=leader_options,
        format_func=leader_format,
        key=f"{key_prefix}_leader"
    )

    # Calcular capacidad basada en líder seleccionado
    has_leader = selected_leader_id is not None
    leadership_skill = 0
    max_capacity = BASE_CAPACITY

    if has_leader:
        leader_obj = char_map.get(selected_leader_id)
        if leader_obj:
            leadership_skill, max_capacity = get_leader_capacity(leader_obj)
            st.success(f"⭐ Líder seleccionado | Liderazgo: {leadership_skill} | Capacidad: {max_capacity} miembros")
    else:
        st.warning("Debes seleccionar un líder para continuar.")

    st.divider()

    # --- V16.0: PASO 2 - Selección de miembros adicionales ---
    st.markdown(f"**2. Seleccionar Miembros Adicionales** (Capacidad: {max_capacity})")

    # Filtrar personajes disponibles excluyendo al líder
    other_char_options = {k: v for k, v in char_options.items() if k != selected_leader_id}

    # Calcular slots restantes (líder ocupa 1)
    remaining_slots = max_capacity - 1 if has_leader else 0

    # Personajes adicionales (excluyendo líder)
    selected_other_char_ids: List[int] = st.multiselect(
        "Personajes Adicionales",
        options=list(other_char_options.keys()),
        format_func=lambda x: other_char_options.get(x, str(x)),
        max_selections=max(0, remaining_slots),
        disabled=not has_leader,
        key=f"{key_prefix}_other_chars",
        help="Personajes adicionales para la unidad (opcional)"
    )

    # Recalcular slots restantes después de otros personajes
    remaining_after_chars = remaining_slots - len(selected_other_char_ids)

    # Tropas disponibles
    troop_options = {}
    for t in available_troops:
        tid, tlabel = _troop_opt(t)
        troop_options[tid] = tlabel

    selected_troop_ids: List[int] = st.multiselect(
        "Tropas",
        options=list(troop_options.keys()),
        format_func=lambda x: troop_options.get(x, str(x)),
        max_selections=max(0, remaining_after_chars),
        disabled=not has_leader or remaining_after_chars <= 0,
        key=f"{key_prefix}_troops",
        help="Tropas para la unidad (opcional)"
    )

    # --- Métricas reactivas ---
    total_members = 1 + len(selected_other_char_ids) + len(selected_troop_ids) if has_leader else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Miembros", f"{total_members}/{max_capacity}")
    with col2:
        st.metric("Liderazgo", f"{leadership_skill}")
    with col3:
        if has_leader:
            st.success("✓ Líder asignado")
        else:
            st.error("✗ Sin líder")

    if total_members > max_capacity:
        st.error(f"Excede la capacidad máxima ({max_capacity}) del líder.")

    can_create = has_leader and 0 < total_members <= max_capacity and unit_name.strip()

    if st.button("Crear Unidad", type="primary", disabled=not can_create, use_container_width=True):
        new_unit = create_unit(player_id, unit_name.strip(), location_data)
        if new_unit:
            unit_id = new_unit["id"] if isinstance(new_unit, dict) else new_unit.id
            slot = 0

            # V16.0: El líder va primero (slot 0) para auto-asignación de is_leader
            add_unit_member(unit_id, "character", selected_leader_id, slot)
            slot += 1

            # Añadir otros personajes
            for char_id in selected_other_char_ids:
                add_unit_member(unit_id, "character", char_id, slot)
                slot += 1

            # Añadir tropas
            for troop_id in selected_troop_ids:
                add_unit_member(unit_id, "troop", troop_id, slot)
                slot += 1

            st.success(f"Unidad '{unit_name}' creada con {total_members} miembro(s).")
            st.rerun()
        else:
            st.error("Error al crear unidad.")


@st.dialog("Gestionar Unidad", width="large")
def manage_unit_dialog(
    unit: Any,
    player_id: int,
    available_chars: List[Any],
    available_troops: List[Any]
):
    """Dialog para renombrar, disolver o añadir/quitar miembros a una unidad."""
    # Acceso seguro a propiedades de unidad
    unit_id = get_prop(unit, "id")
    current_name = get_prop(unit, "name", "Unidad")
    members = get_prop(unit, "members", [])
    current_count = len(members)
    status = get_prop(unit, "status")

    # Check locks
    # V15.1: Se considera bloqueado si hay movimientos o si está en tránsito
    local_moves = get_prop(unit, "local_moves_count", 0)
    is_transit = status == UnitStatus.TRANSIT.value or status == "TRANSIT"

    is_locked = (local_moves > 0) or is_transit

    st.subheader(f"Gestionar: {current_name}")

    # V15.1: Mensajes de advertencia diferenciados
    if is_transit:
        st.warning("Acciones restringidas: Unidad en tránsito interestelar.")
    elif local_moves > 0:
        st.warning("Acciones restringidas: Unidad ya ha realizado movimientos este tick.")

    # --- TAB 1: MIEMBROS ---
    tab_members, tab_rename, tab_dissolve = st.tabs(["Miembros", "Renombrar", "Disolver"])

    with tab_members:
        # 1. Lista de Miembros Actuales
        # V16.0: Mostrar capacidad dinámica
        max_capacity = calculate_unit_display_capacity(members)
        st.markdown(f"##### Miembros Actuales ({current_count}/{max_capacity})")
        if members:
            # Sort seguro
            sorted_members = sorted(members, key=sort_key_by_prop("slot_index", 0))

            for m in sorted_members:
                col_name, col_action = st.columns([4, 1])

                # Acceso seguro a propiedades de miembro
                etype = get_prop(m, "entity_type", "?")
                slot = get_prop(m, "slot_index", 0)
                member_name = get_prop(m, "name", "???")
                # V16.0: Indicador de líder
                is_leader = get_prop(m, "is_leader", False)
                leader_icon = "⭐ " if is_leader else ""
                icon_e = "👤" if etype == "character" else "🪖"

                with col_name:
                    st.markdown(f"`[{slot}]` {leader_icon}{icon_e} {member_name}")

                with col_action:
                    # V16.0: No se puede quitar al líder, ni al último character
                    # Contar caracteres de forma segura
                    char_count = sum(1 for x in members if get_prop(x, "entity_type") == "character")
                    is_last_char = (etype == "character" and char_count == 1)

                    # V16.0: Proteger específicamente al líder
                    is_protected = is_leader or is_last_char

                    # Tooltip diferenciado según la razón del bloqueo
                    if is_leader:
                        remove_tooltip = "El líder no puede ser removido. Usa 'Disolver' para eliminar la unidad."
                    elif is_last_char:
                        remove_tooltip = "No puedes quitar al último personaje."
                    else:
                        remove_tooltip = "Quitar miembro de la unidad"

                    if st.button("❌", key=f"rm_mbr_{unit_id}_{slot}", help=remove_tooltip, disabled=is_locked or is_protected):
                        if remove_unit_member(unit_id, slot):
                            st.success("Miembro removido.")
                            st.rerun()

            # V16.0: Mostrar nota sobre líder protegido
            leader_member = next((m for m in members if get_prop(m, "is_leader", False)), None)
            if leader_member:
                leader_name = get_prop(leader_member, "name", "Líder")
                st.caption(f"⭐ **{leader_name}** es el líder de esta unidad y no puede ser removido.")
        else:
            st.info("Sin miembros.")

        st.divider()

        # 2. Añadir Miembros
        st.markdown("##### Añadir Personal")

        # V16.0: Usar capacidad dinámica basada en líder
        slots_available = max_capacity - current_count
        st.caption(f"Slots disponibles: {slots_available} (Capacidad: {max_capacity})")

        if slots_available <= 0:
            st.warning(f"La unidad está llena ({current_count}/{max_capacity}).")
        else:
            # Personajes disponibles en la ubicación
            char_opts = {}
            for c in available_chars:
                cid = get_prop(c, "id")
                cname = get_prop(c, "nombre") or "Sin Nombre"
                clvl = get_prop(c, "level", 1)
                char_opts[cid] = f"👤 {cname} (Nvl {clvl})"

            add_chars: List[int] = st.multiselect(
                "Añadir Personajes",
                options=list(char_opts.keys()),
                format_func=lambda x: char_opts.get(x, str(x)),
                max_selections=slots_available,
                key=f"add_chars_{unit_id}",
                disabled=is_locked
            )

            remaining = slots_available - len(add_chars)

            troop_opts = {}
            for t in available_troops:
                tid = get_prop(t, "id")
                tname = get_prop(t, "name") or "Sin Nombre"
                ttype = get_prop(t, "type", "INF")
                troop_opts[tid] = f"🪖 {tname} ({ttype})"

            add_troops: List[int] = st.multiselect(
                "Añadir Tropas",
                options=list(troop_opts.keys()),
                format_func=lambda x: troop_opts.get(x, str(x)),
                max_selections=max(0, remaining),
                disabled=remaining <= 0 or is_locked,
                key=f"add_troops_{unit_id}"
            )

            total_to_add = len(add_chars) + len(add_troops)
            if total_to_add > 0:
                if st.button(
                    f"Añadir {total_to_add} miembro(s)",
                    type="primary",
                    use_container_width=True,
                    key=f"btn_add_{unit_id}",
                    disabled=is_locked
                ):
                    slot = current_count
                    # Encontrar el siguiente slot libre (naive approach, append)
                    current_slots = [get_prop(m, "slot_index", 0) for m in members]
                    next_slot = max(current_slots) + 1 if current_slots else 0

                    cursor = next_slot
                    for cid in add_chars:
                        add_unit_member(unit_id, "character", cid, cursor)
                        cursor += 1
                    for tid in add_troops:
                        add_unit_member(unit_id, "troop", tid, cursor)
                        cursor += 1
                    st.success(f"{total_to_add} miembro(s) añadido(s).")
                    st.rerun()

    with tab_rename:
        new_name = st.text_input("Nuevo nombre", value=current_name, key=f"rename_{unit_id}", disabled=is_locked)
        if st.button(
            "Renombrar",
            use_container_width=True,
            disabled=is_locked or not new_name.strip() or new_name == current_name,
            key=f"btn_rename_{unit_id}"
        ):
            if rename_unit(unit_id, new_name.strip(), player_id):
                st.success("Nombre actualizado.")
                st.rerun()
            else:
                st.error("Error al renombrar.")

    # --- TAB 3: DISOLVER ---
    with tab_dissolve:
        st.markdown("**Disolver Unidad**")
        st.caption("Los miembros quedarán sueltos en la ubicación actual.")
        if st.button(
            "Disolver Unidad",
            type="secondary",
            use_container_width=True,
            key=f"btn_dissolve_{unit_id}",
            disabled=is_locked
        ):
            if delete_unit(unit_id, player_id):
                st.success("Unidad disuelta.")
                st.rerun()
            else:
                st.error("Error al disolver.")
