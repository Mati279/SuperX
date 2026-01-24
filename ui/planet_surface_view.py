# ui/planet_surface_view.py (Completo)
"""
Vista Planetaria.
Interfaz para la gestión de sectores, visualización orbital y construcción.
Implementa la visualización de la Planetología Avanzada.
Actualizado V4.5: Soporte para Modo Omnisciencia (Debug) y modernización UI.
Refactor V5.8: Estandarización a 'population' y métricas mejoradas.
Corrección V6.0: Adaptación a 'sector_type' para consistencia con DB.
Refactor V7.0: Modo Observador, Navegación de Sistema, Sección Orbital y Estilo de Recursos estricto.
Mejora V7.1: Navegación contextual (Volver al Sistema del planeta actual).
Actualizado V7.2: Implementación de Niebla de Superficie (Exploración de Sectores).
Actualizado V7.6: Visualización Orbital Integrada y Filtro de Superficie.
Feature: Visualización de Soberanía y Dueños de Sectores.
"""

import streamlit as st
from data.database import get_supabase
from data.planet_repository import (
    get_planet_by_id,
    get_planet_asset,
    get_base_slots_info,
    get_planet_sectors_status,
    get_planet_buildings,
    build_structure,
    demolish_building,
    grant_sector_knowledge
)
from core.rules import calculate_planet_habitability
from core.world_constants import BUILDING_TYPES, PLANET_BIOMES, SECTOR_TYPE_ORBITAL
from ui.state import get_player_id


# --- Helpers de Facciones ---
@st.cache_data(ttl=600)
def _get_faction_map():
    """Cache simple para nombres de facciones."""
    try:
        factions = get_supabase().table("factions").select("id, name").execute().data
        return {f['id']: f['name'] for f in factions}
    except:
        return {}

def _resolve_faction_name(faction_id):
    if faction_id is None: return "Neutral"
    f_map = _get_faction_map()
    return f_map.get(faction_id, "Desconocido")

def _get_faction_name_by_player(player_id):
    """Resuelve el nombre de la facción de un jugador específico."""
    if not player_id: return "Desconocido"
    try:
        res = get_supabase().table("players").select("faction_id, factions(name)").eq("id", player_id).maybe_single().execute()
        if res.data and res.data.get('factions'):
            return res.data['factions']['name']
    except: pass
    return "Desconocido"


def render_planet_surface(planet_id: int):
    """
    Renderiza la interfaz completa de gestión y visualización para un planeta.
    Soporta modo 'Observador' si no existe una colonia (asset).
    
    Args:
        planet_id: ID del planeta que se desea visualizar y gestionar.
    """
    player_id = get_player_id()
    if not player_id:
        st.error("Error: Sesión de jugador no detectada. Por favor, reincie sesión.")
        return

    # 1. Carga de Datos (Prioritaria para navegación)
    planet = get_planet_by_id(planet_id)
    
    if not planet:
        st.error("Datos del planeta no encontrados.")
        if st.button("⬅ Volver al Mapa"):
            st.session_state.map_view = "galaxy"
            st.rerun()
        return

    asset = get_planet_asset(planet_id, player_id)

    # --- Navegación ---
    if st.button("⬅ Volver al Sistema"):
        # Actualizamos el contexto del sistema para asegurar el retorno correcto
        st.session_state.selected_system = planet['system_id']
        st.session_state.map_view = "system"
        st.rerun()
    
    # Validar modo Omnisciencia (Debug)
    debug_mode = st.session_state.get("debug_omniscience", False)

    # Lógica de Modo Observador: Ya no retornamos si no hay asset
    is_observer = asset is None and not debug_mode

    # 2. Cabecera de Información General
    _render_info_header(planet, asset)
    
    if is_observer:
        st.info("🔭 Modo Observador: No hay colonia establecida en este planeta.")
    elif not asset and debug_mode:
        st.info("🔭 Modo Omnisciencia Activado: Visualizando superficie sin colonia establecida.")

    st.divider()

    # Pre-carga de datos de sectores y edificios para distribución
    sectors = get_planet_sectors_status(planet['id'], player_id=player_id)
    buildings = get_planet_buildings(asset['id']) if asset else []
    asset_id = asset['id'] if asset else None

    # Filtrado de sectores (Orbital vs Superficie)
    orbital_sector = next((s for s in sectors if s.get('sector_type') == SECTOR_TYPE_ORBITAL), None)
    surface_sectors = [s for s in sectors if s.get('sector_type') != SECTOR_TYPE_ORBITAL]

    if debug_mode:
        st.info(f"🐛 Debug Sectores: Total {len(sectors)} | Superficie {len(surface_sectors)} | Orbital {1 if orbital_sector else 0}")

    # 3. Nueva Sección: Órbita
    st.subheader("🛰️ Órbita")
    
    if orbital_sector:
        with st.container(border=True):
             _render_sector_card(orbital_sector, buildings, asset_id, player_id, debug_mode)
    else:
        # Fallback por si la generación antigua no tiene sector orbital
        with st.container(border=True):
            st.caption("Espacio orbital no cartografiado.")
            if debug_mode: st.warning("Falta registro SECTOR_TYPE_ORBITAL en DB.")

    st.divider()

    # 4. Grid de Sectores y Gestión de Edificios (Solo Superficie)
    _render_sectors_management(planet, asset, player_id, debug_mode, surface_sectors, buildings)


