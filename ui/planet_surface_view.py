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
Hotfix V7.7: Sincronización DB (nombre) y corrección de Slots Urbanos.
Hotfix V7.8: Corrección visualización Soberanía (Join backend).
Actualizado V7.9.0: Cambio de fuente de nombre de facción a 'players.faccion_nombre' y actualización de etiquetas UI.
Actualizado V8.1.0: Estandarización de Recursos (RESOURCE_UI_CONFIG) y Limpieza de UI (Remove ID, Fix Colors).
Actualizado V8.2.0: Botón directo de Puesto de Avanzada (Debug Mode) en sectores no reclamados.
Actualizado V8.3.0: Estandarización de Seguridad (Sp) - Base 30 para todos los planetas.
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
from core.world_constants import (
    BUILDING_TYPES, 
    PLANET_BIOMES, 
    SECTOR_TYPE_ORBITAL,
    SECTOR_SLOTS_CONFIG,
    RESOURCE_UI_CONFIG
)
from ui.state import get_player_id


# --- Helpers de Facciones (Simplificado) ---
# Ya no necesitamos _get_faction_map masivo para la cabecera, 
# pero lo mantenemos para _get_faction_name_by_player en tarjetas de sector individuales

@st.cache_data(ttl=600)
def _get_faction_name_by_player(player_id):
    """Resuelve el nombre de la facción de un jugador específico."""
    if not player_id: return "Desconocido"
    try:
        # DB Sync: Cambio de fuente a 'faccion_nombre' directo de la tabla players
        res = get_supabase().table("players").select("faccion_nombre").eq("id", player_id).maybe_single().execute()
        if res.data:
            return res.data.get('faccion_nombre', "Sin Facción")
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
    # Ahora 'planet' trae surface_owner_name y orbital_owner_name pre-cargados
    planet = get_planet_by_id(planet_id)
    
    if not planet:
        st.error("Datos del planeta no encontrados.")
        if st.button("🌌 Volver a la Galaxia"):
            st.session_state.map_view = "galaxy"
            st.session_state.selected_planet_id = None
            st.session_state.current_page = "Mapa de la Galaxia"
            st.rerun()
        return

    asset = get_planet_asset(planet_id, player_id)

    # Navegación manejada por breadcrumbs globales en main_game_page.py

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
    
    # --- VISUALIZACIÓN DE SOBERANÍA (FIX V8.1.0) ---
    s_owner = planet.get('surface_owner_name', "Desconocido")
    o_owner = planet.get('orbital_owner_name') # Puede ser None
    
    # Validación segura para string
    o_owner_str = o_owner if o_owner else "Neutral"
    
    # Actualización de etiquetas a 'Controlador' y corrección de color orbital (:cyan -> :blue)
    st.markdown(f"**Controlador planetario:** :orange[{s_owner}] | **Controlador de la órbita:** :blue[{o_owner_str}]")

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
        
        st.metric(
            "Seguridad (Sp)", 
            f"{security_val:.1f}%", 
            help="Base Estándar (30) + Población + Infraestructura."
        )
        
        if sec_breakdown and "text" in sec_breakdown:
            with st.expander("🔍 Desglose"):
                st.caption(f"{sec_breakdown['text']}")
    
    # V8.1: Eliminada la sección redundante de "Slots Info" para limpiar la cabecera.
    st.divider()


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
    V7.7: Cálculo de Slots dinámico basado en World Constants.
    V8.1: Refactor UI (Recursos Estandarizados, Sin ID, Propiedad Destacada).
    V8.2: Botón 'Puesto de Avanzada' directo en sectores no reclamados (Debug).
    """
    # --- LÓGICA DE NIEBLA DE SUPERFICIE (V7.2) ---
    is_explored = sector.get('is_explored_by_player', False)
    is_orbital = sector.get('sector_type') == SECTOR_TYPE_ORBITAL
    
    # La órbita siempre es visible, independientemente del flag (safety check)
    if not is_explored and not is_orbital and not debug_mode:
        # Renderizado Oculto
        st.markdown(f"### 🌫️ Sector Desconocido")
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
    
    # V8.1: Título Limpio (Sin ID visible)
    st.markdown(f"### {icon} {s_type}")
    
    # --- PROPIEDAD DEL SECTOR ---
    sector_buildings = [b for b in buildings if b.get('sector_id') == sector['id']]
    
    # Determinamos el dueño actual del sector para lógica de construcción
    current_sector_owner_id = None
    
    if sector_buildings:
        # Tomar el primer edificio para determinar el dueño
        owner_pid = sector_buildings[0].get('player_id')
        current_sector_owner_id = owner_pid
        if owner_pid:
            faction_name = _get_faction_name_by_player(owner_pid)
            # V8.1: Nombre de facción destacado en color
            st.caption(f"Propiedad de: :orange[**{faction_name}**]")
        else:
             st.caption("Propiedad: Desconocida")
    else:
        st.caption("Sector No Reclamado")


    # V8.1: Visualización Estricta de Recursos (RESOURCE_UI_CONFIG)
    res_cat = sector.get('resource_category')
    lux_res = sector.get('luxury_resource')
    
    if res_cat:
        # Normalizar clave (por si viene en mayúsculas o sucio)
        cat_key = res_cat.lower().strip()
        
        if cat_key in RESOURCE_UI_CONFIG:
            cfg = RESOURCE_UI_CONFIG[cat_key]
            # Formato: :color[**ICON Nombre.**] en Sentence Case
            name_display = cat_key.capitalize()
            st.markdown(f":{cfg['color']}[**{cfg['icon']} {name_display}.**]")
        else:
            # Fallback si no está en config
            st.markdown(f":gray[**{res_cat.capitalize()}.**]")
        
    if lux_res:
        # Recurso de lujo con estilo genérico diamante magenta
        st.markdown(f":magenta[**💎 {lux_res}.**]")

    # Visualización de capacidad del sector
    # Nota: 'buildings_count' es inyectado dinámicamente por planet_repository V6.0
    used = sector.get('buildings_count', 0)
    
    # Fix V7.7: Uso de SECTOR_SLOTS_CONFIG para determinar total de slots
    total = sector.get('slots') or SECTOR_SLOTS_CONFIG.get(s_type, 2)
    
    st.write(f"Capacidad: {used} / {total}")
    st.progress(min(1.0, used / total) if total > 0 else 0)
    
    if sector_buildings:
        st.markdown("**Estructuras:**")
        for b in sector_buildings:
            b_def = BUILDING_TYPES.get(b['building_type'], {})
            name = b_def.get("name", b['building_type'])
            
            c1, c2 = st.columns([0.8, 0.2])
            c1.write(f"• {name} (Tier {b['building_tier']})")
            
            # Opción de Demolición (Solo si hay asset/colonia Y es mi edificio)
            # Nota: Si asset_id existe, implica que el jugador tiene presencia en el planeta.
            # Verificamos si el edificio pertenece al jugador actual.
            if asset_id and b.get('player_id') == player_id and c2.button("🗑️", key=f"dem_{b['id']}", help=f"Demoler {name}"):
                if demolish_building(b['id'], player_id):
                    st.toast(f"Estructura {name} demolida.")
                    st.rerun()
    else:
        st.caption("No hay estructuras en este sector.")

    # --- PANEL DE CONSTRUCCIÓN (V8.2) ---
    # REGLA 1: Sector VACÍO -> Mostrar Botón directo "Construir Puesto de Avanzada".
    # REGLA 2: Sector PROPIO -> Mostrar Expander para construir otros edificios.
    # REGLA 3: Sector AJENO -> Bloqueado.
    
    is_sector_empty = (not sector_buildings)
    is_my_sector = (current_sector_owner_id == player_id)
    
    if asset_id and used < total:
        if is_sector_empty:
             # CASO 1: SECTOR NO RECLAMADO (Botón Outpost Debug)
             # Verificar que el terreno sea válido para Outpost
             outpost_def = BUILDING_TYPES.get("outpost", {})
             allowed_terrain = outpost_def.get("allowed_terrain", [])
             
             # Si no hay restricción explícita o el tipo está en la lista:
             if not allowed_terrain or s_type in allowed_terrain:
                 if st.button("🏛 Construir Puesto de Avanzada (Debug)", key=f"btn_out_{sector['id']}", use_container_width=True, help="Coste: 0 (Debug Mode). Construcción inmediata."):
                     # Modo Debug: Llamada directa sin validación de recursos en UI
                     new_struct = build_structure(
                        planet_asset_id=asset_id,
                        player_id=player_id,
                        building_type="outpost",
                        sector_id=sector['id']
                     )
                     
                     if new_struct:
                         st.toast("✅ Puesto de Avanzada establecido (Debug Force).")
                         st.rerun()
                     else:
                         st.error("❌ No se pudo construir (Restricción de terreno o bloqueo).")
             else:
                 st.caption("🔒 Terreno no apto para asentamientos.")

        elif is_my_sector:
             # CASO 2: MI SECTOR (Menú Completo)
             with st.expander("🏗️ Construir"):
                available_types = list(BUILDING_TYPES.keys())
                
                # Regla de Negocio: Evitar múltiples HQ
                has_hq = any(b['building_type'] == 'hq' for b in buildings)
                if has_hq and 'hq' in available_types:
                    available_types.remove('hq')
                
                # Filtrar por terreno
                filtered_types = []
                for t in available_types:
                    b_def = BUILDING_TYPES[t]
                    allowed = b_def.get("allowed_terrain")
                    if not allowed or s_type in allowed:
                         filtered_types.append(t)

                selected_type = st.selectbox(
                    "Tipo de Edificio",
                    filtered_types,
                    format_func=lambda x: BUILDING_TYPES[x]['name'],
                    key=f"sel_build_{sector['id']}"
                )
                
                if selected_type:
                    st.info(BUILDING_TYPES[selected_type]['description'])
                    cost = BUILDING_TYPES[selected_type].get("material_cost", 0)
                    st.caption(f"Costo: {cost} Materiales")
                
                    if st.button("Confirmar Construcción", key=f"btn_b_{sector['id']}", use_container_width=True):
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
                            st.error("Error en la construcción.")

        else:
             # CASO 3: SECTOR AJENO
             st.warning("⛔ Sector controlado por otra facción.")