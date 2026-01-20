# ui/galaxy_map_page.py
"""
Mapa Galáctico - Usa datos directamente de la Base de Datos.
Refactorizado MMFR V2: Indicadores de Seguridad (Ss/Sp), Mantenimiento y Tooltips.
Corrección: Cálculo de Seguridad (Ss) ponderada para planetas neutrales/habitados.
"""
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.world_constants import METAL_RESOURCES, BUILDING_TYPES, INFRASTRUCTURE_MODULES, ECONOMY_RATES
from data.database import get_supabase
from data.planet_repository import (
    get_all_player_planets, 
    build_structure, 
    get_planet_buildings,
    get_base_slots_info,
    upgrade_base_tier,
    upgrade_infrastructure_module,
    demolish_building
)
from data.world_repository import (
    get_all_systems_from_db,
    get_system_by_id,
    get_planets_by_system_id,
    get_starlanes_from_db
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


def show_galaxy_map_page():
    st.title("Mapa de la Galaxia")
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
            system_info = get_system_by_id(system_id)
            system_name = system_info.get('name', '???') if system_info else "Desconocido"
            
            # Recuperar seguridad (default 25.0 si no migrado)
            sp = asset.get('seguridad', 25.0)

            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            c1.write(f"🏠 **{asset.get('nombre_asentamiento', 'Colonia')}**")
            c2.write(f"{system_name}")
            
            # Semáforo de seguridad
            sec_color = "green" if sp >= 70 else "orange" if sp >= 40 else "red"
            c3.markdown(f":{sec_color}[{sp:.1f}/100]")
            
            if c4.button("Gestionar", key=f"btn_pl_{asset['id']}"):
                st.session_state.selected_system_id = system_id
                st.session_state.selected_planet_id = planet_id
                st.session_state.map_view = "planet"
                st.rerun()


def _render_system_view():
    system_id = st.session_state.selected_system_id
    system = get_system_by_id(system_id)
    if not system: _reset_to_galaxy_view(); return

    # 1. Obtener todos los planetas del sistema (Realidad física)
    planets = get_planets_by_system_id(system_id)
    total_planets = len(planets)

    # 2. Obtener assets del sistema (Gobernanza)
    try:
        assets_res = get_supabase().table("planet_assets").select("planet_id, seguridad").eq("system_id", system_id).execute()
        assets = assets_res.data if assets_res.data else []
        # Mapa de seguridad real de los assets existentes
        asset_map = {a['planet_id']: a.get('seguridad', 0.0) for a in assets}
    except: 
        asset_map = {}

    # 3. Calcular Métricas Consolidadas
    # Seguridad (Ss) = Promedio de la seguridad de todos los planetas.
    # Planetas con Asset -> Usan seguridad del Asset (Sp).
    # Planetas Neutrales -> Usan seguridad estimada basada en población.
    
    total_pop = 0.0
    security_sum = 0.0

    for p in planets:
        # Población real del planeta
        pop = p.get('poblacion') or 0.0
        total_pop += pop
        
        if p['id'] in asset_map:
            # Es un asset colonizado: Usamos su seguridad real
            security_sum += (asset_map[p['id']] or 0.0)
        else:
            # Es neutral: Imputamos seguridad base por población
            # Fórmula: Base + (Población * Tasa)
            base = ECONOMY_RATES.get('security_base', 25.0)
            per_pop = ECONOMY_RATES.get('security_per_1b_pop', 5.0)
            
            est_sec = base + (pop * per_pop)
            est_sec = max(0.0, min(est_sec, 100.0)) # Clamp 0-100
            
            security_sum += est_sec

    if total_planets > 0:
        ss = security_sum / total_planets
    else:
        ss = 0.0

    st.header(f"Sistema: {system.get('name', 'Desconocido')}")
    
    col_back, col_metrics = st.columns([4, 3])
    
    if col_back.button("← Volver al mapa", type="primary"):
        _reset_to_galaxy_view()
    
    with col_metrics:
        m1, m2 = st.columns(2)
        m1.metric("Seguridad (Ss)", f"{ss:.1f}/100", help="Promedio de seguridad del sistema (incluye estimación para mundos neutrales).")
        m2.metric("Población Total", f"{total_pop:,.1f}B")

    st.subheader("Cuerpos celestiales")
    
    for ring in range(1, 10):
        planet = next((p for p in planets if p.get('orbital_ring') == ring), None)
        if not planet: continue
        
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 4, 2])
            c1.caption(f"Anillo {ring}")
            
            biome = planet.get('biome', 'Desconocido')
            color = BIOME_COLORS.get(biome, "#7ec7ff")
            c2.markdown(f"<span style='color: {color}; font-weight: 700'>{planet['name']}</span>", unsafe_allow_html=True)
            
            p_pop = planet.get('poblacion') or 0.0
            info_str = f"Recursos: {', '.join(planet.get('resources', [])[:3])}"
            if p_pop > 0:
                info_str += f" | Pop: {p_pop:.1f}B"
            
            # Indicar estado político
            if planet['id'] in asset_map:
                info_str += " | 🏳️ Colonizado"
            
            c2.caption(info_str)
            
            if c3.button("Ver Detalles", key=f"pl_det_{planet['id']}"):
                st.session_state.selected_planet_id = planet['id']
                st.session_state.map_view = "planet"
                st.rerun()


