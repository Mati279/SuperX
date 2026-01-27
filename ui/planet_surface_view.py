# ui/planet_surface_view.py (Completo)
"""
Vista Planetaria.
Interfaz para la gestión de sectores, visualización orbital y construcción.
Implementa la visualización de la Planetología Avanzada.
Refactor V10.0: Limpieza total de acciones de exploración manual y debug buttons. 
Ahora todas las acciones tácticas (Explorar/Colonizar) se realizan desde la Consola de Movimiento.
Refactor V16.0: Soporte para visualización de "En Construcción" y Puestos de Avanzada.
Refactor V17.0: Consolidación de gestión de edificios mediante modal único. Integración de bases militares.
Refactor V17.1 (Fix): Corrección de detección de soberanía basada en Planet Owner IDs.
Refactor V18.0: Eliminación de construcción manual de Bases Militares (delegado a Unidades). Unificación de UI.
Refactor V18.1 (Fix): Inyección de botón de gestión para Bases Militares detectadas fuera de la lista de edificios estándar.
Refactor V18.2 (Fix): Corrección de visibilidad del botón de gestión (gear icon) independiente del asset_id y propiedad del sector.
"""

import streamlit as st
from data.database import get_supabase
from data.planet_repository import (
    get_planet_by_id,
    get_planet_asset,
    get_planet_sectors_status,
    get_planet_buildings,
    build_structure,
    demolish_building
)
from data.world_repository import get_world_state
from core.rules import calculate_planet_habitability
from core.world_constants import (
    BUILDING_TYPES,
    PLANET_BIOMES,
    SECTOR_TYPE_ORBITAL,
    SECTOR_TYPE_URBAN,
    SECTOR_SLOTS_CONFIG,
    RESOURCE_UI_CONFIG
)
from ui.state import get_player_id
from ui.base_management import render_base_management_panel


# --- Helpers de Facciones (Simplificado) ---
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


@st.dialog("Gestión de Estructura")
def show_structure_management_modal(building: dict, asset_id: int, player_id: int, planet_id: int):
    """
    Modal unificado para la gestión de estructuras.
    Maneja tanto edificios estándar como Bases Militares virtuales.
    """
    b_type = building.get('building_type')
    is_virtual_base = building.get('is_virtual', False)
    
    # 1. Gestión de Base Militar (Integración de base_management)
    if is_virtual_base or b_type == 'military_base':
        sector_id = building.get('sector_id')
        render_base_management_panel(sector_id, planet_id)
        
        st.divider()
        st.markdown("#### Zona de Peligro")
        if st.button("🚨 Desmantelar Base Militar", type="primary", key=f"nuke_base_{building['id']}"):
             # Lógica específica para destruir bases (tabla 'bases')
             try:
                 db = get_supabase()
                 # Nota: building['id'] aquí corresponde al ID real de la base en la tabla 'bases'
                 # gracias a la inyección virtual.
                 db.table("bases").delete().eq("id", building['id']).execute()
                 st.toast("Base Militar desmantelada. Soberanía perdida.")
                 st.rerun()
             except Exception as e:
                 st.error(f"Error al desmantelar: {e}")
        return

    # 2. Gestión de Edificio Estándar
    b_def = BUILDING_TYPES.get(b_type, {})
    name = b_def.get("name", b_type)
    tier = building.get('building_tier', 1)
    
    st.header(f"{name} (Nivel {tier})")
    st.info(b_def.get('description', 'Estructura operativa.'))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Demoler
        if st.button("🗑️ Demoler", use_container_width=True, key=f"btn_dem_{building['id']}"):
            if demolish_building(building['id'], player_id):
                st.success("Orden de demolición enviada. Efectiva en el próximo ciclo.")
                st.rerun()
            else:
                st.error("Error al procesar demolición.")
                
    with col2:
        # Mejorar (Placeholder lógica básica)
        can_upgrade = False # TODO: Implementar lógica real de check_upgrade
        st.button("⬆️ Mejorar", disabled=not can_upgrade, use_container_width=True, help="Funcionalidad en desarrollo", key=f"btn_upg_{building['id']}")
        
    with col3:
        # Asignar Guardia
        st.button("🛡️ Guardia", disabled=True, use_container_width=True, help="Asignar unidad defensiva (Próximamente)", key=f"btn_grd_{building['id']}")

    st.caption("Nota: La demolición recupera el 50% de los materiales invertidos.")


