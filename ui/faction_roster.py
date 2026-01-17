# ui/faction_roster.py
"""
Comando de Faccion - Centro de Gestion de Personal.
Fichas tecnicas de personajes con estilo Terminal de Comando Galactico.
"""

import streamlit as st
from typing import Dict, Any, List, Union
from data.character_repository import (
    get_all_characters_by_player_id,
    update_character,
    add_xp_to_character,
    update_character_stats,
    update_character_level
)
from ui.state import get_player
from core.character_engine import (
    calculate_level_progress,
    apply_level_up,
    reroll_character_stats,
    XP_TABLE
)
from .styles import Colors, render_terminal_header, render_status_badge

# --- Constantes de Estado ---
POSIBLES_ESTADOS = ["Disponible", "En Mision", "Descansando", "Herido", "Entrenando"]

# --- Colores para atributos ---
ATTR_COLORS = {
    "fuerza": Colors.ATTR_FUERZA,
    "agilidad": Colors.ATTR_AGILIDAD,
    "intelecto": Colors.ATTR_INTELECTO,
    "tecnica": Colors.ATTR_TECNICA,
    "presencia": Colors.ATTR_PRESENCIA,
    "voluntad": Colors.ATTR_VOLUNTAD
}

# --- Iconos para atributos ---
ATTR_ICONS = {
    "fuerza": "&#128170;",
    "agilidad": "&#127939;",
    "intelecto": "&#129504;",
    "tecnica": "&#128295;",
    "presencia": "&#128081;",
    "voluntad": "&#128293;"
}


