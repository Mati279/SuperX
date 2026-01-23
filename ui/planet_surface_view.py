# ui/planet_surface_view.py (Completo)
"""
Vista de Superficie Planetaria.
Interfaz para la gestión de sectores y construcción de estructuras.
Implementa la visualización de la Planetología Avanzada (V4.3).
Actualizado V4.4: Desglose de seguridad transparente.
Actualizado V4.5: Soporte para Modo Omnisciencia (Debug) y modernización UI.
Refactor V5.8: Estandarización a 'population' y métricas mejoradas.
Corrección V6.0: Adaptación a 'sector_type' para consistencia con DB.
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
    
    # Validar modo Omnisciencia
    debug_mode = st.session_state.get("debug_omniscience", False)
    
    if not planet:
        st.error("Datos del planeta no encontrados.")
        return

    if not asset and not debug_mode:
        st.warning("⚠️ No tienes una colonia establecida en este planeta o los datos no están disponibles.")
        return

    if not asset and debug_mode:
        st.info("🔭 Modo Omnisciencia Activado: Visualizando superficie sin colonia establecida.")

    # 2. Cabecera de Información General
    _render_info_header(planet, asset)
    
    st.divider()

    # 3. Grid de Sectores y Gestión de Edificios
    _render_sectors_management(planet, asset, player_id, debug_mode)


def _render_info_header(planet: dict, asset: dict):
    """Muestra el resumen de habitabilidad, bioma y capacidad global."""
    st.title(f"🌍 Superficie: {planet['name']}")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        biome = planet['biome']
        st.metric("Bioma Planetario", biome)
        st.caption(PLANET_BIOMES.get(biome, {}).get("description", "Entorno hostil."))
        
    with col2:
        # Refactor V5.8: Métrica de población estandarizada
        pop_val = planet.get('population', 0.0)
        st.metric("Población Total", f"{pop_val:,.2f}B")
        st.caption("Ciudadanos registrados")

    with col3:
        habitability = calculate_planet_habitability(planet['id'])
        # Código de color basado en la hostilidad del entorno
        hb_color = "green" if habitability > 35 else ("orange" if habitability > -15 else "red")
        st.metric("Habitabilidad", f"{habitability}%", delta_color="normal" if habitability > 0 else "inverse")
        st.progress(max(0.0, min(1.0, (habitability + 100) / 200)))

    # V4.4: Visualización Transparente de Seguridad
    with col4:
        # Usamos el valor centralizado en 'planets' como Source of Truth
        security_val = planet.get('security', 0.0)
        sec_breakdown = planet.get('security_breakdown') or {}
        
        st.metric("Seguridad (Sp)", f"{security_val:.1f}%", help="Nivel de seguridad fiscal y policial.")
        
        if sec_breakdown and "text" in sec_breakdown:
            with st.expander("🔍 Desglose"):
                st.caption(f"{sec_breakdown['text']}")
        else:
            st.caption("Calculando...")
    
    # Slots Info (Extra row)
    st.divider()
    if asset:
        slots = get_base_slots_info(asset['id'])
        st.write(f"**Capacidad de Construcción:** {slots['used']} / {slots['total']} Slots utilizados.")
    else:
        st.write("**Capacidad de Construcción:** Modo Observador (Sin Colonia)")


def _render_sectors_management(planet: dict, asset: dict, player_id: int, debug_mode: bool):
    """Renderiza el grid de sectores y sus opciones interactivas."""
    st.subheader("Distribución de Sectores")
    
    sectors = get_planet_sectors_status(planet['id'])
    
    if debug_mode:
        st.info(f"🐛 Debug Sectores: Encontrados {len(sectors)} registros en DB para PlanetID {planet['id']}")

    if not sectors:
        st.info("🛰️ No se han detectado sectores. El escaneo de superficie podría estar incompleto.")
        return

    # Obtener edificios para filtrarlos por sector en la visualización
    # Si asset es None (Debug), buildings será vacío
    buildings = get_planet_buildings(asset['id']) if asset else []
    asset_id = asset['id'] if asset else None

    # Crear Grid de Sectores (2 columnas para legibilidad en Streamlit)
    for i in range(0, len(sectors), 2):
        row_sectors = sectors[i:i+2]
        cols = st.columns(2)
        
        for idx, sector in enumerate(row_sectors):
            with cols[idx]:
                with st.container(border=True):
                    _render_sector_card(sector, buildings, asset_id, player_id)


def _render_sector_card(sector: dict, buildings: list, asset_id: int, player_id: int):
    """Renderiza una tarjeta individual para un sector específico."""
    # Iconografía por tipo de sector
    icons = {
        "Urbano": "🏙️",
        "Llanura": "🌿",
        "Montañoso": "🏔️",
        "Inhospito": "🌋"
    }
    
    # Fix V6.0: Uso seguro de 'sector_type' (DB) con fallback a 'type' (Legacy/Model)
    s_type = sector.get('sector_type') or sector.get('type') or "Desconocido"
    icon = icons.get(s_type, "💠")
    
    st.markdown(f"### {icon} {s_type} (Sector {sector['id']})")
    
    # V4.5: Visualización de Recursos
    res_cat = sector.get('resource_category')
    lux_res = sector.get('luxury_resource')
    if res_cat:
        st.caption(f"Recurso: **{res_cat}**")
    if lux_res:
        st.caption(f"💎 Recurso de Lujo: **{lux_res}**")

    # Visualización de capacidad del sector
    # Nota: 'buildings_count' es inyectado dinámicamente por planet_repository V6.0
    used = sector.get('buildings_count', 0)
    total = sector.get('slots', 2)
    
    st.write(f"Capacidad: {used} / {total}")
    st.progress(min(1.0, used / total) if total > 0 else 0)
    
    # Listado de edificios construidos
    sector_buildings = [b for b in buildings if b.get('sector_id') == sector['id']]
    
    if sector_buildings:
        st.markdown("**Estructuras:**")
        for b in sector_buildings:
            b_def = BUILDING_TYPES.get(b['building_type'], {})
            name = b_def.get("name", b['building_type'])
            
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"• {name} (Tier {b['building_tier']})")
            
            # Opción de Demolición (Solo si hay asset)
            if asset_id and c2.button("🗑️", key=f"dem_{b['id']}", help=f"Demoler {name}"):
                if demolish_building(b['id'], player_id):
                    st.toast(f"Estructura {name} demolida.")
                    st.rerun()
    else:
        st.caption("No hay estructuras en este sector.")

    # Panel de Construcción (Solo si hay slots libres y asset existe)
    if asset_id and used < total:
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