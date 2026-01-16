# ui/ship_status_page.py
import json
import streamlit as st
import streamlit.components.v1 as components


def show_ship_status_page():
    """Pagina de estado de la nave (mock generico)."""
    ship, subsystems = _get_mock_ship_status()

    if "ship_focus" not in st.session_state:
        st.session_state.ship_focus = subsystems[0]["id"]

    _render_ship_styles()

    st.title("Estado de la Nave")
    st.caption("Panel de estado generico. Datos simulados por ahora.")
    st.markdown("---")

    st.markdown(_render_ship_header(ship), unsafe_allow_html=True)
    st.markdown(_render_summary_cards(ship, subsystems), unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2], gap="large")
    with col_left:
        selection = _render_ship_diagram(subsystems, st.session_state.ship_focus)
        new_id = _parse_component_selection(selection, subsystems)
        if new_id and new_id != st.session_state.ship_focus:
            st.session_state.ship_focus = new_id
            st.rerun()

    with col_right:
        _render_subsystem_selector(subsystems)
        focused = _get_subsystem(subsystems, st.session_state.ship_focus) or subsystems[0]
        st.markdown(_render_subsystem_detail(focused), unsafe_allow_html=True)
        st.markdown(_render_subsystem_list(subsystems, focused["id"]), unsafe_allow_html=True)
        _render_quick_actions(focused)


def _get_mock_ship_status():
    ship = {
        "name": "Asteria NX-7",
        "class": "Fragata de Exploracion",
        "registry": "NX-07",
        "status": "Operativa",
        "location": "Sector Iota-9",
        "mission": "Cartografiado y enlace",
        "crew": 48,
        "crew_max": 60,
        "hull": 86,
        "shields": 62,
        "power": 74,
        "fuel": 57,
        "heat": 38,
    }

    subsystems = [
        {
            "id": "sensors",
            "name": "Sensores",
            "health": 40,
            "power": 11,
            "temp": 52,
            "role": "Barrido y deteccion",
            "notes": "Calibracion pendiente. Interferencias en rango medio.",
            "label": "SEN",
            "x": 270,
            "y": 26,
            "w": 180,
            "h": 26,
        },
        {
            "id": "bridge",
            "name": "Puente",
            "health": 92,
            "power": 9,
            "temp": 33,
            "role": "Comando tactico",
            "notes": "Enlace de mando estable. Tripulacion completa.",
            "label": "PNT",
            "x": 295,
            "y": 60,
            "w": 130,
            "h": 40,
        },
        {
            "id": "shields",
            "name": "Escudos",
            "health": 62,
            "power": 21,
            "temp": 44,
            "role": "Defensa primaria",
            "notes": "Capacitadores al 62%. Recomendada redistribucion.",
            "label": "ESC",
            "x": 260,
            "y": 112,
            "w": 200,
            "h": 42,
        },
        {
            "id": "port_thrusters",
            "name": "Propulsores Babor",
            "health": 71,
            "power": 13,
            "temp": 41,
            "role": "Maniobra lateral",
            "notes": "Respuesta nominal. Ajuste fino disponible.",
            "label": "BAB",
            "x": 110,
            "y": 170,
            "w": 90,
            "h": 70,
        },
        {
            "id": "reactor",
            "name": "Reactor",
            "health": 58,
            "power": 32,
            "temp": 65,
            "role": "Energia principal",
            "notes": "Flujo estable pero con perdida de eficiencia.",
            "label": "RCT",
            "x": 315,
            "y": 170,
            "w": 90,
            "h": 70,
        },
        {
            "id": "starboard_thrusters",
            "name": "Propulsores Estribor",
            "health": 76,
            "power": 13,
            "temp": 39,
            "role": "Maniobra lateral",
            "notes": "Torque equilibrado. Sin fallas.",
            "label": "EST",
            "x": 520,
            "y": 170,
            "w": 90,
            "h": 70,
        },
        {
            "id": "weapons",
            "name": "Armas",
            "health": 82,
            "power": 18,
            "temp": 46,
            "role": "Defensa y disuasion",
            "notes": "Baterias alineadas. Municion al 78%.",
            "label": "ARM",
            "x": 260,
            "y": 252,
            "w": 200,
            "h": 38,
        },
        {
            "id": "engines",
            "name": "Motores",
            "health": 78,
            "power": 27,
            "temp": 58,
            "role": "Propulsion principal",
            "notes": "Impulso estable. Ciclo de mantenimiento en 12h.",
            "label": "MTR",
            "x": 280,
            "y": 300,
            "w": 160,
            "h": 60,
        },
        {
            "id": "life_support",
            "name": "Soporte Vital",
            "health": 88,
            "power": 10,
            "temp": 28,
            "role": "Oxigeno y clima",
            "notes": "Filtros limpios. Reservas al 94%.",
            "label": "VTL",
            "x": 250,
            "y": 370,
            "w": 220,
            "h": 34,
        },
    ]

    return ship, subsystems


