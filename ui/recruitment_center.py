# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine.
"""

import streamlit as st
from typing import Dict, Any, List
from ui.state import get_player
from core.character_engine import generate_random_character, calculate_recruitment_cost
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION
from ui.styles import inject_global_styles, render_terminal_header, render_resource_display, Colors, render_stat_bar, render_data_chip


def _generate_recruitment_pool(pool_size: int, existing_names: List[str], min_level: int = 1, max_level: int = 3) -> List[Dict[str, Any]]:
    """
    Genera una piscina de candidatos para reclutamiento usando el motor de personajes.

    Args:
        pool_size: Cantidad de candidatos a generar.
        existing_names: Nombres existentes para evitar duplicados.
        min_level: Nivel minimo de los candidatos.
        max_level: Nivel maximo de los candidatos.

    Returns:
        Lista de candidatos con stats completos y costo calculado.
    """
    candidates = []
    names_in_use = list(existing_names)

    for _ in range(pool_size):
        # Generar personaje con el motor
        char = generate_random_character(
            min_level=min_level,
            max_level=max_level,
            existing_names=names_in_use
        )

        # Calcular costo de reclutamiento
        costo = calculate_recruitment_cost(char)

        # Preparar candidato para la UI
        candidate = {
            "nombre": char["nombre"],
            "nivel": char["nivel"],
            "raza": char["raza"],
            "clase": char["clase"],
            "costo": costo,
            "stats_json": char["stats_json"]
        }

        candidates.append(candidate)
        names_in_use.append(char["nombre"])

    return candidates


def _render_candidate_card(candidate: Dict[str, Any], index: int, player_credits: int, player_id: int):
    """Renderiza la tarjeta de un candidato con todos sus detalles."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    atributos = stats.get("atributos", {})
    habilidades = stats.get("habilidades", {})
    feats = stats.get("feats", [])

    can_afford = player_credits >= candidate["costo"]

    with st.container(border=True):
        st.subheader(candidate['nombre'])

        chip_html = f"""
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;">
            {render_data_chip('Nivel', str(candidate['nivel']), Colors.ATTR_TECNICA)}
            {render_data_chip('Raza', candidate['raza'], Colors.ATTR_PRESENCIA)}
            {render_data_chip('Clase', candidate['clase'], Colors.ATTR_INTELECTO)}
        </div>
        """
        st.markdown(chip_html, unsafe_allow_html=True)

        st.caption(f"*{bio.get('descripcion_raza', '')}*")
        st.caption(f"*{bio.get('descripcion_clase', '')}*")

        with st.expander("Ver Atributos", expanded=False):
            attr_colors = {
                "Fuerza": Colors.ATTR_FUERZA, "Agilidad": Colors.ATTR_AGILIDAD,
                "Intelecto": Colors.ATTR_INTELECTO, "Tecnica": Colors.ATTR_TECNICA,
                "Presencia": Colors.ATTR_PRESENCIA, "Voluntad": Colors.ATTR_VOLUNTAD
            }
            for attr, value in atributos.items():
                render_stat_bar(attr, value, 20, attr_colors.get(attr, Colors.TEXT_DIM))

        with st.expander("Ver Habilidades", expanded=False):
            if habilidades:
                sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])
                for skill, val in sorted_skills[:5]:
                    render_stat_bar(skill, val, 50, Colors.NOMINAL, show_value=True)
            else:
                st.caption("Sin habilidades calculadas")

        if feats:
            with st.expander("Ver Rasgos", expanded=False):
                for feat in feats:
                    st.markdown(f"- {feat}")

        st.markdown("---")

        col_cost, col_btn = st.columns([2, 1])

        with col_cost:
            cost_color = Colors.SUCCESS if can_afford else Colors.DANGER
            st.markdown(f"""
                <div style="text-align: center;">
                    <span style="font-family: 'Rajdhani', sans-serif; color: {Colors.TEXT_DIM}; font-size: 0.85em;">COSTE</span><br>
                    <span style="font-family: 'Orbitron', sans-serif; font-size: 1.8em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                </div>
            """, unsafe_allow_html=True)

        with col_btn:
            if st.button(
                "CONTRATAR",
                key=f"recruit_{index}",
                type="primary",
                disabled=not can_afford,
                use_container_width=True
            ):
                _process_recruitment(player_id, candidate, player_credits)

