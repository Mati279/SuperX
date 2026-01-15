# ui/galaxy_map_page.py
import streamlit as st
import streamlit.components.v1 as components
from core.galaxy_generator import get_galaxy
from core.world_models import System, Planet, AsteroidBelt

def show_galaxy_map_page():
    """Punto de entrada para la página del mapa galáctico."""
    st.title("Mapa de la Galaxia")
    st.markdown("---")

    # Inicializar el estado de la vista si no existe
    if 'map_view' not in st.session_state:
        st.session_state.map_view = 'galaxy'
        st.session_state.selected_system_id = None
        st.session_state.selected_planet_id = None

    # Enrutador de vistas
    if st.session_state.map_view == 'galaxy':
        _render_interactive_galaxy_map()
    elif st.session_state.map_view == 'system' and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == 'planet' and st.session_state.selected_planet_id is not None:
        _render_planet_view()

def _render_interactive_galaxy_map():
    """Muestra el mapa galáctico interactivo como un componente HTML/SVG."""
    st.header("Sistemas Conocidos")
    galaxy = get_galaxy()
    
    # --- Generación del Componente HTML/SVG ---
    svg_elements = []
    # Definir el color de cada estrella según su clase
    star_colors = {"G": "#FFF", "O": "#A9D0F5", "M": "#F7BE81", "D": "#E6E6E6", "X": "#E2A9F3"}

    for system in galaxy.systems:
        cx, cy = system.position
        color = star_colors.get(system.star.class_type, "#FFFFFF")
        
        # Círculo para la estrella
        svg_elements.append(
            f'<circle id="star-{system.id}" cx="{cx}" cy="{cy}" r="4" fill="{color}" class="star" onclick="handleClick({system.id})"></circle>'
        )
        # Texto con el nombre (inicialmente oculto)
        svg_elements.append(
            f'<text x="{cx + 10}" y="{cy + 5}" class="star-label" id="label-{system.id}">{system.name}</text>'
        )

    svg_content = "".join(svg_elements)

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; background-color: #0F1116; }}
        svg {{ cursor: pointer; }}
        .star {{ transition: r 0.2s ease-in-out, filter 0.2s ease-in-out; }}
        .star:hover {{ r: 8; filter: drop-shadow(0 0 5px #fff); }}
        .star-label {{ fill: #ccc; font-family: sans-serif; font-size: 12px; pointer-events: none; visibility: hidden; }}
        .star:hover + .star-label {{ visibility: visible; }}
    </style>
    </head>
    <body>
        <svg width="1000" height="800" viewbox="0 0 1000 800">
            {svg_content}
        </svg>
        <script>
            const streamlit = window.parent.Streamlit;
            function handleClick(systemId) {{
                streamlit.setComponentValue(systemId);
            }}
        </script>
    </body>
    </html>
    """

    selected_system_id = components.html(html_template, height=800)
    
    if selected_system_id:
        st.session_state.map_view = 'system'
        st.session_state.selected_system_id = selected_system_id
        st.rerun()

def _render_system_view():
    """Muestra los detalles de un sistema estelar seleccionado."""
    galaxy = get_galaxy()
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)
    
    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    st.header(f"Sistema: {system.name}")
    if st.button("<- Volver al Mapa Galáctico"):
        _reset_to_galaxy_view()

    # Detalles de la estrella
    with st.expander("Información de la Estrella Central", expanded=True):
        st.subheader(f"Estrella: {system.star.name}")
        st.metric("Modificador de Energía", f"{system.star.energy_modifier:+.0%}")
        st.info(f"Regla Especial: {system.star.special_rule}")
        st.caption(f"Clase: {system.star.class_type} | Rareza: {system.star.rarity}")
    
    st.subheader("Anillos Orbitales")
    
    for ring in range(1, 10):
        body = system.orbital_rings.get(ring)
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                st.subheader(f"Anillo {ring}")
            
            with col2:
                if body is None:
                    st.write("_(Vacío)_")
                elif isinstance(body, Planet):
                    st.write(f"**Planeta:** {body.name} ({body.biome})")
                elif isinstance(body, AsteroidBelt):
                    st.write(f"**Cinturón de Asteroides:** {body.name}")
            
            with col3:
                if isinstance(body, Planet):
                    if st.button("Ver Detalles", key=f"planet_{body.id}"):
                        st.session_state.map_view = 'planet'
                        st.session_state.selected_planet_id = body.id
                        st.rerun()

def _render_planet_view():
    """Muestra los detalles de un planeta seleccionado."""
    galaxy = get_galaxy()
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)
    
    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    planet = None
    for body in system.orbital_rings.values():
        if isinstance(body, Planet) and body.id == st.session_state.selected_planet_id:
            planet = body
            break
            
    if not planet:
        st.error("Error: Planeta no encontrado.")
        _reset_to_system_view()
        return

    st.header(f"Informe del Planeta: {planet.name}")
    if st.button(f"<- Volver al Sistema {system.name}"):
        _reset_to_system_view()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Anillo Orbital", planet.ring)
        st.metric("Slots de Construcción", planet.construction_slots)
        st.metric("Mod. Mantenimiento", f"{planet.maintenance_mod:+.0%}")
    with col2:
        st.subheader(f"Bioma: {planet.biome}")
        st.info(f"Bonus: {planet.bonuses}")

    st.subheader("Satélites Naturales (Lunas)")
    if planet.moons:
        for moon in planet.moons:
            st.write(f"- {moon.name}")
    else:
        st.write("_Este planeta no tiene lunas._")

def _reset_to_galaxy_view():
    st.session_state.map_view = 'galaxy'
    st.session_state.selected_system_id = None
    st.session_state.selected_planet_id = None
    st.rerun()

def _reset_to_system_view():
    st.session_state.map_view = 'system'
    st.session_state.selected_planet_id = None
    st.rerun()