def render_planet_surface(planet_id: int):
    """
    Renderiza la interfaz completa de gestión y visualización para un planeta.
    """
    player_id = get_player_id()
    if not player_id:
        st.error("Error: Sesión de jugador no detectada. Por favor, reincie sesión.")
        return

    # 1. Carga de Datos
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

    # Validar modo Omnisciencia (Debug)
    debug_mode = st.session_state.get("debug_omniscience", False)

    # Lógica de Modo Observador
    is_observer = asset is None and not debug_mode

    # 2. Cabecera de Información General
    _render_info_header(planet, asset)
    
    if is_observer:
        st.info("🔭 Modo Observador: No hay colonia establecida en este planeta.")
    elif not asset and debug_mode:
        st.info("🔭 Modo Omnisciencia Activado: Visualizando superficie sin colonia establecida.")

    st.divider()

    # Pre-carga de datos
    sectors = get_planet_sectors_status(planet['id'], player_id=player_id)
    buildings = get_planet_buildings(asset['id']) if asset else []
    asset_id = asset['id'] if asset else None

    # Filtrado de sectores
    orbital_sector = next((s for s in sectors if s.get('sector_type') == SECTOR_TYPE_ORBITAL), None)
    surface_sectors = [s for s in sectors if s.get('sector_type') != SECTOR_TYPE_ORBITAL]

    if debug_mode:
        st.info(f"🐛 Debug Sectores: Total {len(sectors)} | Superficie {len(surface_sectors)} | Orbital {1 if orbital_sector else 0}")

    # 3. Nueva Sección: Órbita
    st.subheader("🛰️ Órbita")
    
    if orbital_sector:
        with st.container(border=True):
             # MODIFICADO V17.1: Pasamos el objeto planet completo en lugar del ID
             _render_sector_card(orbital_sector, buildings, asset_id, player_id, debug_mode, planet)
    else:
        with st.container(border=True):
            st.caption("Espacio orbital no cartografiado.")

    st.divider()

    # 4. Grid de Sectores y Gestión de Edificios (Solo Superficie)
    _render_sectors_management(planet, asset, player_id, debug_mode, surface_sectors, buildings)


def _render_info_header(planet: dict, asset: dict):
    """Muestra el resumen del planeta, tamaño y capacidad global."""
    st.title(f"Vista Planetaria: {planet['name']}")
    
    s_owner = planet.get('surface_owner_name', "Desconocido")
    o_owner = planet.get('orbital_owner_name') # Puede ser None
    o_owner_str = o_owner if o_owner else "Neutral"
    
    st.markdown(f"**Controlador planetario:** :orange[{s_owner}] | **Controlador de la órbita:** :blue[{o_owner_str}]")

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        biome = planet['biome']
        st.metric("Bioma", biome)
        st.caption(PLANET_BIOMES.get(biome, {}).get("description", "Entorno."))
        
    with col2:
        pop_val = planet.get('population', 0.0)
        st.metric("Población", f"{pop_val:,.2f}B")
        st.caption("Ciudadanos registrados")

    with col3:
        mass_class = planet.get('mass_class', 'Estándar')
        st.metric("Clase", mass_class)
        st.caption("Tamaño Planetario")

    with col4:
        security_val = planet.get('security', 0.0)
        sec_breakdown = planet.get('security_breakdown') or {}
        st.metric("Seguridad (Sp)", f"{security_val:.1f}%")
        
        if sec_breakdown and "text" in sec_breakdown:
            with st.expander("🔍 Desglose"):
                st.caption(f"{sec_breakdown['text']}")
    
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
                    # MODIFICADO V17.1: Pasamos el objeto planet completo
                    _render_sector_card(sector, buildings, asset_id, player_id, debug_mode, planet)


