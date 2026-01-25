# ui/recruitment_center.py (Completo)
"""
Centro de Reclutamiento Galáctico - Contratación de nuevos operativos.

Sistema de Reclutamiento v3 (Asíncrono):
- Solicitud de búsqueda encolada.
- Generación diferida al Tick.
- Persistencia unificada.
Debug v2.3: Validación de IA en cabecera y disparador manual de emergencia para pruebas.
Debug v2.4: Fix error en actualización de columnas SQL al reclutar.
Debug v2.5: Herramientas de investigación determinista implementadas.
Actualizado v5.1.8: Fuente de Verdad Unificada (SQL Knowledge System).
Actualizado v5.1.9: Visualización estrictamente basada en KnowledgeLevel.
Fix v5.2.0: Corrección de falso positivo en "already_investigated" por comparación de strings en Enum.
Fix v5.2.1: Eliminación de constante de ubicación obsoleta (Refactorización v4.3.1).
Refactorizado V10: Integración con coordenadas SQL (get_player_base_coordinates) y limpieza de lógica local.
"""

import streamlit as st
from typing import Dict, Any, Optional

from ui.state import get_player
from data.database import get_service_container
from data.player_repository import get_player_credits, update_player_credits
# Importamos recruit_candidate_db para manejar la conversion de datos al DB
from data.character_repository import (
    update_character,
    set_character_knowledge_level,
    get_character_knowledge_level, # Nueva importación para Source of Truth
    recruit_candidate_db
)
from data.recruitment_repository import (
    get_recruitment_candidates,
    set_candidate_tracked,
    get_tracked_candidate,
    set_investigation_state
)
from data.world_repository import (
    queue_player_action,
    has_pending_investigation,
    has_pending_search,
    get_world_state,
    get_investigating_target_info
)
# TAREA 4: Importamos el nuevo helper y eliminamos las funciones viejas
from data.planet_repository import get_player_base_coordinates

from data.log_repository import log_event
# Modificación: Eliminada DEFAULT_RECRUIT_LOCATION por ser obsoleta en v4.3.1
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS
from core.character_engine import BIO_ACCESS_UNKNOWN, BIO_ACCESS_KNOWN
from core.models import KnowledgeLevel # Importación de Enum
# Importamos la nueva función de análisis
from core.recruitment_logic import process_recruitment, analyze_candidates_value


# --- CONSTANTES ---
SEARCH_COST = 50
INVESTIGATION_COST = 150
CANDIDATE_LIFESPAN_TICKS = 4

# Colores para habilidades
COLOR_SKILL_GRAY = "#888888"
COLOR_SKILL_GREEN = "#26de81"
COLOR_SKILL_BLUE = "#45b7d1"
COLOR_SKILL_GOLD = "#ffd700"

# Abreviaturas de Atributos
ATTR_ABBREVIATIONS = {
    "fuerza": "FUE",
    "agilidad": "AGI",
    "tecnica": "TEC",
    "intelecto": "INT",
    "voluntad": "VOL",
    "presencia": "PRE"
}

