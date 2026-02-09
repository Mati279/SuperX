# ui/components/roster_widgets.py
"""
Componentes visuales para el Dashboard de Comando.
V19.0: Refactorización completa con Cards, Badges modernos y Layouts flexibles.
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

# --- CSS INJECTION ---

def inject_dashboard_css():
    """CSS específico para el dashboard de comando."""
    st.markdown("""
    <style>
    /* Card Styles */
    .unit-card {
        background-color: #1E1E1E;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 10px;
        transition: border 0.2s;
    }
    .unit-card:hover {
        border-color: #555;
    }
    .unit-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .unit-title {
        font-weight: 600;
        font-size: 1.05em;
        color: #E0E0E0;
    }
    .unit-meta {
        font-size: 0.8em;
        color: #888;
    }
    
    /* Status Badges */
    .status-badge {
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.75em;
        font-weight: 500;
        text-transform: uppercase;
    }
    .status-ground { background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid rgba(46, 204, 113, 0.3); }
    .status-space { background: rgba(69, 183, 209, 0.15); color: #45b7d1; border: 1px solid rgba(69, 183, 209, 0.3); }
    .status-transit { background: rgba(241, 196, 15, 0.15); color: #f1c40f; border: 1px solid rgba(241, 196, 15, 0.3); }
    .status-constructing { background: rgba(155, 89, 182, 0.15); color: #9b59b6; border: 1px solid rgba(155, 89, 182, 0.3); }
    
    /* Loyalty Indicators */
    .loyalty-dot {
        height: 8px;
        width: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 4px;
    }
    .loyalty-high { background-color: #2ecc71; }
    .loyalty-mid { background-color: #f1c40f; }
    .loyalty-low { background-color: #e74c3c; }

    /* Empty States */
    .empty-state-box {
        text-align: center;
        padding: 30px;
        border: 2px dashed #444;
        border-radius: 10px;
        color: #666;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)


# --- BADGES & HELPERS ---

def render_status_badge(status: str) -> str:
    """Renderiza badge de estado con CSS classes."""
    classes = {
        "GROUND": "status-ground",
        "SPACE": "status-space",
        "TRANSIT": "status-transit", 
        "CONSTRUCTING": "status-constructing"
    }
    labels = {
        "GROUND": "Tierra",
        "SPACE": "Espacio",
        "TRANSIT": "Tránsito",
        "CONSTRUCTING": "Construcción"
    }
    
    cls = classes.get(status, "status-ground")
    label = labels.get(status, status)
    
    return f'<span class="status-badge {cls}">{label}</span>'

def render_loyalty_indicator(loyalty: int) -> str:
    """Indicador visual de lealtad."""
    cls = "loyalty-high"
    if loyalty < 30: cls = "loyalty-low"
    elif loyalty < 70: cls = "loyalty-mid"
    
    return f'<span class="loyalty-dot {cls}" title="Lealtad: {loyalty}%"></span>'

# --- COMPONENTS ---

def render_unit_card(
    unit: Any, 
    player_id: int, 
    available_chars: List[Any], 
    available_troops: List[Any],
    show_location: bool = False
):
    """
    Tarjeta detallada para una unidad en el dashboard.
    """
    unit_id = get_prop(unit, "id")
    name = get_prop(unit, "name", "Unidad Sin Nombre")
    members = get_prop(unit, "members", [])
    status = get_prop(unit, "status", "GROUND")
    local_moves = get_prop(unit, "local_moves_count", 0)
    max_capacity = calculate_unit_display_capacity(members)
    current_count = len(members)
    
    # Risk check
    is_at_risk = get_prop(unit, "is_at_risk", False)
    
    # Icon based on type/composition could be added here
    icon = "🛡️" 
    if status == "SPACE": icon = "🚀"
    
    # Card Container
    with st.container():
        st.markdown(f"""
        <div class="unit-card">
            <div class="unit-card-header">
                <span class="unit-title">{icon} {name}</span>
                {render_status_badge(status)}
            </div>
            <div class="unit-meta">
                <span>👥 {current_count}/{max_capacity}</span> • 
                <span>🔄 Movs: {local_moves}/2</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Risk Warning
        if is_at_risk:
            st.warning("⚠️ Unidad en riesgo operativo.", icon="⚠️")
        
        # Location Context (Optional)
        if show_location:
            sys_id = get_prop(unit, "system_id")
            sector = get_prop(unit, "sector_id")
            st.caption(f"📍 Sistema {sys_id} | Sector {sector}")

        # Expanded Details
        with st.expander("Ver Detalles y Acciones"):
            c1, c2 = st.columns(2)
            with c1:
                # Skills Summary mockup
                skill_det = get_prop(unit, "skill_deteccion", 0)
                st.write(f"👁️ Detección: **{skill_det}**")
            with c2:
                # Members list
                st.write("**Miembros:**")
                for m in members[:3]: # Show first 3
                    mname = get_prop(m, "name", "???")
                    st.caption(f"• {mname}")
                if len(members) > 3:
                    st.caption(f"...y {len(members)-3} más")

            # Actions Toolbar
            st.divider()
            ac1, ac2, ac3 = st.columns([1, 1, 1])
            
            with ac1:
                if status == "TRANSIT":
                     st.button("✈️", key=f"u_mov_{unit_id}", disabled=True, help="En Tránsito")
                elif local_moves >= 2:
                     st.button("🛑", key=f"u_mov_{unit_id}", disabled=True, help="Sin movimientos")
                else:
                    if st.button("🚀 Mover", key=f"u_mov_{unit_id}", use_container_width=True):
                        st.session_state.selected_unit_movement = unit_id
                        movement_dialog(unit_id)
            
            with ac2:
                 if st.button("⚙️ Gestionar", key=f"u_man_{unit_id}", use_container_width=True):
                     manage_unit_dialog(unit, player_id, available_chars, available_troops)
            
            with ac3:
                 # Future action: Split/Merge?
                 pass

def render_character_listing_compact(char: Any, player_id: int):
    """
    Listado compacto para personajes sin asignar.
    """
    cid = get_prop(char, "id")
    nombre = get_prop(char, "nombre", "???")
    lvl = get_prop(char, "level", 1)
    rol = get_prop(char, "rol", "Agente")
    loyalty = get_prop(char, "loyalty", 50)
    
    col1, col2, col3, col4 = st.columns([3, 1.5, 1, 1])
    
    with col1:
        st.markdown(f"**{nombre}**")
        st.caption(f"{rol}")
    with col2:
        st.caption(f"Nvl {lvl}")
    with col3:
        st.markdown(render_loyalty_indicator(loyalty), unsafe_allow_html=True)
    with col4:
         if st.button("📄", key=f"c_view_{cid}"):
             view_character_dialog(char, player_id)

def render_empty_state_box(title: str, subtitle: str, icon: str = "∅"):
    st.markdown(f"""
    <div class="empty-state-box">
        <div style="font-size: 2em; margin-bottom: 10px;">{icon}</div>
        <div style="font-weight: 600;">{title}</div>
        <div style="font-size: 0.9em;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def render_create_unit_area(
    player_id: int,
    location_data: Dict[str, Any],
    available_chars: List[Any],
    available_troops: List[Any],
    is_orbit: bool = False
):
    """Área dedicada para crear unidades en un sector/sistema específico."""
    
    # Solo mostrar si hay recursos para crear
    if not available_chars:
        return

    st.markdown("##### ➕ Nueva Unidad")
    st.caption("Forma una nueva escuadra o flota con el personal disponible.")
    
    # Generamos un ID único para el botón basado en location
    loc_id = f"{location_data.get('system_id')}_{location_data.get('sector_id')}_{location_data.get('ring')}"
    
    if st.button("Crear Unidad aquí", key=f"btn_create_{loc_id}", use_container_width=True):
        create_unit_dialog(
            sector_id=location_data.get("sector_id"), # Puede ser None para espacio prof.
            player_id=player_id,
            location_data=location_data,
            available_chars=available_chars,
            available_troops=available_troops,
            is_orbit=is_orbit
        )