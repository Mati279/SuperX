# ui/faction_roster.py
"""
Comando de Faccion - Centro de gestion de personajes.
Muestra tarjetas visuales con atributos, habilidades y sistema de level up.
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

# --- Constantes de Estado ---
POSIBLES_ESTADOS = ["Disponible", "En Mision", "Descansando", "Herido", "Entrenando"]

# --- Colores para atributos ---
ATTR_COLORS = {
    "fuerza": "#ff6b6b",
    "agilidad": "#4ecdc4",
    "intelecto": "#45b7d1",
    "tecnica": "#f9ca24",
    "presencia": "#a55eea",
    "voluntad": "#26de81"
}


def _render_attribute_bar(attr_name: str, value: int, max_value: int = 20) -> None:
    """Renderiza una barra de atributo visual."""
    color = ATTR_COLORS.get(attr_name.lower(), "#888")
    percentage = min(100, (value / max_value) * 100)

    st.markdown(f"""
        <div style="margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
                <span style="font-size: 0.85em; color: #ccc;">{attr_name.upper()}</span>
                <span style="font-size: 0.85em; font-weight: bold; color: {color};">{value}</span>
            </div>
            <div style="background: #1a1a2e; border-radius: 4px; height: 8px; overflow: hidden;">
                <div style="background: {color}; width: {percentage}%; height: 100%; border-radius: 4px;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def _render_skill_chip(skill_name: str, value: int) -> str:
    """Genera HTML para un chip de habilidad."""
    # Determinar color basado en el valor
    if value >= 30:
        color = "#ffd700"  # Dorado - Maestro
        border = "#ffd700"
    elif value >= 20:
        color = "#45b7d1"  # Azul - Experto
        border = "#45b7d1"
    else:
        color = "#888"  # Gris - Normal
        border = "#444"

    return f"""
        <span style="
            display: inline-block;
            padding: 4px 10px;
            margin: 2px 4px 2px 0;
            background: rgba(0,0,0,0.3);
            border: 1px solid {border};
            border-radius: 12px;
            font-size: 0.75em;
            color: {color};
        ">{skill_name}: <b>{value}</b></span>
    """