def _render_attribute_display(attr_name: str, value: int, max_value: int = 20) -> None:
    """Renderiza un atributo con barra visual estilo terminal."""
    color = ATTR_COLORS.get(attr_name.lower(), Colors.TEXT_SECONDARY)
    icon = ATTR_ICONS.get(attr_name.lower(), "&#9679;")
    percentage = min(100, (value / max_value) * 100)

    st.markdown(f"""
        <div style="
            background: {Colors.BG_DARK};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 8px;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 6px;
            ">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.1em;">{icon}</span>
                    <span style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.7em;
                        letter-spacing: 1px;
                        color: {Colors.TEXT_SECONDARY};
                        text-transform: uppercase;
                    ">{attr_name}</span>
                </div>
                <span style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 1.2em;
                    font-weight: 700;
                    color: {color};
                ">{value}</span>
            </div>
            <div style="
                background: {Colors.BG_PANEL};
                border-radius: 3px;
                height: 6px;
                overflow: hidden;
            ">
                <div style="
                    background: linear-gradient(90deg, {color} 0%, {color}80 100%);
                    width: {percentage}%;
                    height: 100%;
                    box-shadow: 0 0 8px {color}40;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def _render_skill_panel(skills: Dict[str, int]) -> None:
    """Renderiza el panel de habilidades con chips visuales."""
    if not skills:
        st.markdown(f"""
            <div style="
                text-align: center;
                padding: 20px;
                color: {Colors.TEXT_DIM};
                font-family: 'Share Tech Mono', monospace;
            ">SIN HABILIDADES REGISTRADAS</div>
        """, unsafe_allow_html=True)
        return

    sorted_skills = sorted(skills.items(), key=lambda x: -x[1])

    skills_html = ""
    for skill, val in sorted_skills:
        if val >= 8:
            skill_color = Colors.LEGENDARY
            tier = "MAESTRO"
        elif val >= 6:
            skill_color = Colors.EPIC
            tier = "EXPERTO"
        elif val >= 4:
            skill_color = Colors.RARE
            tier = "COMPETENTE"
        else:
            skill_color = Colors.TEXT_SECONDARY
            tier = "BASICO"

        skills_html += f"""
            <div style="
                background: {Colors.BG_DARK};
                border: 1px solid {skill_color}40;
                border-left: 3px solid {skill_color};
                border-radius: 4px;
                padding: 8px 12px;
                margin-bottom: 6px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <div>
                    <div style="
                        font-family: 'Rajdhani', sans-serif;
                        font-size: 0.9em;
                        color: {Colors.TEXT_PRIMARY};
                    ">{skill}</div>
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.55em;
                        color: {skill_color};
                        letter-spacing: 1px;
                    ">{tier}</div>
                </div>
                <span style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 1.3em;
                    font-weight: 700;
                    color: {skill_color};
                ">{val}</span>
            </div>
        """

    st.markdown(f"""
        <div style="max-height: 300px; overflow-y: auto;">
            {skills_html}
        </div>
    """, unsafe_allow_html=True)


def _render_traits_panel(feats: List[str]) -> None:
    """Renderiza el panel de rasgos/feats."""
    if not feats:
        st.markdown(f"""
            <div style="
                text-align: center;
                padding: 20px;
                color: {Colors.TEXT_DIM};
                font-family: 'Share Tech Mono', monospace;
            ">SIN RASGOS ESPECIALES</div>
        """, unsafe_allow_html=True)
        return

    feats_html = ""
    for feat in feats:
        feats_html += f"""
            <div style="
                display: inline-block;
                background: {Colors.EPIC}15;
                border: 1px solid {Colors.EPIC}40;
                border-radius: 4px;
                padding: 6px 12px;
                margin: 4px;
                font-family: 'Rajdhani', sans-serif;
                font-size: 0.85em;
                color: {Colors.EPIC};
            ">&#9733; {feat}</div>
        """

    st.markdown(f"<div>{feats_html}</div>", unsafe_allow_html=True)


def _render_xp_progress(progress: Dict[str, Any]) -> None:
    """Renderiza la barra de progreso de XP estilo terminal."""
    pct = progress["progress_percent"]
    current = progress["xp_progress"]
    needed = progress["xp_next"] - progress["xp_current"]

    if progress["can_level_up"]:
        color = Colors.LEGENDARY
        glow = f"0 0 10px {Colors.LEGENDARY}60"
    else:
        color = Colors.INFO
        glow = "none"

    st.markdown(f"""
        <div style="
            background: {Colors.BG_DARK};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 6px;
            padding: 12px;
            margin: 12px 0;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            ">
                <div>
                    <span style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.6em;
                        color: {Colors.TEXT_DIM};
                        letter-spacing: 1px;
                    ">EXPERIENCIA</span>
                </div>
                <div style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 0.8em;
                    color: {Colors.TEXT_SECONDARY};
                ">
                    <span style="color: {color};">{current}</span> / {needed} XP
                </div>
            </div>

            <div style="
                background: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER_DIM};
                border-radius: 4px;
                height: 10px;
                overflow: hidden;
                box-shadow: {glow};
            ">
                <div style="
                    background: linear-gradient(90deg, {color} 0%, {color}80 100%);
                    width: {pct}%;
                    height: 100%;
                    box-shadow: 0 0 10px {color}60;
                    transition: width 0.5s ease;
                "></div>
            </div>

            <div style="
                display: flex;
                justify-content: space-between;
                margin-top: 6px;
                font-family: 'Share Tech Mono', monospace;
                font-size: 0.7em;
                color: {Colors.TEXT_DIM};
            ">
                <span>Nivel {progress['current_level']}</span>
                <span>Nivel {progress['next_level']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)


