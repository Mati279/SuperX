# ui/galaxy_map_page.py (Completo)
"""
Mapa Galáctico - Usa datos directamente de la Base de Datos.
Refactorizado MMFR V2: Indicadores de Seguridad (Ss/Sp), Mantenimiento y Tooltips.
Actualizado V4.4: Uso de 'systems.security' pre-calculado y desglose.
Corrección V4.4.1: Manejo seguro de 'maybe_single' para assets inexistentes.
Corrección V5.0: Fix Mismatch 'population' vs 'poblacion' y Cálculo Dinámico de Seguridad (Ss).
Refactorizado V5.1: Protecciones 'NoneType' en respuestas de Supabase.
Actualizado V5.2: Integración con Modo Omnisciencia (Debug).
Refactor V5.8: Estandarización final a 'population' y navegación directa a Superficie.
Feature: Visualización de Soberanía (Controlador de Sistema y Planetas).
Actualizado V7.9.0: Actualización de etiquetas de interfaz para Soberanía.
Actualizado V8.0: Visualización de Sectores Estelares y Megaestructuras.
Refactor Debug V8.1: Control de Soberanía por Player ID (sin facción obligatoria).
"""
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.world_constants import BUILDING_TYPES, INFRASTRUCTURE_MODULES, ECONOMY_RATES, SECTOR_TYPE_STELLAR
from data.database import get_supabase
from data.planet_repository import (
    get_all_player_planets, 
    build_structure, 
    get_planet_buildings, 
    get_base_slots_info,
    upgrade_base_tier,
    upgrade_infrastructure_module,
    demolish_building,
    get_planet_by_id, 
    get_planet_asset
)
from data.world_repository import (
    get_all_systems_from_db,
    get_system_by_id,
    get_planets_by_system_id,
    get_starlanes_from_db,
    update_system_controller
)
from ui.state import get_player


# --- Constantes de visualización ---
STAR_COLORS = {"G": "#f8f5ff", "O": "#8ec5ff", "M": "#f2b880", "D": "#d7d7d7", "X": "#d6a4ff"}
STAR_SIZES = {"G": 7, "O": 8, "M": 6, "D": 7, "X": 9}
BIOME_COLORS = {
    "Terrestre (Gaya)": "#7be0a5",
    "Desértico": "#e3c07b",
    "Oceánico": "#6fb6ff",
    "Volcánico": "#ff7058",
    "Gélido": "#a8d8ff",
    "Gigante Gaseoso": "#c6a3ff",
}


# --- Helpers de Controladores (V9.0: Solo Jugadores) ---
from typing import Optional


def _get_player_name_by_id(player_id: Optional[int]) -> str:
    """
    Resuelve el nombre de un jugador por su ID.
    V9.0: Usa 'faccion_nombre' de la tabla players (consistente con planet_surface_view).
    Fallback a nombre de personaje (characters.nombre) si no hay facción.
    """
    if player_id is None:
        return "Neutral"
    try:
        # Primero: Buscar faccion_nombre en players (fuente principal de soberanía)
        res = get_supabase().table("players").select("faccion_nombre").eq("id", player_id).maybe_single().execute()
        if res and res.data:
            faction_name = res.data.get('faccion_nombre')
            if faction_name and str(faction_name).strip():
                return faction_name

        # Fallback: Buscar nombre del comandante en characters
        char_res = get_supabase().table("characters").select("nombre").eq("player_id", player_id).limit(1).maybe_single().execute()
        if char_res and char_res.data:
            char_name = char_res.data.get('nombre')
            if char_name and str(char_name).strip():
                return char_name

        return f"Jugador {player_id}"
    except Exception:
        return "Desconocido"


def _resolve_controller_name(controller_id: Optional[int]) -> str:
    """
    Resuelve el nombre del controlador de un sistema o planeta.
    V9.0: Migración completa a Jugadores (eliminación del concepto de Facciones).
    """
    if controller_id is None:
        return "Neutral"
    return _get_player_name_by_id(controller_id)


