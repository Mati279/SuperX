# ui/faction_roster.py
"""
Comando - Dashboard Táctico de Facción (V19.0)
Reescritura completa para mejorar estabilidad, UI y UX.
"""

import streamlit as st
import time
from typing import Dict, List, Any, Optional, Set

# --- Repositories ---
from data.character_repository import get_all_player_characters
from data.unit_repository import (
    get_units_by_player,
    get_troops_by_player,
    create_troop,
)
from data.world_repository import (
    get_all_systems_from_db,
    get_system_by_id,
)
from data.planet_repository import get_player_base_coordinates

# --- Services ---
from services.character_generation_service import recruit_character_with_ai, recruit_initial_crew_fast

# --- Core Models ---
from core.models import CharacterStatus, KnowledgeLevel

# --- Logic & Components (New V19) ---
from ui.logic.roster_logic import (
    get_prop,
    hydrate_unit_members,
    get_assigned_entity_ids,
    build_location_index,
    get_systems_with_presence,
)
from ui.components.roster_widgets import (
    inject_dashboard_css,
    render_unit_card,
    render_character_listing_compact,
    render_empty_state_box,
    render_create_unit_area,
)
from ui.components.tactical import render_tactical_alert_center

# --- CONSTANTS ---
RECRUITMENT_CONFIG = [
    (5, KnowledgeLevel.KNOWN, "Oficial de Mando"),
    (3, KnowledgeLevel.KNOWN, "Oficial Técnico"),
    (3, KnowledgeLevel.KNOWN, "Oficial Táctico"),
    (1, KnowledgeLevel.UNKNOWN, "Recluta"),
    (1, KnowledgeLevel.UNKNOWN, "Recluta"),
    (1, KnowledgeLevel.UNKNOWN, "Recluta"),
    (1, KnowledgeLevel.UNKNOWN, "Recluta")
]

def render_comando_page():
    """Entry point for the Command Dashboard."""
    # Lazy import to avoid circular dependency
    from ui.state import get_player

    inject_dashboard_css()
    
    player = get_player()
    if not player:
        st.error("Sesión inválida. Por favor recarga la página.")
        return

    st.title("Comando Táctico")

    # 1. DATA LOADING
    with st.spinner("Sincronizando red táctica..."):
        try:
            player_id = player.id
            all_chars = get_all_player_characters(player_id)
            
            # Filter candidates (safety check)
            active_chars = [c for c in all_chars if get_prop(c, "status_id") != CharacterStatus.CANDIDATE.value]
            
            # Check initialization state
            has_commander = any(get_prop(c, "es_comandante", False) for c in active_chars)
            total_active = len(active_chars)
            
            # --- INITIAL SETUP FLOW ---
            if total_active <= 1: # Only commander or empty
                _render_initial_setup(player_id, active_chars)
                return

            # Load full tactical data
            units = get_units_by_player(player_id)
            troops = get_troops_by_player(player_id)
            
            # Hydration
            char_map = {get_prop(c, "id"): get_prop(c, "nombre", "???") for c in active_chars}
            troop_map = {get_prop(t, "id"): get_prop(t, "name", "Tropa") for t in troops}
            
            units = hydrate_unit_members(units, char_map, troop_map)
            
            # Assignments
            assigned_chars, assigned_troops = get_assigned_entity_ids(units)
            
            # Build Index
            loc_index = build_location_index(active_chars, units, assigned_chars, troops, assigned_troops)
            
        except Exception as e:
            st.error(f"Error crítico cargando datos tácticos: {str(e)}")
            st.code(str(e)) # Debug info
            return

    # 2. DASHBOARD HEADER
    _render_dashboard_header(len(active_chars), len(units), len(loc_index.get("units_in_transit", [])))
    
    # 3. TACTICAL ALERTS
    if units:
         with st.expander("📡 Centro de Alertas Tácticas", expanded=False):
            render_tactical_alert_center(player_id, units, show_header=False)

    # 4. SYSTEM TABS
    present_systems = get_systems_with_presence(loc_index, active_chars, assigned_chars)
    
    if not present_systems and not loc_index["units_in_transit"]:
        render_empty_state_box("Sin Presencia Activa", "No hay unidades desplegadas ni personal en sistemas conocidos.")
        return

    # Create Tabs: Transit + Systems
    tabs_labels = []
    
    has_transit = len(loc_index["units_in_transit"]) > 0
    if has_transit:
        tabs_labels.append("✈️ En Tránsito")
        
    system_names = {}
    for sid in present_systems:
        sys_data = get_system_by_id(sid)
        sname = sys_data.get("name", f"Sistema {sid}") if sys_data else f"Sistema {sid}"
        system_names[sid] = sname
        tabs_labels.append(f"☀️ {sname}")
        
    if not tabs_labels:
        st.info("Iniciando sistemas de rastreo...")
        return
        
    tabs = st.tabs(tabs_labels)
    
    # Render Transit Tab
    current_tab_idx = 0
    if has_transit:
        with tabs[current_tab_idx]:
            _render_transit_tab(loc_index["units_in_transit"], player_id)
        current_tab_idx += 1
        
    # Render System Tabs
    for sid in present_systems:
        with tabs[current_tab_idx]:
            _render_system_dashboard(sid, loc_index, player_id, active_chars, troops, assigned_chars, assigned_troops)
        current_tab_idx += 1