@st.dialog("ASCENSO DE RANGO", width="large")
def _show_level_up_dialog(char: Dict[str, Any], player_id: int, progress: Dict[str, Any]):
    """Modal de ascenso de nivel con estilo terminal."""
    stats = char.get('stats_json', {})
    bio = stats.get('bio', {})
    atributos = stats.get('atributos', {})
    nivel_actual = stats.get('nivel', 1)
    nivel_nuevo = progress['next_level']

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.LEGENDARY}10 100%);
            border: 2px solid {Colors.LEGENDARY};
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 0 30px {Colors.LEGENDARY}30;
        ">
            <div style="font-size: 2.5em; margin-bottom: 10px;">&#9650;</div>
            <h2 style="
                font-family: 'Orbitron', sans-serif;
                color: {Colors.LEGENDARY};
                font-size: 1.6em;
                margin: 0;
                text-shadow: 0 0 10px {Colors.LEGENDARY}50;
            ">{char['nombre']}</h2>
            <p style="
                font-family: 'Rajdhani', sans-serif;
                color: {Colors.EPIC};
                margin: 8px 0;
            ">{bio.get('raza', 'N/A')} // {bio.get('clase', 'N/A')}</p>

            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 24px;
                margin-top: 20px;
            ">
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 2.2em;
                    color: {Colors.TEXT_DIM};
                ">Nv.{nivel_actual}</div>
                <div style="
                    font-size: 1.8em;
                    color: {Colors.LEGENDARY};
                ">&#10132;</div>
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 2.2em;
                    color: {Colors.LEGENDARY};
                    text-shadow: 0 0 15px {Colors.LEGENDARY}70;
                ">Nv.{nivel_nuevo}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <div style="
            font-family: 'Orbitron', sans-serif;
            font-size: 0.8em;
            color: {Colors.TEXT_DIM};
            letter-spacing: 2px;
            margin-bottom: 12px;
        ">BONIFICACIONES DEL ASCENSO</div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
            <div style="
                background: {Colors.SUCCESS}15;
                border: 1px solid {Colors.SUCCESS};
                border-radius: 8px;
                padding: 16px;
                text-align: center;
            ">
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.7em;
                    color: {Colors.SUCCESS};
                    letter-spacing: 1px;
                ">PUNTOS DE ATRIBUTO</div>
                <div style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 2em;
                    font-weight: 700;
                    color: {Colors.TEXT_PRIMARY};
                ">+2</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
            <div style="
                background: {Colors.INFO}15;
                border: 1px solid {Colors.INFO};
                border-radius: 8px;
                padding: 16px;
                text-align: center;
            ">
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.7em;
                    color: {Colors.INFO};
                    letter-spacing: 1px;
                ">PUNTOS DE HABILIDAD</div>
                <div style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 2em;
                    font-weight: 700;
                    color: {Colors.TEXT_PRIMARY};
                ">+5</div>
            </div>
        """, unsafe_allow_html=True)

    if nivel_nuevo % 3 == 0:
        st.markdown(f"""
            <div style="
                background: {Colors.EPIC}15;
                border: 1px solid {Colors.EPIC};
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                margin-top: 12px;
            ">
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.8em;
                    color: {Colors.EPIC};
                ">&#9733; NUEVO RASGO DISPONIBLE</span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    with st.expander("VER ATRIBUTOS ACTUALES", expanded=False):
        for attr, value in atributos.items():
            color = ATTR_COLORS.get(attr.lower(), Colors.TEXT_SECONDARY)
            st.markdown(f"""
                <div style="
                    display: flex;
                    justify-content: space-between;
                    padding: 6px 0;
                    border-bottom: 1px solid {Colors.BORDER_DIM}40;
                ">
                    <span style="color: {Colors.TEXT_SECONDARY}; text-transform: uppercase; font-size: 0.85em;">{attr}</span>
                    <span style="color: {color}; font-weight: 600;">{value}</span>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_cancel, col_confirm = st.columns([1, 2])

    with col_cancel:
        if st.button("CANCELAR", use_container_width=True):
            st.rerun()

    with col_confirm:
        if st.button("CONFIRMAR ASCENSO", type="primary", use_container_width=True):
            try:
                new_stats, changes = apply_level_up(char)
                result = update_character_level(char['id'], changes['nivel_nuevo'], new_stats, player_id)
                if result:
                    st.balloons()
                    st.success(f"{char['nombre']} ha ascendido a Nivel {changes['nivel_nuevo']}")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al ascender: {e}")


def render_character_card(char: Union[Dict[str, Any], Any], player_id: int, is_commander: bool = False):
    """
    Renderiza la ficha tecnica completa de un personaje.
    Estilo: Terminal de Comando Galactico.
    """
    if hasattr(char, "model_dump"):
        char = char.model_dump()
    elif hasattr(char, "dict"):
        char = char.dict()

    stats = char.get('stats_json', {})
    bio = stats.get('bio', {})
    atributos = stats.get('atributos', {})
    habilidades = stats.get('habilidades', {})
    feats = stats.get('feats', [])
    nivel = stats.get('nivel', 1)
    xp = stats.get('xp', 0)

    progress = calculate_level_progress(xp, stored_level=nivel)

    if is_commander:
        rank_color = Colors.LEGENDARY
        rank_icon = "&#128081;"
        rank_text = "COMANDANTE"
    else:
        rank_color = Colors.INFO
        rank_icon = "&#127942;"
        rank_text = "OPERATIVO"

    estado = char.get('estado', 'Desconocido')

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.BG_PANEL} 100%);
            border: 1px solid {rank_color}40;
            border-top: 3px solid {rank_color};
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 16px;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
            ">
                <div>
                    <div style="
                        display: flex;
                        align-items: center;
                        gap: 10px;
                        margin-bottom: 8px;
                    ">
                        <span style="font-size: 1.4em;">{rank_icon}</span>
                        <span style="
                            font-family: 'Orbitron', sans-serif;
                            font-size: 1.4em;
                            font-weight: 700;
                            color: {Colors.TEXT_PRIMARY};
                        ">{char['nombre']}</span>
                        {render_status_badge(estado)}
                    </div>

                    <div style="
                        font-family: 'Rajdhani', sans-serif;
                        color: {Colors.TEXT_SECONDARY};
                        font-size: 0.9em;
                    ">
                        <span style="color: {Colors.EPIC};">{bio.get('raza', 'N/A')}</span>
                        <span style="color: {Colors.TEXT_DIM};"> // </span>
                        <span style="color: {Colors.WARNING};">{bio.get('clase', char.get('rango', 'N/A'))}</span>
                    </div>

                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 0.7em;
                        color: {Colors.TEXT_DIM};
                        margin-top: 6px;
                    ">ID: {char['id']} // {rank_text}</div>
                </div>

                <div style="text-align: right;">
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.6em;
                        color: {Colors.TEXT_DIM};
                        letter-spacing: 1px;
                    ">NIVEL</div>
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 2.5em;
                        font-weight: 700;
                        color: {rank_color};
                        line-height: 1;
                        text-shadow: 0 0 20px {rank_color}40;
                    ">{nivel}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    _render_xp_progress(progress)

    if progress["can_level_up"]:
        st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, {Colors.LEGENDARY}20, {Colors.WARNING}20);
                border: 1px solid {Colors.LEGENDARY};
                border-radius: 6px;
                padding: 12px;
                text-align: center;
                margin-bottom: 12px;
            ">
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.9em;
                    color: {Colors.LEGENDARY};
                    letter-spacing: 1px;
                ">&#9889; XP SUFICIENTE PARA ASCENDER</span>
            </div>
        """, unsafe_allow_html=True)

        if st.button(
            "INICIAR ASCENSO",
            key=f"levelup_{char['id']}",
            type="primary",
            use_container_width=True
        ):
            _show_level_up_dialog(char, player_id, progress)

    tab_attrs, tab_skills, tab_traits, tab_manage = st.tabs([
        "ATRIBUTOS",
        "HABILIDADES",
        "RASGOS",
        "GESTIONAR"
    ])

    with tab_attrs:
        col1, col2 = st.columns(2)
        attr_list = list(atributos.items())

        for i, (attr, value) in enumerate(attr_list):
            with col1 if i % 2 == 0 else col2:
                _render_attribute_display(attr, value)

    with tab_skills:
        _render_skill_panel(habilidades)

    with tab_traits:
        _render_traits_panel(feats)

    with tab_manage:
        st.markdown(f"""
            <div style="
                font-family: 'Orbitron', sans-serif;
                font-size: 0.7em;
                color: {Colors.TEXT_DIM};
                letter-spacing: 1px;
                margin-bottom: 12px;
            ">ASIGNACION DE ESTADO</div>
        """, unsafe_allow_html=True)

        current_status_index = POSIBLES_ESTADOS.index(estado) if estado in POSIBLES_ESTADOS else 0

        new_status = st.selectbox(
            "Estado operativo:",
            options=POSIBLES_ESTADOS,
            index=current_status_index,
            key=f"status_{char['id']}",
            label_visibility="collapsed"
        )

        if new_status != estado:
            if st.button("CONFIRMAR CAMBIO", key=f"btn_status_{char['id']}", use_container_width=True):
                try:
                    update_character(char['id'], {'estado': new_status})
                    st.success(f"Estado actualizado a '{new_status}'")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