def _render_stellar_sector_panel(system_id: int, system: dict, player):
    """
    V9.0: Renderiza el panel del sector estelar con información de megaestructuras.
    Permite construcción si el jugador es el controlador del sistema.
    """
    st.subheader("🌟 Sector Estelar")

    # Obtener sector estelar de la base de datos
    stellar_sector = None
    all_stellar_buildings = []
    try:
        sector_res = get_supabase().table("sectors")\
            .select("*")\
            .eq("system_id", system_id)\
            .is_("planet_id", "null")\
            .maybe_single()\
            .execute()
        if sector_res and sector_res.data:
            stellar_sector = sector_res.data
    except Exception as e:
        st.caption(f"⚠️ Error cargando sector estelar: {e}")

    if not stellar_sector:
        st.info("ℹ️ Este sistema no tiene un sector estelar registrado en la base de datos.")
        st.caption("Ejecuta el script `populate_galaxy_db.py` después de aplicar la migración SQL.")

        # Botón debug para tomar control aunque no haya sector
        if st.session_state.get("debug_omniscience", False):
            _render_debug_control_button(system_id, system, player)
        return

    # Datos del sistema
    star_type = system.get('star_type', 'G')
    max_slots = stellar_sector.get('max_slots', 3)
    controller_id = system.get('controlling_player_id')
    controller_name = _resolve_controller_name(controller_id)
    is_controller = player and controller_id == player.id

    # Obtener TODOS los edificios estelares del sector
    try:
        buildings_res = get_supabase().table("stellar_buildings")\
            .select("*")\
            .eq("sector_id", stellar_sector['id'])\
            .execute()
        if buildings_res and buildings_res.data:
            all_stellar_buildings = buildings_res.data
    except:
        # Fallback: intentar con planet_buildings
        try:
            buildings_res = get_supabase().table("planet_buildings")\
                .select("*")\
                .eq("sector_id", stellar_sector['id'])\
                .execute()
            if buildings_res and buildings_res.data:
                all_stellar_buildings = buildings_res.data
        except:
            pass

    used_slots = len(all_stellar_buildings)
    free_slots = max(0, max_slots - used_slots)

    # --- HEADER INFO ---
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

        col1.markdown(f"**{stellar_sector.get('name', 'Espacio Estelar')}**")
        col1.caption(f"Controlador: **{controller_name}**")

        col2.metric("Clase Estelar", star_type, help=_get_star_class_description(star_type))
        col3.metric("Slots", f"{used_slots}/{max_slots}")
        col4.metric("Disponibles", f"{free_slots}")

    # --- EDIFICIOS EXISTENTES ---
    if all_stellar_buildings:
        st.markdown("#### 🏗️ Megaestructuras Activas")
        for b in all_stellar_buildings:
            b_type = b.get('building_type', 'unknown')
            b_def = BUILDING_TYPES.get(b_type, {})
            owner_id = b.get('player_id')
            owner_name = _get_player_name_by_id(owner_id)
            status_icon = "✅" if b.get('is_active', True) else "🛑"

            with st.container(border=True):
                c1, _ = st.columns([4, 1])
                c1.markdown(f"**{b_def.get('name', b_type)}** | {status_icon}")
                c1.caption(f"Propietario: {owner_name}")

                # Mostrar bonus del sistema
                bonus = b_def.get('system_bonus', {})
                prod = b_def.get('production', {})
                if bonus:
                    bonus_text = ", ".join([f"{k}: {v}" for k, v in bonus.items()])
                    c1.caption(f"🎯 Bonus: {bonus_text}")
                if prod:
                    prod_text = ", ".join([f"+{v} {k}" for k, v in prod.items()])
                    c1.caption(f"📈 Producción: {prod_text}")
    else:
        st.caption("No hay megaestructuras construidas en este sistema.")

    # --- CONSTRUCCIÓN (Solo para el controlador) ---
    st.markdown("---")

    if not player:
        st.warning("Inicia sesión para ver opciones de construcción.")
    elif not is_controller:
        st.info(f"🔒 Solo el controlador del sistema ({controller_name}) puede construir megaestructuras aquí.")
    elif free_slots == 0:
        st.warning("⚠️ No hay slots disponibles en el sector estelar.")
    else:
        st.markdown("#### 🔨 Construir Megaestructura")
        st.caption(f"Como controlador del sistema, puedes construir en {free_slots} slot(s) disponible(s).")

        # Filtrar edificios disponibles
        available_buildings = []
        for key, bdef in BUILDING_TYPES.items():
            if not bdef.get('is_stellar', False):
                continue
            required_star = bdef.get('required_star_class')
            # Verificar compatibilidad con tipo de estrella
            if required_star and required_star != star_type:
                continue
            # Verificar que no esté ya construido (solo 1 de cada tipo por sistema)
            already_built = any(b.get('building_type') == key for b in all_stellar_buildings)
            if not already_built:
                available_buildings.append((key, bdef))

        if not available_buildings:
            st.caption("Ya has construido todas las estructuras disponibles para esta clase de estrella.")
        else:
            # Selector de estructura
            options = {key: bdef['name'] for key, bdef in available_buildings}
            selected_key = st.selectbox(
                "Seleccionar estructura",
                options=list(options.keys()),
                format_func=lambda x: options[x],
                key=f"stellar_build_select_{system_id}"
            )

            if selected_key:
                bdef = BUILDING_TYPES[selected_key]

                # Mostrar detalles
                with st.container(border=True):
                    st.markdown(f"**{bdef['name']}**")
                    st.write(bdef.get('description', ''))

                    # Costos
                    cost = bdef.get('material_cost', 0)
                    maint = bdef.get('maintenance', {})
                    maint_str = ", ".join([f"{v} {k}" for k, v in maint.items()]) if maint else "Ninguno"

                    col_cost, col_maint = st.columns(2)
                    col_cost.metric("Costo", f"{cost} materiales")
                    col_maint.caption(f"**Mantenimiento:** {maint_str}")

                    # Bonus/Producción
                    bonus = bdef.get('system_bonus', {})
                    prod = bdef.get('production', {})
                    if bonus:
                        st.success(f"🎯 **Bonus del Sistema:** {', '.join([f'{k}: {v}' for k, v in bonus.items()])}")
                    if prod:
                        st.success(f"📈 **Producción:** {', '.join([f'+{v} {k}' for k, v in prod.items()])}")

                    # Restricción de estrella
                    req_star = bdef.get('required_star_class')
                    if req_star:
                        st.info(f"⭐ Requiere estrella clase **{req_star}** (actual: {star_type})")

                # Botón de construcción
                if st.button(f"🚀 Construir {bdef['name']}", key=f"build_stellar_{selected_key}_{system_id}", type="primary"):
                    success = _build_stellar_structure(
                        system_id=system_id,
                        sector_id=stellar_sector['id'],
                        player_id=player.id,
                        building_type=selected_key
                    )
                    if success:
                        st.success(f"✅ ¡{bdef['name']} construida exitosamente!")
                        st.rerun()
                    else:
                        st.error("❌ Error al construir. Verifica recursos y permisos.")

    # Botón de debug para tomar control
    if st.session_state.get("debug_omniscience", False):
        st.markdown("---")
        _render_debug_control_button(system_id, system, player)