def _render_initial_setup(player_id: int, active_chars: List[Any]):
    """Renderiza la pantalla de inicialización de facción (Conozca al Personal)."""
    st.info("⚠️ La facción requiere personal operativo para iniciar operaciones.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📋 Protocolo de Reclutamiento Estándar")
        st.write("El sistema de IA seleccionará y reclutará automáticamente el personal necesario para establecer tu cadena de mando inicial.")
        st.write("**Incluye:** Oficiales, Técnicos, Reclutas y Guarnición de Infantería.")
        
        if st.button("⚜️ Ejecutar Protocolo de Inicio", type="primary", use_container_width=True):
            _execute_initial_recruitment(player_id)
            
    with col2:
        st.markdown("### ⚡ Protocolo de Emergencia")
        st.write("Leva forzosa de personal básico. Rápido, pero sin antecedentes verificados.")
        
        if st.button("⚡ Despliegue Rápido", type="secondary", use_container_width=True):
            with st.spinner("Reclutando..."):
                recruit_initial_crew_fast(player_id, count=7)
                st.success("Personal desplegado.")
                time.sleep(1)
                st.rerun()

def _execute_initial_recruitment(player_id: int):
    """Ejecuta la lógica de reclutamiento inicial con feedback visual."""
    base_coords = get_player_base_coordinates(player_id)
    # Default to home system if base not set (rare)
    loc_data = {
        "system_id": base_coords.get("system_id"),
        "planet_id": base_coords.get("planet_id"),
        "sector_id": base_coords.get("sector_id"),
        "ring": 0
    }

    progress_bar = st.progress(0, text="Iniciando reclutamiento...")
    status_text = st.empty()
    
    total_steps = len(RECRUITMENT_CONFIG) + 1 # +1 for troops
    current_step = 0
    
    # 1. Recruit Characters
    for level, k_level, label in RECRUITMENT_CONFIG:
        status_text.text(f"Reclutando: {label}...")
        try:
            recruit_character_with_ai(player_id, level, level, k_level)
            current_step += 1
            progress_bar.progress(current_step / total_steps)
        except Exception as e:
            st.toast(f"Error parcial en reclutamiento: {e}")
            
    # 2. Recruit Troops
    status_text.text("Desplegando guarnición...")
    for i in range(1, 5):
        try:
            create_troop(player_id, f"Inf. Alpha-{i}", "INFANTRY", 1, loc_data)
        except: pass
        
    progress_bar.progress(1.0)
    status_text.text("¡Personal Listo!")
    st.success("Cadena de mando establecida.")
    time.sleep(1.5)
    st.rerun()