# TAREA 4: Función local _get_active_base_location ELIMINADA.
# Se usa directamente data.planet_repository.get_player_base_coordinates


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

    # Ordenar por valor descendente
    sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])
    
    # Si count es > 0, limitamos. Si es 0 o negativo, mostramos todas.
    if count > 0:
        sorted_skills = sorted_skills[:count]

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
    current_tick: int,
    recommendation: Optional[str] = None
):
    """Renderiza la tarjeta de un candidato."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    atributos = stats.get("capacidades", {}).get("atributos", {})
    habilidades = stats.get("capacidades", {}).get("habilidades", {})
    rasgos = stats.get("comportamiento", {}).get("rasgos_personalidad", [])

    # Extraer datos basicos
    nivel = stats.get("progresion", {}).get("nivel", 1)
    raza = stats.get("taxonomia", {}).get("raza", "Desconocido")
    clase = stats.get("progresion", {}).get("clase", "Recluta")
    
    # Extraer edad
    edad = bio.get("edad", "??")

    # Estados (inyectados por el adaptador del repositorio)
    costo = candidate.get("costo", 100)
    can_afford = player_credits >= costo
    can_afford_investigation = player_credits >= INVESTIGATION_COST
    is_tracked = candidate.get("is_tracked", False)
    is_being_investigated = candidate.get("is_being_investigated", False)
    
    # FIX: Fuente de verdad SQL ÚNICA
    # Ya no miramos flags en JSON, solo la tabla character_knowledge
    current_knowledge_level = get_character_knowledge_level(candidate['id'], player_id)
    
    # FIX BUG V5.2.0: Comparación explícita.
    # El operador >= con strings ("desconocido" > "conocido") causaba falsos positivos.
    # Ahora verificamos explícitamente si está en los niveles que permiten ver info completa.
    already_investigated = current_knowledge_level in [KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND]
    
    # Datos de lógica interna (para descuentos/estado tracking)
    investigation_outcome = candidate.get("investigation_outcome")
    discount_applied = candidate.get("discount_applied", False)

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

        # Badge de conocimiento
        if already_investigated:
            badges_html += '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #45b7d1;">CONOCIDO</span>'
        else:
            badges_html += '<span style="background: rgba(255,107,107,0.15); color: #ff6b6b; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #ff6b6b;">DESCONOCIDO</span>'

        # Render Header
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
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85em; margin-top: 4px;">
                    <div><span style="color: #a55eea;">{raza}</span> | <span style="color: #f9ca24;">Nivel {nivel}</span> | <span style="color: #ccc;">{edad} años</span></div>
                    <div style="color: {'#ff6b6b' if ticks_left <= 1 else '#888'};">Expira en: {max(0, ticks_left)} Tick{'s' if ticks_left != 1 else ''}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # --- SMART ADVISOR VISUALIZATION ---
        if recommendation:
            st.info(recommendation, icon="💡")

        # Bio
        if already_investigated:
            bio_text = bio.get('bio_conocida', bio.get('bio_superficial', 'Datos revelados.'))
            st.success(f"INTELIGENCIA: {bio_text}")
            if discount_applied:
                st.caption("Vulnerabilidad explotable detectada (Descuento 30% aplicado).")
        else:
            bio_text = bio.get('bio_superficial') or bio.get('biografia_corta') or "Sin datos biometricos."
            st.caption(f"*{bio_text}*")

        # Atributos (Resumidos)
        st.markdown("**Atributos:**")
        if atributos:
            cols = st.columns(3)
            for i, (attr, value) in enumerate(atributos.items()):
                with cols[i % 3]:
                    color = _get_skill_color(value)
                    short_name = ATTR_ABBREVIATIONS.get(attr.lower(), attr[:3].upper())
                    st.markdown(f"<span style='color:{color};'>{short_name}: **{value}**</span>", unsafe_allow_html=True)
        else:
            st.caption("Datos no disponibles.")

        st.write("") # Espaciador

        # Habilidades (Lógica dinámica: Top 5 si Desconocido, Todas si Conocido)
        skill_count = 0 if already_investigated else 5
        label_skills = "Ver Todas las Habilidades" if already_investigated else "Ver Habilidades (Top 5)"
        
        with st.expander(label_skills, expanded=False):
             _render_top_skills(habilidades, count=skill_count)

        # Rasgos de personalidad
        if already_investigated and rasgos:
            traits_html = " ".join([f'<span style="display: inline-block; padding: 2px 8px; margin: 2px; border-radius: 10px; background: rgba(165,94,234,0.15); color: #a55eea; font-size: 0.75em; border: 1px solid #a55eea40;">{t}</span>' for t in rasgos])
            st.markdown(f"**Personalidad:** {traits_html}", unsafe_allow_html=True)
        elif not already_investigated:
            st.caption("*Rasgos de personalidad: Desconocidos*")


        # --- Visualizacion del Costo ---
        cost_color = "#26de81" if can_afford else "#ff6b6b"
        
        cost_display_html = ""
        if discount_applied:
             cost_display_html = f'<span style="color: #ffd700; font-weight: bold; font-size: 1.1em;">{costo:,} C</span> (Oferta)'
        else:
             cost_display_html = f'<span style="color: {cost_color}; font-weight: bold; font-size: 1.1em;">{costo:,} C</span>'

        st.markdown(f"""
            <div style="text-align: right; margin-top: 10px; margin-bottom: -12px; font-size: 0.9em; color: #aaa;">
                Costo de contratacion: {cost_display_html}
            </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # --- HERRAMIENTAS DE DEBUG (Solo Desarrollo) ---
        # Permite forzar resultados de investigación para probar flujos
        with st.expander("🛠️ DEBUG: Forzar Resultado", expanded=False):
            d1, d2, d3, d4 = st.columns(4)
            debug_disabled = not can_afford_investigation or investigation_active or already_investigated or is_being_investigated
            
            if d1.button("✅ Éxito", key=f"d_suc_{candidate['id']}", disabled=debug_disabled, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, debug_outcome="SUCCESS")
            
            if d2.button("🌟 Crítico", key=f"d_csuc_{candidate['id']}", disabled=debug_disabled, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_SUCCESS")
            
            if d3.button("❌ Fallo", key=f"d_fail_{candidate['id']}", disabled=debug_disabled, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, debug_outcome="FAIL")
            
            if d4.button("💀 Pifia", key=f"d_cfail_{candidate['id']}", disabled=debug_disabled, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_FAIL")

        # --- Footer Actions ---
        col_track, col_inv, col_recruit = st.columns([0.7, 1.5, 2])

        # 1. Boton de Seguimiento (Icono Ojo)
        with col_track:
            track_icon = "👁"
            track_help = "Dejar de seguir" if is_tracked else "Seguir (Evita expiracion)"
            btn_type = "primary" if is_tracked else "secondary"

            if st.button(track_icon, key=f"track_{candidate['id']}", help=track_help, use_container_width=True, type=btn_type):
                if is_tracked:
                    from data.recruitment_repository import untrack_candidate
                    untrack_candidate(player_id, candidate['id'])
                else:
                    set_candidate_tracked(player_id, candidate['id'])
                st.rerun()

        # 2. Boton Investigar
        with col_inv:
            disable_inv = False
            inv_label = "🕵️‍♂️ Investigar"
            inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."
            button_type = "secondary"

            if is_being_investigated:
                disable_inv = True
                inv_label = "🕵️‍♂️ Investigando..."
                inv_help = "Investigacion en curso. Resultado en el proximo Tick."
                button_type = "primary" # Azul
            elif not can_afford_investigation:
                disable_inv = True
                inv_help = "Creditos insuficientes."
            elif investigation_active:
                disable_inv = True
                inv_help = "Otra investigacion en curso. Espere al reporte."
            elif already_investigated:
                disable_inv = True
                inv_label = "🕵️‍♂️ Investigado"
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

        # 3. Boton Contratar (Azul / Primary)
        with col_recruit:
            if can_afford:
                if st.button("CONTRATAR", key=f"recruit_{candidate['id']}", type="primary", use_container_width=True):
                    _process_recruitment_ui(player_id, candidate, player_credits)
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
        if debug_outcome:
            st.toast(f"Investigación (DEBUG: {debug_outcome}) iniciada.", icon="🛠️")
        else:
            st.toast(f"Investigacion iniciada. -{INVESTIGATION_COST} C.", icon="🕵️")
        st.rerun()
    else:
        st.error("Error al encolar orden.")
        # Rollback
        update_player_credits(player_id, current_credits)
        set_investigation_state(candidate['id'], False)


def _process_recruitment_ui(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """
    Procesa el reclutamiento final (Actualizacion de Estado).
    Refactor V10: Incluye ubicación real de la base del jugador.
    """
    try:
        # TAREA 4: Obtener ubicación desde la Fuente de Verdad (SQL)
        base_location = get_player_base_coordinates(player_id)

        new_credits, update_data = process_recruitment(
            player_id,
            player_credits,
            candidate,
            base_location_data=base_location
        )
        
        # Obtenemos el nivel inicial calculado (puede venir de reglas de contratación o default)
        initial_knowledge = update_data.pop("initial_knowledge_level", None)

        if not update_player_credits(player_id, new_credits):
            st.error("Error en transaccion financiera.")
            return

        # CORRECCION: Usar recruit_candidate_db para manejar el mapeo de columnas SQL vs JSON
        # Evita error "Error actualizando datos" por pasar columnas invalidas (estado, ubicacion)
        updated_char = recruit_candidate_db(candidate["id"], update_data)

        if updated_char:
            # Si se definió un nivel inicial explícito (ej. reclutamiento VIP), se asegura aquí.
            # En la mayoría de los casos de contratación estándar, esto ya está manejado, 
            # pero recruit_candidate_db no toca character_knowledge por defecto, así que esto es seguro.
            if initial_knowledge:
                set_character_knowledge_level(candidate["id"], player_id, initial_knowledge)

            st.success(f"¡{candidate['nombre']} se ha unido a tu faccion!")
            log_event(f"RECLUTAMIENTO: {candidate['nombre']} contratado (ID: {candidate['id']}).", player_id)
            st.rerun()
        else:
            st.error("Error critico al actualizar el estado del personal.")

    except ValueError as ve:
        st.error(str(ve))
    except Exception as e:
        st.error(f"Error inesperado: {e}")


def _handle_search_request_async(player_id: int, player_credits: int):
    """
    Maneja la solicitud de buscar nuevos candidatos de forma ASÍNCRONA.
    """
    if player_credits < SEARCH_COST:
        st.error("Créditos insuficientes para iniciar búsqueda.")
        return

    if not update_player_credits(player_id, player_credits - SEARCH_COST):
        st.error("Error en transacción financiera.")
        return

    cmd = "[INTERNAL_SEARCH_CANDIDATES]"
    
    if queue_player_action(player_id, cmd):
        log_event(f"RECLUTAMIENTO: Solicitud de búsqueda enviada a la red. Costo: {SEARCH_COST} C.", player_id)
        st.toast(f"Solicitud enviada. -{SEARCH_COST} C.", icon="📡")
        st.rerun()
    else:
        update_player_credits(player_id, player_credits)
        st.error("Error al conectar con la red de reclutamiento.")


def show_recruitment_center():
    """Pagina principal del Centro de Reclutamiento."""

    st.title("Centro de Reclutamiento")
    
    player = get_player()
    if not player:
        st.warning("Error de sesion.")
        return
    player_id = player.id

    # 1. VALIDACIÓN DE CONECTIVIDAD IA (NUEVO)
    container = get_service_container()
    ai_status = container.is_ai_available()
    if ai_status:
        st.success("🛰️ Red de Inteligencia Gemini activa. Generación de perfiles de alta fidelidad disponible.", icon="✅")
    else:
        st.warning("📡 Red de Inteligencia en modo local. Los nuevos perfiles podrían ser genéricos hasta restablecer conexión.", icon="⚠️")

    # Estado del mundo
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)

    # Estados de bloqueo
    investigation_active = has_pending_investigation(player_id)
    search_pending = has_pending_search(player_id)
    investigating_target = get_investigating_target_info(player_id)

    candidates = get_recruitment_candidates(player_id)
    player_credits = get_player_credits(player_id)

    # Header con creditos y boton de busqueda
    col_credits, col_refresh = st.columns([3, 1])

    with col_credits:
        st.metric("CRÉDITOS DISPONIBLES", f"{player_credits:,} C")

    with col_refresh:
        st.write("")
        if search_pending:
            st.info("📡 Búsqueda en curso")
            # 2. TRIGGER MANUAL DE EMERGENCIA (NUEVO)
            if st.button("⚡ Forzar Generación (Test)", help="Solo para depuración: Genera candidatos inmediatamente sin esperar al Tick."):
                from services.character_generation_service import generate_character_pool
                try:
                    with st.spinner("Generando pool de emergencia..."):
                        # TAREA 4: Obtener ubicación de la base activa para los candidatos desde SQL
                        base_loc = get_player_base_coordinates(player_id)
                        
                        generate_character_pool(
                            player_id,
                            pool_size=3,
                            location_planet_id=base_loc.get("planet_id"),
                            location_system_id=base_loc.get("system_id"),
                            location_sector_id=base_loc.get("sector_id")
                        )
                    st.success("Pool generado manualmente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error en trigger manual: {e}")
        else:
            can_search = player_credits >= SEARCH_COST
            if st.button(f"Buscar Nuevos\n({SEARCH_COST} C)", disabled=not can_search, type="primary", use_container_width=True):
                _handle_search_request_async(player_id, player_credits)

    if investigation_active:
        target_name = investigating_target.get("target_name", "un objetivo") if investigating_target else "un objetivo"
        st.info(f"🕵️ **Investigación en curso** sobre **{target_name}**.")

    st.markdown("---")

    if not candidates:
        if search_pending:
            st.markdown("""
                <div style="text-align: center; padding: 60px 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 15px; border: 2px dashed #45b7d1;">
                    <div style="font-size: 4em; margin-bottom: 20px; animation: pulse 2s infinite;">📡</div>
                    <h3 style="color: #45b7d1; margin-bottom: 10px;">Enlace de Reclutamiento Activo</h3>
                    <p style="color: #ccc;">La red está procesando tu solicitud. Los perfiles de los candidatos llegarán en el próximo ciclo.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("No hay candidatos disponibles. Utiliza el botón de búsqueda.")
    else:
        recommendations = analyze_candidates_value(player_id, candidates)
        tracked = get_tracked_candidate(player_id)
        st.subheader(f"Candidatos Disponibles ({len(candidates)})")
        if tracked: st.caption(f"(Siguiendo: **{tracked['nombre']}**)")

        cols = st.columns(4)
        for i, candidate in enumerate(candidates):
            col_idx = i % 4
            if i > 0 and col_idx == 0:
                cols = st.columns(4)
            cand_recommendation = recommendations.get(candidate['id'])
            with cols[col_idx]:
                _render_candidate_card(candidate, player_credits, player_id, investigation_active, current_tick, recommendation=cand_recommendation)

    st.markdown("---")
    st.caption(f"Los candidatos expiran despues de {CANDIDATE_LIFESPAN_TICKS} ciclos si no son reclutados o seguidos.")