def _get_star_class_description(star_type: str) -> str:
    """Retorna descripción de la clase estelar y estructuras especiales disponibles."""
    descriptions = {
        "O": "Gigante Azul - Permite: Colector de Radiación (+200 energía)",
        "B": "Blanca-Azul - Permite: Sincrotrón Estelar (+20% datos)",
        "A": "Blanca - Permite: Relé de Salto (viajes rápidos)",
        "F": "Blanca-Amarilla - Sin estructuras especiales",
        "G": "Amarilla (tipo Sol) - Sin estructuras especiales",
        "K": "Naranja - Permite: Refinería Integrada (+15% materiales)",
        "M": "Enana Roja - Sin estructuras especiales"
    }
    return descriptions.get(star_type, "Clase desconocida")


def _build_stellar_structure(system_id: int, sector_id: int, player_id: int, building_type: str) -> bool:
    """
    Construye una megaestructura estelar.
    V9.0: Inserta en stellar_buildings o planet_buildings según disponibilidad.
    """
    try:
        db = get_supabase()
        bdef = BUILDING_TYPES.get(building_type)
        if not bdef or not bdef.get('is_stellar'):
            return False

        # Preparar datos
        building_data = {
            "sector_id": sector_id,
            "player_id": player_id,
            "building_type": building_type,
            "is_active": True
        }

        # Intentar insertar en stellar_buildings
        try:
            response = db.table("stellar_buildings").insert(building_data).execute()
            if response and response.data:
                from data.log_repository import log_event
                log_event(f"Megaestructura '{bdef['name']}' construida en sistema {system_id}", player_id)
                return True
        except Exception:
            pass

        # Fallback a planet_buildings
        try:
            # Añadir campos requeridos por planet_buildings
            building_data["building_tier"] = 1
            building_data["pops_required"] = bdef.get("pops_required", 0)
            building_data["energy_consumption"] = bdef.get("maintenance", {}).get("celulas_energia", 0)

            response = db.table("planet_buildings").insert(building_data).execute()
            if response and response.data:
                from data.log_repository import log_event
                log_event(f"Megaestructura '{bdef['name']}' construida en sistema {system_id}", player_id)
                return True
        except Exception as e:
            print(f"Error construyendo estructura estelar: {e}")

        return False
    except Exception as e:
        print(f"Error crítico en _build_stellar_structure: {e}")
        return False


def _render_debug_control_button(system_id: int, system: dict, player):
    """
    V8.1: Botón de debug para tomar control de un sistema.
    Refactorizado para usar player_id directamente, sin requerir facción.
    """
    st.markdown("#### 🔧 Debug: Control de Sistema")

    current_controller_id = system.get('controlling_player_id')
    current_name = _resolve_controller_name(current_controller_id)
    st.caption(f"Controlador actual: {current_name} (ID: {current_controller_id})")

    if player:
        col1, col2 = st.columns(2)
        # Usamos update_system_controller del repositorio para consistencia
        
        if col1.button("🏴 Tomar Control", key=f"debug_take_control_{system_id}", type="primary"):
            try:
                # V8.1: Usar ID directo del jugador. 
                # NOTA: Requiere que la DB no tenga FK estricta a 'factions' en este campo.
                success = update_system_controller(system_id, player.id)
                
                if success:
                    st.success(f"✅ ¡Ahora controlas el sistema {system.get('name', system_id)}!")
                    st.rerun()
                else:
                    st.error("❌ Falló la actualización de soberanía.")
            except Exception as e:
                st.error(f"Error crítico: {e}")

        if col2.button("🏳️ Liberar Control", key=f"debug_release_control_{system_id}"):
            try:
                success = update_system_controller(system_id, None)
                if success:
                    st.success("✅ Sistema liberado (Neutral)")
                    st.rerun()
                else:
                    st.error("❌ Error al liberar sistema.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Inicia sesión para usar los controles de debug.")


