# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine.
"""

import streamlit as st
from typing import Dict, Any, List
from ui.state import get_player
from core.character_engine import calculate_recruitment_cost, get_visible_biography, BIO_ACCESS_KNOWN, BIO_ACCESS_SUPERFICIAL
from services.character_generation_service import generate_random_character_with_ai, RecruitmentContext
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from config.app_constants import (
    DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION,
    DEFAULT_RECRUITMENT_POOL_SIZE
)
from core.mrg_engine import resolve_action
from core.mrg_constants import DIFFICULTY_NORMAL

def _generate_recruitment_pool(
    player_id: int, 
    pool_size: int, 
    existing_names: List[str], 
    min_level: int = 1, 
    max_level: int = 3
) -> List[Dict[str, Any]]:
    candidates = []
    names_in_use = list(existing_names)

    for i in range(pool_size):
        if i < 2:
            current_min = 1
            current_max = 1
        else:
            current_min = min_level
            current_max = max_level

        context = RecruitmentContext(
            player_id=player_id,
            min_level=current_min,
            max_level=current_max
        )

        char = generate_random_character_with_ai(
            context=context,
            existing_names=names_in_use
        )

        costo = calculate_recruitment_cost(char)
        stats = char.get("stats_json", {})
        progresion = stats.get("progresion", {})
        taxonomia = stats.get("taxonomia", {})

        candidate = {
            "nombre": char["nombre"],
            "nivel": progresion.get("nivel", 1),
            "raza": taxonomia.get("raza", "Desconocida"),
            "clase": progresion.get("clase", "Novato"),
            "costo": costo,
            "stats_json": stats
        }

        candidates.append(candidate)
        names_in_use.append(char["nombre"])

    return candidates


def _render_candidate_card(candidate: Dict[str, Any], index: int, player_credits: int, player_id: int):
    """Renderiza la tarjeta de un candidato."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    capacidades = stats.get("capacidades", {})
    atributos = capacidades.get("atributos", {})
    habilidades = capacidades.get("habilidades", {})
    feats = capacidades.get("feats", [])

    can_afford = player_credits >= candidate["costo"]
    border_color = "#26de81" if can_afford else "#ff6b6b"

    with st.container(border=True):
        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-left: 4px solid {border_color};
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 12px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.2em; font-weight: bold; color: #fff;">{candidate['nombre']}</span>
                    <span style="
                        font-size: 1.4em;
                        font-weight: bold;
                        color: #45b7d1;
                    ">Nv. {candidate['nivel']}</span>
                </div>
                <div style="color: #888; font-size: 0.85em; margin-top: 4px;">
                    <span style="color: #a55eea;">{candidate['raza']}</span> |
                    <span style="color: #f9ca24;">{candidate['clase']}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # USAR get_visible_biography
        visible_bio = get_visible_biography(stats)
        st.caption(f"_{visible_bio}_")

        # Opción de Investigación
        access_level = bio.get("nivel_acceso", BIO_ACCESS_SUPERFICIAL)
        if access_level == BIO_ACCESS_SUPERFICIAL:
            investigation_cost = 150
            if st.button(f"🕵️ Investigar Antecedentes ({investigation_cost} CR)", key=f"inv_{index}", use_container_width=True):
                if player_credits >= investigation_cost:
                    if update_player_credits(player_id, player_credits - investigation_cost):
                        mrg = resolve_action(merit_points=2, difficulty=DIFFICULTY_NORMAL, action_description="Investigar recluta")
                        
                        if mrg.success:
                            stats['bio']['nivel_acceso'] = BIO_ACCESS_KNOWN
                            st.success("✅ ¡Investigación exitosa! Archivos desbloqueados.")
                            st.rerun()
                        else:
                            st.error("❌ La encriptación de los archivos es muy fuerte. Intento fallido.")
                            st.rerun()
                    else:
                        st.error("Error al procesar transacción.")
                else:
                    st.error("Créditos insuficientes.")

        with st.expander("Ver Atributos", expanded=False):
            cols = st.columns(3)
            for i, (attr, value) in enumerate(atributos.items()):
                with cols[i % 3]:
                    color = "#26de81" if value >= 12 else "#888"
                    st.markdown(f"<span style='color:{color};'>{attr.upper()}: **{value}**</span>", unsafe_allow_html=True)

        with st.expander("Ver Habilidades", expanded=False):
            if habilidades:
                sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])
                for skill, val in sorted_skills[:5]:
                    color = "#ffd700" if val >= 25 else "#45b7d1" if val >= 18 else "#888"
                    st.markdown(f"<span style='color:{color};'>{skill}: **{val}**</span>", unsafe_allow_html=True)
            else:
                st.caption("Sin habilidades calculadas")

        if feats:
            with st.expander("Ver Rasgos", expanded=False):
                for feat in feats:
                    st.markdown(f"- {feat}")

        st.markdown("---")

        col_cost, col_btn = st.columns([2, 1])

        with col_cost:
            cost_color = "#26de81" if can_afford else "#ff6b6b"
            st.markdown(f"""
                <div style="text-align: center;">
                    <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                    <span style="font-size: 1.8em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                </div>
            """, unsafe_allow_html=True)

        with col_btn:
            if can_afford:
                if st.button(f"CONTRATAR", key=f"recruit_{index}", type="primary", use_container_width=True):
                    _process_recruitment(player_id, candidate, player_credits)
            else:
                st.button("FONDOS INSUFICIENTES", key=f"recruit_{index}", disabled=True, use_container_width=True)