def _render_ship_styles():
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Chakra+Petch:wght@500;600&display=swap");

        .ship-hero {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            padding: 18px 22px;
            border-radius: 18px;
            background: linear-gradient(120deg, #0f1b2a, #182f45);
            border: 1px solid #24364d;
            box-shadow: 0 18px 35px rgba(0, 0, 0, 0.25);
            color: #e7f0ff;
            font-family: "Space Grotesk", sans-serif;
        }
        .ship-hero-title {
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 0.4px;
            margin-bottom: 4px;
        }
        .ship-hero-tag {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(53, 203, 179, 0.2);
            border: 1px solid rgba(53, 203, 179, 0.45);
            color: #b9f5e6;
            font-size: 12px;
            font-family: "Chakra Petch", sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .ship-hero-meta {
            color: #b6c6dc;
            font-size: 13px;
            margin-top: 6px;
        }
        .ship-hero-right {
            text-align: right;
            font-size: 13px;
            color: #cfe0ff;
        }
        .ship-hero-right span {
            display: block;
            color: #9fb3cd;
        }
        .ship-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 14px;
            margin: 18px 0 22px 0;
            font-family: "Space Grotesk", sans-serif;
        }
        .ship-card {
            padding: 14px 16px;
            border-radius: 14px;
            background: radial-gradient(circle at top, #1b2a3d, #0d1622);
            border: 1px solid #223248;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
            animation: fadeUp 0.6s ease both;
        }
        .ship-card:nth-child(2) { animation-delay: 0.05s; }
        .ship-card:nth-child(3) { animation-delay: 0.1s; }
        .ship-card:nth-child(4) { animation-delay: 0.15s; }
        .ship-card:nth-child(5) { animation-delay: 0.2s; }
        .ship-card:nth-child(6) { animation-delay: 0.25s; }
        .ship-card-label {
            font-size: 12px;
            color: #9fb3cd;
            text-transform: uppercase;
            letter-spacing: 1.1px;
            margin-bottom: 8px;
        }
        .ship-card-value {
            font-size: 22px;
            font-weight: 700;
            color: #f4f7ff;
        }
        .ship-card-note {
            font-size: 12px;
            color: #9fb3cd;
            margin-top: 6px;
        }
        .ship-detail {
            padding: 16px;
            border-radius: 16px;
            background: linear-gradient(140deg, #121c2a, #0b121b);
            border: 1px solid #1f2e44;
            font-family: "Space Grotesk", sans-serif;
            margin-bottom: 16px;
        }
        .ship-detail-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .ship-detail-title {
            font-size: 18px;
            font-weight: 700;
            color: #e7f0ff;
        }
        .ship-badge {
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-family: "Chakra Petch", sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .badge-ok { background: rgba(86, 213, 159, 0.2); color: #b7f5d7; border: 1px solid rgba(86, 213, 159, 0.5); }
        .badge-warn { background: rgba(246, 196, 91, 0.2); color: #ffe0a0; border: 1px solid rgba(246, 196, 91, 0.6); }
        .badge-crit { background: rgba(240, 100, 100, 0.2); color: #ffc0c0; border: 1px solid rgba(240, 100, 100, 0.6); }

        .ship-detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .ship-detail-item {
            background: rgba(11, 17, 26, 0.8);
            border: 1px solid #20304a;
            border-radius: 10px;
            padding: 10px;
            color: #d9e6ff;
            font-size: 12px;
        }
        .ship-detail-item span {
            display: block;
            color: #8fa5c4;
            font-size: 11px;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .ship-bar {
            height: 6px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.08);
            margin-top: 6px;
            overflow: hidden;
        }
        .ship-bar-fill {
            height: 100%;
            border-radius: 999px;
        }
        .ship-notes {
            margin-top: 12px;
            font-size: 12px;
            color: #9fb3cd;
        }
        .ship-list {
            padding: 16px;
            border-radius: 16px;
            border: 1px solid #1f2e44;
            background: #0b121b;
            font-family: "Space Grotesk", sans-serif;
        }
        .ship-list-title {
            font-size: 14px;
            color: #cfe0ff;
            margin-bottom: 10px;
        }
        .ship-list-row {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 10px;
            padding: 8px 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 12px;
        }
        .ship-list-row:last-child { border-bottom: none; }
        .ship-list-row.active {
            background: rgba(84, 150, 214, 0.12);
        }
        .ship-list-name {
            font-size: 13px;
            color: #e7f0ff;
        }
        .ship-list-pill {
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 999px;
            font-family: "Chakra Petch", sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_ship_header(ship):
    return f"""
    <div class="ship-hero">
        <div>
            <div class="ship-hero-tag">{ship['status']}</div>
            <div class="ship-hero-title">{ship['name']}</div>
            <div class="ship-hero-meta">
                Clase: {ship['class']} | Registro: {ship['registry']}<br />
                Mision: {ship['mission']}
            </div>
        </div>
        <div class="ship-hero-right">
            Ubicacion actual
            <span>{ship['location']}</span>
            Tripulacion
            <span>{ship['crew']}/{ship['crew_max']}</span>
        </div>
    </div>
    """


def _render_summary_cards(ship, subsystems):
    readiness = round(sum(s["health"] for s in subsystems) / len(subsystems))
    cards = [
        ("Integridad casco", f"{ship['hull']}%", "Estructura principal"),
        ("Escudos", f"{ship['shields']}%", "Capacitadores activos"),
        ("Energia", f"{ship['power']}%", "Reactor y baterias"),
        ("Combustible", f"{ship['fuel']}%", "Reserva actual"),
        ("Temperatura", f"{ship['heat']}C", "Nucleo estable"),
        ("Estado general", f"{readiness}%", "Promedio de subsistemas"),
    ]
    html_cards = "\n".join(
        f"""
        <div class="ship-card">
            <div class="ship-card-label">{label}</div>
            <div class="ship-card-value">{value}</div>
            <div class="ship-card-note">{note}</div>
        </div>
        """
        for label, value, note in cards
    )
    return f'<div class="ship-card-grid">{html_cards}</div>'


def _render_subsystem_selector(subsystems):
    options = {f"{s['name']} ({s['health']}%)": s["id"] for s in subsystems}
    label_for_id = {v: k for k, v in options.items()}
    current_label = label_for_id.get(st.session_state.ship_focus, list(options.keys())[0])

    if "ship_focus_select" not in st.session_state:
        st.session_state.ship_focus_select = current_label
    elif options.get(st.session_state.ship_focus_select) != st.session_state.ship_focus:
        st.session_state.ship_focus_select = current_label

    selection = st.selectbox("Sistema seleccionado", list(options.keys()), key="ship_focus_select")
    new_id = options.get(selection)
    if new_id and new_id != st.session_state.ship_focus:
        st.session_state.ship_focus = new_id


def _render_subsystem_detail(subsystem):
    status_label, status_class = _status_from_health(subsystem["health"])
    health_color = _health_color(subsystem["health"])
    power_color = _health_color(100 - max(0, subsystem["power"]))
    temp_color = _health_color(100 - max(0, subsystem["temp"]))

    return f"""
    <div class="ship-detail">
        <div class="ship-detail-header">
            <div class="ship-detail-title">{subsystem['name']}</div>
            <div class="ship-badge {status_class}">{status_label}</div>
        </div>
        <div class="ship-detail-grid">
            <div class="ship-detail-item">
                <span>Integridad</span>
                {subsystem['health']}%
                <div class="ship-bar"><div class="ship-bar-fill" style="width:{subsystem['health']}%; background:{health_color};"></div></div>
            </div>
            <div class="ship-detail-item">
                <span>Consumo energia</span>
                {subsystem['power']}%
                <div class="ship-bar"><div class="ship-bar-fill" style="width:{subsystem['power']}%; background:{power_color};"></div></div>
            </div>
            <div class="ship-detail-item">
                <span>Temperatura</span>
                {subsystem['temp']}C
                <div class="ship-bar"><div class="ship-bar-fill" style="width:{min(subsystem['temp'], 100)}%; background:{temp_color};"></div></div>
            </div>
            <div class="ship-detail-item">
                <span>Rol operativo</span>
                {subsystem['role']}
            </div>
        </div>
        <div class="ship-notes">{subsystem['notes']}</div>
    </div>
    """


def _render_subsystem_list(subsystems, active_id):
    rows = []
    for system in subsystems:
        status_label, status_class = _status_from_health(system["health"])
        active_class = " active" if system["id"] == active_id else ""
        row = f"""
        <div class="ship-list-row{active_class}">
            <div>
                <div class="ship-list-name">{system['name']}</div>
                <div class="ship-bar"><div class="ship-bar-fill" style="width:{system['health']}%; background:{_health_color(system['health'])};"></div></div>
            </div>
            <div class="ship-list-pill {status_class}">{status_label}</div>
        </div>
        """
        rows.append(row)

    return f"""
    <div class="ship-list">
        <div class="ship-list-title">Estado de subsistemas</div>
        {''.join(rows)}
    </div>
    """


def _render_quick_actions(focused):
    st.subheader("Acciones rapidas")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Iniciar diagnostico", use_container_width=True):
            st.info(f"Diagnostico simulado para {focused['name']}.")
    with col_b:
        if st.button("Redistribuir energia", use_container_width=True):
            st.info("Redistribucion simulada entre subsistemas.")
    if st.button("Solicitar reparacion", use_container_width=True):
        st.info("Peticion de reparacion registrada (simulada).")


def _render_ship_diagram(subsystems, active_id):
    parts = []
    for system in subsystems:
        _, status_class = _status_from_health(system["health"])
        parts.append(
            {
                "id": system["id"],
                "name": system["name"],
                "health": system["health"],
                "label": system["label"],
                "x": system["x"],
                "y": system["y"],
                "w": system["w"],
                "h": system["h"],
                "state": status_class.replace("badge-", ""),
                "color": _health_color(system["health"]),
            }
        )

    parts_json = json.dumps(parts)
    active_json = json.dumps(active_id or "")

    html = f"""
    <style>
        @import url("https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=Chakra+Petch:wght@500;600&display=swap");
        .ship-diagram {{
            width: 100%;
            height: 520px;
            border-radius: 18px;
            background: radial-gradient(circle at top, #15253a, #0a111b 70%);
            border: 1px solid #223248;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
            font-family: "Space Grotesk", sans-serif;
        }}
        .ship-diagram::after {{
            content: "";
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(120deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 24px);
            opacity: 0.2;
            pointer-events: none;
        }}
        svg {{
            width: 100%;
            height: 100%;
        }}
        .ship-hull {{
            fill: url(#hullGradient);
            stroke: #2a3a52;
            stroke-width: 2;
        }}
        .ship-wing {{
            fill: #111d2c;
            stroke: #2a3a52;
            stroke-width: 1.5;
        }}
        .ship-node {{
            cursor: pointer;
            transition: transform 0.2s ease, filter 0.2s ease, opacity 0.2s ease;
        }}
        .ship-node:hover {{
            filter: drop-shadow(0 0 10px rgba(139, 200, 255, 0.6));
            transform: translateY(-1px);
        }}
        .ship-node.ok {{
            filter: drop-shadow(0 0 8px rgba(86, 213, 159, 0.35));
        }}
        .ship-node.warn {{
            filter: drop-shadow(0 0 8px rgba(246, 196, 91, 0.35));
        }}
        .ship-node.crit {{
            animation: pulseCrit 1.4s ease-in-out infinite;
            filter: drop-shadow(0 0 10px rgba(240, 100, 100, 0.6));
        }}
        .ship-node.selected {{
            stroke: #9fd1ff;
            stroke-width: 2.5;
        }}
        .ship-label {{
            fill: #d8e6ff;
            font-size: 12px;
            text-anchor: middle;
            font-family: "Chakra Petch", sans-serif;
            pointer-events: none;
        }}
        .ship-tooltip {{
            position: absolute;
            padding: 8px 10px;
            border-radius: 10px;
            background: rgba(10, 15, 25, 0.96);
            border: 1px solid #25344b;
            color: #e7f0ff;
            font-size: 12px;
            display: none;
            pointer-events: none;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.35);
            max-width: 220px;
        }}
        @keyframes pulseCrit {{
            0% {{ opacity: 0.7; }}
            50% {{ opacity: 1; }}
            100% {{ opacity: 0.7; }}
        }}
    </style>
    <div class="ship-diagram" id="ship-diagram">
        <svg id="ship-svg" viewBox="0 0 720 420" preserveAspectRatio="xMidYMid meet">
            <defs>
                <linearGradient id="hullGradient" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stop-color="#19283a" />
                    <stop offset="100%" stop-color="#0c1522" />
                </linearGradient>
            </defs>
            <rect class="ship-hull" x="210" y="30" width="300" height="360" rx="40" ry="40"></rect>
            <rect class="ship-wing" x="110" y="160" width="90" height="100" rx="16" ry="16"></rect>
            <rect class="ship-wing" x="520" y="160" width="90" height="100" rx="16" ry="16"></rect>
            <g id="ship-parts"></g>
            <g id="ship-labels"></g>
        </svg>
        <div id="ship-tooltip" class="ship-tooltip"></div>
    </div>
    <script>
        const parts = {parts_json};
        const activeId = {active_json};
        const partsLayer = document.getElementById("ship-parts");
        const labelsLayer = document.getElementById("ship-labels");
        const tooltip = document.getElementById("ship-tooltip");
        const frame = document.getElementById("ship-diagram");

        function showTooltip(evt, part) {{
            const rect = frame.getBoundingClientRect();
            tooltip.style.display = "block";
            tooltip.style.left = (evt.clientX - rect.left + 12) + "px";
            tooltip.style.top = (evt.clientY - rect.top + 12) + "px";
            tooltip.innerHTML = `<strong>${{part.name}}</strong><br/>Integridad: ${{part.health}}%`;
        }}

        function hideTooltip() {{
            tooltip.style.display = "none";
        }}

        function emitSelection(id) {{
            if (window.parent && window.parent.Streamlit && window.parent.Streamlit.setComponentValue) {{
                window.parent.Streamlit.setComponentValue("subsystem:" + id);
            }} else if (window.parent && window.parent.postMessage) {{
                window.parent.postMessage({{ type: "streamlit:setComponentValue", value: "subsystem:" + id }}, "*");
                window.parent.postMessage({{ type: "streamlit:componentValue", value: "subsystem:" + id }}, "*");
            }}
        }}

        parts.forEach(part => {{
            const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
            rect.setAttribute("x", part.x);
            rect.setAttribute("y", part.y);
            rect.setAttribute("width", part.w);
            rect.setAttribute("height", part.h);
            rect.setAttribute("rx", 10);
            rect.setAttribute("ry", 10);
            rect.setAttribute("fill", part.color);
            rect.setAttribute("class", "ship-node " + part.state + (part.id === activeId ? " selected" : ""));
            rect.addEventListener("mousemove", evt => showTooltip(evt, part));
            rect.addEventListener("mouseleave", hideTooltip);
            rect.addEventListener("click", evt => {{
                evt.preventDefault();
                evt.stopPropagation();
                emitSelection(part.id);
            }});
            partsLayer.appendChild(rect);

            const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
            label.setAttribute("x", part.x + part.w / 2);
            label.setAttribute("y", part.y + part.h / 2 + 4);
            label.setAttribute("class", "ship-label");
            label.textContent = part.label;
            labelsLayer.appendChild(label);
        }});
    </script>
    """
    return components.html(html, height=540)


def _status_from_health(health):
    if health >= 80:
        return "Nominal", "badge-ok"
    if health >= 55:
        return "Alerta", "badge-warn"
    return "Critico", "badge-crit"


def _health_color(health):
    if health >= 80:
        return "#56d59f"
    if health >= 55:
        return "#f6c45b"
    return "#f06464"


def _get_subsystem(subsystems, subsystem_id):
    return next((s for s in subsystems if s["id"] == subsystem_id), None)


def _parse_component_selection(selection, subsystems):
    if not selection or not isinstance(selection, str):
        return None
    if not selection.startswith("subsystem:"):
        return None
    subsystem_id = selection.split("subsystem:", 1)[1]
    if any(s["id"] == subsystem_id for s in subsystems):
        return subsystem_id
    return None