def show_galaxy_map_page():
    st.title("Mapa de la Galaxia")
    
    # Indicador de modo debug
    if st.session_state.get("debug_omniscience", False):
        st.caption("🔭 MODO OMNISCIENCIA ACTIVO: Visibilidad total habilitada.")
        
    _render_player_domains_panel()
    st.markdown("---")

    # Inicialización de estado
    if "map_view" not in st.session_state: st.session_state.map_view = "galaxy"
    if "selected_system_id" not in st.session_state: st.session_state.selected_system_id = None
    if "preview_system_id" not in st.session_state: st.session_state.preview_system_id = None
    if "selected_planet_id" not in st.session_state: st.session_state.selected_planet_id = None

    # Bridge JS -> Python params
    if "preview_id" in st.query_params:
        try:
            p_id = int(st.query_params["preview_id"])
            st.session_state.preview_system_id = p_id
            del st.query_params["preview_id"]
        except: pass
        st.rerun()

    # Router de Vistas
    if st.session_state.map_view == "galaxy": _render_interactive_galaxy_map()
    elif st.session_state.map_view == "system": _render_system_view()
    elif st.session_state.map_view == "planet": _render_planet_view()


def _render_player_domains_panel():
    player = get_player()
    if not player: return
    # Ahora devuelve objeto joined con 'planets'
    player_assets = get_all_player_planets(player.id)
    if not player_assets: return

    st.subheader("🪐 Mis Dominios")
    with st.expander(f"Gestionar {len(player_assets)} Asentamientos", expanded=True):
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown("**Asentamiento**")
        cols[1].markdown("**Ubicación**")
        cols[2].markdown("**Seguridad (Sp)**")
        cols[3].markdown("**Acción**")
        
        st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

        for asset in player_assets:
            planet_id = asset['planet_id']
            system_id = asset['system_id']
            
            # Info desde el join 'planets'
            planet_info = asset.get('planets', {}) or {}
            system_name = planet_info.get('name') or "Sistema" # Fallback si no viene nombre sistema
            
            # Si el join no trajo system_id/name, hacemos query extra (fallback)
            if not system_name or system_name == "Sistema":
                 sys_info = get_system_by_id(system_id)
                 if sys_info: system_name = sys_info.get('name', '???')

            # Seguridad desde la tabla planets (Source of Truth)
            sp = planet_info.get('security', 0.0) 
            if sp is None: sp = 0.0

            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.write(f"🏠 **{asset.get('nombre_asentamiento', 'Colonia')}**")
            c2.write(f"{system_name}")
            
            # Semáforo de seguridad
            sec_color = "green" if sp >= 70 else "orange" if sp >= 40 else "red"
            c3.markdown(f":{sec_color}[{sp:.1f}/100]")
            
            # BOTONERA DE ACCIÓN
            with c4:
                b1, b2 = st.columns(2)
                # Botón 1: Ver en mapa (comportamiento original)
                if b1.button("🗺️", key=f"btn_map_{asset['id']}", help="Ver en Mapa"):
                    st.session_state.selected_system_id = system_id
                    st.session_state.selected_planet_id = planet_id
                    st.session_state.map_view = "planet"
                    st.rerun()
                
                # Botón 2: Ir a Superficie (Navegación directa)
                if b2.button("🌐", key=f"btn_surf_{asset['id']}", help="Gestionar Superficie"):
                    st.session_state.selected_system_id = system_id
                    st.session_state.selected_planet_id = planet_id
                    st.session_state.current_page = "Superficie" # Redirige a la nueva página
                    st.rerun()