def _render_xp_progress_bar(progress: Dict[str, Any]) -> None:
    """Renderiza la barra de progreso de XP."""
    pct = progress["progress_percent"]
    current = progress["xp_progress"]
    needed = progress["xp_next"] - progress["xp_current"]

    color = "#26de81" if progress["can_level_up"] else "#45b7d1"

    st.markdown(f"""
        <div style="margin: 10px 0;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #888;">
                <span>XP: {current} / {needed}</span>
                <span>Nivel {progress['current_level']} → {progress['next_level']}</span>
            </div>
            <div style="background: #1a1a2e; border-radius: 6px; height: 12px; overflow: hidden; margin-top: 4px;">
                <div style="background: linear-gradient(90deg, {color}, {color}aa); width: {pct}%; height: 100%; border-radius: 6px; transition: width 0.3s;"></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


@st.dialog("⬆️ ASCENSO DE RANGO", width="large")
def _show_level_up_dialog(char: Dict[str, Any], player_id: int, progress: Dict[str, Any]):
    """Popup modal para el ascenso de nivel."""
    stats = char.get('stats_json', {})
    bio = stats.get('bio', {})
    atributos = stats.get('atributos', {})
    nivel_actual = stats.get('nivel', 1)
    nivel_nuevo = progress['next_level']

    # Header con animación visual
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #2d1f4e 50%, #1a1a2e 100%);
            border: 2px solid #ffd700;
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.3);
        ">
            <div style="font-size: 3em; margin-bottom: 10px;">⬆️</div>
            <h2 style="
                color: #ffd700;
                font-size: 1.8em;
                margin: 0;
                text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
            ">{char['nombre']}</h2>
            <p style="color: #a55eea; margin: 8px 0;">
                {bio.get('raza', 'N/A')} • {bio.get('clase', 'N/A')}
            </p>
            <div style="
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 20px;
                margin-top: 16px;
            ">
                <span style="
                    font-size: 2.5em;
                    color: #888;
                ">Nv. {nivel_actual}</span>
                <span style="
                    font-size: 2em;
                    color: #ffd700;
                    animation: pulse 1s infinite;
                ">➡️</span>
                <span style="
                    font-size: 2.5em;
                    color: #ffd700;
                    font-weight: bold;
                    text-shadow: 0 0 15px rgba(255, 215, 0, 0.7);
                ">Nv. {nivel_nuevo}</span>
            </div>
        </div>
        <style>
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; transform: scale(1); }}
                50% {{ opacity: 0.7; transform: scale(1.1); }}
            }}
        </style>
    """, unsafe_allow_html=True)

    # Bonificaciones esperadas
    st.markdown("### 🎁 Bonificaciones del Ascenso")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
            <div style="
                background: rgba(38, 222, 129, 0.1);
                border: 1px solid #26de81;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
            ">
                <div style="color: #26de81; font-size: 0.85em;">PUNTOS DE ATRIBUTO</div>
                <div style="color: #fff; font-size: 1.5em; font-weight: bold;">+2</div>
            </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
            <div style="
                background: rgba(69, 183, 209, 0.1);
                border: 1px solid #45b7d1;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
            ">
                <div style="color: #45b7d1; font-size: 0.85em;">PUNTOS DE HABILIDAD</div>
                <div style="color: #fff; font-size: 1.5em; font-weight: bold;">+5</div>
            </div>
        """, unsafe_allow_html=True)

    # Posible nuevo rasgo
    if nivel_nuevo % 3 == 0:
        st.markdown("""
            <div style="
                background: rgba(165, 94, 234, 0.1);
                border: 1px solid #a55eea;
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                margin-top: 12px;
            ">
                <div style="color: #a55eea; font-size: 0.85em;">🌟 NUEVO RASGO DISPONIBLE</div>
                <div style="color: #fff; font-size: 1em;">¡Nivel múltiplo de 3!</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Atributos actuales
    with st.expander("📊 Atributos Actuales", expanded=False):
        attr_colors = {
            "fuerza": "#ff6b6b", "agilidad": "#4ecdc4", "intelecto": "#45b7d1",
            "tecnica": "#f9ca24", "presencia": "#a55eea", "voluntad": "#26de81"
        }
        for attr, value in atributos.items():
            color = attr_colors.get(attr.lower(), "#888")
            st.markdown(f"<span style='color:{color};'>{attr.upper()}: **{value}**</span>", unsafe_allow_html=True)

    st.markdown("")

    # Botones de acción
    col_cancel, col_confirm = st.columns([1, 2])

    with col_cancel:
        if st.button("Cancelar", width='stretch'):
            st.rerun()

    with col_confirm:
        if st.button("⬆️ CONFIRMAR ASCENSO", type="primary", width='stretch'):
            try:
                new_stats, changes = apply_level_up(char)
                result = update_character_level(char['id'], changes['nivel_nuevo'], new_stats, player_id)
                if result:
                    st.balloons()
                    st.success(f"🎉 ¡{char['nombre']} ha ascendido a Nivel {changes['nivel_nuevo']}!")
                    for bonus in changes['bonificaciones']:
                        st.info(f"✨ {bonus}")
                    st.rerun()
            except Exception as e:
                st.error(f"Error al ascender: {e}")


