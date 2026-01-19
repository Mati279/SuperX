# ui/faction_roster.py
"""
Gestión del Personal de la Facción.
Muestra los miembros reclutados con sistema de conocimiento e investigación.
Refactorizado para usar layout compacto tipo tabla y botones de acción simplificados.
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

# --- HELPERS DE ESTILO ---

def _get_level_color(level: int) -> str:
    """Retorna el color hexadecimal según el nivel del personaje."""
    if level <= 3:
        return "#7f8c8d"  # Gris (Bajo)
    if level <= 7:
        return "#ecf0f1"  # Blanco/Gris Claro (Medio-Bajo)
    if level <= 12:
        return "#26de81"  # Verde/Azul (Medio)
    if level <= 17:
        return "#45b7d1"  # Azul/Violeta (Alto)
    return "#f1c40f"      # Dorado (Elite)

def _render_character_info_html(char: dict, is_being_investigated: bool) -> str:
    """Genera el HTML compacto para la columna de información principal."""
    stats = char.get("stats_json", {})
    bio = stats.get("bio", {})
    prog = stats.get("progresion", {})
    tax = stats.get("taxonomia", {})
    
    nombre = char.get("nombre", "Desconocido")
    nivel = prog.get("nivel", 1)
    clase = prog.get("clase", "Recluta")
    raza = tax.get("raza", "Humano")
    
    # badges
    badges_html = ""
    if is_being_investigated:
         badges_html += '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 1px 4px; border-radius: 3px; font-size: 0.6em; margin-left: 6px; border: 1px solid #45b7d1; vertical-align: middle;">INV</span>'
    
    level_color = _get_level_color(nivel)

    # Layout ultra compacto: Nombre | Nivel | Clase | Raza
    html = f"""
        <div style="line-height: 1.2; display: flex; align-items: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            <span style="font-weight: bold; color: #fff; font-size: 1em; margin-right: 8px;">{nombre}</span>
            {badges_html}
        </div>
        <div style="line-height: 1.1; font-size: 0.8em; margin-top: 2px;">
            <span style="color: {level_color}; font-weight: bold;">Nvl {nivel}</span>
            <span style="color: #666; margin: 0 4px;">|</span>
            <span style="color: #ccc;">{clase}</span>
            <span style="color: #666; margin: 0 4px;">|</span>
            <span style="color: #a55eea;">{raza}</span>
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

    # --- CSS Injection para Tabla Compacta ---
    st.markdown("""
        <style>
            /* Reducir padding vertical de las columnas */
            div[data-testid="column"] {
                padding-top: 0rem !important;
                padding-bottom: 0rem !important;
            }
            /* Ajustar altura de botones para que sean más finos */
            .stButton button {
                min-height: 32px !important;
                height: 32px !important;
                padding-top: 0px !important;
                padding-bottom: 0px !important;
                font-size: 0.9em !important;
            }
            /* Ajustar Selectbox para que ocupe menos altura */
            div[class*="stSelectbox"] > div > div {
                min-height: 32px !important;
                height: 32px !important;
            }
            /* Reducir gap del contenedor principal si es posible */
            .block-container {
                padding-top: 2rem;
            }
            hr {
                margin-top: 0.5rem !important;
                margin-bottom: 0.5rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

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

    # Filtros y Ordenamiento Compactos
    with st.expander("Filtros y Ordenamiento", expanded=False):
        col_sort, col_filter = st.columns(2)
        with col_sort:
            sort_by = st.selectbox("Ordenar por", ["Rango", "Clase", "Nombre", "Nivel"])
        with col_filter:
            filter_role = st.selectbox("Filtrar por Rol", ["Todos"] + [r.value for r in CharacterRole])

    st.markdown("---") # Separador sutil

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

    # --- LISTA DE PERSONAL (Layout de Tabla) ---
    # Header simulado
    h_cols = st.columns([3.5, 2, 2, 2.5])
    h_cols[0].markdown("**Agente**")
    h_cols[1].markdown("**Rol**")
    h_cols[2].markdown("**Misión**")
    h_cols[3].markdown("**Acciones**")
    
    st.markdown("<hr style='margin: 0; border-top: 1px solid #444;'>", unsafe_allow_html=True)
    
    for char in filtered_chars:
        char_id = char['id']
        is_commander = char.get("es_comandante", False)
        
        # Verificar si este personaje está siendo investigado
        is_being_investigated = (
            investigating_target and
            investigating_target.get("target_type") == "MEMBER" and
            investigating_target.get("target_id") == char_id
        )

        # Contenedor de la fila para alineación vertical
        with st.container():
            # Definición de columnas: [Info, Rol, Misión, Acciones Agrupadas]
            cols = st.columns([3.5, 2, 2, 2.5], gap="small", vertical_alignment="center")
            
            # --- COL 1: Info Principal ---
            with cols[0]:
                st.markdown(_render_character_info_html(char, is_being_investigated), unsafe_allow_html=True)

            # --- COL 2: Selector de Rol ---
            with cols[1]:
                current_role = char.get("stats_json", {}).get("estado", {}).get("rol_asignado", "Sin Asignar")
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
                    disabled=is_commander
                )

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
                    disabled=True
                )

            # --- COL 4: Acciones Agrupadas ---
            with cols[3]:
                # Sub-columnas para botones pegados
                # Calculamos cuántos botones necesitamos
                knowledge_level = get_character_knowledge_level(char_id, player_id)
                can_investigate = (knowledge_level == KnowledgeLevel.UNKNOWN 
                                   and not is_being_investigated 
                                   and not investigation_active)
                
                # Layout de botones: [Investigar (opcional)] [Ficha] [Despedir]
                # Usamos ratios para que queden compactos a la izquierda de la celda si hay pocos
                if can_investigate:
                    ac_cols = st.columns([1.5, 1, 1])
                else:
                    ac_cols = st.columns([0.1, 1, 1]) # Placeholder col 0 vacío

                # 1. Investigar
                with ac_cols[0]:
                    if can_investigate:
                        can_afford = player_credits >= INVESTIGATION_COST
                        if st.button("🔍 Inv.", key=f"btn_inv_row_{char_id}", disabled=not can_afford, help=f"Investigar Antecedentes. Costo: {INVESTIGATION_COST} C"):
                            _handle_member_investigation(player_id, char, player_credits)
                    else:
                        st.empty()

                # 2. Ficha
                with ac_cols[1]:
                    if st.button("📄", key=f"sheet_{char_id}", help="Ver Hoja de Servicio"):
                        view_character_dialog(char, player_id)

                # 3. Despedir (Popover con Confirmación)
                with ac_cols[2]:
                    if is_commander:
                        st.button("⛔", disabled=True, key=f"no_fire_{char_id}", help="Comandante inamovible")
                    else:
                        # Usar popover para confirmación
                        with st.popover("🗑️", help="Despedir agente"):
                            st.markdown("¿Confirmar baja?")
                            if st.button("Confirmar", key=f"conf_fire_{char_id}", type="primary"):
                                if dismiss_character(char_id, player_id):
                                    st.success("Despedido.")
                                    st.rerun()
                                else:
                                    st.error("Error.")
            
            # Separador visual de fila muy fino
            st.markdown("<hr style='margin: 0; border-top: 1px solid #333;'>", unsafe_allow_html=True)


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