# ui/faction_roster.py
"""
Gestión del Personal de la Facción.
Muestra los miembros reclutados con sistema de conocimiento e investigación.
"""

import streamlit as st
from data.character_repository import (
    get_all_player_characters,
    update_character_stats,
    get_character_knowledge_level,
    set_character_knowledge_level,
    recruit_random_character_with_ai
)
from data.player_repository import get_player_credits, update_player_credits
from data.world_repository import queue_player_action, has_pending_investigation, get_investigating_target_info
from data.log_repository import log_event
from core.models import CharacterRole, KnowledgeLevel
from ui.character_sheet import render_character_sheet


# --- CONSTANTES ---
INVESTIGATION_COST = 150


def render_faction_roster():
    from .state import get_player

    st.title("Personal de la Faccion")

    player = get_player()
    if not player:
        st.warning("Error de sesion.")
        return

    player_id = player.id
    player_credits = get_player_credits(player_id)

    # Obtener personajes
    characters = get_all_player_characters(player_id)

    # Verificar si hay investigación en curso (bloqueo global)
    investigation_active = has_pending_investigation(player_id)
    investigating_target = get_investigating_target_info(player_id)

    # --- LÓGICA DE BIENVENIDA / STARTER PACK ---
    non_commander_count = sum(1 for c in characters if not c.get("es_comandante", False))

    if non_commander_count == 0:
        st.info("Parece que tu faccion recien se esta estableciendo. Reune a tu equipo inicial.")

        if st.button("Conocer a la tripulacion", type="primary", help="Genera tu equipo inicial con ayuda de la IA"):
            try:
                with st.spinner("Convocando personal y estableciendo enlaces neuronales..."):
                    # 1. Un personaje Nivel 5 (Conocido) - El veterano
                    vet = recruit_random_character_with_ai(player_id, min_level=5, max_level=5)
                    if vet:
                        set_character_knowledge_level(vet['id'], player_id, KnowledgeLevel.KNOWN)

                    # 2. Dos personajes Nivel 3 (Conocidos) - Los oficiales
                    for _ in range(2):
                        off = recruit_random_character_with_ai(player_id, min_level=3, max_level=3)
                        if off:
                            set_character_knowledge_level(off['id'], player_id, KnowledgeLevel.KNOWN)

                    # 3. Tres personajes Nivel 1 (Desconocidos) - Los reclutas
                    for _ in range(3):
                        recruit_random_character_with_ai(player_id, min_level=1, max_level=1)

                st.success("La tripulacion se ha reportado en el puente!")
                st.rerun()

            except Exception as e:
                st.error(f"Error durante el proceso de reclutamiento inicial: {e}")

    if not characters:
        st.info("No hay personal reclutado en tu faccion.")
        return

    # Mensaje de investigación en curso
    if investigation_active:
        target_name = investigating_target.get("target_name", "un objetivo") if investigating_target else "un objetivo"
        st.info(f"**Investigacion en curso** sobre **{target_name}**. Los canales de inteligencia estan ocupados.")

    # Filtros y Ordenamiento
    col1, col2 = st.columns(2)
    with col1:
        sort_by = st.selectbox("Ordenar por", ["Rango", "Clase", "Nombre", "Nivel"])
    with col2:
        filter_role = st.selectbox("Filtrar por Rol", ["Todos"] + [r.value for r in CharacterRole])

    # Aplicar filtros
    filtered_chars = characters
    if filter_role != "Todos":
        filtered_chars = [c for c in filtered_chars if c.get("stats_json", {}).get("estado", {}).get("rol_asignado") == filter_role]

    # Aplicar orden
    if sort_by == "Nombre":
        filtered_chars.sort(key=lambda x: x["nombre"])
    elif sort_by == "Nivel":
        filtered_chars.sort(key=lambda x: x.get("stats_json", {}).get("progresion", {}).get("nivel", 0), reverse=True)
    elif sort_by == "Clase":
        filtered_chars.sort(key=lambda x: x.get("stats_json", {}).get("progresion", {}).get("clase", ""))

    # Mostrar lista
    for char in filtered_chars:
        # Verificar si este personaje está siendo investigado
        is_being_investigated = (
            investigating_target and
            investigating_target.get("target_type") == "MEMBER" and
            investigating_target.get("target_id") == char['id']
        )

        # Badge para el título
        badge = ""
        if is_being_investigated:
            badge = " [INVESTIGANDO]"

        with st.expander(f"{char['rango']} {char['nombre']} - {char.get('stats_json', {}).get('progresion', {}).get('clase', 'Sin Clase')}{badge}"):

            # --- SECCIÓN DE GESTIÓN DE CONOCIMIENTO ---
            char_id = char['id']
            knowledge_level = get_character_knowledge_level(char_id, player_id)

            # Botón de Investigar (Solo para UNKNOWN)
            if knowledge_level == KnowledgeLevel.UNKNOWN:
                st.warning(f"Nivel de Conocimiento: {knowledge_level.value.upper()}")
                st.write("No tienes acceso a los datos completos de este personal. Puedes ordenar una investigacion interna.")

                # Determinar si se puede investigar
                can_afford = player_credits >= INVESTIGATION_COST
                disable_inv = False
                inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."

                if is_being_investigated:
                    disable_inv = True
                    inv_help = "Investigacion en curso sobre este personaje."
                elif investigation_active:
                    disable_inv = True
                    inv_help = "Otra investigacion en curso. Espere al proximo Tick."
                elif not can_afford:
                    disable_inv = True
                    inv_help = "Creditos insuficientes."

                col_btn, col_debug = st.columns([2, 1])

                with col_btn:
                    btn_label = "Investigando..." if is_being_investigated else f"Investigar ({INVESTIGATION_COST} C)"

                    if st.button(
                        btn_label,
                        key=f"investigate_{char_id}",
                        disabled=disable_inv,
                        help=inv_help
                    ):
                        _handle_member_investigation(player_id, char, player_credits)

                # --- DEBUG MENU ---
                with col_debug:
                    with st.popover("Debug"):
                        st.caption("Forzar resultado:")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Exito", key=f"d_s_{char_id}", help="Exito normal"):
                                _handle_member_investigation(player_id, char, player_credits, debug_outcome="SUCCESS")
                        with c2:
                            if st.button("Fallo", key=f"d_f_{char_id}", help="Fallo normal"):
                                _handle_member_investigation(player_id, char, player_credits, debug_outcome="FAIL")

            else:
                # Si ya es Conocido o Amigo, mostramos el indicador discreto
                color = "blue" if knowledge_level == KnowledgeLevel.KNOWN else "gold"
                st.markdown(f"**Nivel de Acceso:** :{color}[{knowledge_level.value.upper()}]")

            # --- FICHA DE PERSONAJE ---
            render_character_sheet(char, player_id)

            st.divider()

            # --- ACCIONES DE GESTIÓN (Roles, Despido, etc.) ---
            c1, c2 = st.columns(2)
            with c1:
                current_role = char.get("stats_json", {}).get("estado", {}).get("rol_asignado", "Sin Asignar")
                new_role = st.selectbox(
                    "Asignar Rol",
                    [r.value for r in CharacterRole],
                    index=[r.value for r in CharacterRole].index(current_role) if current_role in [r.value for r in CharacterRole] else 0,
                    key=f"role_{char['id']}"
                )

                if new_role != current_role:
                    if st.button("Confirmar Cambio de Rol", key=f"btn_role_{char['id']}"):
                        stats = char.get("stats_json", {})
                        if "estado" not in stats:
                            stats["estado"] = {}
                        stats["estado"]["rol_asignado"] = new_role
                        update_character_stats(char['id'], stats)
                        st.success(f"Rol actualizado a {new_role}")
                        st.rerun()


def _handle_member_investigation(player_id: int, character: dict, current_credits: int, debug_outcome: str = ""):
    """Maneja el cobro y encolado de investigación de un miembro."""

    if current_credits < INVESTIGATION_COST:
        st.error("Creditos insuficientes.")
        return

    if not update_player_credits(player_id, current_credits - INVESTIGATION_COST):
        st.error("Error en transaccion financiera.")
        return

    # Construir comando
    debug_param = f" debug_outcome={debug_outcome}" if debug_outcome != "" else ""
    cmd = f"[INTERNAL_EXECUTE_INVESTIGATION] character_id={character['id']} target_type=MEMBER{debug_param}"

    if queue_player_action(player_id, cmd):
        log_event(f"INTEL: Iniciando investigacion interna sobre {character['nombre']}...", player_id)
        st.toast(f"Investigacion iniciada. -{INVESTIGATION_COST} C.", icon="🕵️")
        st.rerun()
    else:
        st.error("Error al encolar orden.")
        # Rollback
        update_player_credits(player_id, current_credits)
