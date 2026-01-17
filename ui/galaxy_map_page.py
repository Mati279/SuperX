# ui/galaxy_map_page.py
"""
Mapa Galáctico - Usa datos directamente de la Base de Datos.
Sin generación procedural, la galaxia es fija.
"""
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.world_constants import METAL_RESOURCES, BUILDING_TYPES, INFRASTRUCTURE_MODULES
from data.planet_repository import (
    get_all_player_planets, 
    build_structure, 
    get_planet_buildings,
    get_base_slots_info,
    upgrade_base_tier,
    upgrade_infrastructure_module,
    demolish_building
)
# Aseguramos que data.player_repository tenga la función get_player_resources
from data.player_repository import get_player_resources, update_player_resources
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
    """Punto de entrada para la página del mapa galáctico."""
    st.title("Mapa de la Galaxia")

    # --- NUEVO: Panel de Dominios del Jugador ---
    _render_player_domains_panel()
    
    st.markdown("---")

    # Inicialización de estado
    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
    if "selected_system_id" not in st.session_state:
        st.session_state.selected_system_id = None
    if "preview_system_id" not in st.session_state:
        st.session_state.preview_system_id = None
    if "selected_planet_id" not in st.session_state:
        st.session_state.selected_planet_id = None

    # --- LÓGICA DE NAVEGACIÓN (Bridging JS -> Python) ---
    if "preview_id" in st.query_params:
        try:
            p_id = int(st.query_params["preview_id"])
            st.session_state.preview_system_id = p_id
            del st.query_params["preview_id"]
        except (ValueError, TypeError):
            if "preview_id" in st.query_params:
                del st.query_params["preview_id"]
        st.rerun()

    # --- Renderizado de Vistas ---
    if st.session_state.map_view == "galaxy":
        _render_interactive_galaxy_map()
    elif st.session_state.map_view == "system" and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == "planet" and st.session_state.selected_planet_id is not None:
        _render_planet_view()


def _render_player_domains_panel():
    """
    Muestra una lista de los planetas controlados por el jugador
    con botones de acceso rápido.
    """
    player = get_player()
    if not player:
        return

    # Obtener activos (colonias) del jugador
    player_assets = get_all_player_planets(player.id)

    if not player_assets:
        return

    st.subheader("🪐 Mis Dominios")
    
    with st.expander(f"Gestionar {len(player_assets)} Asentamientos", expanded=True):
        # Cabecera
        cols = st.columns([3, 2, 2, 2])
        cols[0].markdown("**Asentamiento**")
        cols[1].markdown("**Ubicación**")
        cols[2].markdown("**Acción Sistema**")
        cols[3].markdown("**Acción Planeta**")
        
        st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

        for asset in player_assets:
            planet_id = asset['planet_id']
            system_id = asset['system_id']
            settlement_name = asset.get('nombre_asentamiento', 'Colonia Sin Nombre')
            
            # Recuperamos nombre del sistema
            system_info = get_system_by_id(system_id)
            system_name = system_info.get('name', f"Sys-{system_id}") if system_info else "Desconocido"

            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            
            with c1:
                st.write(f"🏠 **{settlement_name}**")
                st.caption(f"Población: {asset.get('poblacion', 0)}")
            
            with c2:
                st.write(f"Sist: {system_name}")
            
            with c3:
                # Botón: Ir a la vista del SISTEMA
                if st.button("🔭 Ver Sistema", key=f"btn_sys_{asset['id']}"):
                    st.session_state.selected_system_id = system_id
                    st.session_state.map_view = "system"
                    st.session_state.preview_system_id = system_id 
                    st.rerun()
            
            with c4:
                # Botón: Ir a los detalles del PLANETA
                if st.button("🌍 Gestionar", key=f"btn_pl_{asset['id']}"):
                    st.session_state.selected_system_id = system_id
                    st.session_state.selected_planet_id = planet_id
                    st.session_state.map_view = "planet"
                    st.rerun()
            
            st.markdown("<hr style='margin: 5px 0; opacity: 0.1'>", unsafe_allow_html=True)


