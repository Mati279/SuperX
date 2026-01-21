# ui/faction_roster.py
"""
Gestión del Personal de la Facción.
Muestra los miembros reclutados con sistema de conocimiento e investigación.
Refactorizado MMFR: Fuente de Verdad SQL (Nivel, Lealtad, Ubicación).
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
from core.models import CharacterRole, KnowledgeLevel, CommanderData
from ui.character_sheet import render_character_sheet


# --- CONSTANTES ---
INVESTIGATION_COST = 150

# --- HELPERS DE ESTILO ---
def _render_character_info_html(char_obj: CommanderData, is_being_investigated: bool) -> str:
    """
    Genera el HTML para la columna de información principal.
    Usa CommanderData hidratado.
    """
    # Obtenemos el esquema completo procesado (hidratado)
    sheet = char_obj.sheet
    
    nombre = sheet.bio.nombre
    nivel = sheet.progresion.nivel
    clase = sheet.progresion.clase
    raza = sheet.taxonomia.raza
    edad = sheet.bio.edad
    rango = sheet.progresion.rango
    
    badges_html = ""
    if is_being_investigated:
         badges_html += '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin-left: 8px; border: 1px solid #45b7d1;">INVESTIGANDO</span>'

    if char_obj.es_comandante:
        badges_html += '<span style="background: rgba(255,215,0,0.2); color: #ffd700; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin-left: 8px; border: 1px solid #ffd700;">LÍDER</span>'

    html = f"""
        <div style="line-height: 1.2;">
            <div style="font-size: 1.1em; font-weight: bold; color: #fff; margin-bottom: 4px;">
                {nombre}{badges_html}
            </div>
            <div style="font-size: 0.85em; color: #aaa;">
                <span style="color: #a55eea;">{raza}</span> | 
                <span style="color: #ffd700; font-weight: bold;">Nvl {nivel}</span> | 
                <span style="color: #ccc;">{clase}</span> |
                <span style="color: #888;">{rango}</span>
            </div>
        </div>
    """
    return html

def _render_loyalty_html(loyalty: int) -> str:
    """Renderiza indicador de lealtad."""
    color = "#e74c3c" if loyalty < 30 else "#f1c40f" if loyalty < 70 else "#2ecc71"
    return f"""
        <div style="text-align: center;">
            <div style="font-size: 0.8em; color: #aaa; margin-bottom: 2px;">Lealtad</div>
            <div style="color: {color}; font-weight: bold; font-size: 1.1em;">{loyalty}%</div>
            <div style="width: 100%; background: #333; height: 4px; border-radius: 2px; margin-top: 4px;">
                <div style="width: {loyalty}%; background: {color}; height: 4px; border-radius: 2px;"></div>
            </div>
        </div>
    """

def _render_location_html(char_obj: CommanderData) -> str:
    """Renderiza ubicación hidratada."""
    sheet = char_obj.sheet
    # La propiedad sheet ya inyectó la ubicación correcta en 'ubicacion_local'
    loc_text = sheet.estado.ubicacion.ubicacion_local
    
    return f"""
        <div style="font-size: 0.85em; color: #ccc; display: flex; align-items: center;">
            <span style="margin-right: 6px;">📍</span> {loc_text}
        </div>
    """

# --- COMPONENTES UI ---

@st.dialog("Expediente del Personal", width="large")
def view_character_dialog(char_dict: dict, player_id: int):
    """Muestra la ficha de personaje en un modal."""
    render_character_sheet(char_dict, player_id)


def render_faction_roster():
    from .state import get_player

    st.title("Personal de la Faccion")

    player = get_player()
    if not player:
        st.warning("Error de sesion.")
        return

    player_id = player.id
    player_credits = get_player_credits(player_id)

    # 1. Obtener personajes (Raw dicts)
    raw_characters = get_all_player_characters(player_id)
    
    # 2. Convertir a Objetos de Dominio (Hydration) para manejo robusto
    # Esto asegura que si faltan columnas, CommanderData maneje los defaults
    characters_objects = []
    for char_dict in raw_characters:
        try:
            characters_objects.append(CommanderData.from_dict(char_dict))
        except Exception:
            continue

    # Verificar si hay investigación en curso (bloqueo global)
    investigation_active = has_pending_investigation(player_id)
    investigating_target = get_investigating_target_info(player_id)

    # --- LÓGICA DE BIENVENIDA / STARTER PACK ---
    non_commander_count = sum(1 for c in characters_objects if not c.es_comandante)

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

    if not characters_objects:
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
        sort_by = st.selectbox("Ordenar por", ["Rango", "Clase", "Nombre", "Nivel", "Lealtad"])
    with col_filter:
        filter_role = st.selectbox("Filtrar por Rol", ["Todos"] + [r.value for r in CharacterRole])

    st.divider()

    # Aplicar filtros (sobre objetos)
    filtered_chars = characters_objects
    if filter_role != "Todos":
        # Acceso seguro a través del sheet hidratado
        filtered_chars = [c for c in filtered_chars if c.sheet.estado.rol_asignado == filter_role]

    # Aplicar orden (usando atributos directos del modelo SQL)
    if sort_by == "Nombre":
        filtered_chars.sort(key=lambda x: x.nombre)
    elif sort_by == "Nivel":
        filtered_chars.sort(key=lambda x: x.level, reverse=True)
    elif sort_by == "Lealtad":
        filtered_chars.sort(key=lambda x: x.loyalty, reverse=True)
    elif sort_by == "Clase":
        # Clase puede estar en JSON o ID, usamos el sheet para normalizar
        filtered_chars.sort(key=lambda x: x.sheet.progresion.clase)
    # Por defecto Rango/Orden de llegada se mantiene

    # --- LISTA DE PERSONAL (Layout de Filas) ---
    
    # Encabezados visuales simples
    cols_header = st.columns([3, 1, 1.2, 1.2, 1, 1])
    cols_header[0].caption("Identidad")
    cols_header[1].caption("Lealtad")
    cols_header[2].caption("Ubicación")
    cols_header[3].caption("Asignación")
    
    for char_obj in filtered_chars:
        char_id = char_obj.id
        is_commander = char_obj.es_comandante
        
        # Verificar si este personaje está siendo investigado
        is_being_investigated = (
            investigating_target and
            investigating_target.get("target_type") == "MEMBER" and
            investigating_target.get("target_id") == char_id
        )

        # Contenedor de la fila con estilo
        with st.container():
            # Definición de columnas: [Info, Lealtad, Ubicación, Rol/Misión, Ficha, Acciones]
            cols = st.columns([3, 1, 1.2, 1.2, 1, 1])
            
            # --- COL 1: Info Principal (HTML) ---
            with cols[0]:
                st.markdown(_render_character_info_html(char_obj, is_being_investigated), unsafe_allow_html=True)

            # --- COL 2: Lealtad (Visual) ---
            with cols[1]:
                st.markdown(_render_loyalty_html(char_obj.loyalty), unsafe_allow_html=True)

            # --- COL 3: Ubicación (Visual) ---
            with cols[2]:
                st.markdown(_render_location_html(char_obj), unsafe_allow_html=True)

            # --- COL 4: Selector de Rol ---
            with cols[3]:
                # Usamos el sheet para obtener el estado actual normalizado
                current_role = char_obj.sheet.estado.rol_asignado
                role_options = [r.value for r in CharacterRole]
                
                # Normalizar selección
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
                    disabled=is_commander # Bloquear cambio de rol al comandante
                )

                # Persistencia inmediata del cambio de rol
                if new_role != current_role and not is_commander:
                    # Recuperamos el dict crudo para el update (que espera dict o json)
                    # NOTA: Idealmente update_character_stats debería aceptar objetos, pero por ahora adaptamos.
                    stats = char_obj.stats_json
                    if "estado" not in stats: stats["estado"] = {}
                    stats["estado"]["rol_asignado"] = new_role
                    
                    update_character_stats(char_id, stats)
                    st.toast(f"Rol actualizado a {new_role}")
                    st.rerun()

            # --- COL 5: Ver Ficha (Dialog) ---
            with cols[4]:
                st.write("") # Spacer vertical
                if st.button("📄 Ficha", key=f"sheet_{char_id}", use_container_width=True):
                    # Pasamos el dict original o reconstruimos uno compatible
                    # UI components esperan dict con 'stats_json'
                    char_dict = char_obj.model_dump()
                    view_character_dialog(char_dict, player_id)

            # --- COL 6: Despedir / Investigar ---
            with cols[5]:
                st.write("") # Spacer vertical
                # Si es comandante no se puede despedir
                if is_commander:
                    st.button("⛔", disabled=True, key=f"no_fire_{char_id}", help="No puedes despedir al Comandante.")
                else:
                    # Lógica de Despido Segura (Popover)
                    with st.popover("👋", help="Gestionar Salida"):
                        st.markdown(f"**¿Despedir a {char_obj.nombre}?**")
                        st.caption("Esta acción es irreversible.")
                        if st.button("Confirmar Despido", key=f"confirm_fire_{char_id}", type="primary", use_container_width=True):
                             if dismiss_character(char_id, player_id):
                                 st.success("Personal despedido.")
                                 st.rerun()
                             else:
                                 st.error("Error al despedir.")
            
            # --- Investigar (Si aplica) ---
            knowledge_level = get_character_knowledge_level(char_id, player_id)
            if knowledge_level == KnowledgeLevel.UNKNOWN and not is_being_investigated and not investigation_active:
                 can_afford = player_credits >= INVESTIGATION_COST
                 if st.button(f"🔍 Investigar ({INVESTIGATION_COST} C)", key=f"btn_inv_row_{char_id}", disabled=not can_afford):
                     # Reconvertimos a dict para compatibilidad con handlers legacy
                     _handle_member_investigation(player_id, char_obj.model_dump(), player_credits)
            
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