def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """Procesa la contratacion de un candidato."""
    try:
        can_afford, message = can_recruit(player_credits, candidate['costo'])
        if not can_afford:
            st.error(message)
            return

        new_credits = player_credits - candidate['costo']

        new_character_data = {
            "player_id": player_id,
            "nombre": candidate["nombre"],
            "rango": DEFAULT_RECRUIT_RANK,
            "es_comandante": False,
            "clase": candidate["clase"],
            "stats_json": candidate["stats_json"],
            "estado": DEFAULT_RECRUIT_STATUS,
            "ubicacion": DEFAULT_RECRUIT_LOCATION
        }

        update_ok = update_player_credits(player_id, new_credits)
        char_ok = create_character(player_id, new_character_data)

        if update_ok and char_ok:
            st.success(f"¡{candidate['nombre']} se ha unido a tu faccion!")
            if 'recruitment_pool' in st.session_state:
                st.session_state.recruitment_pool = [
                    c for c in st.session_state.recruitment_pool if c['nombre'] != candidate['nombre']
                ]
            st.rerun()
        else:
            st.error("Error al completar el reclutamiento.")

    except Exception as e:
        st.error(f"Error inesperado: {e}")


def show_recruitment_center():
    """Pagina principal del Centro de Reclutamiento."""
    inject_global_styles()
    render_terminal_header(
        title="Centro de Reclutamiento",
        subtitle="Encuentra y contrata nuevos operativos para tu faccion.",
        icon="🧑‍🚀"
    )

    player = get_player()
    if not player:
        st.warning("Error de sesion. Por favor, inicie sesion de nuevo.")
        return

    player_id = player.id

    # --- Header con creditos ---
    player_credits = get_player_credits(player_id)

    col_credits, col_refresh = st.columns([3, 1])

    with col_credits:
        st.markdown(render_resource_display(
            icon="💰",
            label="Creditos Disponibles",
            value=player_credits,
            color=Colors.LEGENDARY
        ), unsafe_allow_html=True)

    with col_refresh:
        st.write("")  # Espaciado
        refresh_cost = 50
        can_refresh = player_credits >= refresh_cost

        if st.button(
            f"Buscar Nuevos ({refresh_cost} C)",
            disabled=not can_refresh,
            use_container_width=True
        ):
            if update_player_credits(player_id, player_credits - refresh_cost):
                if 'recruitment_pool' in st.session_state:
                    del st.session_state.recruitment_pool
                st.rerun()
            else:
                st.error("Error al actualizar creditos")

    st.markdown("---")

    # --- Opciones de nivel ---
    with st.expander("Opciones de Busqueda"):
        col_min, col_max = st.columns(2)
        with col_min:
            min_level = st.number_input("Nivel Minimo", min_value=1, max_value=10, value=1)
        with col_max:
            max_level = st.number_input("Nivel Maximo", min_value=1, max_value=10, value=3)

        if max_level < min_level:
            max_level = min_level

        # Guardar en session para regenerar con estos parametros
        if st.button("Aplicar Filtros"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.session_state.recruit_min_level = min_level
            st.session_state.recruit_max_level = max_level
            st.rerun()

    # --- Generar/Obtener piscina de candidatos ---
    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        # Obtener nombres existentes para evitar duplicados
        all_chars = get_all_characters_by_player_id(player_id)
        
        # FIX: Manejo seguro de nombres ya sea objeto o dict
        existing_names = []
        for c in all_chars:
            if hasattr(c, 'nombre'): # Es objeto
                existing_names.append(c.nombre)
            elif isinstance(c, dict): # Es dict
                existing_names.append(c.get('nombre'))

        # Obtener parametros de nivel
        min_lvl = st.session_state.get('recruit_min_level', 1)
        max_lvl = st.session_state.get('recruit_max_level', 3)

        # Generar candidatos
        st.session_state.recruitment_pool = _generate_recruitment_pool(
            pool_size=3,
            existing_names=existing_names,
            min_level=min_lvl,
            max_level=max_lvl
        )

    candidates = st.session_state.recruitment_pool

    # --- Mostrar candidatos ---
    if not candidates:
        st.info("No hay candidatos disponibles. Pulsa 'Buscar Nuevos' para generar mas.")
        if st.button("Generar Candidatos Gratis"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.rerun()
        return

    st.subheader(f"Candidatos Disponibles ({len(candidates)})")

    # Mostrar en columnas
    cols = st.columns(len(candidates))

    for i, candidate in enumerate(candidates):
        with cols[i]:
            _render_candidate_card(candidate, i, player_credits, player_id)

    # --- Footer con info ---
    st.markdown("---")
    st.caption("Los candidatos son generados proceduralmente. El costo se basa en nivel y atributos.")