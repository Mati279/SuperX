# ui/galaxy_map_page.py
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.galaxy_generator import get_galaxy
from core.world_models import System, Planet, AsteroidBelt
from core.world_constants import RESOURCE_STAR_WEIGHTS, METAL_RESOURCES


def show_galaxy_map_page():
    """Punto de entrada para la pagina del mapa galactico."""
    st.title("Mapa de la Galaxia")
    st.markdown("---")

    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
        st.session_state.selected_system_id = None
        st.session_state.selected_planet_id = None

    # --- LÓGICA DE NAVEGACIÓN (Bridging JS -> Python) ---
    # Capturamos el parámetro system_id que el JS inyecta en la URL
    if "system_id" in st.query_params:
        try:
            target_system_id = int(st.query_params["system_id"])
            st.session_state.selected_system_id = target_system_id
            st.session_state.map_view = "system"
            
            # Limpiamos la URL para que no se quede el parámetro pegado
            del st.query_params["system_id"]
            st.rerun()
        except (ValueError, TypeError):
             if "system_id" in st.query_params:
                del st.query_params["system_id"]

    # --- Renderizado de Vistas ---
    if st.session_state.map_view == "galaxy":
        _render_interactive_galaxy_map()
    elif st.session_state.map_view == "system" and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == "planet" and st.session_state.selected_planet_id is not None:
        _render_planet_view()


def _scale_positions(systems: list[System], target_width: int = 1400, target_height: int = 900, margin: int = 80):
    xs = [s.position[0] for s in systems]
    ys = [s.position[1] for s in systems]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    def scale(value: float, min_val: float, span: float, target: int) -> float:
        usable = target - (2 * margin)
        return margin + ((value - min_val) / span) * usable

    return {
        system.id: (
            scale(system.position[0], min_x, span_x, target_width),
            scale(system.position[1], min_y, span_y, target_height),
        )
        for system in systems
    }


def _build_connections(systems: list[System], positions: dict[int, tuple[float, float]], neighbors: int = 3):
    edges = set()
    for system in systems:
        x1, y1 = positions[system.id]
        distances = []
        for other in systems:
            if other.id == system.id:
                continue
            x2, y2 = positions[other.id]
            dist = math.hypot(x1 - x2, y1 - y2)
            distances.append((dist, other.id))
        distances.sort(key=lambda t: t[0])
        for _, neighbor_id in distances[:neighbors]:
            edge_key = tuple(sorted((system.id, neighbor_id)))
            edges.add(edge_key)

    connections = []
    for a_id, b_id in edges:
        ax, ay = positions[a_id]
        bx, by = positions[b_id]
        connections.append(
            {"a_id": a_id, "b_id": b_id, "ax": ax, "ay": ay, "bx": bx, "by": by}
        )
    return connections


def _resource_probability(resource_name: str, star_class: str) -> float:
    weights = RESOURCE_STAR_WEIGHTS.get(star_class, {})
    total = sum(weights.values())
    if total <= 0:
        return 0.0
    return round((weights.get(resource_name, 0) / total) * 100, 2)


def _planet_color_for_biome(biome: str) -> str:
    biome_key = (biome or "").lower()
    if "terrestre" in biome_key:
        return "#7be0a5"
    if "des" in biome_key:
        return "#e3c07b"
    if "oce" in biome_key:
        return "#6fb6ff"
    if "volc" in biome_key:
        return "#ff7058"
    if "lido" in biome_key:
        return "#a8d8ff"
    if "gaseoso" in biome_key:
        return "#c6a3ff"
    return "#7ec7ff"


def _resource_radius_factor(probability: float) -> float:
    if probability is None:
        return 1.0
    clamped = max(0.0, min(probability, 100.0))
    return 0.3 + (clamped / 100.0) * 3.2


def _resource_color(resource_name: str) -> str:
    resource_colors = {
        "Hierro": "#9aa2ad",
        "Cobre": "#c77a48",
        "Niquel": "#b6b6b6",
        "Titanio": "#9bb7d6",
        "Platino": "#d3d7db",
        "Oricalco Oscuro": "#5b6a8a",
        "Neutrilium": "#67c7b1",
        "Aetherion": "#f1d26a",
    }
    return resource_colors.get(resource_name, "#9fb2ff")