def _render_dashboard_header(num_chars, num_units, num_transit):
    """Métricas clave en la parte superior."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Personal Activo", num_chars)
    c2.metric("Unidades Operativas", num_units)
    c3.metric("Movimientos Pendientes", num_transit, delta_color="off")
    st.divider()


def _render_transit_tab(units_in_transit: List[Any], player_id: int):
    """Muestra unidades en tránsito."""
    st.caption("Unidades viajando entre sistemas o sectores.")
    
    for u in units_in_transit:
        # Usamos available_chars vacio pues en transito no se edita composicion usualmente
        render_unit_card(u, player_id, [], [], show_location=True)


def _render_system_dashboard(
    system_id: int, 
    loc_index: Dict[str, Any], 
    player_id: int,
    all_active_chars: List[Any], # Para filtrar disponibles
    all_troops: List[Any], 
    assigned_chars: Set[int],
    assigned_troops: Set[int]
):
    """Panel principal para un sistema."""
    
    # Split View: Space vs Ground
    c_space, c_ground = st.columns([1, 1], gap="large")
    
    # --- SPACE COLUMN ---
    with c_space:
        st.markdown("#### 🌌 Flotas y Estaciones")
        
        # Unidades Espaciales
        space_units = loc_index.get("space_forces", {}).get(system_id, [])
        if space_units:
            for u in space_units:
                render_unit_card(u, player_id, [], [], show_location=True)
        else:
            render_empty_state_box("Órbita Despejada", "Sin unidades espaciales.", "🛰️")
            
        # Unassigned Personnel in Space (e.g. on stations)
        st.divider()
        st.caption("Personal en Espacio (Sin Asignar)")
        
        # Filter chars in this system AND in space (ring != None or sector type)
        # Simplified: We use the index
        space_chars = []
        # Check by ring
        for key, chars in loc_index.get("chars_by_system_ring", {}).items():
            if key[0] == system_id:
                space_chars.extend(chars)
                
        if space_chars:
            for c in space_chars:
                render_character_listing_compact(c, player_id)
        else:
            st.caption("Ninguno.")
            
        # Create Unit Button Area (Space)
        # Default to Ring 0 (Deep Space) or first available
        loc_data = {"system_id": system_id, "ring": 0, "sector_id": None}
        avail_space_chars = [c for c in space_chars if get_prop(c, "id") not in assigned_chars]
        avail_global_troops = [t for t in all_troops if get_prop(t, "id") not in assigned_troops]
        
        if avail_space_chars:
            render_create_unit_area(player_id, loc_data, avail_space_chars, avail_global_troops, is_orbit=True)


    # --- GROUND COLUMN ---
    with c_ground:
        st.markdown("#### 🌍 Fuerzas Planetarias")
        
        # Unidades Terrestres
        ground_units = loc_index.get("ground_forces", {}).get(system_id, [])
        if ground_units:
             for u in ground_units:
                render_unit_card(u, player_id, [], [], show_location=True)
        else:
             render_empty_state_box("Sin Guarnición", "No hay fuerzas en superficie.", "⛺")

        # Unassigned Personnel on Ground
        st.divider()
        st.caption("Personal en Superficie (Sin Asignar)")
        
        ground_chars = []
        # Check by sector (exclude known space sectors if any, strictly surface)
        # Logic: If in chars_by_sector and NOT in space lists (this is a simplification)
        # Better: iterate all chars in sector index, check if sector is orbital? 
        # For now, let's grab all chars in index for this system that strictly aren't in ring index
        
        # Helper: Get all chars in this system from main list to be sure
        for c in all_active_chars:
            loc = get_prop(c, "location", {})
            if get_prop(loc, "system_id") == system_id:
                # Exclude if in hydration list of space chars
                cid = get_prop(c, "id")
                if not any(get_prop(sc, "id") == cid for sc in space_chars):
                     if cid not in assigned_chars:
                         ground_chars.append(c)

        if ground_chars:
            for c in ground_chars:
                render_character_listing_compact(c, player_id)
        else:
            st.caption("Ninguno.")

        # Create Unit Button Area (Ground)
        # We need a valid sector. Pick the first one from chars or default base
        if ground_chars:
            target_sector = get_prop(get_prop(ground_chars[0], "location"), "sector_id")
            if target_sector:
                loc_data_ground = {"system_id": system_id, "sector_id": target_sector}
                render_create_unit_area(player_id, loc_data_ground, ground_chars, avail_global_troops, is_orbit=False)

# Alias for compatibility
def render_faction_roster():
    render_comando_page()