def _get_player_home_info():
    """Obtiene el system_id y planet_id de la base del jugador."""
    player = get_player()
    if not player:
        return None, None

    home_base_name = f"Base {player.faccion_nombre}"
    player_planets = get_all_player_planets(player.id)
    
    if player_planets:
        for p in player_planets:
             if "Base" in p.get('nombre_asentamiento', ''):
                 return p.get('system_id'), p.get('planet_id')
        first = player_planets[0]
        return first.get('system_id'), first.get('planet_id')

    return None, None


def _scale_positions(systems: list, target_width: int = 1400, target_height: int = 900, margin: int = 80):
    """Escala las posiciones de los sistemas para el canvas."""
    if not systems:
        return {}

    xs = [s.get('x', 0) for s in systems]
    ys = [s.get('y', 0) for s in systems]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    def scale(value: float, min_val: float, span: float, target: int) -> float:
        usable = target - (2 * margin)
        return margin + ((value - min_val) / span) * usable

    return {
        s['id']: (
            scale(s.get('x', 0), min_x, span_x, target_width),
            scale(s.get('y', 0), min_y, span_y, target_height),
        )
        for s in systems
    }


def _build_connections_from_starlanes(starlanes: list, positions: dict):
    """Construye las conexiones visuales desde las starlanes de la BD."""
    connections = []
    for lane in starlanes:
        a_id = lane.get('system_a_id')
        b_id = lane.get('system_b_id')
        if a_id in positions and b_id in positions:
            ax, ay = positions[a_id]
            bx, by = positions[b_id]
            connections.append({
                "a_id": a_id, "b_id": b_id,
                "ax": ax, "ay": ay, "bx": bx, "by": by
            })
    return connections


def _build_connections_fallback(systems: list, positions: dict, max_neighbors: int = 3):
    """Fallback: genera conexiones basadas en vecinos cercanos."""
    edges = set()
    for sys_a in systems:
        a_id = sys_a['id']
        if a_id not in positions:
            continue
        x1, y1 = positions[a_id]

        distances = []
        for sys_b in systems:
            b_id = sys_b['id']
            if b_id == a_id or b_id not in positions:
                continue
            x2, y2 = positions[b_id]
            dist = math.hypot(x1 - x2, y1 - y2)
            distances.append((dist, b_id))

        distances.sort(key=lambda t: t[0])
        for _, neighbor_id in distances[:max_neighbors]:
            edge_key = tuple(sorted((a_id, neighbor_id)))
            edges.add(edge_key)

    connections = []
    for a_id, b_id in edges:
        if a_id in positions and b_id in positions:
            ax, ay = positions[a_id]
            bx, by = positions[b_id]
            connections.append({
                "a_id": a_id, "b_id": b_id,
                "ax": ax, "ay": ay, "bx": bx, "by": by
            })
    return connections