def _render_sector_card(sector: dict, buildings: list, asset_id: int, player_id: int, debug_mode: bool, planet: dict):
    """
    Renderiza una tarjeta individual para un sector específico.
    V17.0: Reemplazo de botones directos por Modal de Gestión (Gear Icon).
    V18.1: Fix para visualizar botón de gestión en bases militares que no aparecen en la lista de edificios.
    V18.2: Fix de visibilidad de botón independiente del asset_id o propiedad del sector.
    """
    # --- LÓGICA DE NIEBLA DE SUPERFICIE ---
    is_explored = sector.get('is_explored_by_player', False)
    is_orbital = sector.get('sector_type') == SECTOR_TYPE_ORBITAL
    planet_id = planet['id']
    
    # La órbita siempre es visible, independientemente del flag (safety check)
    if not is_explored and not is_orbital and not debug_mode:
        # Renderizado Oculto
        st.markdown(f"### 🌫️ Sector Desconocido")
        st.caption("Zona no cartografiada. Sensores bloqueados.")
        st.write("**Terreno:** ???")
        st.write("**Recursos:** ???")
        st.markdown("---")
        st.info("⚠️ Requiere exploración mediante Unidad en el menú de Comando.", icon="📡")
        return # Salir temprano
    
    # --- RENDERIZADO VISIBLE ---
    
    icons = {
        "Urbano": "🏙️",
        "Llanura": "🌿",
        "Montañoso": "🏔️",
        "Inhospito": "🌋",
        "Orbital": "🛰️"
    }
    
    s_type = sector.get('sector_type') or sector.get('type') or "Desconocido"
    icon = icons.get(s_type, "💠")
    
    st.markdown(f"### {icon} {s_type}")
    
    # --- PROPIEDAD DEL SECTOR ---
    sector_buildings = [b for b in buildings if b.get('sector_id') == sector['id']]
    
    # Determinamos el dueño efectivo basándonos en la tabla PLANETS
    current_sector_owner_id = None
    
    if is_orbital:
        current_sector_owner_id = planet.get('orbital_owner_id')
    else:
        current_sector_owner_id = planet.get('surface_owner_id')

    # Visualización del Dueño
    if current_sector_owner_id:
        faction_name = _get_faction_name_by_player(current_sector_owner_id)
        # Diferenciar visualmente si soy yo
        color = "green" if current_sector_owner_id == player_id else "orange"
        st.caption(f"Propiedad de: :{color}[**{faction_name}**]")
    else:
        # Si sovereignty dice None, verificamos si hay edificios
        if sector_buildings:
            b_owner = sector_buildings[0].get('player_id')
            f_name = _get_faction_name_by_player(b_owner)
            st.caption(f"Ocupado por: :gray[**{f_name}**]")
        else:
            st.caption("Sector No Reclamado")

    # Obtener tick actual
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)

    # --- RECURSOS ---
    res_cat = sector.get('resource_category')
    lux_res = sector.get('luxury_resource')
    
    if res_cat:
        cat_key = res_cat.lower().strip()
        if cat_key in RESOURCE_UI_CONFIG:
            cfg = RESOURCE_UI_CONFIG[cat_key]
            name_display = cat_key.capitalize()
            st.markdown(f":{cfg['color']}[**{cfg['icon']} {name_display}.**]")
        else:
            st.markdown(f":gray[**{res_cat.capitalize()}.**]")
        
    if lux_res:
        st.markdown(f":violet[**💎 {lux_res}.**]")

    # --- CAPACIDAD ---
    used = sector.get('buildings_count', 0)
    total = sector.get('slots') or SECTOR_SLOTS_CONFIG.get(s_type, 2)
    
    st.write(f"Capacidad: {used} / {total}")
    st.progress(min(1.0, used / total) if total > 0 else 0)
    
    if sector_buildings:
        st.markdown("**Estructuras:**")
        for b in sector_buildings:
            b_type = b['building_type']
            b_def = BUILDING_TYPES.get(b_type, {})
            name = b.get("custom_name") or b_def.get("name", b_type)
            
            # Verificar si está en construcción
            built_at = b.get('built_at_tick', 0)
            is_under_construction = built_at > current_tick
            
            # Layout de fila: Nombre + Estado | Botón Gestión
            c1, c2 = st.columns([0.8, 0.2])
            
            with c1:
                if is_under_construction:
                    ticks_left = built_at - current_tick
                    st.markdown(f"🚧 *Construyendo: {name}* (T-{ticks_left})")
                else:
                    st.write(f"• {name} (Tier {b['building_tier']})")
            
            # Botón de Gestión (Gear Icon) - Corrección V18.2: Chequeo directo de propiedad
            # No dependemos de asset_id ya que el edificio existe
            if b.get('player_id') == player_id:
                with c2:
                    if st.button("⚙️", key=f"mng_btn_{b['id']}", help=f"Gestionar {name}"):
                        show_structure_management_modal(b, asset_id, player_id, planet_id)

    else:
        # Caso especial: Slot ocupado pero no hay edificios visibles en planet_buildings
        # Típicamente una BASE MILITAR (que vive en tabla 'bases')
        if used > 0 and not sector_buildings:
            
            # Intentar recuperar la base real para habilitar gestión
            base_obj = None
            
            # Corrección V18.2: Intentar fetch siempre si está ocupado, no solo si soy dueño del sector.
            # Esto permite ver y gestionar bases de ocupación o antes de que se actualice la soberanía.
            try:
                # Fetch al vuelo para obtener ID real para el modal
                res = get_supabase().table("bases").select("id, custom_name, level, player_id").eq("sector_id", sector['id']).maybe_single().execute()
                if res.data:
                    d = res.data
                    # Solo construimos el objeto virtual si la base es del jugador actual para gestionarla
                    # O si queremos mostrar info (aunque la gestión estará restringida)
                    if d['player_id'] == player_id:
                        base_obj = {
                            'id': d['id'],
                            'building_type': 'military_base',
                            'is_virtual': True,
                            'sector_id': sector['id'],
                            'player_id': d['player_id'],
                            'building_tier': d.get('level', 1),
                            'custom_name': d.get('custom_name')
                        }
                    # Opcional: Podríamos capturar base de enemigo aquí también para mostrar nombre real
            except Exception as e:
                    if debug_mode: st.error(f"Error fetching base: {e}")

            if base_obj:
                # Renderizado con botón de gestión habilitado
                c1, c2 = st.columns([0.8, 0.2])
                with c1:
                     name = base_obj.get('custom_name') or "Base Militar"
                     st.markdown(f"🛡️ **{name}**")
                     st.caption(f"Nivel {base_obj['building_tier']} • Operativa")
                
                with c2:
                     # El check de propiedad ya se hizo al crear base_obj
                     if st.button("⚙️", key=f"mng_base_v_{base_obj['id']}", help="Gestionar Base"):
                         show_structure_management_modal(base_obj, asset_id, player_id, planet_id)
            
            elif current_sector_owner_id == player_id:
                 # Fallback visual si falla la carga pero el sector es mío
                 st.info("🛡️ Base Militar Operativa")
            else:
                 st.warning("🛡️ Instalación Militar Detectada")

        else:
            st.caption("No hay estructuras en este sector.")

    # --- DEFINICIONES DE PROPIEDAD Y PERMISOS ---
    is_sector_empty = (used == 0)
    is_my_sector = (current_sector_owner_id == player_id)

    # --- PANEL DE CONSTRUCCIÓN (Solo si es dueño) ---
    
    if asset_id and used < total:
        if is_sector_empty and not is_my_sector:
             st.caption("🔒 Sector libre. Utiliza una unidad para establecer un Puesto de Avanzada.")

        elif is_my_sector:
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
                    
                    if t == "outpost": continue
                    if t == "military_base": continue # Bases se construyen via unidades
                        
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
             st.warning("⛔ Sector controlado por otra facción.")