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

    # Si viene system_id por querystring, navegar directo
    query_params = st.query_params
    if st.session_state.map_view == "galaxy" and "system_id" in query_params:
        try:
            st.session_state.selected_system_id = int(query_params.get("system_id"))
            st.session_state.map_view = "system"
        except Exception:
            pass

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
            --bg-2: #0f1b2b;
            --panel: #121826;
            --stroke: #1f2a3d;
            --text: #e6ecff;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Inter", system-ui, -apple-system, sans-serif;
            background: radial-gradient(circle at 30% 20%, #142034, #0a0f18 55%, #050910 85%);
            color: var(--text);
        }}
        .wrapper {{ width: 100%; height: 100%; }}
        .map-frame {{
            position: relative;
            width: 100%;
            height: 820px;
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid var(--stroke);
            box-shadow: 0 25px 60px rgba(0,0,0,0.35);
            background: radial-gradient(circle at 50% 35%, #0f1c2d, #070b12 75%);
        }}
        svg {{ width: 100%; height: 100%; cursor: grab; }}
        .star {{
            transition: r 0.25s ease, filter 0.25s ease, opacity 0.25s ease;
            filter: drop-shadow(0 0 6px rgba(255,255,255,0.35));
            cursor: pointer;
        }}
        .star.dim {{ opacity: 0.2; filter: drop-shadow(0 0 3px rgba(255,255,255,0.1)); }}
        .star.resource-dim {{ opacity: 0.12; filter: drop-shadow(0 0 2px rgba(255,255,255,0.05)); }}
        .star.highlight {{ filter: drop-shadow(0 0 14px rgba(150, 255, 255, 0.9)); r: 11; }}
        .star:hover {{ r: 12; filter: drop-shadow(0 0 16px rgba(255,255,255,0.9)); }}
        .route {{ stroke: #5b7bff; stroke-opacity: 0.25; stroke-width: 2; stroke-linecap: round; }}
        .route.highlight {{ stroke-opacity: 0.5; }}
        .legend {{
            position: absolute;
            top: 16px;
            left: 16px;
            background: rgba(10, 14, 24, 0.9);
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid var(--stroke);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            backdrop-filter: blur(6px);
        }}
        .legend h4 {{ margin: 0 0 8px 0; font-size: 14px; letter-spacing: 0.4px; color: #9fb2d9; }}
        .legend-row {{ display: flex; align-items: center; gap: 8px; font-size: 13px; margin: 4px 0; color: #cfd8f5; }}
        .swatch {{ width: 14px; height: 14px; border-radius: 50%; display: inline-block; box-shadow: 0 0 10px rgba(255,255,255,0.35); }}
        .swatch.g {{ background: #f8f5ff; }}
        .swatch.o {{ background: #8ec5ff; }}
        .swatch.m {{ background: #f2b880; }}
        .swatch.d {{ background: #d7d7d7; }}
        .swatch.x {{ background: #d6a4ff; }}
        .toolbar {{ position: absolute; top: 16px; right: 16px; display: flex; gap: 8px; }}
        .btn {{ background: rgba(16, 26, 42, 0.9); color: #e6ecff; border: 1px solid var(--stroke); padding: 8px 10px; border-radius: 10px; cursor: pointer; font-size: 12px; transition: all 0.2s ease; }}
        .btn:hover {{ border-color: #5b7bff; color: #9fb2ff; }}
        #tooltip {{
            position: absolute;
            pointer-events: none;
            background: rgba(8, 12, 22, 0.95);
            border: 1px solid var(--stroke);
            color: #dfe8ff;
            padding: 10px 12px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            font-size: 12px;
            display: none;
            max-width: 240px;
            backdrop-filter: blur(6px);
        }}
    </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="map-frame">
                <div class="legend">
                    <h4>Clases estelares</h4>
                    <div class="legend-row"><span class="swatch g"></span> G - Enana Amarilla</div>
                    <div class="legend-row"><span class="swatch o"></span> O - Gigante Azul</div>
                    <div class="legend-row"><span class="swatch m"></span> M - Enana Roja</div>
                    <div class="legend-row"><span class="swatch d"></span> D - Enana Blanca</div>
                    <div class="legend-row"><span class="swatch x"></span> X - Exotica</div>
                </div>
                <div class="toolbar">
                    <button id="resetView" class="btn">Reset vista</button>
                    <button id="zoomIn" class="btn">+</button>
                    <button id="zoomOut" class="btn">-</button>
                </div>
                <svg id="galaxy-map" viewBox="0 0 {canvas_width} {canvas_height}" preserveAspectRatio="xMidYMid meet">
                    <g id="routes-layer"></g>
                    <g id="stars-layer"></g>
                </svg>
                <div id="tooltip"></div>
            </div>
        </div>

        <script>
            const systems = {systems_json};
            const routes = {connections_json};
            const filteredIds = new Set({filtered_json});
            const highlightIds = new Set({highlight_json});
            const resourceMode = {"true" if resource_filter_active else "false"};
            const resourceName = {resource_name_js};
            const streamlit = window.parent && window.parent.Streamlit ? window.parent.Streamlit : null;

            const starsLayer = document.getElementById("stars-layer");
            const routesLayer = document.getElementById("routes-layer");
            const tooltip = document.getElementById("tooltip");

            function drawRoutes() {{
                routesLayer.innerHTML = "";
                routes.forEach(route => {{
                    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                    line.setAttribute("x1", route.ax);
                    line.setAttribute("y1", route.ay);
                    line.setAttribute("x2", route.bx);
                    line.setAttribute("y2", route.by);
                    line.setAttribute("class", "route");
                    if (highlightIds.has(route.a_id) || highlightIds.has(route.b_id)) {{
                        line.classList.add("highlight");
                    }}
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
                    circle.setAttribute("data-id", sys.id);
                    circle.setAttribute("data-name", sys.name);
                    circle.setAttribute("data-class", sys.class);
                    circle.setAttribute("data-rarity", sys.rarity);
                    circle.setAttribute("data-energy", sys.energy);
                    circle.setAttribute("data-rule", sys.rule);
                    if (resourceMode && sys.resource_prob !== null && sys.resource_prob !== undefined) {{
                        circle.setAttribute("data-resource-prob", sys.resource_prob);
                    }}
                    if (!filteredIds.has(sys.id)) {{
                        circle.classList.add("dim");
                    }}
                    if (resourceMode && (!sys.resource_prob || sys.resource_prob <= 0)) {{
                        circle.classList.add("resource-dim");
                    }}
                    if (highlightIds.has(sys.id)) {{
                        circle.classList.add("highlight");
                    }}
                    circle.style.pointerEvents = "all";
                    circle.addEventListener("mousemove", (event) => showTooltip(event, sys));
                    circle.addEventListener("mouseleave", hideTooltip);
                    circle.addEventListener("mousedown", (evt) => {{ evt.stopPropagation(); evt.preventDefault(); }});
                    circle.addEventListener("touchstart", (evt) => {{ evt.stopPropagation(); }});
                    circle.addEventListener("click", (evt) => {{
                        evt.stopPropagation();
                        evt.preventDefault();
                        console.log("planeta apretado", sys.name);
                        handleClick(sys.id);
                    }});
                    starsLayer.appendChild(circle);
                }});
            }}

            function showTooltip(evt, sys) {{
                tooltip.style.display = "block";
                tooltip.style.left = (evt.pageX + 14) + "px";
                tooltip.style.top = (evt.pageY + 14) + "px";
                const resourceLine = resourceMode ? `<br/>${{resourceName}}: ${{sys.resource_prob ?? 0}}%` : "";
                tooltip.innerHTML = `
                    <strong>(ID ${{sys.id}}) ${{sys.name}}</strong><br/>
                    Clase: ${{sys.class}} - Rareza: ${{sys.rarity}}<br/>
                    Energia: ${{sys.energy}}<br/>
                    Regla: ${{sys.rule}}${{resourceLine}}
                `;
            }}

            function hideTooltip() {{
                tooltip.style.display = "none";
            }}

            function handleClick(systemId) {{
                console.log("click sistema -> navegar con query param", systemId);
                try {{
                    const targetWin = window.parent || window.top || window;
                    const url = new URL(targetWin.location.href);
                    url.searchParams.set("system_id", systemId);
                    targetWin.location.href = url.toString();
                }} catch (e) {{
                    console.warn("No se pudo navegar por query param", e);
                }}
            }}

            drawRoutes();
            drawStars();

            const panZoom = svgPanZoom("#galaxy-map", {{
                zoomEnabled: true,
                controlIconsEnabled: false,
                fit: true,
                minZoom: 0.6,
                maxZoom: 12,
                center: true,
                zoomScaleSensitivity: 0.25
            }});
            document.getElementById("resetView").onclick = () => {{
                panZoom.resetZoom();
                panZoom.resetPan();
            }};
            document.getElementById("zoomIn").onclick = () => panZoom.zoomIn();
            document.getElementById("zoomOut").onclick = () => panZoom.zoomOut();
        </script>
    </body>
    </html>
    """

    with col_map:
        selection_raw = components.html(html_template, height=860, scrolling=False)

    selected_system_id = None
    if selection_raw not in (None, "", "null"):
        try:
            selected_system_id = int(selection_raw)
        except (TypeError, ValueError):
            selected_system_id = None

    if selected_system_id is not None:
        st.session_state.map_view = "system"
        st.session_state.selected_system_id = selected_system_id
        st.rerun()


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
        planet.addEventListener("click", () => {{
            console.log("planeta apretado (mapa orbital)", p.name);
            if (window.parent && window.parent.Streamlit && window.parent.Streamlit.setComponentValue) {{
                window.parent.Streamlit.setComponentValue("planet:" + p.id);
            }} else if (window.parent && window.parent.postMessage) {{
                window.parent.postMessage({{ type: "streamlit:setComponentValue", value: "planet:" + p.id }}, "*");
                window.parent.postMessage({{ type: "streamlit:componentValue", value: "planet:" + p.id }}, "*");
            }}
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
    planet_click = _render_system_orbits(system)
    if planet_click:
        if isinstance(planet_click, str) and planet_click.startswith("planet:"):
            try:
                planet_id = int(planet_click.split("planet:")[1])
                st.session_state.map_view = "planet"
                st.session_state.selected_planet_id = planet_id
                st.rerun()
            except ValueError:
                pass

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
