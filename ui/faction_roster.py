# ui/faction_roster.py (Completo)
"""
Comando - Vista jerárquica de personajes, tropas y unidades organizados por ubicación.
V11.1: Hidratación de nombres, filtrado de sistemas, UI compacta, gestión mejorada.
V11.2: Restauración de flujo inicial "Reunir al personal".
V11.3: Reclutamiento jerárquico inicial con feedback visual mejorado.
V11.4: Filtro de seguridad para excluir candidatos (Status 7) del Roster.
V11.5: Encabezados dinámicos con métricas y visibilidad estricta de nodos vacíos.
V11.6: Visibilidad permanente de órbita en planetas activos.
V12.0: Integración de diálogo de movimiento, gestión avanzada de miembros y contadores locales.
V13.0: Restricción de reclutamiento orbital (solo personal local).
V13.5: Fix Agrupación - Tránsito intra-sistema (SCO) se muestra en el sistema, no en Starlanes.
V14.1: Integración del Centro de Alertas Tácticas y Panel de Simulación de Detección.
Refactor V15.0: Compatibilidad Híbrida Pydantic V2/Dict para Unidades y Miembros.
V15.1: Bloqueo de seguridad en gestión de unidades durante Tránsito Interestelar.
V15.2: Fix Visualización - Soporte para personajes sueltos en espacio profundo (Anillos).
V15.3: Fix UX - Botón 'Crear Unidad' habilitado en espacio profundo y anillos.
V16.1: Inclusión de tropas iniciales (Infantería) en el flujo "Reunir al personal".
V17.0: Visualización de tropas sueltas en Roster (sector, órbita y anillos planetarios).
"""

import streamlit as st
import time
import json
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from data.character_repository import (
    get_all_player_characters,
    get_character_knowledge_level,
)
from data.unit_repository import (
    get_units_by_player,
    get_troops_by_player,
    create_unit,
    create_troop,  # NEW: Importado para generar tropas iniciales
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
    get_player_base_coordinates,  # NEW: Importado para ubicar tropas iniciales
)
from core.models import CommanderData, KnowledgeLevel, CharacterStatus, UnitStatus, LocationRing
from ui.character_sheet import render_character_sheet
from services.character_generation_service import recruit_character_with_ai
from ui.movement_console import render_movement_console

# V14.1: Componentes Tácticos
from ui.components.tactical import (
    render_tactical_alert_center,
    render_debug_simulation_panel
)


# --- HELPERS DE ACCESO SEGURO (PYDANTIC V2 COMPATIBILITY) ---

