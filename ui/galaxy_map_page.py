# ui/galaxy_map_page.py
import math
import streamlit as st
import plotly.graph_objects as go
from core.galaxy_generator import get_galaxy
from core.world_models import System, Planet, AsteroidBelt
from core.world_constants import RESOURCE_STAR_WEIGHTS, METAL_RESOURCES


def show_galaxy_map_page():
    """Punto de entrada para la pagina del mapa galactico (Version Plotly)."""
    st.title("Mapa de la Galaxia")
    st.markdown("---")

    # --- GESTIÓN DEL ESTADO ---
    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
    if "selected_system_id" not in st.session_state:
        st.session_state.selected_system_id = None
    if "preview_system_id" not in st.session_state:
        # ID del sistema que el usuario clickeó en el mapa pero aun no entró
        st.session_state.preview_system_id = None 
    if "selected_planet_id" not in st.session_state:
        st.session_state.selected_planet_id = None

    # --- RENDERIZADO DE VISTAS ---
    if st.session_state.map_view == "galaxy":
        _render_plotly_galaxy_map()
    elif st.session_state.map_view == "system" and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == "planet" and st.session_state.selected_planet_id is not None:
        _render_planet_view()


# -----------------------------------------------------------------------------
# LÓGICA DEL MAPA GALÁCTICO (PLOTLY)
# -----------------------------------------------------------------------------

def _render_plotly_galaxy_map():
    galaxy = get_galaxy()
    systems = sorted(galaxy.systems, key=lambda s: s.id)
    
    # --- LAYOUT DE COLUMNAS ---
    # Izquierda: Mapa (Grande) | Derecha: Panel de Info (Pequeño)
    col_map, col_info = st.columns([3, 1])

    # --- 1. CONSTRUCCIÓN DEL GRÁFICO (Izquierda) ---
    with col_map:
        # Controles de filtro rápidos sobre el mapa
        c1, c2 = st.columns([1, 1])
        with c1:
            show_routes = st.checkbox("Mostrar rutas comerciales", value=True)
        with c2:
             # Sincronizamos el selector con el preview_id
            options = {f"{s.name} (ID {s.id})": s.id for s in systems}
            # Buscar index actual si hay preview
            current_idx = 0
            if st.session_state.preview_system_id:
                for i, s in enumerate(systems):
                    if s.id == st.session_state.preview_system_id:
                        current_idx = i
                        break
            
            selected_label = st.selectbox("Buscar sistema", list(options.keys()), index=current_idx)
            # Si el usuario cambia el combo, actualizamos preview
            manual_id = options[selected_label]
            if manual_id != st.session_state.preview_system_id:
                st.session_state.preview_system_id = manual_id
                st.rerun()

        # Generar la figura
        fig = _build_plotly_figure(systems, show_routes)
        
        # RENDERIZADO INTERACTIVO
        # on_select="rerun" hace que al clickear, streamlit se recargue y nos devuelva la selección
        event = st.plotly_chart(
            fig, 
            use_container_width=True, 
            on_select="rerun",
            selection_mode="points",
            key="galaxy_map_chart"
        )
        
        # PROCESAMIENTO DE SELECCIÓN (CLICK EN MAPA)
        if event and event.selection and event.selection.points:
            # Obtenemos el punto clickeado
            point_data = event.selection.points[0]
            # Usamos 'customdata' donde guardamos el ID del sistema
            if "customdata" in point_data:
                clicked_id = point_data["customdata"]
                # Si es diferente al actual, actualizamos y recargamos
                if clicked_id != st.session_state.preview_system_id:
                    st.session_state.preview_system_id = clicked_id
                    st.rerun()

    # --- 2. PANEL DE INFORMACIÓN (Derecha) ---
    with col_info:
        if st.session_state.preview_system_id:
            _render_side_panel_info(st.session_state.preview_system_id, systems)
        else:
            st.info("👈 Selecciona un sistema en el mapa para ver sus detalles.")
            st.markdown("""
                <div style="opacity: 0.5; font-size: 0.8em;">
                Tip: Usa la rueda del mouse para hacer zoom y arrastra para moverte.
                </div>
            """, unsafe_allow_html=True)


