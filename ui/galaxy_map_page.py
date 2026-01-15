# ui/galaxy_map_page.py
import streamlit as st
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
        _render_galaxy_view()
    elif st.session_state.map_view == 'system' and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == 'planet' and st.session_state.selected_planet_id is not None:
        _render_planet_view()

def _render_galaxy_view():
    """Muestra la lista de sistemas estelares."""
    st.header("Sistemas Conocidos")
    galaxy = get_galaxy()
    
    # Crear una cuadrícula de sistemas
    cols = st.columns(4)
    for i, system in enumerate(galaxy.systems):
        with cols[i % 4]:
            with st.container(border=True):
                st.subheader(system.name)
                st.caption(f"Tipo de Estrella: {system.star.type}")
                if st.button("Explorar Sistema", key=f"sys_{system.id}"):
                    st.session_state.map_view = 'system'
                    st.session_state.selected_system_id = system.id
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
    
    # Mostrar los 9 anillos
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

    # Encontrar el planeta dentro del sistema
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


# --- Funciones de navegación de estado ---
def _reset_to_galaxy_view():
    st.session_state.map_view = 'galaxy'
    st.session_state.selected_system_id = None
    st.session_state.selected_planet_id = None
    st.rerun()

def _reset_to_system_view():
    st.session_state.map_view = 'system'
    st.session_state.selected_planet_id = None
    st.rerun()