def _render_info_header(planet: dict, asset: dict):
    """Muestra el resumen del planeta, tamaño y capacidad global."""
    st.title(f"Vista Planetaria: {planet['name']}")
    
    # --- VISUALIZACIÓN DE SOBERANÍA ---
    s_owner = _resolve_faction_name(planet.get('surface_owner_id'))
    o_owner = _resolve_faction_name(planet.get('orbital_owner_id'))
    st.markdown(f"**Soberanía de Superficie:** :orange[{s_owner}] | **Soberanía Orbital:** :cyan[{o_owner}]")

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        biome = planet['biome']
        st.metric("Bioma", biome)
        st.caption(PLANET_BIOMES.get(biome, {}).get("description", "Entorno."))
        
    with col2:
        # Refactor V5.8: Métrica de población estandarizada
        pop_val = planet.get('population', 0.0)
        st.metric("Población", f"{pop_val:,.2f}B")
        st.caption("Ciudadanos registrados")

    with col3:
        # Refactor V7.0: Reemplazo de Habitabilidad por Tamaño/Clase
        mass_class = planet.get('mass_class', 'Estándar')
        st.metric("Clase", mass_class)
        st.caption("Tamaño Planetario")

    # V4.4: Visualización Transparente de Seguridad
    with col4:
        # Usamos el valor centralizado en 'planets' como Source of Truth
        security_val = planet.get('security', 0.0)
        sec_breakdown = planet.get('security_breakdown') or {}
        
        st.metric("Seguridad (Sp)", f"{security_val:.1f}%", help="Nivel de seguridad fiscal y policial.")
        
        if sec_breakdown and "text" in sec_breakdown:
            with st.expander("🔍 Desglose"):
                st.caption(f"{sec_breakdown['text']}")
    
    # Slots Info (Extra row)
    st.divider()
    if asset:
        slots = get_base_slots_info(asset['id'])
        st.write(f"**Capacidad de Construcción:** {slots['used']} / {slots['total']} Slots utilizados.")
    else:
        st.write("**Capacidad de Construcción:** Modo Observador (Sin Colonia)")


def _render_sectors_management(planet: dict, asset: dict, player_id: int, debug_mode: bool, sectors: list, buildings: list):
    """Renderiza el grid de sectores de superficie y sus opciones interactivas."""
    st.subheader("Distribución de Sectores")
    
    if not sectors:
        st.info("🛰️ No se han detectado sectores de superficie. El escaneo podría estar incompleto.")
        return

    asset_id = asset['id'] if asset else None

    # Crear Grid de Sectores (2 columnas para legibilidad en Streamlit)
    for i in range(0, len(sectors), 2):
        row_sectors = sectors[i:i+2]
        cols = st.columns(2)
        
        for idx, sector in enumerate(row_sectors):
            with cols[idx]:
                with st.container(border=True):
                    _render_sector_card(sector, buildings, asset_id, player_id, debug_mode)


