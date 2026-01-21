# ui/planet_surface_view.py
"""
Vista de Superficie Planetaria.
Interfaz para la gestión de sectores y construcción de estructuras.
Implementa la visualización de la Planetología Avanzada (V4.3).
"""

import streamlit as st
from data.planet_repository import (
    get_planet_by_id,
    get_planet_asset,
    get_base_slots_info,
    get_planet_sectors_status,
    get_planet_buildings,
    build_structure,
    demolish_building
)
from core.rules import calculate_planet_habitability
from core.world_constants import BUILDING_TYPES, PLANET_BIOMES
from ui.state import get_player_id


def render_planet_surface(planet_id: int):
    """
    Renderiza la interfaz completa de gestión de superficie para un planeta.
    
    Args:
        planet_id: ID del planeta que se desea visualizar y gestionar.
    """
    player_id = get_player_id()
    if not player_id:
        st.error("Error: Sesión de jugador no detectada. Por favor, reincie sesión.")
        return

    # 1. Carga de Datos (Sincronizada con V4.3)
    planet = get_planet_by_id(planet_id)
    asset = get_planet_asset(planet_id, player_id)
    
    if not planet or not asset:
        st.warning("⚠️ No tienes una colonia establecida en este planeta o los datos no están disponibles.")
        return

    # 2. Cabecera de Información General
    _render_info_header(planet, asset)
    
    st.divider()

    # 3. Grid de Sectores y Gestión de Edificios
    _render_sectors_management(planet, asset, player_id)


def _render_info_header(planet: dict, asset: dict):
    """Muestra el resumen de habitabilidad, bioma y capacidad global."""
    st.title(f"🌍 Superficie: {planet['name']}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        biome = planet['biome']
        st.metric("Bioma Planetario", biome)
        # Descripción del bioma desde constantes
        desc = PLANET_BIOMES.get(biome, {}).get("description", "Entorno hostil sin catalogar.")
        st.caption(desc)
        
    with col2:
        habitability = calculate_planet_habitability(planet['id'])
        # Código de color basado en la hostilidad del entorno
        hb_color = "green" if habitability > 35 else ("orange" if habitability > -15 else "red")
        
        st.write(f"**Habitabilidad Global:** :{hb_color}[{habitability}%]")
        
        # Barra de progreso normalizada (-100 a 100 mapeado a 0.0 a 1.0)
        norm_hab = (habitability + 100) / 200
        st.progress(max(0.0, min(1.0, norm_hab)))
        st.caption("Afectada por el bioma y el desarrollo de los sectores.")
        
    with col3:
        slots = get_base_slots_info(asset['id'])
        st.metric("Slots Globales", f"{slots['used']} / {slots['total']}")
        st.caption(f"Disponibles: {slots['free']} espacios de construcción.")


def _render_sectors_management(planet: dict, asset: dict, player_id: int):
    """Renderiza el grid de sectores y sus opciones interactivas."""
    st.subheader("Distribución de Sectores")
    
    sectors = get_planet_sectors_status(planet['id'])
    if not sectors:
        st.info("🛰️ No se han detectado sectores. El escaneo de superficie podría estar incompleto.")
        return

    # Obtener edificios para filtrarlos por sector en la visualización
    buildings = get_planet_buildings(asset['id'])

    # Crear Grid de Sectores (2 columnas para legibilidad en Streamlit)
    for i in range(0, len(sectors), 2):
        row_sectors = sectors[i:i+2]
        cols = st.columns(2)
        
        for idx, sector in enumerate(row_sectors):
            with cols[idx]:
                with st.container(border=True):
                    _render_sector_card(sector, buildings, asset['id'], player_id)


def _render_sector_card(sector: dict, buildings: list, asset_id: int, player_id: int):
    """Renderiza una tarjeta individual para un sector específico."""
    # Iconografía por tipo de sector
    icons = {
        "Urbano": "🏙️",
        "Llanura": "🌿",
        "Montañoso": "🏔️",
        "Inhospito": "🌋"
    }
    icon = icons.get(sector['type'], "💠")
    
    st.markdown(f"### {icon} {sector['type']} (Sector {sector['id']})")
    
    # Visualización de capacidad del sector
    used = sector['buildings_count']
    total = sector['slots']
    st.write(f"Capacidad: {used} / {total}")
    st.progress(used / total if total > 0 else 0)
    
    # Listado de edificios construidos
    sector_buildings = [b for b in buildings if b.get('sector_id') == sector['id']]
    
    if sector_buildings:
        st.markdown("**Estructuras:**")
        for b in sector_buildings:
            b_def = BUILDING_TYPES.get(b['building_type'], {})
            name = b_def.get("name", b['building_type'])
            
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"• {name} (Tier {b['building_tier']})")
            
            # Opción de Demolición
            if c2.button("🗑️", key=f"dem_{b['id']}", help=f"Demoler {name}"):
                if demolish_building(b['id'], player_id):
                    st.toast(f"Estructura {name} demolida.")
                    st.rerun()
    else:
        st.caption("No hay estructuras en este sector.")

    # Panel de Construcción (Solo si hay slots libres)
    if used < total:
        with st.expander("🏗️ Construir Estructura"):
            available_types = list(BUILDING_TYPES.keys())
            
            # Regla de Negocio: Evitar múltiples HQ en la UI (el backend también lo valida)
            has_hq = any(b['building_type'] == 'hq' for b in buildings)
            if has_hq and 'hq' in available_types:
                available_types.remove('hq')
                
            selected_type = st.selectbox(
                "Tipo de Edificio",
                available_types,
                format_func=lambda x: BUILDING_TYPES[x]['name'],
                key=f"sel_build_{sector['id']}"
            )
            
            st.info(BUILDING_TYPES[selected_type]['description'])
            
            if st.button("Confirmar Construcción", key=f"btn_b_{sector['id']}", use_container_width=True):
                # Llamada atómica a la lógica de construcción V4.3
                new_struct = build_structure(
                    planet_asset_id=asset_id,
                    player_id=player_id,
                    building_type=selected_type,
                    sector_id=sector['id']
                )
                
                if new_struct:
                    st.toast(f"Construcción de {BUILDING_TYPES[selected_type]['name']} iniciada.")
                    st.rerun()
                else:
                    st.error("Error en la construcción. Verifique recursos o requisitos.")