def _render_system_view():
    system_id = st.session_state.selected_system_id
    system = get_system_by_id(system_id)
    if not system: _reset_to_galaxy_view(); return

    # 1. Obtener planetas
    planets = get_planets_by_system_id(system_id)
    
    # 2. Calcular Métricas en vivo (Fix V5.0)
    # Refactor V5.8: Solo population
    total_pop = sum(p.get('population', 0.0) or 0.0 for p in planets)

    # Seguridad (Ss): Si es nula en sistema, calculamos promedio de planetas
    ss = system.get('security')
    if ss is None: 
        secs = [p.get('security', 0.0) or 0.0 for p in planets]
        ss = sum(secs) / len(secs) if secs else 0.0
    
    st.header(f"Sistema: {system.get('name', 'Desconocido')}")

    # Obtener player temprano para usarlo en múltiples secciones
    player = get_player()

    # --- VISUALIZACIÓN DEL CONTROLADOR ---
    ctl_id = system.get('controlling_player_id')
    ctl_name = _resolve_controller_name(ctl_id) # V8.1: Resolver nombre genérico
    st.subheader(f"Controlador del Sistema: :blue[{ctl_name}]")
    
    col_back, col_metrics = st.columns([4, 3])
    
    if col_back.button("← Volver al mapa", type="primary"):
        _reset_to_galaxy_view()
    
    with col_metrics:
        m1, m2 = st.columns(2)
        m1.metric("Seguridad (Ss)", f"{ss:.1f}/100", help="Promedio de seguridad del sistema.")
        m2.metric("Población Total", f"{total_pop:,.1f}B")
    
    # Mostrar Desglose de Sistema si existe
    sys_breakdown = system.get('security_breakdown')
    if sys_breakdown and isinstance(sys_breakdown, dict) and "details" in sys_breakdown:
        with st.expander("📊 Ver Desglose de Seguridad del Sistema"):
            st.write(sys_breakdown.get("details", ""))
            st.caption("Promedio basado en la seguridad individual de los cuerpos celestes.")

    # --- V8.0: SECTOR ESTELAR ---
    _render_stellar_sector_panel(system_id, system, player)

    st.subheader("Cuerpos celestiales")
    
    # Mapa de assets para identificar colonias propias
    player = get_player()
    my_assets_ids = set()
    if player:
        try:
            # Solo necesitamos saber SI tenemos asset
            assets_res = get_supabase().table("planet_assets")\
                .select("planet_id")\
                .eq("system_id", system_id)\
                .eq("player_id", player.id)\
                .execute()
            if assets_res and assets_res.data:
                my_assets_ids = {a['planet_id'] for a in assets_res.data}
        except: pass

    # Debug check: Si Omnisciencia está activo, asumimos "known" implícitamente
    is_omni = st.session_state.get("debug_omniscience", False)

    for ring in range(1, 10):
        planet = next((p for p in planets if p.get('orbital_ring') == ring), None)
        if not planet: continue
        
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 4, 2])
            c1.caption(f"Anillo {ring}")
            
            biome = planet.get('biome', 'Desconocido')
            color = BIOME_COLORS.get(biome, "#7ec7ff")
            c2.markdown(f"<span style='color: {color}; font-weight: 700'>{planet['name']}</span>", unsafe_allow_html=True)
            
            # Refactor V5.8: Solo population
            p_pop = planet.get('population', 0.0) or 0.0
            
            # --- INFO STRING BUILDER ---
            info_parts = []
            info_parts.append(f"Recursos: {', '.join((planet.get('resources') or [])[:3])}")
            
            if p_pop > 0:
                info_parts.append(f"👥 {p_pop:.1f}B")
            else:
                info_parts.append("🏜️ Deshabitado")
            
            pl_sec = planet.get('security', 0.0) or 0.0
            info_parts.append(f"🛡️ {pl_sec:.1f}")
            
            if planet['id'] in my_assets_ids:
                info_parts.append("🏳️ Tu Colonia")
            
            c2.caption(" | ".join(info_parts))
            
            # Botón siempre visible, el detalle interno manejará si se puede ver o no la superficie
            if c3.button("Ver Detalles", key=f"pl_det_{planet['id']}"):
                st.session_state.selected_planet_id = planet['id']
                st.session_state.map_view = "planet"
                st.rerun()


def _render_planet_view():
    player = get_player()
    planet_id = st.session_state.selected_planet_id
    
    # --- FIX V4.4.1 & V5.1: Consultas seguras y guards contra NoneType ---
    try:
        # 1. Planeta (Debe existir, usamos single)
        planet_res = get_supabase().table("planets").select("*, security, security_breakdown").eq("id", planet_id).single().execute()
        
        # Guard Crítico
        if not planet_res:
            st.error("Error de comunicación con el servidor central de datos.")
            if st.button("Reintentar"): st.rerun()
            if st.button("Volver"): _reset_to_system_view()
            return

        planet = planet_res.data
        
        # 2. Asset (Puede NO existir, usamos maybe_single)
        asset_res = get_supabase().table("planet_assets")\
            .select("*")\
            .eq("planet_id", planet_id)\
            .eq("player_id", player.id)\
            .maybe_single()\
            .execute()
        
        # Guard para asset opcional
        asset = asset_res.data if asset_res else None
        
    except Exception as e:
        st.error(f"Error recuperando datos del planeta: {e}")
        if st.button("Volver"): _reset_to_system_view()
        return

    if not planet: 
        st.error("Planeta no encontrado en la base de datos.")
        if st.button("Regresar"): _reset_to_system_view()
        return

    st.header(f"Planeta: {planet['name']}")
    
    # --- VISUALIZACIÓN DE SOBERANÍA ---
    s_owner = _resolve_controller_name(planet.get('surface_owner_id'))
    o_owner = _resolve_controller_name(planet.get('orbital_owner_id'))
    
    # Actualización de etiquetas a 'Controlador' (V7.9.0)
    st.markdown(f"**Controlador planetario:** :orange[{s_owner}] | **Controlador de la órbita:** :cyan[{o_owner}]")
    
    if st.button("← Volver al Sistema"):
        _reset_to_system_view()

    # DATOS MÉTRICOS (MMFR V2)
    m1, m2, m3 = st.columns(3)
    
    # Refactor V5.8: Solo population
    real_pop = planet.get('population', 0.0) or 0.0
    security_val = planet.get('security', 0.0)
    if security_val is None: security_val = 0.0

    if asset:
        asset_pop = asset.get('population', 0.0) or 0.0
        m1.metric("Población (Ciudadanos)", f"{asset_pop:,.1f}B")
        
        delta_color = "normal" if security_val >= 50 else "inverse" 
        m2.metric("Seguridad (Sp)", f"{security_val:.1f}/100", delta_color=delta_color)
        
        tier = asset.get('base_tier', 1)
        m3.metric("Nivel de Base", f"Tier {tier}")
    else:
        m1.metric("Población (Nativa/Neutral)", f"{real_pop:,.1f}B")
        m2.metric("Seguridad Global", f"{security_val:.1f}/100")
        
        # Feedback de Omnisciencia
        if st.session_state.get("debug_omniscience", False):
            m3.write("🕵️ Modo Omnisciencia")
        else:
            m3.write("No colonizado por ti")
        
    # Mostrar Desglose (Si hay asset, ya se muestra abajo, sino aqui)
    # Si estamos en debug o hay desglose, lo mostramos
    if not asset and planet.get('security_breakdown'):
        bd = planet.get('security_breakdown')
        if isinstance(bd, dict) and "text" in bd:
             st.caption(f"Cálculo: {bd['text']}")

    st.markdown("---")
    if asset: 
        _render_construction_ui(player, planet, asset)
    elif st.session_state.get("debug_omniscience", False):
         st.info("ℹ️ Para ver y gestionar la superficie en Modo Omnisciencia, utiliza la herramienta de Superficie (ui/planet_surface_view). Esta vista es el resumen cartográfico.")


