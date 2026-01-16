# ui/galaxy_map_page.py
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.galaxy_generator import get_galaxy
from core.world_models import System, Planet, AsteroidBelt


def show_galaxy_map_page():
    """Punto de entrada para la pagina del mapa galactico."""
    st.title("Mapa de la Galaxia")
    st.markdown("---")

    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
        st.session_state.selected_system_id = None
        st.session_state.selected_planet_id = None

    if st.session_state.map_view == "galaxy":
        _render_interactive_galaxy_map()
    elif st.session_state.map_view == "system" and st.session_state.selected_system_id is not None:
        _render_system_view()
    elif st.session_state.map_view == "planet" and st.session_state.selected_planet_id is not None:
        _render_planet_view()


def _scale_positions(systems: list[System], target_width: int = 1400, target_height: int = 900, margin: int = 80):
    """Escala las coordenadas originales para aprovechar mejor el canvas."""
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
    """Genera rutas simples conectando cada sistema con sus vecinos mas cercanos."""
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


def _render_interactive_galaxy_map():
    """Muestra el mapa galactico interactivo como un componente HTML/SVG mejorado."""
    st.header("Sistemas Conocidos")
    galaxy = get_galaxy()

    col_map, col_controls = st.columns([5, 2])
    with col_controls:
        search_term = st.text_input("Buscar sistema", placeholder="Ej. Alpha-Orionis")
        class_options = sorted({s.star.class_type for s in galaxy.systems})
        selected_classes = st.multiselect(
            "Clases visibles", class_options, default=class_options
        )
        show_routes = st.toggle("Mostrar rutas", value=True)
        star_scale = st.slider("Tamano relativo", 0.8, 2.0, 1.0, 0.05)
        st.caption("Click en una estrella abre el detalle del sistema.")

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
                "color": star_colors.get(system.star.class_type, "#FFFFFF"),
                "radius": round(size_by_class.get(system.star.class_type, 7) * star_scale, 2),
            }
        )

    connections = _build_connections(galaxy.systems, scaled_positions) if show_routes else []

    systems_json = json.dumps(systems_payload)
    connections_json = json.dumps(connections)
    filtered_json = json.dumps(list(filtered_ids))
    highlight_json = json.dumps(list(highlight_ids))

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
        .wrapper {{
            width: 100%;
            height: 100%;
        }}
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
        svg {{
            width: 100%;
            height: 100%;
            cursor: grab;
        }}
        .star {{
            transition: r 0.25s ease, filter 0.25s ease, opacity 0.25s ease;
            filter: drop-shadow(0 0 6px rgba(255,255,255,0.35));
        }}
        .star.dim {{ opacity: 0.2; filter: drop-shadow(0 0 3px rgba(255,255,255,0.1)); }}
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
        .legend h4 {{
            margin: 0 0 8px 0;
            font-size: 14px;
            letter-spacing: 0.4px;
            color: #9fb2d9;
        }}
        .legend-row {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            margin: 4px 0;
            color: #cfd8f5;
        }}
        .swatch {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 10px rgba(255,255,255,0.35);
        }}
        .swatch.g {{ background: #f8f5ff; }}
        .swatch.o {{ background: #8ec5ff; }}
        .swatch.m {{ background: #f2b880; }}
        .swatch.d {{ background: #d7d7d7; }}
        .swatch.x {{ background: #d6a4ff; }}
        .toolbar {{
            position: absolute;
            top: 16px;
            right: 16px;
            display: flex;
            gap: 8px;
        }}
        .btn {{
            background: rgba(16, 26, 42, 0.9);
            color: #e6ecff;
            border: 1px solid var(--stroke);
            padding: 8px 10px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s ease;
        }}
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
                    <defs>
                        <filter id="halo">
                            <feGaussianBlur stdDeviation="6" result="blur" />
                            <feMerge>
                                <feMergeNode in="blur" />
                                <feMergeNode in="SourceGraphic" />
                            </feMerge>
                        </filter>
                    </defs>
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
                    if (!filteredIds.has(sys.id)) {{
                        circle.classList.add("dim");
                    }}
                    if (highlightIds.has(sys.id)) {{
                        circle.classList.add("highlight");
                    }}
                    circle.addEventListener("mousemove", (event) => showTooltip(event, sys));
                    circle.addEventListener("mouseleave", hideTooltip);
                    circle.addEventListener("click", () => handleClick(sys.id));
                    starsLayer.appendChild(circle);
                }});
            }}

            function showTooltip(evt, sys) {{
                tooltip.style.display = "block";
                tooltip.style.left = (evt.pageX + 14) + "px";
                tooltip.style.top = (evt.pageY + 14) + "px";
                tooltip.innerHTML = `
                    <strong>${{sys.name}}</strong><br/>
                    Clase: ${{sys.class}} - Rareza: ${{sys.rarity}}<br/>
                    Energia: ${{sys.energy}}<br/>
                    Regla: ${{sys.rule}}
                `;
            }}

            function hideTooltip() {{
                tooltip.style.display = "none";
            }}

            function handleClick(systemId) {{
                if (window.parent && window.parent.Streamlit) {{
                    window.parent.Streamlit.setComponentValue(systemId);
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
        selection_raw = components.html(
            html_template,
            height=860,
            scrolling=False,
            key="galaxy_map_component",
        )

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


def _render_system_view():
    """Muestra los detalles de un sistema estelar seleccionado."""
    galaxy = get_galaxy()
    system = next((s for s in galaxy.systems if s.id == st.session_state.selected_system_id), None)

    if not system:
        st.error("Error: Sistema no encontrado.")
        _reset_to_galaxy_view()
        return

    st.header(f"Sistema: {system.name}")
    if st.button("<- Volver al Mapa Galactico"):
        _reset_to_galaxy_view()

    with st.expander("Informacion de la Estrella Central", expanded=True):
        st.subheader(f"Estrella: {system.star.name}")
        st.metric("Modificador de Energia", f"{system.star.energy_modifier:+.0%}")
        st.info(f"Regla Especial: {system.star.special_rule}")
        st.caption(f"Clase: {system.star.class_type} | Rareza: {system.star.rarity}")

    st.subheader("Anillos Orbitales")

    for ring in range(1, 10):
        body = system.orbital_rings.get(ring)

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                st.subheader(f"Anillo {ring}")

            with col2:
                if body is None:
                    st.write("_(Vacio)_")
                elif isinstance(body, Planet):
                    st.write(f"**Planeta:** {body.name} ({body.biome})")
                elif isinstance(body, AsteroidBelt):
                    st.write(f"**Cinturon de Asteroides:** {body.name}")

            with col3:
                if isinstance(body, Planet):
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
    with col2:
        st.subheader(f"Bioma: {planet.biome}")
        st.info(f"Bonus: {planet.bonuses}")

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