def _render_planet_view():
    player = get_player()
    planet_id = st.session_state.selected_planet_id

    try:
        planet = get_supabase().table("planets").select("*").eq("id", planet_id).single().execute().data
        # Intentar obtener asset del jugador
        asset_res = get_supabase().table("planet_assets").select("*").eq("planet_id", planet_id).eq("player_id", player.id).single().execute()
        asset = asset_res.data if asset_res.data else None
    except: planet, asset = None, None

    if not planet: _reset_to_system_view(); return

    st.header(f"Planeta: {planet['name']}")
    
    if st.button("← Volver al Sistema"):
        _reset_to_system_view()

    # DATOS MÉTRICOS (MMFR V2)
    m1, m2, m3 = st.columns(3)
    
    real_pop = planet.get('poblacion') or 0.0

    if asset:
        m1.metric("Población (Ciudadanos)", f"{asset['poblacion']:,}B")
        
        sp = asset.get('seguridad', 25.0)
        delta_color = "normal" if sp >= 50 else "inverse" 
        m2.metric("Seguridad (Sp)", f"{sp:.1f}/100", delta_color=delta_color)
        m3.metric("Nivel de Base", f"Tier {asset['base_tier']}")
    else:
        # Cálculo estimado para visualización
        base = ECONOMY_RATES.get('security_base', 25.0)
        per_pop = ECONOMY_RATES.get('security_per_1b_pop', 5.0)
        est_sec = min(100.0, base + (real_pop * per_pop))
        
        m1.metric("Población (Nativa/Neutral)", f"{real_pop:,.1f}B")
        m2.metric("Seguridad Estimada", f"~{est_sec:.1f}/100", help="Valor proyectado si colonizaras este mundo.")
        m3.write("No colonizado por ti")

    st.markdown("---")
    if asset: _render_construction_ui(player, planet, asset)