def _render_construction_ui(player, planet, planet_asset):
    st.markdown("### 🏯 Gestión de Colonia")
    
    # 📡 INFRAESTRUCTURA DE SEGURIDAD
    st.markdown("#### 📡 Infraestructura de Seguridad")
    st.caption("Aumenta la **Seguridad (Sp)** para mejorar la eficiencia fiscal y protegerte de ataques.")
    
    # Mostrar desglose específico aquí
    bd = planet.get('security_breakdown')
    if bd and isinstance(bd, dict) and "text" in bd:
        st.info(f"📊 Desglose Actual: {bd['text']}")
    
    mod_cols = st.columns(2)
    modules = ["sensor_ground", "sensor_orbital", "defense_aa", "defense_ground"]
    
    for idx, mod_key in enumerate(modules):
        col = mod_cols[idx % 2]
        mod_def = INFRASTRUCTURE_MODULES.get(mod_key, {})
        lvl = planet_asset.get(f"module_{mod_key}", 0)
        with col.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{mod_def['name']}** (Lvl {lvl})")
            c1.caption(mod_def.get('desc', ''))
            if c2.button("✚", key=f"up_{mod_key}"):
                res = upgrade_infrastructure_module(planet_asset['id'], mod_key, player.id)
                if res == "OK": st.rerun()
                else: st.error(res)

    st.markdown("---")

    # 🏗️ EDIFICIOS (SLOTS)
    slots = get_base_slots_info(planet_asset['id'])
    st.markdown(f"#### 🏗️ Distrito Industrial ({slots['used']}/{slots['total']} Slots)")
    st.progress(slots['used'] / slots['total'] if slots['total'] > 0 else 0)
    
    buildings = get_planet_buildings(planet_asset['id'])
    for b in buildings:
        b_def = BUILDING_TYPES.get(b['building_type'], {})
        
        status_icon = "✅" if b['is_active'] else "🛑"
        status_text = "Operativo" if b['is_active'] else "DETENIDO (Sin recursos)"
        
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{b_def['name']}** | {status_icon} {status_text}")
            
            maint = b_def.get('maintenance', {})
            maint_str = ", ".join([f"{v} {k.capitalize()}" for k, v in maint.items()])
            c1.caption(f"Mantenimiento: {maint_str}")
            
            if c2.button("🗑️", key=f"dem_{b['id']}"):
                if demolish_building(b['id'], player.id): st.rerun()

    if slots['free'] > 0:
        with st.expander("Proyectar nuevo edificio"):
            selected = st.selectbox("Tipo", list(BUILDING_TYPES.keys()), format_func=lambda x: BUILDING_TYPES[x]['name'])
            b_def = BUILDING_TYPES[selected]
            st.write(b_def['description'])
            
            maint = b_def.get('maintenance', {})
            if maint:
                st.info(f"Requiere mantenimiento: {', '.join([f'{v} {k}' for k, v in maint.items()])}")
            
            if st.button(f"Construir {b_def['name']}"):
                if build_structure(planet_asset['id'], player.id, selected): st.rerun()


# FUNCIONES DE NAVEGACIÓN
def _reset_to_galaxy_view():
    st.session_state.map_view = "galaxy"
    st.rerun()

def _reset_to_system_view():
    st.session_state.map_view = "system"
    st.rerun()

# --- UTILS MAPA ---

def _get_player_home_info():
    player = get_player()
    if not player: return None, None
    player_planets = get_all_player_planets(player.id)
    if player_planets:
        for p in player_planets:
             if "Base" in p.get('nombre_asentamiento', ''): return p.get('system_id'), p.get('planet_id')
        first = player_planets[0]
        return first.get('system_id'), first.get('planet_id')
    return None, None

def _scale_positions(systems: list, target_width: int = 1400, target_height: int = 900, margin: int = 80):
    if not systems: return {}
    xs = [s.get('x', 0) for s in systems]
    ys = [s.get('y', 0) for s in systems]
    if not xs: return {}
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)
    def scale(value, min_val, span, target):
        return margin + ((value - min_val) / span) * (target - 2 * margin)
    return {s['id']: (scale(s.get('x', 0), min_x, span_x, target_width), scale(s.get('y', 0), min_y, span_y, target_height)) for s in systems}