def get_prop(obj: Any, key: str, default: Any = None) -> Any:
    """
    Obtiene una propiedad de forma segura ya sea de un Diccionario o de un Modelo Pydantic/Objeto.
    Reemplaza a obj.get(key, default).
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def set_prop(obj: Any, key: str, value: Any) -> None:
    """
    Establece una propiedad de forma segura en un Diccionario o Modelo.
    """
    if isinstance(obj, dict):
        obj[key] = value
    else:
        # Asume que el objeto es mutable (Pydantic models por defecto lo son)
        if hasattr(obj, key):
            setattr(obj, key, value)
        else:
            # Si el modelo permite extra fields o es dinámico
            try:
                setattr(obj, key, value)
            except AttributeError:
                pass # No se pudo setear, ignorar en modelos estrictos

def sort_key_by_prop(key: str, default: Any = 0):
    """
    Retorna una función lambda para usar en sorted() o .sort() compatible con Dict y Objetos.
    """
    return lambda x: getattr(x, key, default) if not isinstance(x, dict) else x.get(key, default)


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

    # Constantes de capacidad V16.0
    BASE_CAPACITY = 4
    MAX_CAPACITY = 12

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

    # Helper para calcular Liderazgo y Capacidad de un personaje
    def _get_leader_capacity(char_obj) -> tuple:
        """Retorna (liderazgo_skill, max_capacity) para un personaje."""
        stats = get_prop(char_obj, "stats_json", {})
        if not stats or not isinstance(stats, dict):
            return 0, BASE_CAPACITY

        capacidades = stats.get("capacidades", {})
        attrs = capacidades.get("atributos", {})
        presencia = attrs.get("presencia", 5)
        voluntad = attrs.get("voluntad", 5)

        # Liderazgo = (presencia + voluntad) * 2
        leadership_skill = (presencia + voluntad) * 2
        # Capacidad = 4 + (Liderazgo // 10)
        capacity = min(MAX_CAPACITY, BASE_CAPACITY + (leadership_skill // 10))

        return leadership_skill, capacity

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
            leadership_skill, max_capacity = _get_leader_capacity(leader_obj)
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
        max_capacity = _calculate_unit_display_capacity(members)
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


# --- HELPERS DE DATOS ---

def _get_assigned_entity_ids(units: List[Any]) -> Tuple[Set[int], Set[int]]:
    """Retorna sets de IDs de characters y troops asignados a unidades."""
    assigned_chars: Set[int] = set()
    assigned_troops: Set[int] = set()
    for unit in units:
        members = get_prop(unit, "members", [])
        for member in members:
            etype = get_prop(member, "entity_type")
            eid = get_prop(member, "entity_id")
            if etype == "character":
                assigned_chars.add(eid)
            elif etype == "troop":
                assigned_troops.add(eid)
    return assigned_chars, assigned_troops


def _hydrate_unit_members(
    units: List[Any],
    char_map: Dict[int, str],
    troop_map: Dict[int, str]
) -> List[Any]:
    """Inyecta nombres reales en los miembros de cada unidad (Compatible Híbrido)."""
    for unit in units:
        members = get_prop(unit, "members", [])
        for member in members:
            eid = get_prop(member, "entity_id")
            etype = get_prop(member, "entity_type")
            
            name = f"{etype} {eid}" # Fallback
            if etype == "character":
                name = char_map.get(eid, f"Personaje {eid}")
            elif etype == "troop":
                name = troop_map.get(eid, f"Tropa {eid}")
            
            # Set seguro usando helper
            set_prop(member, "name", name)
            
    return units


def _get_systems_with_presence(
    location_index: dict,
    characters: List[Any],
    assigned_char_ids: Set[int]
) -> Set[int]:
    """Obtiene IDs de sistemas donde hay presencia del jugador."""
    system_ids: Set[int] = set()

    # Desde unidades por sector
    for sector_id, unit_list in location_index["units_by_sector"].items():
        for u in unit_list:
            sid = get_prop(u, "location_system_id")
            if sid:
                system_ids.add(sid)

    # Desde unidades por ring
    for (sys_id, ring), unit_list in location_index["units_by_system_ring"].items():
        if unit_list:
            system_ids.add(sys_id)

    # Desde personajes sueltos
    for char in characters:
        cid = get_prop(char, "id")
        if cid not in assigned_char_ids:
            sys_id = get_prop(char, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # Desde chars_by_sector (inferir sistema desde planeta)
    for sector_id, char_list in location_index["chars_by_sector"].items():
        for c in char_list:
            sys_id = get_prop(c, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # V17.0: Desde tropas sueltas por sector
    for sector_id, troop_list in location_index.get("troops_by_sector", {}).items():
        for t in troop_list:
            sys_id = get_prop(t, "location_system_id")
            if sys_id:
                system_ids.add(sys_id)

    # V17.0: Desde tropas sueltas por ring
    for (sys_id, _ring), troop_list in location_index.get("troops_by_system_ring", {}).items():
        if troop_list:
            system_ids.add(sys_id)

    return system_ids


def _build_location_index(
    characters: List[Any],
    units: List[Any],
    assigned_char_ids: Set[int],
    troops: Optional[List[Any]] = None,
    assigned_troop_ids: Optional[Set[int]] = None
) -> Dict[str, Any]:
    """
    Construye índice de entidades por ubicación.
    Retorna dict con claves:
    - 'chars_by_sector': {sector_id: [chars]}
    - 'units_by_sector': {sector_id: [units]}
    - 'units_by_system_ring': {(system_id, ring): [units]}
    - 'units_in_transit': [units]
    - 'chars_by_system_ring': {(system_id, ring): [chars]} (V15.2 Fix)
    - 'troops_by_sector': {sector_id: [troops]} (V17.0 Tropas sueltas)
    - 'troops_by_system_ring': {(system_id, ring): [troops]} (V17.0 Tropas sueltas)
    """
    troops = troops or []
    assigned_troop_ids = assigned_troop_ids or set()

    chars_by_sector: Dict[int, List[Any]] = {}
    units_by_sector: Dict[int, List[Any]] = {}
    units_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}
    units_in_transit: List[Any] = []

    # NEW V15.2: Soporte para chars sueltos en espacio
    chars_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}

    # NEW V17.0: Soporte para tropas sueltas
    troops_by_sector: Dict[int, List[Any]] = {}
    troops_by_system_ring: Dict[Tuple[int, int], List[Any]] = {}

    # Personajes sueltos
    for char in characters:
        cid = get_prop(char, "id")
        if cid in assigned_char_ids:
            continue
            
        sector_id = get_prop(char, "location_sector_id")
        if sector_id:
            chars_by_sector.setdefault(sector_id, []).append(char)
        else:
            # Check si está en espacio (System + Ring sin sector)
            system_id = get_prop(char, "location_system_id")
            if system_id:
                ring = get_prop(char, "ring", 0)
                # Ensure value is int
                if isinstance(ring, LocationRing):
                    ring = ring.value
                chars_by_system_ring.setdefault((system_id, ring), []).append(char)

    # V17.0: Tropas sueltas (no asignadas a unidades)
    for troop in troops:
        tid = get_prop(troop, "id")
        if tid in assigned_troop_ids:
            continue

        sector_id = get_prop(troop, "location_sector_id")
        if sector_id:
            troops_by_sector.setdefault(sector_id, []).append(troop)
        else:
            # Check si está en espacio (System + Ring sin sector)
            system_id = get_prop(troop, "location_system_id")
            if system_id:
                ring = get_prop(troop, "ring", 0)
                if isinstance(ring, LocationRing):
                    ring = ring.value
                troops_by_system_ring.setdefault((system_id, ring), []).append(troop)

    # Unidades por ubicación
    for unit in units:
        status = get_prop(unit, "status", "GROUND")
        
        # V13.5: Lógica de agrupación corregida
        if status == "TRANSIT":
            origin = get_prop(unit, "transit_origin_system_id")
            dest = get_prop(unit, "transit_destination_system_id")
            
            # Tránsito Local (SCO): Se queda en el sistema
            if origin is not None and origin == dest:
                # Se asigna al sistema origen y al anillo actual
                ring_val = get_prop(unit, "ring", 0)
                if isinstance(ring_val, LocationRing): 
                    ring_val = ring_val.value
                
                key = (origin, ring_val)
                units_by_system_ring.setdefault(key, []).append(unit)
                continue
            
            # Tránsito Interestelar: Va a la lista global de Starlanes
            units_in_transit.append(unit)
            continue

        sector_id = get_prop(unit, "location_sector_id")
        if sector_id:
            units_by_sector.setdefault(sector_id, []).append(unit)
        else:
            system_id = get_prop(unit, "location_system_id")
            ring = get_prop(unit, "ring", 0)
            if isinstance(ring, LocationRing): 
                ring = ring.value
                
            if system_id:
                key = (system_id, ring)
                units_by_system_ring.setdefault(key, []).append(unit)

    return {
        "chars_by_sector": chars_by_sector,
        "units_by_sector": units_by_sector,
        "units_by_system_ring": units_by_system_ring,
        "units_in_transit": units_in_transit,
        "chars_by_system_ring": chars_by_system_ring,  # V15.2
        "troops_by_sector": troops_by_sector,  # V17.0
        "troops_by_system_ring": troops_by_system_ring,  # V17.0
    }


# --- RENDERIZADO ---

def _render_loyalty_badge(loyalty: int) -> str:
    """Retorna badge de lealtad con color."""
    if loyalty < 30:
        return f'<span class="loyalty-low">{loyalty}%</span>'
    elif loyalty < 70:
        return f'<span class="loyalty-mid">{loyalty}%</span>'
    return f'<span class="loyalty-high">{loyalty}%</span>'


def _render_character_row(char: Any, player_id: int, is_space: bool):
    """Renderiza fila de personaje suelto."""
    char_id = get_prop(char, "id")
    nombre = get_prop(char, "nombre", "???")
    nivel = get_prop(char, "level", 1)
    loyalty = get_prop(char, "loyalty", 50)

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


def _render_troop_row(troop: Any, is_space: bool):
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


def _calculate_unit_display_capacity(members: List[Any]) -> int:
    """
    V16.0: Calcula la capacidad máxima de una unidad para display en UI.
    Basado en la habilidad de Liderazgo del líder.
    Fórmula: 4 + (skill_liderazgo // 10)
    """
    BASE_CAPACITY = 4
    MAX_CAPACITY = 12

    # Buscar el líder (is_leader=True y character)
    leader = None
    for m in members:
        if get_prop(m, "is_leader", False) and get_prop(m, "entity_type") == "character":
            leader = m
            break

    # Fallback: primer character si no hay líder explícito
    if not leader:
        for m in members:
            if get_prop(m, "entity_type") == "character":
                leader = m
                break

    if not leader:
        return BASE_CAPACITY

    # Obtener habilidad de Liderazgo del snapshot
    details = get_prop(leader, "details", {})
    if not details:
        return BASE_CAPACITY

    skills = details.get("habilidades", {})
    leadership_skill = skills.get("Liderazgo", 0)

    return min(MAX_CAPACITY, BASE_CAPACITY + (leadership_skill // 10))


def _render_unit_row(
    unit: Any,
    player_id: int,
    is_space: bool,
    available_chars: List[Any],
    available_troops: List[Any]
):
    """Renderiza unidad con header expandible: nombre + botones de gestión y movimiento."""
    unit_id = get_prop(unit, "id")
    name = get_prop(unit, "name", "Unidad")
    members = get_prop(unit, "members", [])
    status = get_prop(unit, "status", "GROUND")
    local_moves = get_prop(unit, "local_moves_count", 0)

    # V16.0: Calcular capacidad dinámica y estado de riesgo
    is_at_risk = get_prop(unit, "is_at_risk", False)
    max_capacity = _calculate_unit_display_capacity(members)
    current_count = len(members)

    icon = "🌌" if is_space else "🌍"
    status_emoji = {"GROUND": "🏕️", "SPACE": "🚀", "TRANSIT": "✈️"}.get(status, "❓")

    # Header dinámico con contador de movimientos
    moves_badge = f"[Movs: {local_moves}/2]" if local_moves < 2 else "[🛑 Sin Movs]"

    # V13.5: Formateo de texto para tránsito SCO local
    if status == "TRANSIT":
        # Intentar recuperar destino para mostrar SCO R[X] -> R[Y]
        origin_ring = get_prop(unit, "ring", 0)
        dest_ring = "?"
        try:
            # Recuperación robusta del anillo destino
            dest_ring_raw = get_prop(unit, "transit_destination_ring")
            if dest_ring_raw is not None:
                dest_ring = dest_ring_raw
            else:
                t_data = get_prop(unit, "transit_destination_data")
                if t_data:
                    if isinstance(t_data, str):
                        parsed = json.loads(t_data)
                        dest_ring = parsed.get("ring", "?")
                    elif isinstance(t_data, dict):
                        dest_ring = t_data.get("ring", "?")
        except:
            pass

        status_text = f"✈️ SCO R[{origin_ring}] → R[{dest_ring}]"
    else:
        status_text = status_emoji

    # V16.0: Capacidad dinámica y color de riesgo
    capacity_display = f"({current_count}/{max_capacity})"
    risk_indicator = "⚠️ " if is_at_risk else ""

    header_text = f"{icon} 🎖️ **{name}** {capacity_display} {status_text} {moves_badge} {risk_indicator}"

    # Header compacto con expander
    with st.expander(header_text, expanded=False):
        # V16.0: Mostrar advertencia si está en riesgo
        if is_at_risk:
            st.warning("Esta unidad está en riesgo: territorio hostil o excede capacidad del líder.")

        # Botones de acción en la parte superior del contenido expandido
        col_info, col_move, col_btn = st.columns([3, 1, 1])

        # Botón de movimiento (solo si no está en tránsito)
        with col_move:
            if status != "TRANSIT":
                if local_moves >= 2:
                    st.button("🛑", key=f"move_unit_lock_{unit_id}", disabled=True, help="Límite de movimientos diarios alcanzado")
                else:
                    if st.button("🚀", key=f"move_unit_{unit_id}", help="Control de Movimiento"):
                        st.session_state.selected_unit_movement = unit_id
                        movement_dialog()
            else:
                st.markdown("✈️", help="En tránsito")

        # Botón de gestión
        with col_btn:
            if st.button("⚙️", key=f"manage_unit_{unit_id}", help="Gestionar unidad"):
                manage_unit_dialog(unit, player_id, available_chars, available_troops)

        # Lista de miembros
        if members:
            st.caption("Composición:")
            # Sort seguro
            sorted_members = sorted(members, key=sort_key_by_prop("slot_index", 0))

            for m in sorted_members:
                etype = get_prop(m, "entity_type", "?")
                slot = get_prop(m, "slot_index", 0)
                member_name = get_prop(m, "name", "???")
                # V16.0: Indicador de líder
                is_leader = get_prop(m, "is_leader", False)
                leader_icon = "⭐ " if is_leader else ""

                if etype == "character":
                    st.markdown(f"`[{slot}]` {leader_icon}👤 {member_name}")
                else:
                    st.markdown(f"`[{slot}]` 🪖 {member_name}")
        else:
            st.caption("Sin miembros asignados.")


def _render_create_unit_button(
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
        _render_unit_row(unit, player_id, is_space, available_chars_here, available_troops_here)

    # Renderizar personajes sueltos
    for char in chars:
        _render_character_row(char, player_id, is_space)

    # V17.0: Renderizar tropas sueltas
    for troop in sector_troops:
        _render_troop_row(troop, is_space)

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
    all_troops: List[Any],
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
                    _render_unit_row(unit, player_id, is_space=True,
                                    available_chars=available_chars_space,
                                    available_troops=available_troops_space)
                # Render Chars
                for char in stellar_chars:
                    _render_character_row(char, player_id, is_space=True)
                # V17.0: Render Troops
                for troop in stellar_troops:
                    _render_troop_row(troop, is_space=True)

                # --- NUEVO V15.3: Botón Crear Unidad en Espacio Profundo (Ring 0) ---
                if stellar_chars:
                    # Generar ID único negativo para evitar colisión con sector_ids reales
                    pseudo_sector_id = -(system_id * 10000)
                    loc_data = {"system_id": system_id, "ring": 0, "sector_id": None}
                    # Tropas disponibles (Pool global no asignado, según lógica existente)
                    avail_troops = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

                    _render_create_unit_button(
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
                        _render_unit_row(unit, player_id, is_space=True,
                                        available_chars=[],
                                        available_troops=[t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids])
                    # Render Chars
                    for char in ring_chars:
                        _render_character_row(char, player_id, is_space=True)
                    # V17.0: Render Troops
                    for troop in ring_troops:
                        _render_troop_row(troop, is_space=True)

                    # --- NUEVO V15.3: Botón Crear Unidad en Anillo (Ring 1-6) ---
                    if ring_chars:
                        pseudo_sector_id = -(system_id * 10000 + ring)
                        loc_data = {"system_id": system_id, "ring": ring, "sector_id": None}
                        avail_troops = [t for t in all_troops if get_prop(t, "id") not in assigned_troop_ids]

                        _render_create_unit_button(
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


def _render_starlanes_section(
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
        max_capacity = _calculate_unit_display_capacity(members)
        capacity_display = f"({len(members)}/{max_capacity})"

        with st.expander(f"🌌 ✈️ **{name}** {capacity_display} | Sistema {origin} → {dest} | {ticks} ticks", expanded=False):
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("⚙️", key=f"manage_transit_{unit_id}", help="Gestionar unidad"):
                    manage_unit_dialog(unit, player_id, [], [])

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
        # Nota: get_prop se usa en objetos iterados, aquí all_characters suele ser lista de modelos o dicts.
        # Asumimos que la lista en sí se puede iterar.
        roster_characters = [c for c in all_characters if get_prop(c, "status_id") != CharacterStatus.CANDIDATE.value]
        
        # --- NUEVO: Flujo inicial de reclutamiento ---
        non_commander_count = sum(1 for c in roster_characters if not get_prop(c, "es_comandante", False))
        
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
            return

        # Si hay personal, continuar con carga normal
        troops = get_troops_by_player(player_id)
        units = get_units_by_player(player_id)
        systems = get_all_systems_from_db()

        # Mapas de nombres para hidratación
        char_map: Dict[int, str] = {get_prop(c, "id"): get_prop(c, "nombre", f"Personaje {get_prop(c, 'id')}") for c in all_characters}
        troop_map: Dict[int, str] = {get_prop(t, "id"): get_prop(t, "name", f"Tropa {get_prop(t, 'id')}") for t in troops}

        # Hidratar nombres de miembros
        units = _hydrate_unit_members(units, char_map, troop_map)

        # Obtener IDs asignados
        assigned_chars, assigned_troops = _get_assigned_entity_ids(units)

        # Construir índice de ubicaciones USANDO ROSTER FILTRADO
        # V17.0: Incluir tropas para visualización de tropas sueltas
        location_index = _build_location_index(
            roster_characters, units, assigned_chars,
            troops=troops, assigned_troop_ids=assigned_troops
        )

        # Obtener sistemas con presencia del jugador USANDO ROSTER FILTRADO
        systems_with_presence = _get_systems_with_presence(location_index, roster_characters, assigned_chars)

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
            _render_starlanes_section(location_index, player_id, [], [])

    # V14.1: Panel de Debug para Simulación de Detección
    st.divider()
    render_debug_simulation_panel(player_id, units)


# Alias para compatibilidad
def render_faction_roster():
    """Alias para compatibilidad con código existente."""
    render_comando_page()