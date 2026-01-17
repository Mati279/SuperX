# ui/galaxy_map_page.py
import json
import math
import streamlit as st
import streamlit.components.v1 as components
from core.galaxy_generator import get_galaxy
from core.world_models import System, Planet, AsteroidBelt
from core.world_constants import RESOURCE_STAR_WEIGHTS, METAL_RESOURCES
from data.planet_repository import get_all_player_planets
from ui.state import get_player


def show_galaxy_map_page():
    """Punto de entrada para la pagina del mapa galactico."""
    st.title("Mapa de la Galaxia")
    st.markdown("---")

    # Inicialización de estado
    if "map_view" not in st.session_state:
        st.session_state.map_view = "galaxy"
    if "selected_system_id" not in st.session_state:
        st.session_state.selected_system_id = None
    if "preview_system_id" not in st.session_state:
        st.session_state.preview_system_id = None # ID del sistema seleccionado en el mapa (click)
    if "selected_planet_id" not in st.session_state:
        st.session_state.selected_planet_id = None

    # --- LÓGICA DE NAVEGACIÓN (Bridging JS -> Python) ---
    # Si el mapa envía un 'preview_id' (al hacer click en una estrella), actualizamos la previsualización
    if "preview_id" in st.query_params:
        try:
            p_id = int(st.query_params["preview_id"])
            st.session_state.preview_system_id = p_id
            # Limpiamos la URL para evitar recargas en bucle, pero mantenemos el estado
            del st.query_params["preview_id"]
        except (ValueError, TypeError):
             if "preview_id" in st.query_params:
                del st.query_params["preview_id"]
        # Rerun para mostrar la info en la barra lateral
        st.rerun()

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
    
    # Columnas: Mapa (izquierda grande) - Controles/Info (derecha pequeña)
    col_map, col_controls = st.columns([5, 2])
    
    # --- COLUMNA DERECHA: FILTROS Y DETALLES ---
    with col_controls:
        # 1. Filtros
        search_term = st.text_input("Buscar sistema", placeholder="Ej. Alpha-Orionis")
        
        # Sincronizar el selectbox con el estado de preview si existe
        # Esto permite que si clickeas en el mapa, el selectbox se actualice (truco visual)
        # o si usas el selectbox, se actualice el preview.
        current_idx = 0
        sys_options = [s.name for s in systems_sorted]
        if st.session_state.preview_system_id:
            for i, s in enumerate(systems_sorted):
                if s.id == st.session_state.preview_system_id:
                    current_idx = i
                    break
        
        # Selector manual
        selected_name = st.selectbox(
            "Seleccionar sistema",
            sys_options,
            index=current_idx,
            key="manual_system_selector"
        )
        
        # Si el usuario cambia el selectbox manualmente, actualizamos el preview
        selected_sys_obj = systems_sorted[sys_options.index(selected_name)]
        if selected_sys_obj.id != st.session_state.preview_system_id:
            st.session_state.preview_system_id = selected_sys_obj.id
            st.rerun()

        st.markdown("---")
        
        class_options = sorted({s.star.class_type for s in galaxy.systems})
        selected_classes = st.multiselect(
            "Clases visibles", class_options, default=class_options
        )
        show_routes = st.toggle("Mostrar rutas", value=True)
        star_scale = st.slider("Tamano relativo", 0.8, 2.0, 1.0, 0.05)
        
        resource_options = ["(sin filtro)"] + list(METAL_RESOURCES.keys())
        selected_resource = st.selectbox("Recurso a resaltar", resource_options, index=0)
        
        st.markdown("---")

        # 2. PANEL DE INFORMACIÓN DEL SISTEMA SELECCIONADO
        # Aquí es donde mostramos la info cuando se hace click en el mapa
        if st.session_state.preview_system_id:
            # Buscar el sistema en la lista
            preview_sys = next((s for s in galaxy.systems if s.id == st.session_state.preview_system_id), None)
            
            if preview_sys:
                st.subheader(f"🔭 {preview_sys.name}")
                st.caption(f"ID: {preview_sys.id} | Coordenadas: {preview_sys.position}")
                
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    c1.metric("Clase", preview_sys.star.class_type)
                    c2.metric("Rareza", preview_sys.star.rarity)
                    
                    st.write(f"**Energía:** {preview_sys.star.energy_modifier:+.0%}")
                    st.info(f"📜 {preview_sys.star.special_rule}")
                    
                    # Botón de acción principal
                    if st.button("🚀 ENTRAR AL SISTEMA", type="primary", use_container_width=True):
                        st.session_state.selected_system_id = preview_sys.id
                        st.session_state.map_view = "system"
                        st.rerun()
            else:
                st.warning("Sistema seleccionado no encontrado.")
        else:
            st.info("Selecciona una estrella en el mapa o en la lista para ver detalles.")

    # --- LÓGICA DE DATOS PARA EL MAPA ---
    resource_filter_active = selected_resource != "(sin filtro)"
    
    canvas_width, canvas_height = 1400, 900
    scaled_positions = _scale_positions(galaxy.systems, canvas_width, canvas_height)

    star_colors = {"G": "#f8f5ff", "O": "#8ec5ff", "M": "#f2b880", "D": "#d7d7d7", "X": "#d6a4ff"}
    size_by_class = {"G": 7, "O": 8, "M": 6, "D": 7, "X": 9}

    filtered_ids = {s.id for s in galaxy.systems if s.star.class_type in selected_classes} if selected_classes else {s.id for s in galaxy.systems}
    highlight_ids = {
        s.id for s in galaxy.systems if search_term and search_term.lower() in s.name.lower()
    }
    
    # Si hay uno seleccionado en preview, lo resaltamos también
    if st.session_state.preview_system_id:
        highlight_ids.add(st.session_state.preview_system_id)

    player_home_system_ids = set()
    player = get_player()
    if player:
        home_base_name = f"Base {player.faccion_nombre}"
        player_planets = get_all_player_planets(player.id)
        for p in player_planets:
            if p['nombre_asentamiento'] == home_base_name:
                # El system_id de la BD no coincide con el ID procedural.
                # Buscamos por nombre del sistema para obtener el ID correcto.
                db_system_id = p['system_id']
                try:
                    from data.database import get_supabase
                    sys_res = get_supabase().table("systems").select("name").eq("id", db_system_id).single().execute()
                    if sys_res.data:
                        system_name = sys_res.data.get("name")
                        # Buscar el sistema en la galaxia procedural por nombre
                        for sys in galaxy.systems:
                            if sys.name == system_name:
                                player_home_system_ids.add(sys.id)
                                break
                except Exception:
                    pass
                break  # Assuming only one home base

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
    player_home_system_ids_json = json.dumps(list(player_home_system_ids))

    # --- HTML DEL MAPA ---
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8" />
    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
    <style>
        :root {{
            --bg-1: #0b0f18;
            --stroke: #1f2a3d;
            --text: #e6ecff;
        }}
        body {{
            margin: 0; font-family: "Inter", sans-serif; background: #000; color: var(--text); overflow: hidden;
        }}
        .wrapper {{ width: 100%; height: 100%; }}
        .map-frame {{
            width: 100%; height: 860px;
            border-radius: 12px; overflow: hidden; border: 1px solid var(--stroke);
            background: radial-gradient(circle at 50% 35%, #0f1c2d, #070b12 75%);
        }}
        svg {{ width: 100%; height: 100%; cursor: grab; }}
        .star {{
            transition: all 0.2s ease; cursor: pointer;
            filter: drop-shadow(0 0 4px rgba(255,255,255,0.3));
        }}
        .star.dim {{ opacity: 0.15; pointer-events: none; }}
        .star:hover {{ r: 16; stroke: white; stroke-width: 2px; filter: drop-shadow(0 0 12px rgba(255,255,255,0.8)); }}
        .star.selected {{ stroke: #5b7bff; stroke-width: 3px; r: 16; filter: drop-shadow(0 0 15px rgba(91, 123, 255, 0.8)); }}
        .star.player-home {{
            stroke: #4dff88;
            stroke-width: 3px;
            filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8));
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0% {{
                filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8));
            }}
            50% {{
                filter: drop-shadow(0 0 25px rgba(77, 255, 136, 1));
            }}
            100% {{
                filter: drop-shadow(0 0 15px rgba(77, 255, 136, 0.8));
            }}
        }}

        .route {{ stroke: #5b7bff; stroke-opacity: 0.2; stroke-width: 1.5; pointer-events: none; }}
        
        #tooltip {{
            position: absolute; pointer-events: none; background: rgba(0,0,0,0.8);
            padding: 4px 8px; border-radius: 4px; font-size: 11px; color: #fff;
            display: none; border: 1px solid #444; z-index: 100;
        }}
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
            const playerHomeSystemIds = new Set({player_home_system_ids_json});
            
            const starsLayer = document.getElementById("stars-layer");
            const routesLayer = document.getElementById("routes-layer");
            const tooltip = document.getElementById("tooltip");

            // Dibujar Rutas
            routes.forEach(r => {{
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", r.ax); line.setAttribute("y1", r.ay);
                line.setAttribute("x2", r.bx); line.setAttribute("y2", r.by);
                line.setAttribute("class", "route");
                routesLayer.appendChild(line);
            }});

            // Dibujar Estrellas
            systems.forEach(sys => {{
                const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                c.setAttribute("cx", sys.x); c.setAttribute("cy", sys.y);
                c.setAttribute("r", sys.radius);
                c.setAttribute("fill", sys.color);
                c.setAttribute("class", "star");
                
                if (!filteredIds.has(sys.id)) c.classList.add("dim");
                if (highlightIds.has(sys.id)) c.classList.add("selected");
                if (playerHomeSystemIds.has(sys.id)) c.classList.add("player-home");
                
                // Hover simple
                c.addEventListener("mouseenter", () => {{
                    tooltip.style.display = "block";
                    tooltip.textContent = sys.name;
                }});
                c.addEventListener("mousemove", (e) => {{
                    tooltip.style.left = (e.pageX + 10) + "px";
                    tooltip.style.top = (e.pageY - 20) + "px";
                }});
                c.addEventListener("mouseleave", () => tooltip.style.display = "none");
                
                // CLICK: Navegación simple y robusta
                c.addEventListener("click", () => {{
                    console.log("Click en sistema:", sys.id);
                    // Forzar recarga de la ventana PADRE con el parámetro
                    const targetWin = window.parent || window.top || window;
                    const url = new URL(targetWin.location.href);
                    url.searchParams.set("preview_id", sys.id);
                    targetWin.location.href = url.toString();
                }});
                
                starsLayer.appendChild(c);
            }});

            // Pan y Zoom
            const pz = svgPanZoom("#galaxy-map", {{
                zoomEnabled: true, controlIconsEnabled: false, fit: true, center: true, minZoom: 0.5, maxZoom: 10
            }});
            document.getElementById("reset").onclick = () => {{ pz.resetZoom(); pz.resetPan(); }};
            document.getElementById("zin").onclick = () => pz.zoomIn();
            document.getElementById("zout").onclick = () => pz.zoomOut();
        </script>
    </body>
    </html>
    """

    with col_map:
        components.html(html_template, height=860, scrolling=False)


def _render_system_orbits(system: System):
    """Visual del sol y planetas orbitando con click en planeta."""
    player = get_player()
    player_home_planet_id = None
    if player:
        home_base_name = f"Base {player.faccion_nombre}"
        player_planets = get_all_player_planets(player.id)
        for p in player_planets:
            if p['nombre_asentamiento'] == home_base_name:
                player_home_planet_id = p['planet_id']
                break

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
    player_planets_ids_json = json.dumps([player_home_planet_id] if player_home_planet_id else [])
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
    .player-home-planet {{
        stroke: #4dff88 !important;
        stroke-width: 3px !important;
        filter: drop-shadow(0 0 10px rgba(77, 255, 136, 0.9));
        animation: pulse 2s infinite;
    }}
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
      const playerPlanets = new Set({player_planets_ids_json});
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
        orbit.setAttribute("stroke", "rgba(255,255,255,0..08)");
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
        if (playerPlanets.has(p.id)) {{
            planet.classList.add("player-home-planet");
        }}
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