def _render_debug_panel(char: Dict[str, Any], player_id: int):
    """Panel de debug/Game Master para testing."""
    if hasattr(char, "model_dump"):
        char = char.model_dump()
    elif hasattr(char, "dict"):
        char = char.dict()

    st.markdown(f"""
        <div style="
            background: {Colors.WARNING}10;
            border: 1px solid {Colors.WARNING}40;
            border-radius: 6px;
            padding: 12px;
            margin-top: 8px;
        ">
            <div style="
                font-family: 'Orbitron', sans-serif;
                font-size: 0.7em;
                color: {Colors.WARNING};
                letter-spacing: 1px;
                margin-bottom: 10px;
            ">&#9888; ZONA DE DESARROLLO</div>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("+1000 XP", key=f"debug_xp_{char['id']}", use_container_width=True):
            result = add_xp_to_character(char['id'], 1000, player_id)
            if result:
                st.success("+1000 XP")
                st.rerun()

    with col2:
        if st.button("FORZAR NIVEL", key=f"debug_lvl_{char['id']}", use_container_width=True):
            try:
                stats = char.get("stats_json", {})
                current_xp = stats.get("xp", 0)
                current_level = stats.get("nivel", 1)
                progress = calculate_level_progress(current_xp, stored_level=current_level)

                if progress["can_level_up"]:
                    new_stats, changes = apply_level_up(char)
                    result = update_character_level(char['id'], changes['nivel_nuevo'], new_stats, player_id)
                    if result:
                        st.success(f"Nivel {changes['nivel_nuevo']}")
                        st.rerun()
                else:
                    xp_needed = progress["xp_next"] - current_xp
                    add_xp_to_character(char['id'], xp_needed, player_id)
                    st.info(f"+{xp_needed} XP")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with col3:
        if st.button("REROLL", key=f"debug_reroll_{char['id']}", use_container_width=True):
            try:
                new_stats = reroll_character_stats(char)
                result = update_character_stats(char['id'], new_stats, player_id)
                if result:
                    st.success("Stats regenerados")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with st.expander("TABLA DE EXPERIENCIA"):
        xp_data = [(lvl, xp) for lvl, xp in sorted(XP_TABLE.items())]
        cols = st.columns(4)
        for i, (lvl, xp) in enumerate(xp_data):
            with cols[i % 4]:
                st.markdown(f"""
                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 0.8em;
                        color: {Colors.TEXT_SECONDARY};
                        padding: 4px;
                    ">Nv.{lvl}: {xp:,}</div>
                """, unsafe_allow_html=True)


def show_faction_roster():
    """Pagina principal del Comando de Faccion."""

    render_terminal_header(
        title="COMANDO DE FACCION",
        subtitle="CENTRO DE GESTION DE PERSONAL",
        icon="&#128101;"
    )

    player = get_player()
    if not player:
        st.warning("No se ha podido identificar al jugador. Reinicia sesion.")
        return

    player_id = player.id

    try:
        raw_characters = get_all_characters_by_player_id(player_id)

        characters = []
        if raw_characters:
            for c in raw_characters:
                if hasattr(c, "model_dump"):
                    characters.append(c.model_dump())
                elif hasattr(c, "dict"):
                    characters.append(c.dict())
                else:
                    characters.append(c)

        if not characters:
            st.markdown(f"""
                <div style="
                    text-align: center;
                    padding: 40px;
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.BORDER_DIM};
                    border-radius: 8px;
                ">
                    <div style="font-size: 2em; margin-bottom: 12px;">&#128100;</div>
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        color: {Colors.TEXT_SECONDARY};
                    ">NO HAY PERSONAL EN LA FACCION</div>
                    <div style="
                        font-family: 'Rajdhani', sans-serif;
                        color: {Colors.TEXT_DIM};
                        margin-top: 8px;
                    ">Visita el Centro de Reclutamiento para contratar operativos</div>
                </div>
            """, unsafe_allow_html=True)
            return

        commander = next((c for c in characters if c.get('es_comandante')), None)
        crew = [c for c in characters if not c.get('es_comandante')]

        total_chars = len(characters)
        available = len([c for c in characters if c.get('estado') == 'Disponible'])
        on_mission = len([c for c in characters if c.get('estado') == 'En Mision'])

        st.markdown(f"""
            <div style="
                display: flex;
                gap: 16px;
                margin-bottom: 20px;
            ">
                <div style="
                    flex: 1;
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.BORDER_DIM};
                    border-radius: 6px;
                    padding: 12px;
                    text-align: center;
                ">
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.6em;
                        color: {Colors.TEXT_DIM};
                        letter-spacing: 1px;
                    ">TOTAL</div>
                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 1.8em;
                        color: {Colors.TEXT_PRIMARY};
                    ">{total_chars}</div>
                </div>
                <div style="
                    flex: 1;
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.SUCCESS}40;
                    border-radius: 6px;
                    padding: 12px;
                    text-align: center;
                ">
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.6em;
                        color: {Colors.SUCCESS};
                        letter-spacing: 1px;
                    ">DISPONIBLES</div>
                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 1.8em;
                        color: {Colors.SUCCESS};
                    ">{available}</div>
                </div>
                <div style="
                    flex: 1;
                    background: {Colors.BG_CARD};
                    border: 1px solid {Colors.WARNING}40;
                    border-radius: 6px;
                    padding: 12px;
                    text-align: center;
                ">
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 0.6em;
                        color: {Colors.WARNING};
                        letter-spacing: 1px;
                    ">EN MISION</div>
                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 1.8em;
                        color: {Colors.WARNING};
                    ">{on_mission}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        if commander:
            st.markdown(f"""
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.8em;
                    color: {Colors.LEGENDARY};
                    letter-spacing: 2px;
                    margin: 20px 0 12px 0;
                ">&#128081; COMANDANTE EN JEFE</div>
            """, unsafe_allow_html=True)

            with st.container(border=True):
                render_character_card(commander, player_id, is_commander=True)
                with st.expander("HERRAMIENTAS DE DESARROLLO"):
                    _render_debug_panel(commander, player_id)

        if crew:
            st.markdown(f"""
                <div style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.8em;
                    color: {Colors.INFO};
                    letter-spacing: 2px;
                    margin: 24px 0 12px 0;
                ">&#127942; OPERATIVOS ({len(crew)})</div>
            """, unsafe_allow_html=True)

            for char in sorted(crew, key=lambda x: -(x.get('stats_json', {}).get('nivel', 0))):
                with st.container(border=True):
                    render_character_card(char, player_id, is_commander=False)
                    with st.expander("HERRAMIENTAS DE DESARROLLO"):
                        _render_debug_panel(char, player_id)

    except Exception as e:
        st.error(f"Error al cargar la lista de personajes: {e}")
        st.exception(e)