def _render_construction_ui(player, planet, planet_asset):
    st.markdown("### 🏯 Gestión de Colonia")
    
    # 📡 INFRAESTRUCTURA DE SEGURIDAD
    st.markdown("#### 📡 Infraestructura de Seguridad")
    st.caption("Aumenta la **Seguridad (Sp)** para mejorar la eficiencia fiscal y protegerte de ataques.")
    
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

    # --- PRE-CÁLCULO DE MÉTRICAS MASIVO (Optimización) ---
    # Evitamos N+1 queries obteniendo todo de una vez
    
    # 1. Obtener todos los planetas con ID, system_id y población (Datos físicos)
    try:
        all_planets_data = get_supabase().table("planets").select("id, system_id, poblacion").execute().data
    except:
        all_planets_data = []

    # 2. Obtener assets con planet_id y seguridad (Datos políticos)
    try:
        all_assets_data = get_supabase().table("planet_assets").select("planet_id, seguridad, system_id").execute().data
        # Lookup rápido de seguridad por ID de planeta
        asset_security_map = {row['planet_id']: row.get('seguridad', 0.0) for row in all_assets_data}
    except:
        asset_security_map = {}

    # 3. Procesar métricas por sistema
    system_planet_counts = {}
    system_total_pop = {}
    system_security_sum = {}
    
    for p in all_planets_data:
        sid = p['system_id']
        pid = p['id']
        pop = p.get('poblacion') or 0.0
        
        # Denominador de planetas
        system_planet_counts[sid] = system_planet_counts.get(sid, 0) + 1
        # Suma de población real
        system_total_pop[sid] = system_total_pop.get(sid, 0.0) + pop
        
        # Lógica de Seguridad Híbrida
        if pid in asset_security_map:
            # Planeta colonizado: Usar seguridad real del asset
            current_sec = asset_security_map[pid]
        else:
            # Planeta neutral: Calcular seguridad estimada
            base = ECONOMY_RATES.get('security_base', 25.0)
            per_pop = ECONOMY_RATES.get('security_per_1b_pop', 5.0)
            current_sec = base + (pop * per_pop)
            # Clamp 0-100
            current_sec = max(0.0, min(current_sec, 100.0))
            
        system_security_sum[sid] = system_security_sum.get(sid, 0.0) + current_sec


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
                
                # Obtener métricas para el preview
                pid = preview_sys['id']
                p_count = system_planet_counts.get(pid, 0)
                sec_sum = system_security_sum.get(pid, 0.0)
                
                sys_ss = sec_sum / p_count if p_count > 0 else 0.0
                sys_pop = system_total_pop.get(pid, 0.0)
                
                st.subheader(f"🔭 {preview_sys.get('name', 'Sistema')}")
                st.write(f"**Población:** {sys_pop:,.1f}B")
                st.write(f"**Seguridad (Ss):** {sys_ss:.1f}/100")
                
                if st.button("🚀 ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                    st.session_state.selected_system_id = preview_sys['id']
                    st.session_state.map_view = "system"
                    st.rerun()

    canvas_width, canvas_height = 1400, 900
    scaled_positions = _scale_positions(systems, canvas_width, canvas_height)
    
    systems_payload = []
    for sys in systems:
        if sys['id'] not in scaled_positions: continue
        x, y = scaled_positions[sys['id']]
        star_class = sys.get('star_class', 'G')
        base_radius = STAR_SIZES.get(star_class, 7) * star_scale
        
        # Calcular métricas individuales para el tooltip
        sid = sys['id']
        p_count = system_planet_counts.get(sid, 0)
        sec_sum = system_security_sum.get(sid, 0.0)
        
        calculated_ss = sec_sum / p_count if p_count > 0 else 0.0
        total_pop_real = system_total_pop.get(sid, 0.0)
        
        systems_payload.append({
            "id": sys['id'], 
            "name": sys.get('name', f"Sys {sys['id']}"),
            "class": star_class, 
            "x": round(x, 2), 
            "y": round(y, 2),
            "color": STAR_COLORS.get(star_class, "#FFFFFF"), 
            "radius": round(base_radius, 2),
            # Datos extra para tooltip
            "ss": round(calculated_ss, 1),
            "pop": round(total_pop_real, 2)
        })

    connections = _build_connections_from_starlanes(starlanes, scaled_positions) if show_routes and starlanes else _build_connections_fallback(systems, scaled_positions) if show_routes else []
    
    systems_json = json.dumps(systems_payload)
    connections_json = json.dumps(connections)
    player_home_json = json.dumps([player_home_system_id] if player_home_system_id else [])

    # HTML/JS con Tooltips
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
        
        /* Tooltip Styling */
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
        
        // Interaction Logic
        c.onclick=()=>{{const u=new URL(window.parent.location.href);u.searchParams.set("preview_id",s.id);window.parent.location.href=u.toString()}};
        
        // Tooltip Events
        c.onmouseenter = () => {{
            tooltip.style.display = 'block';
            tooltip.innerHTML = `<strong>${{s.name}}</strong> (Clase ${{s.class}})<br>` +
                                `<span style="color:#aaa">Población:</span> ${{s.pop}}B<br>` +
                                `<span style="color:#aaa">Seguridad (Ss):</span> ${{s.ss}}`;
        }};
        
        c.onmousemove = (e) => {{
            // Coordenadas relativas al viewport
            tooltip.style.left = (e.clientX + 15) + 'px';
            tooltip.style.top = (e.clientY + 15) + 'px';
        }};
        
        c.onmouseleave = () => {{
            tooltip.style.display = 'none';
        }};

        sLayer.appendChild(c)
    }});
    
    // PanZoom Initialization
    const panZoom = svgPanZoom("#galaxy-map",{{zoomEnabled:true,controlIconsEnabled:false,fit:true,center:true,minZoom:0.5,maxZoom:10}});
    </script></body></html>
    """
    with col_map:
        components.html(html_template, height=860)