# ui/galaxy_map_page.py

# ... (mantén los imports existentes) ...
# Asegúrate de que este import incluya 'get_system_by_id' si queremos mostrar el nombre del sistema
from data.world_repository import (
    get_all_systems_from_db,
    get_system_by_id,
    get_planets_by_system_id,
    get_starlanes_from_db
)
# ...

def show_galaxy_map_page():
    """Punto de entrada para la página del mapa galáctico."""
    st.title("Mapa de la Galaxia")
    
    # --- NUEVO: Panel de Dominios del Jugador ---
    # Lo colocamos antes del mapa para acceso rápido
    _render_player_domains_panel()
    
    st.markdown("---")

    # Inicialización de estado (el resto de tu código sigue igual...)
    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
    # ... (resto de la función show_galaxy_map_page)


def _render_player_domains_panel():
    """
    Muestra una lista de los planetas controlados por el jugador
    con botones de acceso rápido.
    """
    player = get_player()
    if not player:
        return

    # 1. Obtener los activos (colonias) del jugador
    # Esta función ya existe en tu repositorio y trae todo lo de la tabla 'planet_assets'
    player_assets = get_all_player_planets(player.id)

    if not player_assets:
        return

    st.subheader("🪐 Mis Dominios")
    
    # Usamos un expander por si el jugador tiene 50 planetas y no quiere tapar el mapa
    with st.expander(f"Gestionar {len(player_assets)} Asentamientos", expanded=True):
        if not player_assets:
            st.info("No tienes colonias establecidas.")
            return

        # Cabecera de la tabla visual
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown("**Asentamiento**")
        cols[1].markdown("**Ubicación**")
        cols[2].markdown("**Acción Sistema**")
        cols[3].markdown("**Acción Planeta**")
        
        st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

        for asset in player_assets:
            planet_id = asset['planet_id']
            system_id = asset['system_id']
            settlement_name = asset.get('nombre_asentamiento', 'Colonia Sin Nombre')
            
            # Recuperamos nombre del sistema para mostrarlo bonito (opcional, pero queda bien)
            # Nota: Si esto se vuelve lento con muchos planetas, se puede optimizar en la query
            system_info = get_system_by_id(system_id)
            system_name = system_info.get('name', f"Sys-{system_id}") if system_info else "Desconocido"

            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            
            with c1:
                st.write(f"🏠 **{settlement_name}**")
                st.caption(f"Población: {asset.get('poblacion', 0)}")
            
            with c2:
                st.write(f"Sist: {system_name}")
            
            with c3:
                # Botón: Ir a la vista del SISTEMA
                if st.button("🔭 Ver Sistema", key=f"btn_sys_{asset['id']}"):
                    st.session_state.selected_system_id = system_id
                    st.session_state.map_view = "system"
                    st.session_state.preview_system_id = system_id # Para que se seleccione en los filtros tmb
                    st.rerun()
            
            with c4:
                # Botón: Ir a los detalles del PLANETA
                if st.button("🌍 Gestionar", key=f"btn_pl_{asset['id']}"):
                    st.session_state.selected_system_id = system_id # Necesario para el contexto
                    st.session_state.selected_planet_id = planet_id
                    st.session_state.map_view = "planet"
                    st.rerun()
            
            st.markdown("<hr style='margin: 5px 0; opacity: 0.1'>", unsafe_allow_html=True)

# ... (resto de funciones del archivo como _render_interactive_galaxy_map, etc.)