def _build_plotly_figure(systems: list[System], show_routes: bool):
    """Crea el objeto Figura de Plotly con estrellas y rutas."""
    
    # 1. Preparar datos de Sistemas (Nodos)
    x_vals, y_vals = [], []
    colors, sizes = [], []
    texts, custom_ids = [], []
    
    # Mapeo de colores estelares
    color_map = {
        "G": "#f8f5ff", # Amarillo/Blanco
        "O": "#5b7bff", # Azul intenso
        "M": "#ff8e5b", # Rojo/Naranja
        "D": "#e0e0e0", # Enana Blanca
        "X": "#d6a4ff"  # Exotica (Violeta)
    }
    size_map = {"G": 12, "O": 16, "M": 10, "D": 8, "X": 14}
    
    # Detectamos cual es el seleccionado para resaltarlo
    selected_id = st.session_state.preview_system_id

    for s in systems:
        x_vals.append(s.position[0])
        y_vals.append(s.position[1])
        
        # Color base o destacado
        c = color_map.get(s.star.class_type, "#ffffff")
        s_size = size_map.get(s.star.class_type, 10)
        
        if s.id == selected_id:
            colors.append("#00ff00") # Verde brillante para selección
            sizes.append(s_size + 6) # Más grande
        else:
            colors.append(c)
            sizes.append(s_size)
            
        # Hover info
        texts.append(f"<b>{s.name}</b><br>Clase: {s.star.class_type}<br>ID: {s.id}")
        custom_ids.append(s.id) # Dato oculto para recuperar al clickear

    # 2. Preparar Rutas (Aristas)
    edge_x, edge_y = [], []
    if show_routes:
        # Calculamos conexiones simples basadas en distancia (vecinos cercanos)
        # Nota: Idealmente esto vendría del modelo, aquí lo recalculamos visualmente
        connections = _calculate_visual_routes(systems)
        for p1, p2 in connections:
            edge_x.extend([p1[0], p2[0], None]) # None corta la línea
            edge_y.extend([p1[1], p2[1], None])

    fig = go.Figure()

    # Capa 1: Rutas (Líneas)
    if show_routes:
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color='rgba(255, 255, 255, 0.2)'),
            hoverinfo='none',
            mode='lines',
            name='Rutas'
        ))

    # Capa 2: Estrellas (Puntos)
    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals,
        mode='markers',
        marker=dict(
            color=colors,
            size=sizes,
            line=dict(width=1, color='rgba(0,0,0,0.5)')
        ),
        text=texts,
        hoverinfo='text',
        customdata=custom_ids, # CLAVE: Aquí viaja el ID
        name='Sistemas'
    ))

    # Configuración Visual (Estilo Dark Space)
    fig.update_layout(
        plot_bgcolor='#0b0f18',
        paper_bgcolor='#0b0f18',
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False, scaleanchor="x", scaleratio=1),
        height=600, # Altura fija cómoda
        clickmode='event+select', # Habilitar selección
        dragmode='pan' # Modo por defecto mover, no seleccionar area
    )
    
    return fig


def _calculate_visual_routes(systems):
    """Genera rutas visuales basadas en proximidad simple."""
    positions = {s.id: s.position for s in systems}
    edges = set()
    
    # Lógica simple: conectar a los 2-3 más cercanos
    for s in systems:
        others = sorted(systems, key=lambda o: math.dist(s.position, o.position))
        # El 0 es el mismo s, tomamos 1, 2, 3
        for neighbor in others[1:3]: # 2 vecinos más cercanos
            # Evitar duplicados ordenando IDs
            link = tuple(sorted((s.id, neighbor.id)))
            edges.add(link)
            
    return [(positions[id1], positions[id2]) for id1, id2 in edges]