def _render_interactive_galaxy_map():
    st.header("Sistemas Conocidos")
    galaxy = get_galaxy()
    systems_sorted = sorted(galaxy.systems, key=lambda s: s.id)
    system_options = {f"(ID {s.id}) {s.name}": s.id for s in systems_sorted}
    placeholder_opt = "(Seleccionar sistema)"

    col_map, col_controls = st.columns([5, 2])
    with col_controls:
        chooser = st.selectbox(
            "Abrir sistema manualmente",
            [placeholder_opt] + list(system_options.keys()),
            index=0,
            key="manual_system_selector",
        )
        if chooser and chooser != placeholder_opt:
            st.session_state.map_view = "system"
            st.session_state.selected_system_id = system_options[chooser]
            st.rerun()
        search_term = st.text_input("Buscar sistema", placeholder="Ej. Alpha-Orionis")
        class_options = sorted({s.star.class_type for s in galaxy.systems})
        selected_classes = st.multiselect(
            "Clases visibles", class_options, default=class_options
        )
        show_routes = st.toggle("Mostrar rutas", value=True)
        star_scale = st.slider("Tamano relativo", 0.8, 2.0, 1.0, 0.05)
        resource_options = ["(sin filtro)"] + list(METAL_RESOURCES.keys())
        selected_resource = st.selectbox("Recurso a resaltar", resource_options, index=0)
        resource_filter_active = selected_resource != "(sin filtro)"
        if resource_filter_active:
            st.caption("Probabilidad por clase estelar:")
            probs = {k: _resource_probability(selected_resource, k) for k in class_options}
            for cls in class_options:
                st.write(f"{cls}: {probs.get(cls, 0):.1f}%")

    canvas_width, canvas_height = 1400, 900
    scaled_positions = _scale_positions(galaxy.systems, canvas_width, canvas_height)

    star_colors = {"G": "#f8f5ff", "O": "#8ec5ff", "M": "#f2b880", "D": "#d7d7d7", "X": "#d6a4ff"}
    size_by_class = {"G": 7, "O": 8, "M": 6, "D": 7, "X": 9}

    filtered_ids = {s.id for s in galaxy.systems if s.star.class_type in selected_classes} if selected_classes else {s.id for s in galaxy.systems}
    highlight_ids = {
        s.id for s in galaxy.systems if search_term and search_term.lower() in s.name.lower()
    }

    systems_payload = []
    for system in galaxy.systems:
        x, y = scaled_positions[system.id]
        base_radius = size_by_class.get(system.star.class_type, 7) * star_scale
        resource_prob = _resource_probability(selected_resource, system.star.class_type) if resource_filter_active else None
        radius = base_radius
        if resource_filter_active and resource_prob is not None:
            radius = base_radius * _resource_radius_factor(resource_prob)
        color = star_colors.get(system.star.class_type, "#FFFFFF")
        if resource_filter_active:
            color = _resource_color(selected_resource)
        systems_payload.append(
            {
                "id": system.id,
                "name": system.name,
                "class": system.star.class_type,
                "rarity": system.star.rarity,
                "energy": f"{system.star.energy_modifier:+.0%}",
                "rule": system.star.special_rule,
                "x": round(x, 2),
                "y": round(y, 2),
                "color": color,
                "radius": round(radius, 2),
                "resource_prob": resource_prob,
            }
        )

    connections = _build_connections(galaxy.systems, scaled_positions) if show_routes else []

    systems_json = json.dumps(systems_payload)
    connections_json = json.dumps(connections)
    filtered_json = json.dumps(list(filtered_ids))
    highlight_json = json.dumps(list(highlight_ids))
    resource_name_js = json.dumps(selected_resource if resource_filter_active else "")

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8" />
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        :root {{
            --bg-1: #0b0f18;
            --panel-bg: rgba(13, 19, 30, 0.95);
            --stroke: #1f2a3d;
            --text: #e6ecff;
            --highlight: #5b7bff;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Inter", system-ui, -apple-system, sans-serif;
            background: #000;
            color: var(--text);
            overflow: hidden;
        }}
        .wrapper {{ width: 100%; height: 100%; position: relative; }}
        .map-frame {{
            position: relative;
            width: 100%;
            height: 820px;
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid var(--stroke);
            background: radial-gradient(circle at 50% 35%, #0f1c2d, #070b12 75%);
        }}
        svg {{ width: 100%; height: 100%; cursor: grab; }}
        .star {{
            transition: r 0.25s ease, filter 0.25s ease, opacity 0.25s ease;
            filter: drop-shadow(0 0 6px rgba(255,255,255,0.35));
            cursor: pointer;
        }}
        .star.dim {{ opacity: 0.2; pointer-events: none; }}
        .star:hover {{ r: 14; filter: drop-shadow(0 0 16px rgba(255,255,255,0.9)); stroke: white; stroke-width: 2px; }}
        .route {{ stroke: #5b7bff; stroke-opacity: 0.25; stroke-width: 2; stroke-linecap: round; pointer-events: none; }}
        
        .legend {{
            position: absolute; top: 16px; left: 16px;
            background: rgba(16, 26, 42, 0.85); padding: 12px 14px;
            border-radius: 12px; border: 1px solid var(--stroke);
            backdrop-filter: blur(8px);
        }}
        .swatch {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }}
        .swatch.g {{ background: #f8f5ff; }} .swatch.o {{ background: #8ec5ff; }}
        .swatch.m {{ background: #f2b880; }} .swatch.d {{ background: #d7d7d7; }} .swatch.x {{ background: #d6a4ff; }}
        .legend-row {{ font-size: 12px; color: #cfd8f5; margin-bottom: 4px; }}
        
        .toolbar {{ position: absolute; top: 16px; right: 16px; display: flex; gap: 8px; z-index: 10; }}
        .btn {{ 
            background: rgba(16, 26, 42, 0.85); color: #e6ecff; border: 1px solid var(--stroke); 
            padding: 8px 12px; border-radius: 8px; cursor: pointer; transition: 0.2s;
        }}
        .btn:hover {{ border-color: var(--highlight); color: var(--highlight); }}

        /* --- SIDE PANEL (Fixed Right) --- */
        #side-panel {{
            position: absolute;
            top: 0; right: 0; bottom: 0;
            width: 320px;
            background: var(--panel-bg);
            border-left: 1px solid var(--stroke);
            box-shadow: -10px 0 30px rgba(0,0,0,0.5);
            padding: 24px;
            display: flex;
            flex-direction: column;
            transform: translateX(100%);
            transition: transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
            z-index: 100;
            backdrop-filter: blur(10px);
        }}
        #side-panel.open {{ transform: translateX(0); }}
        
        .panel-header {{ border-bottom: 1px solid var(--stroke); padding-bottom: 16px; margin-bottom: 16px; }}
        .panel-title {{ margin: 0 0 4px 0; font-size: 22px; color: #fff; font-weight: 700; }}
        .panel-subtitle {{ font-size: 13px; color: var(--highlight); font-weight: 500; text-transform: uppercase; letter-spacing: 1px; }}
        
        .info-grid {{ display: grid; gap: 12px; margin-bottom: 24px; }}
        .info-item {{ display: flex; justify-content: space-between; font-size: 13px; border-bottom: 1px solid #1f2a3d; padding-bottom: 6px; }}
        .info-label {{ color: #8fa5c4; }}
        .info-val {{ color: #e6ecff; font-weight: 600; text-align: right; }}
        
        .special-rule-box {{ 
            background: rgba(91, 123, 255, 0.1); border: 1px solid rgba(91, 123, 255, 0.3);
            border-radius: 8px; padding: 12px; font-size: 12px; color: #d0dfff; margin-bottom: 24px;
            line-height: 1.4;
        }}
        
        .action-area {{ margin-top: auto; }}
        .enter-btn {{
            width: 100%;
            background: linear-gradient(135deg, #2b4570, #1a2a44);
            border: 1px solid #5b7bff;
            color: white;
            padding: 14px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            transition: all 0.2s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}
        .enter-btn:hover {{ 
            background: #5b7bff; 
            box-shadow: 0 0 20px rgba(91, 123, 255, 0.6); 
            transform: translateY(-2px);
        }}
        
        .close-panel {{
            position: absolute; top: 16px; right: 16px;
            background: transparent; border: none; color: #555;
            cursor: pointer; font-size: 24px; line-height: 1;
        }}
        .close-panel:hover {{ color: #fff; }}
        
        #mini-tooltip {{
            position: absolute; pointer-events: none; background: rgba(0,0,0,0.9);
            padding: 4px 8px; border-radius: 4px; font-size: 11px; color: #fff;
            display: none; border: 1px solid #444; transform: translateY(-30px);
            white-space: nowrap; z-index: 50;
        }}
    </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="map-frame">
                <div id="mini-tooltip"></div>
                
                <div id="side-panel">
                    <button class="close-panel" onclick="closePanel()">×</button>
                    <div class="panel-header">
                        <h2 class="panel-title" id="p-name">Alpha Centauri</h2>
                        <div class="panel-subtitle" id="p-id">ID: 001</div>
                    </div>
                    
                    <div class="info-grid">
                        <div class="info-item"><span class="info-label">Clase Estelar</span><span class="info-val" id="p-class">G</span></div>
                        <div class="info-item"><span class="info-label">Rareza</span><span class="info-val" id="p-rarity">Común</span></div>
                        <div class="info-item"><span class="info-label">Energía</span><span class="info-val" id="p-energy">100%</span></div>
                        <div class="info-item" id="row-resource" style="display:none">
                            <span class="info-label">Recurso</span>
                            <span class="info-val" id="p-resource" style="color:#f1d26a">Oro</span>
                        </div>
                    </div>
                    
                    <div class="special-rule-box">
                        <strong style="display:block; margin-bottom:4px; color:#fff;">Regla Especial:</strong>
                        <span id="p-rule">Sin efectos adversos detectados.</span>
                    </div>
                    
                    <div class="action-area">
                        <button id="btn-enter" class="enter-btn">ENTRAR AL SISTEMA</button>
                    </div>
                </div>

                <div class="legend">
                    <div class="legend-row"><span class="swatch g"></span> G (Amarilla)</div>
                    <div class="legend-row"><span class="swatch o"></span> O (Azul)</div>
                    <div class="legend-row"><span class="swatch m"></span> M (Roja)</div>
                    <div class="legend-row"><span class="swatch d"></span> D (Blanca)</div>
                    <div class="legend-row"><span class="swatch x"></span> X (Exótica)</div>
                </div>
                
                <div class="toolbar">
                    <button id="resetView" class="btn">Centrar</button>
                    <button id="zoomIn" class="btn">+</button>
                    <button id="zoomOut" class="btn">-</button>
                </div>
                
                <svg id="galaxy-map" viewBox="0 0 {canvas_width} {canvas_height}" preserveAspectRatio="xMidYMid meet">
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
            const resourceMode = {"true" if resource_filter_active else "false"};
            const resourceName = {resource_name_js};
            
            const starsLayer = document.getElementById("stars-layer");
            const routesLayer = document.getElementById("routes-layer");
            const miniTooltip = document.getElementById("mini-tooltip");
            const sidePanel = document.getElementById("side-panel");
            const enterBtn = document.getElementById("btn-enter");
            
            let currentSelectedId = null;

            // -- Drawing Functions --
            function drawRoutes() {{
                routesLayer.innerHTML = "";
                routes.forEach(route => {{
                    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    line.setAttribute("x1", route.ax); line.setAttribute("y1", route.ay);
                    line.setAttribute("x2", route.bx); line.setAttribute("y2", route.by);
                    line.setAttribute("class", "route");
                    routesLayer.appendChild(line);
                }});
            }}

            function drawStars() {{
                starsLayer.innerHTML = "";
                systems.forEach(sys => {{
                    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                    circle.setAttribute("cx", sys.x);
                    circle.setAttribute("cy", sys.y);
                    circle.setAttribute("r", sys.radius);
                    circle.setAttribute("fill", sys.color);
                    circle.setAttribute("class", "star");
                    
                    if (!filteredIds.has(sys.id)) {{
                        circle.classList.add("dim");
                    }}
                    
                    // Hover simple (solo nombre)
                    circle.addEventListener("mouseenter", () => {{
                        miniTooltip.style.display = "block";
                        miniTooltip.textContent = sys.name;
                    }});
                    circle.addEventListener("mousemove", (e) => {{
                        miniTooltip.style.left = (e.pageX + 10) + "px";
                        miniTooltip.style.top = (e.pageY - 25) + "px";
                    }});
                    circle.addEventListener("mouseleave", () => {{
                        miniTooltip.style.display = "none";
                    }});
                    
                    // CLICK: Abrir Panel Lateral
                    circle.addEventListener("click", (evt) => {{
                        evt.stopPropagation();
                        evt.preventDefault();
                        openPanel(sys);
                    }});
                    
                    starsLayer.appendChild(circle);
                }});
            }}

            // -- Panel Logic --
            function openPanel(sys) {{
                currentSelectedId = sys.id;
                
                // Rellenar datos
                document.getElementById("p-name").textContent = sys.name;
                document.getElementById("p-id").textContent = "ID SISTEMA: " + sys.id;
                document.getElementById("p-class").textContent = sys.class;
                document.getElementById("p-rarity").textContent = sys.rarity;
                document.getElementById("p-energy").textContent = sys.energy;
                document.getElementById("p-rule").textContent = sys.rule;
                
                const resRow = document.getElementById("row-resource");
                if (resourceMode && sys.resource_prob) {{
                    resRow.style.display = "flex";
                    document.getElementById("p-resource").textContent = `${{resourceName}} (${{sys.resource_prob}}%)`;
                }} else {{
                    resRow.style.display = "none";
                }}
                
                // Mostrar panel
                sidePanel.classList.add("open");
            }}

            function closePanel() {{
                sidePanel.classList.remove("open");
                currentSelectedId = null;
            }}

            // Cerrar panel al hacer clic en el fondo
            document.querySelector(".map-frame").addEventListener("click", (e) => {{
                if (!e.target.classList.contains("star") && !sidePanel.contains(e.target)) {{
                    closePanel();
                }}
            }});
            
            // -- NAVEGACIÓN ROBUSTA --
            enterBtn.addEventListener("click", () => {{
                if (currentSelectedId !== null) {{
                    console.log("Navegando a sistema:", currentSelectedId);
                    // Truco para forzar recarga en Streamlit: modificar window.top.location
                    try {{
                        const targetWin = window.top || window.parent || window;
                        const currentUrl = new URL(targetWin.location.href);
                        currentUrl.searchParams.set("system_id", currentSelectedId);
                        targetWin.location.href = currentUrl.toString();
                    }} catch (e) {{
                        console.error("Error navegando:", e);
                        // Fallback desesperado
                        window.location.search = "?system_id=" + currentSelectedId;
                    }}
                }}
            }});

            drawRoutes();
            drawStars();

            const panZoom = svgPanZoom("#galaxy-map", {{
                zoomEnabled: true, controlIconsEnabled: false, fit: true, center: true, minZoom: 0.6, maxZoom: 12
            }});
            
            document.getElementById("resetView").onclick = () => {{ panZoom.resetZoom(); panZoom.resetPan(); }};
            document.getElementById("zoomIn").onclick = () => panZoom.zoomIn();
            document.getElementById("zoomOut").onclick = () => panZoom.zoomOut();
        </script>
    </body>
    </html>
    """

    with col_map:
        components.html(html_template, height=860, scrolling=False)


def _render_system_orbits(system: System):
    """Visual del sol y planetas orbitando con click en planeta."""
    star_colors = {"G": "#f8f5ff", "O": "#8ec5ff", "M": "#f2b880", "D": "#d7d7d7", "X": "#d6a4ff"}
    star_glow = {"G": 18, "O": 22, "M": 16, "D": 18, "X": 24}
    planet_colors = {
        "Terrestre (Gaya)": "#7be0a5",
        "Desértico": "#e3c07b",
        "Oceánico": "#6fb6ff",
        "Volcánico": "#ff7058",
        "Gélido": "#a8d8ff",
        "Gigante Gaseoso": "#c6a3ff",
    }
    center_x = 360
    center_y = 360
    orbit_step = 38
    planets = []
    planet_items = [(ring, body) for ring, body in sorted(system.orbital_rings.items()) if isinstance(body, Planet)]
    for idx, (ring, body) in enumerate(planet_items):
        # Golden angle for even angular spacing with few planets.
        angle_deg = ((system.id * 23) + (idx * 137.5)) % 360
        angle_rad = math.radians(angle_deg)
        radius = 70 + ring * orbit_step
        px = center_x + radius * math.cos(angle_rad)
        py = center_y + radius * math.sin(angle_rad)
        size_map = {"Pequeno": 7, "Mediano": 10, "Grande": 13}
        pr = size_map.get(body.size, 9)
        color = _planet_color_for_biome(body.biome)
        resources = ", ".join(body.resources[:3]) if body.resources else "Sin recursos"
        planets.append({
            "id": body.id,
            "name": body.name,
            "biome": body.biome,
            "size": body.size,
            "resources": resources,
            "explored": body.explored_pct,
            "x": round(px, 2),
            "y": round(py, 2),
            "r": pr,
            "ring": ring,
            "color": color,
        })

    planets_json = json.dumps(planets)
    star_color = star_colors.get(system.star.class_type, "#f8f5ff")

    html = f"""
    <style>
    .sys-wrapper {{ width: 100%; height: 720px; display: flex; justify-content: center; align-items: center; }}
    .sys-canvas {{
        width: 720px; height: 720px; border-radius: 12px;
        background: radial-gradient(circle at 30% 20%, #111a2e, #080c16 70%);
        border: 1px solid #1d2a3c; position: relative; overflow: hidden;
    }}
    .sys-tooltip {{
        position: absolute; background: rgba(8,12,22,0.95); color: #e6ecff;
        border: 1px solid #1f2a3d; padding: 8px 10px; border-radius: 8px;
        font-size: 12px; pointer-events: none; display: none; max-width: 240px;
    }}
    .legend {{ position:absolute; top:10px; right:10px; background:rgba(10,14,24,0.8); padding:8px 10px; border:1px solid #1f2a3d; border-radius:8px; color:#cfd8f5; font-size:12px; }}
    .legend h4 {{ margin:0 0 6px 0; font-size:12px; color:#9fb2ff; }}
    .legend-row {{ margin:2px 0; }}
    </style>
    <div class="sys-wrapper">
        <svg id="system-orbits" class="sys-canvas" viewBox="0 0 {center_x*2} {center_y*2}" preserveAspectRatio="xMidYMid meet">
            <defs>
                <radialGradient id="starGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stop-color="{star_color}" stop-opacity="0.95" />
                    <stop offset="100%" stop-color="{star_color}" stop-opacity="0.1" />
                </radialGradient>
            </defs>
            <circle cx="{center_x}" cy="{center_y}" r="{star_glow.get(system.star.class_type, 20)}" fill="url(#starGlow)" stroke="{star_color}" stroke-width="2.5" filter="url(#glowShadow)" />
            <defs>
              <filter id="glowShadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="0" stdDeviation="8" flood-color="{star_color}" flood-opacity="0.7" />
              </filter>
            </defs>
        </svg>
        <div id="sys-tooltip" class="sys-tooltip"></div>
        <div class="legend">
            <h4>Claves visuales</h4>
            <div class="legend-row">■ Tamaño y nombre escalan con el planeta</div>
            <div class="legend-row">■ Click en planeta para abrir detalles</div>
        </div>
    </div>
    <script>
      const planets = {planets_json};
      const svg = document.getElementById("system-orbits");
      const tooltip = document.getElementById("sys-tooltip");
      const centerX = {center_x};
      const centerY = {center_y};

      // draw orbits
      planets.forEach(p => {{
        const orbit = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        orbit.setAttribute("cx", centerX);
        orbit.setAttribute("cy", centerY);
        orbit.setAttribute("r", Math.hypot(p.x - centerX, p.y - centerY));
        orbit.setAttribute("fill", "none");
        orbit.setAttribute("stroke", "rgba(255,255,255,0.08)");
        orbit.setAttribute("stroke-width", "1");
        svg.appendChild(orbit);
      }});

      // draw planets
      planets.forEach(p => {{
        const planet = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        planet.setAttribute("cx", p.x);
        planet.setAttribute("cy", p.y);
        planet.setAttribute("r", p.r);
        planet.setAttribute("fill", p.color);
        planet.setAttribute("stroke", "#b2d7ff");
        planet.setAttribute("stroke-width", "1");
        planet.style.cursor = "pointer";
        planet.addEventListener("mousemove", (evt) => {{
            tooltip.style.display = "block";
            tooltip.style.left = (evt.pageX + 10) + "px";
            tooltip.style.top = (evt.pageY + 10) + "px";
            tooltip.innerHTML = `<strong>${{p.name}}</strong><br/>
                Bioma: ${{p.biome}}<br/>
                Tamano: ${{p.size}}<br/>
                Explorado: ${{p.explored}}%<br/>
                Recursos: ${{p.resources}}`;
        }});
        planet.addEventListener("mouseleave", () => tooltip.style.display = "none");
        // Nota: El click en planetas no navega via URL param en esta versión simplificada
        planet.addEventListener("click", () => {{
            console.log("Planeta seleccionado (Orbital View):", p.name);
        }});
        svg.appendChild(planet);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", p.x + 10);
        label.setAttribute("y", p.y + 4);
        label.setAttribute("fill", "#dfe8ff");
        label.setAttribute("font-size", p.r >= 12 ? "13" : "11");
        label.setAttribute("font-weight", "600");
        label.textContent = `${{p.name}} (R${{p.ring}})`;
        svg.appendChild(label);
      }});
    </script>
    """
    return components.html(html, height=780)


def _render_system_view():
    """Muestra los detalles de un sistema estelar seleccionado."""
    galaxy = get_galaxy()
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)

    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    st.header(f"Sistema: {system.name}")
    with st.container():
        if st.button("← Volver al mapa", use_container_width=True, type="primary", key="back_to_map"):
            _reset_to_galaxy_view()

    with st.expander("Informacion de la Estrella Central", expanded=True):
        st.subheader(f"Estrella: {system.star.name}")
        st.metric("Modificador de Energia", f"{system.star.energy_modifier:+.0%}")
        st.info(f"Regla Especial: {system.star.special_rule}")
        st.caption(f"Clase: {system.star.class_type} | Rareza: {system.star.rarity}")

    st.subheader("Vista orbital")
    # Renderizamos la vista orbital
    _render_system_orbits(system)

    st.subheader("Cuerpos celestiales")
    for ring in range(1, 10):
        body = system.orbital_rings.get(ring)
        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 3, 3])
            with col1:
                st.caption(f"Anillo {ring}")
            with col2:
                if body is None:
                    st.write("_(Vacio)_")
                elif isinstance(body, Planet):
                    color = _planet_color_for_biome(body.biome)
                    st.markdown(
                        f"<span style='color: {color}; font-weight: 700'>{body.name}</span>",
                        unsafe_allow_html=True,
                    )
                    st.write(f"Bioma: {body.biome} | Tamano: {body.size}")
                elif isinstance(body, AsteroidBelt):
                    st.write(f"**Cinturon de Asteroides:** {body.name}")
            with col3:
                if isinstance(body, Planet):
                    st.progress(body.explored_pct / 100.0, text=f"Explorado {body.explored_pct}%")
                    top_res = ", ".join(body.resources[:3]) if body.resources else "Sin recursos"
                    st.write(f"Recursos: {top_res}")
                    if st.button("Ver Detalles", key=f"planet_{body.id}"):
                        st.session_state.map_view = "planet"
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
        st.metric("Slots de Construccion", planet.construction_slots)
        st.metric("Mod. Mantenimiento", f"{planet.maintenance_mod:+.0%}")
        st.metric("Tamano", planet.size)
        st.metric("Explorado", f"{planet.explored_pct}%")
    with col2:
        st.subheader(f"Bioma: {planet.biome}")
        st.info(f"Bonus: {planet.bonuses}")
        st.write(f"Recursos: {', '.join(planet.resources[:3]) if planet.resources else 'Sin recursos'}")

    st.subheader("Satelites Naturales (Lunas)")
    if planet.moons:
        for moon in planet.moons:
            st.write(f"- {moon.name}")
    else:
        st.write("_Este planeta no tiene lunas._")


def _reset_to_galaxy_view():
    st.session_state.map_view = "galaxy"
    st.session_state.selected_system_id = None
    st.session_state.selected_planet_id = None
    st.rerun()


def _reset_to_system_view():
    st.session_state.map_view = "system"
    st.session_state.selected_planet_id = None
    st.rerun()