def _render_sector_card(sector: dict, buildings: list, asset_id: int, player_id: int, debug_mode: bool):
    """
    Renderiza una tarjeta individual para un sector específico con estilo estricto.
    V7.2: Manejo de Niebla de Superficie.
    V7.6: Soporte explícito para visualización Orbital y Bypass de Niebla.
    """
    # --- LÓGICA DE NIEBLA DE SUPERFICIE (V7.2) ---
    is_explored = sector.get('is_explored_by_player', False)
    is_orbital = sector.get('sector_type') == SECTOR_TYPE_ORBITAL
    
    # La órbita siempre es visible, independientemente del flag (safety check)
    if not is_explored and not is_orbital and not debug_mode:
        # Renderizado Oculto
        st.markdown(f"### 🌫️ Sector Desconocido ({sector['id']})")
        st.caption("Zona no cartografiada. Sensores bloqueados.")
        st.write("**Terreno:** ???")
        st.write("**Recursos:** ???")
        
        st.markdown("---")
        # Botón de Exploración Temporal
        if st.button("🔭 Iniciar Exploración", key=f"btn_explore_{sector['id']}", use_container_width=True):
            if grant_sector_knowledge(player_id, sector['id']):
                st.toast("¡Exploración completada! Datos del sector actualizados.")
                st.rerun()
            else:
                st.error("Error al registrar la exploración.")
        return # Salir temprano, no mostrar detalles
    
    # --- RENDERIZADO NORMAL (Explorado, Orbital o Debug) ---
    
    # Iconografía por tipo de sector
    icons = {
        "Urbano": "🏙️",
        "Llanura": "🌿",
        "Montañoso": "🏔️",
        "Inhospito": "🌋",
        "Orbital": "🛰️"
    }
    
    # Fix V6.0: Uso seguro de 'sector_type' (DB) con fallback a 'type' (Legacy/Model)
    s_type = sector.get('sector_type') or sector.get('type') or "Desconocido"
    icon = icons.get(s_type, "💠")
    
    st.markdown(f"### {icon} {s_type} (Sector {sector['id']})")
    
    # --- PROPIEDAD DEL SECTOR ---
    sector_buildings = [b for b in buildings if b.get('sector_id') == sector['id']]
    if sector_buildings:
        # Tomar el primer edificio para determinar el dueño
        owner_pid = sector_buildings[0].get('player_id')
        if owner_pid:
            faction_name = _get_faction_name_by_player(owner_pid)
            st.caption(f"Propiedad de: **{faction_name}**")
        else:
             st.caption("Propiedad: Desconocida")
    else:
        st.caption("Sector No Reclamado")


    # V7.0: Visualización Estricta de Recursos
    # Mapeo de colores según requerimiento
    res_color_map = {
        "Materiales": "grey",
        "Energía": "orange",
        "Datos": "blue",
        "Influencia": "violet",
        "Componentes": "red"
    }

    res_cat = sector.get('resource_category')
    lux_res = sector.get('luxury_resource')
    
    if res_cat:
        # Color específico o gris por defecto
        color = res_color_map.get(res_cat, "grey")
        # Formato: :color[**TEXTO.**]
        st.markdown(f":{color}[**{res_cat.upper()}.**]")
        
    if lux_res:
        # Recurso de lujo siempre magenta
        st.markdown(f":magenta[**{lux_res.upper()}.**]")

    # Visualización de capacidad del sector
    # Nota: 'buildings_count' es inyectado dinámicamente por planet_repository V6.0
    used = sector.get('buildings_count', 0)
    total = sector.get('slots', 2)
    
    st.write(f"Capacidad: {used} / {total}")
    st.progress(min(1.0, used / total) if total > 0 else 0)
    
    if sector_buildings:
        st.markdown("**Estructuras:**")
        for b in sector_buildings:
            b_def = BUILDING_TYPES.get(b['building_type'], {})
            name = b_def.get("name", b['building_type'])
            
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"• {name} (Tier {b['building_tier']})")
            
            # Opción de Demolición (Solo si hay asset/colonia)
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