def render_character_card(char: Union[Dict[str, Any], Any], player_id: int, is_commander: bool = False):
    """Muestra la tarjeta completa de un personaje con todos sus stats."""

    # FIX: Convertir Pydantic models a dict si es necesario
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

    # Calcular progreso de nivel (pasando el nivel almacenado para detectar ascensos pendientes)
    progress = calculate_level_progress(xp, stored_level=nivel)

    # Header de la tarjeta
    rank_icon = "👑" if is_commander else "🎖️"
    status_color = "#26de81" if char.get('estado') == "Disponible" else "#f9ca24"

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid #333;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <span style="font-size: 1.4em; font-weight: bold; color: #fff;">{rank_icon} {char['nombre']}</span>
                    <span style="
                        margin-left: 10px;
                        padding: 2px 8px;
                        background: {status_color}22;
                        border: 1px solid {status_color};
                        border-radius: 10px;
                        font-size: 0.75em;
                        color: {status_color};
                    ">{char.get('estado', 'N/A')}</span>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 1.8em; font-weight: bold; color: #45b7d1;">Nv. {nivel}</span>
                </div>
            </div>
            <div style="color: #888; font-size: 0.85em; margin-bottom: 8px;">
                <span style="color: #a55eea;">{bio.get('raza', 'N/A')}</span> |
                <span style="color: #f9ca24;">{bio.get('clase', char.get('rango', 'N/A'))}</span> |
                <span>ID: {char['id']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Barra de XP
    _render_xp_progress_bar(progress)

    # Boton de ASCENDER si puede subir de nivel
    if progress["can_level_up"]:
        col_msg, col_btn = st.columns([3, 1])

        with col_msg:
            st.markdown("""
                <div style="
                    background: linear-gradient(90deg, #ffd700, #ff6b6b);
                    padding: 2px;
                    border-radius: 8px;
                    margin: 10px 0;
                ">
                    <div style="
                        background: #1a1a2e;
                        padding: 8px;
                        border-radius: 6px;
                        text-align: center;
                        color: #ffd700;
                        font-weight: bold;
                    ">
                        ⚡ XP SUFICIENTE PARA ASCENDER
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col_btn:
            # Botón con flecha amarilla hacia arriba
            st.markdown("""
                <style>
                    div[data-testid="stButton"] button[kind="primary"] {
                        background: linear-gradient(135deg, #ffd700 0%, #ffaa00 100%);
                        color: #1a1a2e;
                        font-weight: bold;
                        border: none;
                        font-size: 1.5em;
                    }
                </style>
            """, unsafe_allow_html=True)

            if st.button("⬆️", key=f"levelup_{char['id']}", type="primary", help=f"Ascender a Nivel {progress['next_level']}"):
                _show_level_up_dialog(char, player_id, progress)

    # Tabs para organizar la informacion
    tab_attrs, tab_skills, tab_manage = st.tabs(["Atributos", "Habilidades", "Gestionar"])

    with tab_attrs:
        cols = st.columns(2)
        attr_list = list(atributos.items())
        for i, (attr, value) in enumerate(attr_list):
            with cols[i % 2]:
                _render_attribute_bar(attr, value)

        # Feats/Rasgos
        if feats:
            st.markdown("**Rasgos:**")
            feats_html = " ".join([f'<span style="background: #333; padding: 4px 8px; border-radius: 8px; font-size: 0.8em; margin-right: 4px;">{f}</span>' for f in feats])
            st.markdown(feats_html, unsafe_allow_html=True)

    with tab_skills:
        if habilidades:
            skills_html = "".join([_render_skill_chip(skill, val) for skill, val in sorted(habilidades.items(), key=lambda x: -x[1])])
            st.markdown(f'<div style="margin-top: 8px;">{skills_html}</div>', unsafe_allow_html=True)
        else:
            st.info("No hay habilidades calculadas.")

    with tab_manage:
        # Asignacion de Estado
        current_status_index = POSIBLES_ESTADOS.index(char['estado']) if char.get('estado') in POSIBLES_ESTADOS else 0

        new_status = st.selectbox(
            "Asignar Estado:",
            options=POSIBLES_ESTADOS,
            index=current_status_index,
            key=f"status_{char['id']}"
        )

        if new_status != char.get('estado'):
            if st.button("Confirmar Cambio de Estado", key=f"btn_status_{char['id']}"):
                try:
                    update_character(char['id'], {'estado': new_status})
                    st.success(f"Estado actualizado a '{new_status}'.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


def _render_debug_panel(char: Dict[str, Any], player_id: int):
    """Panel de debug/Game Master para testing."""
    
    # FIX: Asegurar que char sea dict
    if hasattr(char, "model_dump"):
        char = char.model_dump()
    elif hasattr(char, "dict"):
        char = char.dict()

    st.markdown("---")
    st.warning("Zona de pruebas - Los cambios son permanentes")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("+1000 XP", key=f"debug_xp_{char['id']}"):
            result = add_xp_to_character(char['id'], 1000, player_id)
            if result:
                st.success("+1000 XP!")
                st.rerun()
            else:
                st.error("Error")

    with col2:
        if st.button("FORZAR LEVEL UP", key=f"debug_lvl_{char['id']}"):
            try:
                # Dar XP suficiente para el siguiente nivel
                stats = char.get("stats_json", {})
                current_xp = stats.get("xp", 0)
                current_level = stats.get("nivel", 1)
                progress = calculate_level_progress(current_xp, stored_level=current_level)

                if progress["can_level_up"]:
                    new_stats, changes = apply_level_up(char)
                    result = update_character_level(char['id'], changes['nivel_nuevo'], new_stats, player_id)
                    if result:
                        st.success(f"Nivel {changes['nivel_nuevo']}!")
                        st.rerun()
                else:
                    # Dar XP para alcanzar el siguiente nivel
                    xp_needed = progress["xp_next"] - current_xp
                    add_xp_to_character(char['id'], xp_needed, player_id)
                    st.info(f"+{xp_needed} XP (ahora puedes ascender)")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with col3:
        if st.button("REROLL STATS", key=f"debug_reroll_{char['id']}"):
            try:
                new_stats = reroll_character_stats(char)
                result = update_character_stats(char['id'], new_stats, player_id)
                if result:
                    st.success("Stats regenerados!")
                    st.rerun()
                else:
                    st.error("Error")
            except Exception as e:
                st.error(f"Error: {e}")

    # Mostrar XP table para referencia
    with st.expander("Tabla de XP por Nivel"):
        xp_data = [(lvl, xp) for lvl, xp in sorted(XP_TABLE.items())]
        cols = st.columns(4)
        for i, (lvl, xp) in enumerate(xp_data):
            with cols[i % 4]:
                st.caption(f"Nv.{lvl}: {xp:,} XP")


def show_faction_roster():
    """Pagina principal para mostrar la lista de personajes de la faccion."""

    st.title("Comando de Faccion")
    st.caption("Centro de gestion de personal y tripulacion")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("No se ha podido identificar al jugador. Por favor, vuelve a iniciar sesion.")
        return

    # FIX: Acceder como objeto, no como dict
    player_id = player.id

    try:
        raw_characters = get_all_characters_by_player_id(player_id)
        
        # FIX: Normalizar a diccionarios
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
            st.info("No tienes personal en tu faccion. ¡Es hora de reclutar!")
            return

        # Separar comandante del resto
        commander = next((c for c in characters if c.get('es_comandante')), None)
        crew = [c for c in characters if not c.get('es_comandante')]

        # Stats globales
        total_chars = len(characters)
        available = len([c for c in characters if c.get('estado') == 'Disponible'])

        col_stat1, col_stat2, col_stat3 = st.columns(3)
        col_stat1.metric("Total Personal", total_chars)
        col_stat2.metric("Disponibles", available)
        col_stat3.metric("En Mision", len([c for c in characters if c.get('estado') == 'En Mision']))

        st.markdown("---")

        # Comandante
        if commander:
            st.header("Comandante")
            with st.container(border=True):
                render_character_card(commander, player_id, is_commander=True)

                # Panel de Debug para comandante
                with st.expander("ZONA DE DEBUG / GAME MASTER"):
                    _render_debug_panel(commander, player_id)

        # Tripulacion
        if crew:
            st.header(f"Operativos ({len(crew)})")

            for char in sorted(crew, key=lambda x: -(x.get('stats_json', {}).get('nivel', 0))):
                with st.container(border=True):
                    render_character_card(char, player_id, is_commander=False)

                    # Panel de Debug para cada operativo
                    with st.expander("ZONA DE DEBUG / GAME MASTER"):
                        _render_debug_panel(char, player_id)

    except Exception as e:
        st.error(f"Error al cargar la lista de personajes: {e}")
        st.exception(e)