def _render_side_panel_info(system_id: int, all_systems: list[System]):
    """Panel lateral derecho con detalles y botón de entrada."""
    # Buscar el objeto sistema
    sys = next((s for s in all_systems if s.id == system_id), None)
    if not sys:
        st.error("Sistema no encontrado")
        return

    st.markdown(f"### 🔭 {sys.name}")
    st.caption(f"ID: {sys.id} | Coordenadas: {sys.position}")
    
    st.markdown("---")
    
    # Métricas clave
    c1, c2 = st.columns(2)
    c1.metric("Clase", sys.star.class_type)
    c2.metric("Rareza", sys.star.rarity)
    
    st.write(f"**⚡ Energía:** {sys.star.energy_modifier:+.0%}")
    
    # Regla especial con estilo
    if sys.star.special_rule:
        st.info(f"📜 **Regla:** {sys.star.special_rule}")
    
    st.markdown("---")
    
    # Probabilidades de recursos (Simulación visual)
    st.write("**Recursos Potenciales:**")
    # Mostramos los recursos probables segun la clase estelar
    weights = RESOURCE_STAR_WEIGHTS.get(sys.star.class_type, {})
    if weights:
        top_res = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:3]
        for name, w in top_res:
            st.write(f"- {name}")
    else:
        st.write("Desconocidos")

    st.markdown("###")
    
    # --- BOTÓN DE ACCIÓN CRÍTICO ---
    # Al ser un botón nativo de Streamlit, funciona 100% garantizado
    if st.button("🚀 ENTRAR AL SISTEMA", type="primary", use_container_width=True):
        st.session_state.selected_system_id = sys.id
        st.session_state.map_view = "system"
        st.rerun()


# -----------------------------------------------------------------------------
# VISTAS DE DETALLE (Sistema y Planeta) - Sin cambios mayores, solo integración
# -----------------------------------------------------------------------------

def _render_system_view():
    """Vista detallada de un sistema (Orrery View)."""
    galaxy = get_galaxy()
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)

    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    # Header de Navegación
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("⬅ Volver", use_container_width=True):
            _reset_to_galaxy_view()
    with c2:
        st.header(f"Sistema: {system.name}")

    # Info Estrella
    with st.expander("Informacion de la Estrella Central", expanded=True):
        colA, colB, colC = st.columns(3)
        colA.metric("Clase", system.star.class_type)
        colB.metric("Energía", f"{system.star.energy_modifier:+.0%}")
        colC.write(f"**Regla:** {system.star.special_rule}")

    st.subheader("Cuerpos en Órbita")
    
    # Renderizado de lista de planetas
    for ring in range(1, 10):
        body = system.orbital_rings.get(ring)
        if body:
            with st.container(border=True):
                cols = st.columns([1, 4, 2])
                with cols[0]:
                    st.caption(f"Anillo {ring}")
                    if isinstance(body, Planet):
                        # Icono simple segun bioma
                        st.markdown("🌍" if "Terrestre" in body.biome else "🪐")
                
                with cols[1]:
                    if isinstance(body, Planet):
                        st.markdown(f"**{body.name}**")
                        st.caption(f"Bioma: {body.biome} | Tamaño: {body.size}")
                        # Barra de recursos/exploración
                        st.progress(body.explored_pct / 100.0)
                    elif isinstance(body, AsteroidBelt):
                         st.markdown(f"**{body.name}** (Cinturón de Asteroides)")

                with cols[2]:
                    if isinstance(body, Planet):
                        if st.button("Ver", key=f"p_{body.id}"):
                            st.session_state.selected_planet_id = body.id
                            st.session_state.map_view = "planet"
                            st.rerun()


def _render_planet_view():
    """Vista detallada de un planeta."""
    galaxy = get_galaxy()
    # Recuperar sistema y planeta
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)
    if not system:
        _reset_to_galaxy_view()
        return
        
    planet = None
    for body in system.orbital_rings.values():
        if isinstance(body, Planet) and body.id == st.session_state.selected_planet_id:
            planet = body
            break
            
    if not planet:
        st.error("Planeta no encontrado.")
        _reset_to_system_view()
        return

    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("⬅ Volver", use_container_width=True):
            _reset_to_system_view()
    with c2:
        st.header(f"Planeta: {planet.name}")

    # Detalles
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Slots Construcción", planet.construction_slots)
        st.metric("Mantenimiento", f"{planet.maintenance_mod:+.0%}")
    with col2:
        st.write(f"**Bioma:** {planet.biome}")
        if planet.bonuses:
            st.info(f"Bonos: {planet.bonuses}")
        st.write("Recursos Detectados:")
        if planet.resources:
            for r in planet.resources:
                st.write(f"- {r}")
        else:
            st.write("Ninguno")

# --- FUNCIONES AUXILIARES DE NAVEGACIÓN ---
def _reset_to_galaxy_view():
    st.session_state.map_view = "galaxy"
    st.rerun()

def _reset_to_system_view():
    st.session_state.map_view = "system"
    st.session_state.selected_planet_id = None
    st.rerun()