def _build_connections_fallback(systems: list, positions: dict, max_neighbors: int = 3):
    edges = set()
    for sys_a in systems:
        a_id = sys_a['id']
        if a_id not in positions: continue
        x1, y1 = positions[a_id]
        distances = []
        for sys_b in systems:
            b_id = sys_b['id']
            if b_id == a_id or b_id not in positions: continue
            x2, y2 = positions[b_id]
            dist = math.hypot(x1 - x2, y1 - y2)
            distances.append((dist, b_id))
        distances.sort(key=lambda t: t[0])
        for _, neighbor_id in distances[:max_neighbors]:
            edges.add(tuple(sorted((a_id, neighbor_id))))
    connections = []
    for a_id, b_id in edges:
        if a_id in positions and b_id in positions:
            ax, ay = positions[a_id]
            bx, by = positions[b_id]
            connections.append({"a_id": a_id, "b_id": b_id, "ax": ax, "ay": ay, "bx": bx, "by": by})
    return connections

def _build_connections_from_starlanes(starlanes: list, positions: dict):
    connections = []
    for lane in starlanes:
        a_id = lane.get('system_a_id')
        b_id = lane.get('system_b_id')
        if a_id in positions and b_id in positions:
            ax, ay = positions[a_id]
            bx, by = positions[b_id]
            connections.append({"a_id": a_id, "b_id": b_id, "ax": ax, "ay": ay, "bx": bx, "by": by})
    return connections

