# ui/faction_roster.py
"""
Gestión del Personal de la Facción.
Muestra los miembros reclutados con sistema de conocimiento e investigación.
Refactorizado para usar layout de filas y estilo unificado con Recruitment Center.
"""

import streamlit as st
from data.character_repository import (
    get_all_player_characters,
    update_character_stats,
    get_character_knowledge_level,
    set_character_knowledge_level,
    recruit_random_character_with_ai,
    dismiss_character
)
from data.player_repository import get_player_credits, update_player_credits
from data.world_repository import queue_player_action, has_pending_investigation, get_investigating_target_info
from data.log_repository import log_event
from core.models import CharacterRole, KnowledgeLevel
from ui.character_sheet import render_character_sheet


# --- CONSTANTES ---
INVESTIGATION_COST = 150

# --- HELPERS DE ESTILO (Replicados de recruitment_center) ---
def _render_character_info_html(char: dict, is_being_investigated: bool) -> str:
    """Genera el HTML para la columna de información principal."""
    stats = char.get("stats_json", {})
    bio = stats.get("bio", {})
    prog = stats.get("progresion", {})
    tax = stats.get("taxonomia", {})
    
    nombre = char.get("nombre", "Desconocido")
    nivel = prog.get("nivel", 1)
    clase = prog.get("clase", "Recluta")
    raza = tax.get("raza", "Humano")
    edad = bio.get("edad", "??")
    
    badges_html = ""
    if is_being_investigated:
         badges_html += '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin-left: 8px; border: 1px solid #45b7d1;">INVESTIGANDO</span>'

    # Estilo similar a recruitment_center cards
    html = f"""
        <div style="line-height: 1.2;">
            <div style="font-size: 1.1em; font-weight: bold; color: #fff; margin-bottom: 4px;">
                {nombre}{badges_html}
            </div>
            <div style="font-size: 0.85em; color: #aaa;">
                <span style="color: #a55eea;">{raza}</span> | 
                <span style="color: #ffd700; font-weight: bold;">Nvl {nivel}</span> | 
                <span style="color: #ccc;">{clase}</span> |
                <span style="color: #888;">{edad} años</span>
            </div>
        </div>
    """
    return html

# --- COMPONENTES UI ---

@st.dialog("Expediente del Personal", width="large")
def view_character_dialog(char: dict, player_id: int):
    """Muestra la ficha de personaje en un modal."""
    render_character_sheet(char, player_id)


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
        return # Salir para recargar tras generar

    if not characters:
        st.info("No hay personal reclutado en tu faccion.")
        return

    # Mensaje de investigación en curso
    if investigation_active:
        target_name = investigating_target.get("target_name", "un objetivo") if investigating_target else "un objetivo"
        st.info(f"**Investigacion en curso** sobre **{target_name}**. Los canales de inteligencia estan ocupados.")

    # Filtros y Ordenamiento
    st.markdown("### Filtros Operativos")
    col_sort, col_filter = st.columns(2)
    with col_sort:
        sort_by = st.selectbox("Ordenar por", ["Rango", "Clase", "Nombre", "Nivel"])
    with col_filter:
        filter_role = st.selectbox("Filtrar por Rol", ["Todos"] + [r.value for r in CharacterRole])

    st.divider()

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
    # Por defecto Rango/Orden de llegada se mantiene

    # --- LISTA DE PERSONAL (Layout de Filas) ---
    
    for char in filtered_chars:
        char_id = char['id']
        is_commander = char.get("es_comandante", False)
        
        # Verificar si este personaje está siendo investigado
        is_being_investigated = (
            investigating_target and
            investigating_target.get("target_type") == "MEMBER" and
            investigating_target.get("target_id") == char_id
        )

        # Contenedor de la fila
        with st.container():
            # Definición de columnas: [Info, Rol, Misión, Ficha, Acciones]
            cols = st.columns([3, 1.5, 1.5, 1, 1])
            
            # --- COL 1: Info Principal ---
            with cols[0]:
                st.markdown(_render_character_info_html(char, is_being_investigated), unsafe_allow_html=True)

            # --- COL 2: Selector de Rol ---
            with cols[1]:
                current_role = char.get("stats_json", {}).get("estado", {}).get("rol_asignado", "Sin Asignar")
                
                # Si es comandante, el rol suele ser fijo, pero permitimos cambiar si la lógica lo soporta
                role_options = [r.value for r in CharacterRole]
                
                try:
                    idx = role_options.index(current_role)
                except ValueError:
                    idx = 0

                new_role = st.selectbox(
                    "Rol",
                    role_options,
                    index=idx,
                    key=f"role_sel_{char_id}",
                    label_visibility="collapsed",
                    disabled=is_commander # Bloquear cambio de rol al comandante si se desea
                )

                # Persistencia inmediata del cambio de rol
                if new_role != current_role and not is_commander:
                    stats = char.get("stats_json", {})
                    if "estado" not in stats: stats["estado"] = {}
                    stats["estado"]["rol_asignado"] = new_role
                    update_character_stats(char_id, stats)
                    st.toast(f"Rol actualizado a {new_role}")
                    st.rerun()

            # --- COL 3: Selector de Misión (Placeholder) ---
            with cols[2]:
                st.selectbox(
                    "Misión",
                    ["Idle", "Entrenamiento", "Patrulla"],
                    index=0,
                    key=f"mission_sel_{char_id}",
                    label_visibility="collapsed",
                    disabled=True # Placeholder
                )

            # --- COL 4: Ver Ficha (Dialog) ---
            with cols[3]:
                if st.button("📄 Ficha", key=f"sheet_{char_id}", use_container_width=True):
                    view_character_dialog(char, player_id)

            # --- COL 5: Despedir / Investigar (UX REFACTORIZADA) ---
            with cols[4]:
                # Si es comandante no se puede despedir
                if is_commander:
                    st.button("⛔", disabled=True, key=f"no_fire_{char_id}", help="No puedes despedir al Comandante.")
                else:
                    # Lógica de Despido Segura (Popover)
                    with st.popover("👋", help="Gestionar Salida"):
                        st.markdown(f"**¿Despedir a {char['nombre']}?**")
                        st.caption("Esta acción es irreversible.")
                        if st.button("Confirmar Despido", key=f"confirm_fire_{char_id}", type="primary", use_container_width=True):
                             if dismiss_character(char_id, player_id):
                                 st.success("Personal despedido.")
                                 st.rerun()
                             else:
                                 st.error("Error al despedir.")
            
            # --- Investigar (Si aplica) ---
            # Mostramos un pequeño link o botón de investigar debajo si es UNKNOWN
            knowledge_level = get_character_knowledge_level(char_id, player_id)
            if knowledge_level == KnowledgeLevel.UNKNOWN and not is_being_investigated and not investigation_active:
                 can_afford = player_credits >= INVESTIGATION_COST
                 if st.button(f"🔍 Investigar ({INVESTIGATION_COST} C)", key=f"btn_inv_row_{char_id}", disabled=not can_afford):
                     _handle_member_investigation(player_id, char, player_credits)
            
            st.divider()


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