def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
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
    st.title("Centro de Reclutamiento Galactico")
    st.caption("Encuentra y contrata nuevos operativos para tu faccion")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("Error de sesion.")
        return

    player_id = player.id
    player_credits = get_player_credits(player_id)

    col_credits, col_refresh = st.columns([3, 1])

    with col_credits:
        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 16px;
                border-radius: 10px;
                border: 1px solid #333;
            ">
                <span style="color: #888; font-size: 0.85em;">CREDITOS DISPONIBLES</span><br>
                <span style="font-size: 2em; font-weight: bold; color: #ffd700;">{player_credits:,} C</span>
            </div>
        """, unsafe_allow_html=True)

    with col_refresh:
        st.write("")
        refresh_cost = 50
        can_refresh = player_credits >= refresh_cost

        if st.button(
            f"Buscar Nuevos\n({refresh_cost} C)",
            disabled=not can_refresh,
            type="secondary",
            use_container_width=True
        ):
            if update_player_credits(player_id, player_credits - refresh_cost):
                if 'recruitment_pool' in st.session_state:
                    del st.session_state.recruitment_pool
                st.rerun()
            else:
                st.error("Error al actualizar creditos")

    st.markdown("---")

    with st.expander("Opciones de Busqueda"):
        col_min, col_max = st.columns(2)
        with col_min:
            min_level = st.number_input("Nivel Minimo", min_value=1, max_value=10, value=1)
        with col_max:
            max_level = st.number_input("Nivel Maximo", min_value=1, max_value=10, value=3)

        if max_level < min_level:
            max_level = min_level

        if st.button("Aplicar Filtros"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.session_state.recruit_min_level = min_level
            st.session_state.recruit_max_level = max_level
            st.rerun()

    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        all_chars = get_all_characters_by_player_id(player_id)
        
        existing_names = []
        for c in all_chars:
            if hasattr(c, 'nombre'):
                existing_names.append(c.nombre)
            elif isinstance(c, dict):
                existing_names.append(c.get('nombre'))

        min_lvl = st.session_state.get('recruit_min_level', 1)
        max_lvl = st.session_state.get('recruit_max_level', 3)

        with st.spinner("Conectando con la red de reclutamiento IA..."):
            st.session_state.recruitment_pool = _generate_recruitment_pool(
                player_id=player_id,
                pool_size=DEFAULT_RECRUITMENT_POOL_SIZE,
                existing_names=existing_names,
                min_level=min_lvl,
                max_level=max_lvl
            )

    candidates = st.session_state.recruitment_pool

    if not candidates:
        st.info("No hay candidatos disponibles. Pulsa 'Buscar Nuevos' para generar mas.")
        if st.button("Generar Candidatos Gratis"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.rerun()
        return

    st.subheader(f"Candidatos Disponibles ({len(candidates)})")

    cols = st.columns(len(candidates))

    for i, candidate in enumerate(candidates):
        with cols[i]:
            _render_candidate_card(candidate, i, player_credits, player_id)

    st.markdown("---")
    st.caption("Los candidatos son generados proceduralmente. El costo se basa en nivel y atributos.")