def _render_interactive_galaxy_map():
    """Renderiza el mapa interactivo de la galaxia."""
    st.header("Sistemas Conocidos")

    systems = get_all_systems_from_db()
    starlanes = get_starlanes_from_db()
    
    if not systems:
        st.error("No se pudieron cargar los sistemas de la galaxia.")
        return

    systems_sorted = sorted(systems, key=lambda s: s.get('id', 0))
    player_home_system_id, _ = _get_player_home_info()

    col_map, col_controls = st.columns([5, 2])

    with col_controls:
        search_term = st.text_input("Buscar sistema", placeholder="Ej. Alpha-Orionis")

        current_idx = 0
        sys_options = [s.get('name', f"Sistema {s['id']}") for s in systems_sorted]
        if st.session_state.preview_system_id is not None:
            for i, s in enumerate(systems_sorted):
                if s['id'] == st.session_state.preview_system_id:
                    current_idx = i
                    break

        selected_name = st.selectbox(
            "Seleccionar sistema",
            sys_options,
            index=current_idx,
            key="manual_system_selector"
        )

        selected_sys = systems_sorted[sys_options.index(selected_name)]
        if selected_sys['id'] != st.session_state.preview_system_id:
            st.session_state.preview_system_id = selected_sys['id']
            st.rerun()

        st.markdown("---")

        class_options = sorted({s.get('star_class', 'G') for s in systems})
        selected_classes = st.multiselect(
            "Clases visibles", class_options, default=class_options
        )
        show_routes = st.toggle("Mostrar rutas", value=True)
        star_scale = st.slider("Tamaño relativo", 0.8, 2.0, 1.0, 0.05)

        st.markdown("---")

        if st.session_state.preview_system_id is not None:
            preview_sys = next((s for s in systems if s['id'] == st.session_state.preview_system_id), None)

            if preview_sys:
                st.subheader(f"🔭 {preview_sys.get('name', 'Sistema')}")
                st.caption(f"ID: {preview_sys['id']} | Coords: ({preview_sys.get('x', 0):.0f}, {preview_sys.get('y', 0):.0f})")

                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    c1.metric("Clase", preview_sys.get('star_class', 'G'))

                    planets_count = len(get_planets_by_system_id(preview_sys['id']))
                    c2.metric("Planetas", planets_count)

                    if preview_sys['id'] == player_home_system_id:
                        st.success("🏠 Tu sistema base")

                    if st.button("🚀 ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                        st.session_state.selected_system_id = preview_sys['id']
                        st.session_state.map_view = "system"
                        st.rerun()
            else:
                st.warning("Sistema no encontrado.")
        else:
            st.info("Selecciona una estrella en el mapa o en la lista para ver detalles.")

    canvas_width, canvas_height = 1400, 900
    scaled_positions = _scale_positions(systems, canvas_width, canvas_height)

    filtered_ids = {s['id'] for s in systems if s.get('star_class', 'G') in selected_classes}
    highlight_ids = {
        s['id'] for s in systems if search_term and search_term.lower() in s.get('name', '').lower()
    }

    if st.session_state.preview_system_id is not None:
        highlight_ids.add(st.session_state.preview_system_id)

    player_home_system_ids = {player_home_system_id} if player_home_system_id else set()

    systems_payload = []
    for sys in systems:
        if sys['id'] not in scaled_positions:
            continue
        x, y = scaled_positions[sys['id']]
        star_class = sys.get('star_class', 'G')
        base_radius = STAR_SIZES.get(star_class, 7) * star_scale
        color = STAR_COLORS.get(star_class, "#FFFFFF")

        systems_payload.append({
            "id": sys['id'],
            "name": sys.get('name', f"Sistema {sys['id']}"),
            "class": star_class,
            "x": round(x, 2),
            "y": round(y, 2),
            "color": color,
            "radius": round(base_radius, 2),
        })

    if show_routes:
        if starlanes:
            connections = _build_connections_from_starlanes(starlanes, scaled_positions)
        else:
            connections = _build_connections_fallback(systems, scaled_positions, max_neighbors=3)
    else:
        connections = []

    systems_json = json.dumps(systems_payload)
    connections_json = json.dumps(connections)
    filtered_json = json.dumps(list(filtered_ids))
    highlight_json = json.dumps(list(highlight_ids))
    player_home_json = json.dumps(list(player_home_system_ids))

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8" />
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        :root {{ --bg-1: #0b0f18; --stroke: #1f2a3d; --text: #e6ecff; }}
        body {{ margin: 0; font-family: "Inter", sans-serif; background: #000; color: var(--text); overflow: hidden; }}
        .wrapper {{ width: 100%; height: 100%; }}
        .map-frame {{
            width: 100%; height: 860px;
            border-radius: 12px; overflow: hidden; border: 1px solid var(--stroke);
            background: radial-gradient(circle at 50% 35%, #0f1c2d, #070b12 75%);
        }}
        svg {{ width: 100%; height: 100%; cursor: grab; }}
        .star {{ transition: all 0.2s ease; cursor: pointer; filter: drop-shadow(0 0 4px rgba(255,255,255,0.3)); }}
        .star.dim {{ opacity: 0.15; pointer-events: none; }}
        .star:hover {{ r: 16; stroke: white; stroke-width: 2px; filter: drop-shadow(0 0 12px rgba(255,255,255,0.8)); }}
        .star.selected {{ stroke: #5b7bff; stroke-width: 3px; r: 16; filter: drop-shadow(0 0 15px rgba(91, 123, 255, 0.8)); }}
        .star.player-home {{ stroke: #4dff88; stroke-width: 3px; filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8)); animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0% {{ filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8)); }} 50% {{ filter: drop-shadow(0 0 25px rgba(77, 255, 136, 1)); }} 100% {{ filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8)); }} }}
        .route {{ stroke: #5b7bff; stroke-opacity: 0.2; stroke-width: 1.5; pointer-events: none; }}
        #tooltip {{ position: absolute; pointer-events: none; background: rgba(0,0,0,0.8); padding: 4px 8px; border-radius: 4px; font-size: 11px; color: #fff; display: none; border: 1px solid #444; z-index: 100; }}
        .toolbar {{ position: absolute; top: 10px; right: 10px; }}
        .btn {{ background: rgba(0,0,0,0.5); color: #fff; border: 1px solid #333; cursor:pointer; padding: 5px 10px; border-radius: 4px; }}
    </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="map-frame">
                <div id="tooltip"></div>
                <div class="toolbar">
                    <button class="btn" id="reset">Reset</button>
                    <button class="btn" id="zin">+</button>
                    <button class="btn" id="zout">-</button>
                </div>
                <svg id="galaxy-map" viewBox="0 0 {canvas_width} {canvas_height}">
                    <g id="routes-layer"></g>
                    <g id="stars-layer"></g>
                </svg>
            </div>
        </div>
        <script>
            const systems = {systems_json};
            const routes = {connections_json};
            const filteredIds = new Set({filtered_json});
            const highlightIds = new Set({highlight_json});
            const playerHomeSystemIds = new Set({player_home_json});

            const starsLayer = document.getElementById("stars-layer");
            const routesLayer = document.getElementById("routes-layer");
            const tooltip = document.getElementById("tooltip");

            routes.forEach(r => {{
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", r.ax); line.setAttribute("y1", r.ay);
                line.setAttribute("x2", r.bx); line.setAttribute("y2", r.by);
                line.setAttribute("class", "route");
                routesLayer.appendChild(line);
            }});

            systems.forEach(sys => {{
                const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                c.setAttribute("cx", sys.x); c.setAttribute("cy", sys.y);
                c.setAttribute("r", sys.radius);
                c.setAttribute("fill", sys.color);
                c.setAttribute("class", "star");

                if (!filteredIds.has(sys.id)) c.classList.add("dim");
                if (highlightIds.has(sys.id)) c.classList.add("selected");
                if (playerHomeSystemIds.has(sys.id)) c.classList.add("player-home");

                c.addEventListener("mouseenter", () => {{
                    tooltip.style.display = "block";
                    tooltip.textContent = sys.name;
                }});
                c.addEventListener("mousemove", (e) => {{
                    tooltip.style.left = (e.pageX + 10) + "px";
                    tooltip.style.top = (e.pageY - 20) + "px";
                }});
                c.addEventListener("mouseleave", () => tooltip.style.display = "none");
                c.addEventListener("click", () => {{
                    const targetWin = window.parent || window.top || window;
                    const url = new URL(targetWin.location.href);
                    url.searchParams.set("preview_id", sys.id);
                    targetWin.location.href = url.toString();
                }});
                starsLayer.appendChild(c);
            }});

            const pz = svgPanZoom("#galaxy-map", {{ zoomEnabled: true, controlIconsEnabled: false, fit: true, center: true, minZoom: 0.5, maxZoom: 10 }});
            document.getElementById("reset").onclick = () => {{ pz.resetZoom(); pz.resetPan(); }};
            document.getElementById("zin").onclick = () => pz.zoomIn();
            document.getElementById("zout").onclick = () => pz.zoomOut();
        </script>
    </body>
    </html>
    """
    with col_map:
        components.html(html_template, height=860, scrolling=False)


def _render_system_view():
    """Muestra los detalles de un sistema estelar seleccionado."""
    system_id = st.session_state.selected_system_id
    system = get_system_by_id(system_id)

    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    st.header(f"Sistema: {system.get('name', 'Desconocido')}")

    with st.container():
        if st.button("← Volver al mapa", use_container_width=True, type="primary", key="back_to_map"):
            _reset_to_galaxy_view()

    with st.expander("Información de la Estrella Central", expanded=True):
        star_class = system.get('star_class', 'G')
        st.subheader(f"Estrella Clase {star_class}")
        st.caption(f"Coordenadas: ({system.get('x', 0):.0f}, {system.get('y', 0):.0f})")

    st.subheader("Vista orbital")
    _render_system_orbits(system_id)

    st.subheader("Cuerpos celestiales")
    planets = get_planets_by_system_id(system_id)

    _, player_home_planet_id = _get_player_home_info()

    for ring in range(1, 10):
        planet = next((p for p in planets if p.get('orbital_ring') == ring), None)
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 3, 3])
            with col1:
                st.caption(f"Anillo {ring}")
            with col2:
                if planet is None:
                    st.write("_(Vacío)_")
                else:
                    biome = planet.get('biome', 'Desconocido')
                    color = BIOME_COLORS.get(biome, "#7ec7ff")
                    name = planet.get('name', f"Planeta-{ring}")
                    is_home = planet['id'] == player_home_planet_id
                    home_indicator = " 🏠" if is_home else ""
                    st.markdown(f"<span style='color: {color}; font-weight: 700'>{name}{home_indicator}</span>", unsafe_allow_html=True)
                    st.write(f"Bioma: {biome} | Tamaño: {planet.get('planet_size', 'Mediano')}")
            with col3:
                if planet:
                    resources = planet.get('resources', [])
                    top_res = ", ".join(resources[:3]) if resources else "Sin recursos"
                    st.write(f"Recursos: {top_res}")
                    if st.button("Ver Detalles", key=f"planet_{planet['id']}"):
                        st.session_state.map_view = "planet"
                        st.session_state.selected_planet_id = planet['id']
                        st.rerun()


def _render_system_orbits(system_id: int):
    """Visual del sol y planetas orbitando."""
    system = get_system_by_id(system_id)
    planets = get_planets_by_system_id(system_id)
    if not system: return

    _, player_home_planet_id = _get_player_home_info()
    star_class = system.get('star_class', 'G')
    star_color = STAR_COLORS.get(star_class, "#f8f5ff")
    star_glow = {"G": 18, "O": 22, "M": 16, "D": 18, "X": 24}

    center_x, center_y, orbit_step = 360, 360, 38
    
    planets_data = []
    for idx, planet in enumerate(planets):
        ring = planet.get('orbital_ring', idx + 1)
        angle_deg = ((system_id * 23) + (idx * 137.5)) % 360
        angle_rad = math.radians(angle_deg)
        radius = 70 + ring * orbit_step
        px = center_x + radius * math.cos(angle_rad)
        py = center_y + radius * math.sin(angle_rad)
        size_map = {"Pequeno": 7, "Mediano": 10, "Grande": 13}
        pr = size_map.get(planet.get('planet_size', 'Mediano'), 9)
        biome = planet.get('biome', 'Desconocido')
        color = BIOME_COLORS.get(biome, "#7ec7ff")
        resources = planet.get('resources', [])
        resources_str = ", ".join(resources[:3]) if resources else "Sin recursos"

        planets_data.append({
            "id": planet['id'], "name": planet.get('name', f"Planeta-{ring}"),
            "biome": biome, "size": planet.get('planet_size', 'Mediano'),
            "resources": resources_str, "x": round(px, 2), "y": round(py, 2),
            "r": pr, "ring": ring, "color": color,
        })

    orbit_radii = [70 + ring * orbit_step for ring in range(1, 7)]
    planets_json = json.dumps(planets_data)
    orbits_json = json.dumps(orbit_radii)
    player_planet_ids_json = json.dumps([player_home_planet_id] if player_home_planet_id else [])

    html = f"""
    <style>
    .sys-wrapper {{ width: 100%; height: 720px; display: flex; justify-content: center; align-items: center; }}
    .sys-canvas {{ width: 720px; height: 720px; border-radius: 12px; background: radial-gradient(circle at 30% 20%, #111a2e, #080c16 70%); border: 1px solid #1d2a3c; position: relative; overflow: hidden; }}
    .sys-tooltip {{ position: absolute; background: rgba(8,12,22,0.95); color: #e6ecff; border: 1px solid #1f2a3d; padding: 8px 10px; border-radius: 8px; font-size: 12px; pointer-events: none; display: none; max-width: 240px; }}
    .legend {{ position:absolute; top:10px; right:10px; background:rgba(10,14,24,0.8); padding:8px 10px; border:1px solid #1f2a3d; border-radius:8px; color:#cfd8f5; font-size:12px; }}
    .legend h4 {{ margin:0 0 6px 0; font-size:12px; color:#9fb2ff; }}
    .legend-row {{ margin:2px 0; }}
    .player-home-planet {{ stroke: #4dff88 !important; stroke-width: 3px !important; filter: drop-shadow(0 0 10px rgba(77, 255, 136, 0.9)); animation: pulse-planet 2s infinite; }}
    @keyframes pulse-planet {{ 0% {{ filter: drop-shadow(0 0 10px rgba(77, 255, 136, 0.9)); }} 50% {{ filter: drop-shadow(0 0 20px rgba(77, 255, 136, 1)); }} 100% {{ filter: drop-shadow(0 0 10px rgba(77, 255, 136, 0.9)); }} }}
    </style>
    <div class="sys-wrapper">
        <svg id="system-orbits" class="sys-canvas" viewBox="0 0 {center_x*2} {center_y*2}" preserveAspectRatio="xMidYMid meet">
            <defs>
                <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="{star_color}" stop-opacity="0.95" />
                    <stop offset="100%" stop-color="{star_color}" stop-opacity="0.1" />
                </radialGradient>
                <filter id="glowShadow" x="-50%" y="-50%" width="200%" height="200%">
                    <feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="{star_color}" flood-opacity="0.7" />
                </filter>
            </defs>
            <circle cx="{center_x}" cy="{center_y}" r="{star_glow.get(star_class, 20)}" fill="url(#starGlow)" stroke="{star_color}" stroke-width="2.5" filter="url(#glowShadow)" />
        </svg>
        <div id="sys-tooltip" class="sys-tooltip"></div>
        <div class="legend"><h4>Claves visuales</h4><div class="legend-row">■ Tamaño y nombre escalan con el planeta</div><div class="legend-row">■ Click en planeta para abrir detalles</div><div class="legend-row" style="color: #4dff88;">■ Tu base (resaltado verde)</div></div>
    </div>
    <script>
      const planets = {planets_json};
      const orbitRadii = {orbits_json};
      const playerPlanetIds = new Set({player_planet_ids_json});
      const svg = document.getElementById("system-orbits");
      const tooltip = document.getElementById("sys-tooltip");
      const centerX = {center_x};
      const centerY = {center_y};

      orbitRadii.forEach((radius) => {{
        const orbit = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        orbit.setAttribute("cx", centerX); orbit.setAttribute("cy", centerY); orbit.setAttribute("r", radius);
        orbit.setAttribute("fill", "none"); orbit.setAttribute("stroke", "rgba(100, 150, 255, 0.2)"); orbit.setAttribute("stroke-width", "1"); orbit.setAttribute("stroke-dasharray", "4 4");
        svg.appendChild(orbit);
      }});

      planets.forEach(p => {{
        const planet = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        planet.setAttribute("cx", p.x); planet.setAttribute("cy", p.y); planet.setAttribute("r", p.r);
        planet.setAttribute("fill", p.color); planet.setAttribute("stroke", "#b2d7ff"); planet.setAttribute("stroke-width", "1"); planet.style.cursor = "pointer";
        if (playerPlanetIds.has(p.id)) planet.classList.add("player-home-planet");
        planet.addEventListener("mousemove", (evt) => {{
            tooltip.style.display = "block"; tooltip.style.left = (evt.pageX + 10) + "px"; tooltip.style.top = (evt.pageY + 10) + "px";
            tooltip.innerHTML = `<strong>${{p.name}}</strong><br/>Bioma: ${{p.biome}}<br/>Tamaño: ${{p.size}}<br/>Recursos: ${{p.resources}}`;
        }});
        planet.addEventListener("mouseleave", () => tooltip.style.display = "none");
        planet.addEventListener("click", () => {{
             const targetWin = window.parent || window.top || window;
             // Esta lógica es para JS puro, en Streamlit dependemos del rerun del padre, 
             // pero aquí simulamos la interacción para efectos visuales o futuros hooks.
        }});
        svg.appendChild(planet);
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", p.x + 12); label.setAttribute("y", p.y + 4); label.setAttribute("fill", "#dfe8ff");
        label.setAttribute("font-size", p.r >= 12 ? "13" : "11"); label.setAttribute("font-weight", "600");
        label.textContent = `${{p.name}} (R${{p.ring}})`;
        svg.appendChild(label);
      }});
    </script>
    """
    return components.html(html, height=780)


def _render_planet_view():
    """Muestra los detalles de un planeta seleccionado."""
    from data.database import get_supabase
    
    player = get_player()
    planet_id = st.session_state.selected_planet_id

    try:
        planet_res = get_supabase().table("planets").select("*").eq("id", planet_id).single().execute()
        planet = planet_res.data if planet_res.data else None
    except Exception:
        planet = None

    if not planet:
        st.error("Error: Planeta no encontrado.")
        _reset_to_system_view()
        return

    # Verificar si el jugador posee este planeta (para habilitar construcción)
    is_owner = False
    planet_asset = None
    if player:
        try:
            # Buscar si existe asset para este planeta y jugador
            pa_res = get_supabase().table("planet_assets").select("*")\
                .eq("planet_id", planet_id).eq("player_id", player.id).single().execute()
            if pa_res.data:
                is_owner = True
                planet_asset = pa_res.data
        except:
            pass

    system = get_system_by_id(planet.get('system_id'))
    system_name = system.get('name', 'Desconocido') if system else 'Desconocido'

    st.header(f"Informe del Planeta: {planet.get('name', 'Desconocido')}")
    if st.button(f"← Volver al Sistema {system_name}"):
        _reset_to_system_view()

    # --- DATOS GENERALES ---
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Anillo Orbital", planet.get('orbital_ring', '-'))
        st.metric("Tamaño", planet.get('planet_size', 'Mediano'))
        if is_owner:
            st.success("✅ Asentamiento Establecido")
        else:
            st.info("Planeta No Colonizado (o de otra facción)")

    with col2:
        st.subheader(f"Bioma: {planet.get('biome', 'Desconocido')}")
        bonuses = planet.get('bonuses', {})
        if bonuses:
            st.info(f"Bonus: {bonuses.get('desc', 'Ninguno')}")
        resources = planet.get('resources', [])
        st.write(f"Recursos Naturales: {', '.join(resources[:3]) if resources else 'Ninguno'}")

    st.markdown("---")

    # --- GESTIÓN DE EDIFICIOS (Solo si es dueño) ---
    if is_owner and planet_asset:
        _render_construction_ui(player, planet, planet_asset)
    else:
        st.warning("No tienes control sobre este planeta. No puedes construir aquí.")


def _render_construction_ui(player, planet, planet_asset):
    """Panel de gestión según reglas del Módulo 20 (Jerarquía y Slots)."""
    
    base_tier = planet_asset.get('base_tier', 1)
    
    st.markdown("### 🏯 Comando de Base Principal")
    
    # --- SECCIÓN 1: JERARQUÍA DE LA BASE ---
    col_base_img, col_base_info = st.columns([1, 3])
    
    with col_base_info:
        st.write(f"**Nivel de Base (Tier):** {base_tier}")
        # Barra de progreso visual hacia el siguiente Tier (simbólico)
        st.progress(base_tier / 4)
        
        if base_tier < 4:
            if st.button(f"⏫ Ascender a Tier {base_tier + 1}"):
                # Aquí llamaríamos a la lógica real con costos
                if upgrade_base_tier(planet_asset['id'], player.id):
                    st.success("¡Base Mejorada!")
                    st.rerun()
                else:
                    st.error("Error o recursos insuficientes.")
        else:
            st.caption("🏆 Nivel Máximo Alcanzado")

    st.markdown("---")
    
    # --- SECCIÓN 2: MATRIZ DE SENSORES Y DEFENSA (Módulos) ---
    st.markdown("#### 📡 Matriz de Sensores & Defensa")
    st.caption(f"Regla Overclock: Nivel Máximo de Módulos = {base_tier + 1}")
    
    # Grid de módulos
    mod_cols = st.columns(2)
    
    modules_to_show = ["sensor_ground", "sensor_orbital", "defense_aa", "defense_ground"]
    if base_tier >= 3:
        modules_to_show.append("defense_orbital")
        
    for idx, mod_key in enumerate(modules_to_show):
        col = mod_cols[idx % 2]
        mod_def = INFRASTRUCTURE_MODULES.get(mod_key, {})
        current_lvl = planet_asset.get(f"module_{mod_key}", 0) # Asume columnas en DB
        
        with col.container(border=True):
            st.write(f"**{mod_def.get('name')}**")
            c1, c2 = st.columns([2, 1])
            c1.write(f"Nivel: {current_lvl}")
            
            # Botón de mejora
            if c2.button("✚", key=f"upg_{mod_key}"):
                res = upgrade_infrastructure_module(planet_asset['id'], mod_key, player.id)
                if res == "OK":
                    st.toast(f"{mod_def.get('name')} mejorado.")
                    st.rerun()
                else:
                    st.error(res)

    st.markdown("---")

    # --- SECCIÓN 3: DISTRITO INDUSTRIAL (Slots de Construcción) ---
    st.markdown("#### 🏗️ Distrito de Construcción")
    
    # Calcular slots reales usando la lógica del Módulo 20.5
    slots_info = get_base_slots_info(planet_asset['id'])
    used = slots_info['used']
    total = slots_info['total']
    
    st.write(f"Capacidad Modular: {used} / {total} Slots")
    st.progress(used / total if total > 0 else 0)
    
    if slots_info['free'] <= 0:
        st.warning("⚠️ Capacidad máxima alcanzada. Mejora la Base Principal para obtener más slots.")
    
    # Listar edificios
    buildings = get_planet_buildings(planet_asset['id'])
    if buildings:
        for b in buildings:
            b_type = b.get('building_type', 'unknown')
            b_def = BUILDING_TYPES.get(b_type, {})
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{b_def.get('name', b_type)}** (Tier {b.get('building_tier', 1)})")
                c1.caption(b_def.get('description'))
                # Botón de demoler
                if c2.button("🗑️", key=f"dem_{b['id']}"):
                    if demolish_building(b['id'], player.id):
                        st.toast("Edificio demolido.")
                        st.rerun()
    else:
        st.info("Sin edificios civiles/militares construidos.")

    # Formulario de Construcción (Solo si hay slots)
    if slots_info['free'] > 0:
        st.markdown("##### Iniciar Proyecto")
        
        available_types = list(BUILDING_TYPES.keys())
        
        # Filtro simple: No mostrar HQ si ya existe (opcional, por ahora lo dejamos libre)
        # Podríamos agregar: if 'hq' in [b['building_type'] for b in buildings]: available_types.remove('hq')
        
        selected_key = st.selectbox(
            "Plano", 
            available_types, 
            format_func=lambda x: f"{BUILDING_TYPES[x]['name']} (Coste: {BUILDING_TYPES[x].get('material_cost', 0)})"
        )
        
        b_def = BUILDING_TYPES[selected_key]
        
        # Mostrar requisitos
        req_cols = st.columns(3)
        req_cols[0].metric("Materiales", b_def.get('material_cost', 0))
        req_cols[1].metric("Energía", b_def.get('energy_cost', 0))
        req_cols[2].metric("Población", b_def.get('pops_required', 0))
        
        if st.button(f"Construir {b_def['name']}", type="primary"):
            # Lógica de construcción
            res = build_structure(planet_asset['id'], player.id, selected_key)
            if res:
                st.success("Construcción iniciada.")
                st.rerun()
            else:
                st.error("No se pudo construir (Fondos insuficientes o Error DB).")


def _reset_to_galaxy_view():
    st.session_state.map_view = "galaxy"
    st.session_state.selected_system_id = None
    st.session_state.selected_planet_id = None
    st.rerun()


def _reset_to_system_view():
    st.session_state.map_view = "system"
    st.session_state.selected_planet_id = None
    st.rerun()