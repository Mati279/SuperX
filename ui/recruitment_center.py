# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.

Sistema de Reclutamiento v2:
- Roster vacio por defecto (requiere busqueda activa)
- Busqueda de candidatos tarda 1 Tick (diferida)
- Candidatos expiran en 4 Ticks
- Sistema de seguimiento (1 candidato por jugador)
- Investigacion con MRG competitivo
"""

import streamlit as st
from typing import Dict, Any

from ui.state import get_player
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character
from data.recruitment_repository import (
    get_recruitment_candidates,
    remove_candidate,
    set_candidate_tracked,
    get_tracked_candidate,
    clear_untracked_candidates,
    set_investigation_state
)
from data.world_repository import (
    queue_player_action,
    has_pending_investigation,
    has_pending_search,
    get_world_state,
    get_investigating_target_info
)
from data.log_repository import log_event
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION
from core.character_engine import BIO_ACCESS_UNKNOWN, BIO_ACCESS_KNOWN


# --- CONSTANTES ---
SEARCH_COST = 50
INVESTIGATION_COST = 150
CANDIDATE_LIFESPAN_TICKS = 4

# Colores para habilidades
COLOR_SKILL_GRAY = "#888888"
COLOR_SKILL_GREEN = "#26de81"
COLOR_SKILL_BLUE = "#45b7d1"
COLOR_SKILL_GOLD = "#ffd700"


def _get_skill_color(value: int) -> str:
    """Retorna el color apropiado segun el valor de la habilidad."""
    if value < 8:
        return COLOR_SKILL_GRAY
    elif value <= 12:
        return COLOR_SKILL_GREEN
    elif value <= 16:
        return COLOR_SKILL_BLUE
    else:
        return COLOR_SKILL_GOLD


def _render_top_skills(habilidades: Dict[str, int], count: int = 5):
    """Renderiza las mejores habilidades con colores segun su valor."""
    if not habilidades:
        st.caption("Sin habilidades registradas.")
        return

    sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])[:count]

    skills_html = ""
    for skill, val in sorted_skills:
        color = _get_skill_color(val)
        skills_html += f'<span style="display: inline-block; padding: 3px 8px; margin: 2px; border-radius: 12px; background: rgba(255,255,255,0.05); border: 1px solid {color}40; color: {color}; font-size: 0.75em;">{skill}: <b>{val}</b></span>'

    st.markdown(skills_html, unsafe_allow_html=True)


def _render_candidate_card(
    candidate: Dict[str, Any],
    player_credits: int,
    player_id: int,
    investigation_active: bool,
    current_tick: int
):
    """Renderiza la tarjeta de un candidato."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    atributos = stats.get("capacidades", {}).get("atributos", {})
    habilidades = stats.get("capacidades", {}).get("habilidades", {})
    comportamiento = stats.get("comportamiento", {})
    rasgos = comportamiento.get("rasgos_personalidad", [])

    # Extraer datos basicos
    nivel = stats.get("progresion", {}).get("nivel", 1)
    raza = stats.get("taxonomia", {}).get("raza", "Desconocido")
    clase = stats.get("progresion", {}).get("clase", "Recluta")

    # Estados
    can_afford = player_credits >= candidate["costo"]
    can_afford_investigation = player_credits >= INVESTIGATION_COST
    is_tracked = candidate.get("is_tracked", False)
    is_being_investigated = candidate.get("is_being_investigated", False)
    investigation_outcome = candidate.get("investigation_outcome")
    discount_applied = candidate.get("discount_applied", False)

    # Nivel de acceso (basado en resultado de investigacion)
    already_investigated = investigation_outcome in ["SUCCESS", "CRIT_SUCCESS"]
    nivel_acceso = BIO_ACCESS_KNOWN if already_investigated else BIO_ACCESS_UNKNOWN
    show_traits = already_investigated

    # Info de expiracion
    tick_created = candidate.get("tick_created", current_tick)
    ticks_left = CANDIDATE_LIFESPAN_TICKS - (current_tick - tick_created)

    # Color del borde
    border_color = "#26de81" if can_afford else "#ff6b6b"
    if is_being_investigated:
        border_color = "#45b7d1"
    elif is_tracked:
        border_color = "#ffd700"

    with st.container(border=True):
        # Header con badges
        badges_html = ""

        # Badge de seguimiento
        if is_tracked:
            badges_html += '<span style="background: #ffd700; color: #000; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px;">SEGUIDO</span>'

        # Badge de investigacion
        if is_being_investigated:
            badges_html += '<span style="background: #45b7d1; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px;">INVESTIGANDO</span>'

        # Badge de conocimiento
        if already_investigated:
            badges_html += '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #45b7d1;">CONOCIDO</span>'
        else:
            badges_html += '<span style="background: rgba(255,107,107,0.15); color: #ff6b6b; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #ff6b6b;">DESCONOCIDO</span>'

        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-left: 4px solid {border_color};
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 12px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.1em; font-weight: bold; color: #fff;">{candidate['nombre']}{badges_html}</span>
                    <span style="font-size: 1.3em; font-weight: bold; color: #45b7d1;">Nv. {nivel}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85em; margin-top: 4px;">
                    <div><span style="color: #a55eea;">{raza}</span> | <span style="color: #f9ca24;">{clase}</span></div>
                    <div style="color: {'#ff6b6b' if ticks_left <= 1 else '#888'};">Expira en: {max(0, ticks_left)} Tick{'s' if ticks_left != 1 else ''}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Bio
        if already_investigated:
            bio_text = bio.get('bio_conocida', bio.get('bio_superficial', 'Datos revelados.'))
            st.success(f"INTELIGENCIA: {bio_text}")
            if discount_applied:
                st.caption("Vulnerabilidad explotable detectada (Descuento 30% aplicado).")
        else:
            bio_text = bio.get('bio_superficial') or bio.get('biografia_corta') or "Sin datos biometricos."
            st.caption(f"*{bio_text}*")

        # Top 5 Habilidades
        st.markdown("**Habilidades Destacadas:**")
        _render_top_skills(habilidades, count=5)

        # Rasgos de personalidad
        if show_traits and rasgos:
            traits_html = " ".join([f'<span style="display: inline-block; padding: 2px 8px; margin: 2px; border-radius: 10px; background: rgba(165,94,234,0.15); color: #a55eea; font-size: 0.75em; border: 1px solid #a55eea40;">{t}</span>' for t in rasgos])
            st.markdown(f"**Personalidad:** {traits_html}", unsafe_allow_html=True)
        elif not show_traits:
            st.caption("*Rasgos de personalidad: Desconocidos*")

        # Stats expandibles
        with st.expander("Ver Atributos", expanded=False):
            if atributos:
                cols = st.columns(3)
                for i, (attr, value) in enumerate(atributos.items()):
                    with cols[i % 3]:
                        color = _get_skill_color(value)
                        st.markdown(f"<span style='color:{color};'>{attr.upper()}: **{value}**</span>", unsafe_allow_html=True)

        st.markdown("---")

        # Footer Actions
        col_track, col_cost, col_inv, col_recruit = st.columns([1, 2, 1, 1])

        # Boton de Seguimiento
        with col_track:
            track_icon = "⭐" if is_tracked else "☆"
            track_help = "Quitar seguimiento" if is_tracked else "Marcar para seguimiento (no expirara)"

            if st.button(track_icon, key=f"track_{candidate['id']}", help=track_help, use_container_width=True):
                if is_tracked:
                    # Quitar seguimiento (no hay funcion untrack, usamos set_tracked con otro)
                    from data.recruitment_repository import untrack_candidate
                    untrack_candidate(player_id, candidate['id'])
                else:
                    set_candidate_tracked(player_id, candidate['id'])
                st.rerun()

        # Costo
        with col_cost:
            cost_color = "#26de81" if can_afford else "#ff6b6b"
            original_cost = candidate.get("original_cost") if discount_applied else None

            if discount_applied and original_cost:
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.75em;">COSTO</span><br>
                        <span style="text-decoration: line-through; color: #888; font-size: 0.9em;">{original_cost:,}</span>
                        <span style="font-size: 1.2em; font-weight: bold; color: #ffd700;"> {candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.75em;">COSTO</span><br>
                        <span style="font-size: 1.2em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)

        # Boton Investigar
        with col_inv:
            disable_inv = False
            inv_label = "Investigar"
            inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."
            button_type = "secondary"

            if is_being_investigated:
                disable_inv = True
                inv_label = "Investigando..."
                inv_help = "Investigacion en curso. Resultado en el proximo Tick."
                button_type = "primary"
            elif not can_afford_investigation:
                disable_inv = True
                inv_help = "Creditos insuficientes."
            elif investigation_active:
                disable_inv = True
                inv_help = "Otra investigacion en curso. Espere al reporte."
            elif already_investigated:
                disable_inv = True
                inv_label = "Investigado"
                inv_help = "Objetivo ya investigado con exito."

            if st.button(
                inv_label,
                key=f"inv_{candidate['id']}",
                disabled=disable_inv,
                help=inv_help,
                use_container_width=True,
                type=button_type
            ):
                _handle_investigation(player_id, candidate, player_credits)

            # --- DEBUG MENU ---
            with st.popover("Debug"):
                st.caption("Forzar resultado:")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Critico", key=f"d_cs_{candidate['id']}", help="Exito Critico"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_SUCCESS")
                    if st.button("Fallo", key=f"d_f_{candidate['id']}", help="Fallo normal"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="FAIL")
                with c2:
                    if st.button("Exito", key=f"d_s_{candidate['id']}", help="Exito normal"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="SUCCESS")
                    if st.button("Pifia", key=f"d_cf_{candidate['id']}", help="El candidato huye"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_FAIL")

        # Boton Contratar
        with col_recruit:
            if can_afford:
                if st.button("CONTRATAR", key=f"recruit_{candidate['id']}", type="primary", use_container_width=True):
                    _process_recruitment(player_id, candidate, player_credits)
            else:
                st.button("SIN FONDOS", key=f"recruit_{candidate['id']}", disabled=True, use_container_width=True)


def _handle_investigation(player_id: int, candidate: Dict[str, Any], current_credits: int, debug_outcome: str = ""):
    """Maneja el cobro y encolado de investigacion."""

    if current_credits < INVESTIGATION_COST:
        st.error("Creditos insuficientes.")
        return

    if not update_player_credits(player_id, current_credits - INVESTIGATION_COST):
        st.error("Error en transaccion financiera.")
        return

    # Marcar candidato como siendo investigado (y automaticamente seguido)
    set_investigation_state(candidate['id'], True)

    # Construir comando
    debug_param = f" debug_outcome={debug_outcome}" if debug_outcome != "" else ""
    cmd = f"[INTERNAL_EXECUTE_INVESTIGATION] candidate_id={candidate['id']} target_type=CANDIDATE{debug_param}"

    if queue_player_action(player_id, cmd):
        log_event(f"INTEL: Iniciando investigacion sobre {candidate['nombre']}...", player_id)
        st.toast(f"Investigacion iniciada. -{INVESTIGATION_COST} C.", icon="🕵️")
        st.rerun()
    else:
        st.error("Error al encolar orden.")
        # Rollback
        update_player_credits(player_id, current_credits)
        set_investigation_state(candidate['id'], False)


def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """Procesa el reclutamiento final."""
    try:
        costo = candidate['costo']

        if player_credits < costo:
            st.error("Creditos insuficientes.")
            return

        new_credits = player_credits - costo

        # Preparar datos del personaje
        stats = candidate.get("stats_json", {})

        # Si fue investigado exitosamente, actualizar nivel de acceso
        if candidate.get("investigation_outcome") in ["SUCCESS", "CRIT_SUCCESS"]:
            bio_data = stats.get("bio", {})
            if bio_data.get("nivel_acceso") == BIO_ACCESS_UNKNOWN:
                bio_data["nivel_acceso"] = BIO_ACCESS_KNOWN

        new_character_data = {
            "player_id": player_id,
            "nombre": candidate["nombre"],
            "rango": DEFAULT_RECRUIT_RANK,
            "es_comandante": False,
            "stats_json": stats,
            "estado": DEFAULT_RECRUIT_STATUS,
            "ubicacion": DEFAULT_RECRUIT_LOCATION
        }

        update_ok = update_player_credits(player_id, new_credits)
        char_ok = create_character(player_id, new_character_data)

        if update_ok and char_ok:
            # Eliminar candidato del roster
            remove_candidate(candidate['id'])
            st.success(f"¡{candidate['nombre']} se ha unido a tu faccion!")
            log_event(f"RECLUTAMIENTO: {candidate['nombre']} contratado.", player_id)
            st.rerun()
        else:
            st.error("Error critico al procesar el reclutamiento.")

    except Exception as e:
        st.error(f"Error inesperado: {e}")


def _handle_search_new(player_id: int, player_credits: int):
    """Maneja la solicitud de buscar nuevos candidatos."""

    if player_credits < SEARCH_COST:
        st.error("Creditos insuficientes para iniciar busqueda.")
        return

    if not update_player_credits(player_id, player_credits - SEARCH_COST):
        st.error("Error en transaccion financiera.")
        return

    # Eliminar candidatos no seguidos
    cleared = clear_untracked_candidates(player_id)

    # Encolar busqueda
    cmd = "[INTERNAL_SEARCH_CANDIDATES]"

    if queue_player_action(player_id, cmd):
        log_event(f"RECLUTAMIENTO: Busqueda de candidatos iniciada. Resultados en el proximo ciclo.", player_id)
        st.toast(f"Busqueda iniciada. -{SEARCH_COST} C.", icon="🔍")
        if cleared > 0:
            st.toast(f"{cleared} candidato(s) anterior(es) descartado(s).", icon="🗑️")
        st.rerun()
    else:
        st.error("Error al encolar busqueda.")
        update_player_credits(player_id, player_credits)


def show_recruitment_center():
    """Pagina principal del Centro de Reclutamiento."""

    st.title("Centro de Reclutamiento")
    st.caption("Encuentra y contrata nuevos operativos para tu faccion")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("Error de sesion.")
        return

    player_id = player.id

    # Estado del mundo
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)

    # Estados de bloqueo
    investigation_active = has_pending_investigation(player_id)
    search_pending = has_pending_search(player_id)

    # Obtener info de investigacion en curso (para mostrar nombre del objetivo)
    investigating_target = get_investigating_target_info(player_id)

    # Obtener candidatos de DB
    candidates = get_recruitment_candidates(player_id)
    player_credits = get_player_credits(player_id)

    # Header con creditos y boton de busqueda
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
        can_search = player_credits >= SEARCH_COST and not search_pending

        button_label = f"Buscar Nuevos\n({SEARCH_COST} C)"
        if search_pending:
            button_label = "Buscando..."

        if st.button(
            button_label,
            disabled=not can_search,
            type="primary" if not search_pending else "secondary",
            use_container_width=True
        ):
            _handle_search_new(player_id, player_credits)

    # Mensajes de estado
    if search_pending:
        st.info("🔍 **Busqueda en curso.** Los agentes de reclutamiento estan contactando candidatos. Resultados disponibles en el proximo ciclo.")

    if investigation_active:
        target_name = investigating_target.get("target_name", "un objetivo") if investigating_target else "un objetivo"
        st.info(f"🕵️ **Investigacion en curso** sobre **{target_name}**. Los canales de inteligencia estan ocupados hasta el proximo Tick.")

    st.markdown("---")

    # Contenido principal
    if not candidates and not search_pending:
        # Roster vacio
        st.markdown("""
            <div style="
                text-align: center;
                padding: 60px 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 15px;
                border: 2px dashed #333;
            ">
                <div style="font-size: 4em; margin-bottom: 20px;">📭</div>
                <h3 style="color: #888; margin-bottom: 10px;">No hay candidatos disponibles</h3>
                <p style="color: #666;">Utiliza el boton <b>Buscar Nuevos</b> para contactar potenciales reclutas.</p>
                <p style="color: #555; font-size: 0.85em;">La busqueda cuesta {search_cost} creditos y tarda 1 ciclo en completarse.</p>
            </div>
        """.format(search_cost=SEARCH_COST), unsafe_allow_html=True)

    elif not candidates and search_pending:
        # Busqueda en progreso
        st.markdown("""
            <div style="
                text-align: center;
                padding: 60px 20px;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 15px;
                border: 2px solid #45b7d1;
            ">
                <div style="font-size: 4em; margin-bottom: 20px;">🛰️</div>
                <h3 style="color: #45b7d1; margin-bottom: 10px;">Contactando candidatos...</h3>
                <p style="color: #888;">Los agentes de reclutamiento estan explorando la estacion.</p>
                <p style="color: #666; font-size: 0.85em;">Los candidatos estaran disponibles en el proximo ciclo.</p>
            </div>
        """, unsafe_allow_html=True)

    else:
        # Mostrar candidatos
        tracked = get_tracked_candidate(player_id)
        tracked_msg = f" (Siguiendo: **{tracked['nombre']}**)" if tracked else ""

        st.subheader(f"Candidatos Disponibles ({len(candidates)}){tracked_msg}")

        # --- GRID SYSTEM 4 COLUMNAS ---
        # Creamos una fila de 4 columnas inicialmente.
        # Si hubiera mas de 4 (defensa contra bugs), el loop reinicia la fila.
        cols = st.columns(4)
        
        for i, candidate in enumerate(candidates):
            # Indice de columna (0, 1, 2, 3)
            col_idx = i % 4
            
            # Si completamos una fila de 4 y empezamos otra, crear nuevas columnas
            if i > 0 and col_idx == 0:
                cols = st.columns(4)
                
            with cols[col_idx]:
                _render_candidate_card(
                    candidate,
                    player_credits,
                    player_id,
                    investigation_active,
                    current_tick
                )

    st.markdown("---")
    st.caption(f"Los candidatos expiran despues de {CANDIDATE_LIFESPAN_TICKS} ciclos si no son reclutados o seguidos.")