def _render_interactive_galaxy_map():
    st.header("Sistemas Conocidos")
    systems = get_all_systems_from_db()
    starlanes = get_starlanes_from_db()
    if not systems: st.error("No se pudieron cargar los sistemas."); return

    # --- PRE-CÁLCULO DE MÉTRICAS MASIVO (Fix V5.0 & V5.1) ---
    try:
        # Traemos también 'poblacion' además de 'population' por seguridad (aunque ya no se use)
        all_planets_res = get_supabase().table("planets").select("id, system_id, population, security").execute()
        all_planets_data = all_planets_res.data if all_planets_res and all_planets_res.data else []
    except:
        all_planets_data = []

    system_stats = {} 
    
    for p in all_planets_data:
        sid = p['system_id']
        # Refactor V5.8: Solo population
        pop = p.get('population', 0.0) or 0.0
        sec = p.get('security') or 0.0
        
        if sid not in system_stats: 
            system_stats[sid] = {'pop': 0.0, 'sec_sum': 0.0, 'count': 0}
            
        system_stats[sid]['pop'] += pop
        system_stats[sid]['sec_sum'] += sec
        system_stats[sid]['count'] += 1

    # --- UI DE CONTROL ---
    systems_sorted = sorted(systems, key=lambda s: s.get('id', 0))
    player_home_system_id, _ = _get_player_home_info()

    col_map, col_controls = st.columns([5, 2])
    with col_controls:
        search_term = st.text_input("Buscar sistema", placeholder="Ej. Alpha-Orionis")
        current_idx = 0
        if st.session_state.preview_system_id is not None:
            for i, s in enumerate(systems_sorted):
                if s['id'] == st.session_state.preview_system_id: current_idx = i; break
        
        sys_options = [s.get('name', f"Sistema {s['id']}") for s in systems_sorted]
        selected_name = st.selectbox("Seleccionar sistema", sys_options, index=current_idx)
        selected_sys = systems_sorted[sys_options.index(selected_name)]
        
        if selected_sys['id'] != st.session_state.preview_system_id:
            st.session_state.preview_system_id = selected_sys['id']
            st.rerun()

        st.markdown("---")
        show_routes = st.toggle("Mostrar rutas", value=True)
        star_scale = st.slider("Tamaño relativo", 0.8, 2.0, 1.0, 0.05)

        if st.session_state.preview_system_id is not None:
            preview_sys = next((s for s in systems if s['id'] == st.session_state.preview_system_id), None)
            if preview_sys:
                pid = preview_sys['id']
                stats = system_stats.get(pid, {'pop': 0.0, 'sec_sum': 0.0, 'count': 0})
                sys_pop = stats['pop']
                
                if stats['count'] > 0:
                    sys_ss = stats['sec_sum'] / stats['count']
                else:
                    sys_ss = preview_sys.get('security', 0.0) or 0.0
                
                st.subheader(f"🔭 {preview_sys.get('name', 'Sistema')}")
                st.write(f"**Población:** {sys_pop:,.1f}B")
                st.write(f"**Seguridad (Ss):** {sys_ss:.1f}/100")
                
                # Mostrar Controlador en preview
                p_ctl_id = preview_sys.get('controlling_player_id')
                p_ctl_name = _resolve_controller_name(p_ctl_id) # V8.1: Generic resolve
                st.write(f"**Controlador:** {p_ctl_name}")

                if st.button("🚀 ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                    st.session_state.selected_system_id = preview_sys['id']
                    st.session_state.map_view = "system"
                    st.rerun()

    canvas_width, canvas_height = 1400, 900
    scaled_positions = _scale_positions(systems, canvas_width, canvas_height)
    
    systems_payload = []
    
    # Debug: Saber si estamos en modo omnisciencia (aunque aquí renderizamos todo)
    is_omni = st.session_state.get("debug_omniscience", False)
    
    for sys in systems:
        if sys['id'] not in scaled_positions: continue
        x, y = scaled_positions[sys['id']]
        star_class = sys.get('star_class', 'G')
        base_radius = STAR_SIZES.get(star_class, 7) * star_scale
        
        sid = sys['id']
        stats = system_stats.get(sid, {'pop': 0.0, 'sec_sum': 0.0, 'count': 0})
        total_pop_real = stats['pop']
        
        if stats['count'] > 0:
            calculated_ss = stats['sec_sum'] / stats['count']
        else:
            calculated_ss = sys.get('security', 0.0) or 0.0
        
        systems_payload.append({
            "id": sys['id'], 
            "name": sys.get('name', f"Sys {sys['id']}"),
            "class": star_class, 
            "x": round(x, 2), 
            "y": round(y, 2),
            "color": STAR_COLORS.get(star_class, "#FFFFFF"), 
            "radius": round(base_radius, 2),
            "ss": round(calculated_ss, 1),
            "pop": round(total_pop_real, 2)
        })

    connections = _build_connections_from_starlanes(starlanes, scaled_positions) if show_routes and starlanes else _build_connections_fallback(systems, scaled_positions) if show_routes else []
    
    systems_json = json.dumps(systems_payload)
    connections_json = json.dumps(connections)
    player_home_json = json.dumps([player_home_system_id] if player_home_system_id else [])

    html_template = f"""
    <!DOCTYPE html><html><head><script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        body{{margin:0;background:#000;overflow:hidden;font-family:'Courier New', monospace;}}
        .map-frame{{width:100%;height:860px;border-radius:12px;background:radial-gradient(circle at 50% 35%,#0f1c2d,#070b12 75%);border:1px solid #1f2a3d;position:relative;}}
        svg{{width:100%;height:100%;cursor:grab}}
        .star{{cursor:pointer;transition:all 0.2s}}
        .star:hover{{stroke:white;stroke-width:2px;filter:drop-shadow(0 0 8px rgba(255,255,255,0.8));}}
        .star.player-home{{stroke:#4dff88;stroke-width:3px;animation:pulse 2s infinite}}
        @keyframes pulse{{0%{{stroke-opacity:0.5}}50%{{stroke-opacity:1}}100%{{stroke-opacity:0.5}}}}
        .route{{stroke:#5b7bff;stroke-opacity:0.2;stroke-width:1.5;pointer-events:none}}
        #tooltip {{
            position: absolute;
            background: rgba(10, 15, 20, 0.95);
            border: 1px solid #4dff88;
            color: #e0e0e0;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            display: none;
            z-index: 1000;
            box-shadow: 0 0 10px rgba(77, 255, 136, 0.2);
            white-space: nowrap;
        }}
    </style>
    </head><body>
    <div class="map-frame">
        <div id="tooltip"></div>
        <svg id="galaxy-map" viewBox="0 0 {canvas_width} {canvas_height}">
            <g id="routes"></g>
            <g id="stars"></g>
        </svg>
    </div>
    <script>
    const systems={systems_json},routes={connections_json},homes=new Set({player_home_json});
    const sLayer=document.getElementById("stars"),rLayer=document.getElementById("routes");
    const tooltip=document.getElementById("tooltip");

    routes.forEach(r=>{{const l=document.createElementNS("http://www.w3.org/2000/svg","line");l.setAttribute("x1",r.ax);l.setAttribute("y1",r.ay);l.setAttribute("x2",r.bx);l.setAttribute("y2",r.by);l.classList.add("route");rLayer.appendChild(l)}});
    
    systems.forEach(s=>{{
        const c=document.createElementNS("http://www.w3.org/2000/svg","circle");
        c.setAttribute("cx",s.x);c.setAttribute("cy",s.y);c.setAttribute("r",s.radius);c.setAttribute("fill",s.color);
        c.classList.add("star");
        if(homes.has(s.id))c.classList.add("player-home");
        
        c.onclick=()=>{{const u=new URL(window.parent.location.href);u.searchParams.set("preview_id",s.id);window.parent.location.href=u.toString()}};
        
        c.onmouseenter = () => {{
            tooltip.style.display = 'block';
            tooltip.innerHTML = `<strong>${{s.name}}</strong> (Clase ${{s.class}})<br>` +
                                `<span style="color:#aaa">Población:</span> ${{s.pop}}B<br>` +
                                `<span style="color:#aaa">Seguridad (Ss):</span> ${{s.ss}}`;
        }};
        
        c.onmousemove = (e) => {{
            tooltip.style.left = (e.clientX + 15) + 'px';
            tooltip.style.top = (e.clientY + 15) + 'px';
        }};
        
        c.onmouseleave = () => {{
            tooltip.style.display = 'none';
        }};

        sLayer.appendChild(c)
    }});
    
    const panZoom = svgPanZoom("#galaxy-map",{{zoomEnabled:true,controlIconsEnabled:false,fit:true,center:true,minZoom:0.5,maxZoom:10}});
    </script></body></html>
    """
    with col_map:
        components.html(html_template, height=860)