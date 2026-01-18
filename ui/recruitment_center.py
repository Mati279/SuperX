# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine o IA.
"""

import streamlit as st
from typing import Dict, Any, List
from ui.state import get_player
# IMPORTANTE: Usamos el servicio de generación robusto (con IA y fallback)
from services.character_generation_service import generate_random_character_with_ai, RecruitmentContext
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from data.world_repository import queue_player_action, has_pending_investigation # NUEVA FUNCION
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION

# --- CONSTANTES ---
INVESTIGATION_COST = 150  # Costo por investigar antecedentes

def _generate_recruitment_pool(player_id: int, pool_size: int, existing_names: List[str], min_level: int = 1, max_level: int = 3) -> List[Dict[str, Any]]:
    """
    Genera una piscina de candidatos para reclutamiento.
    """
    candidates = []
    names_in_use = list(existing_names)

    # Contexto para el generador
    context = RecruitmentContext(
        player_id=player_id,
        min_level=min_level,
        max_level=max_level
    )

    for _ in range(pool_size):
        # 1. Generar datos crudos del personaje (Dict compatible con DB)
        char_data = generate_random_character_with_ai(
            context=context,
            existing_names=names_in_use
        )

        # 2. Extraer datos de forma segura desde stats_json
        stats = char_data.get("stats_json", {})
        
        nivel = stats.get("progresion", {}).get("nivel")
        if nivel is None: nivel = char_data.get("nivel", 1)

        raza = stats.get("taxonomia", {}).get("raza")
        if raza is None: raza = char_data.get("raza", "Desconocido")

        clase = stats.get("progresion", {}).get("clase")
        if clase is None: clase = char_data.get("clase", "Recluta")

        # 3. Calcular Costo
        atributos = stats.get("capacidades", {}).get("atributos", {})
        total_attrs = sum(atributos.values()) if atributos else 0
        costo = (nivel * 250) + (total_attrs * 5)
        if costo < 100: costo = 100

        # 4. Construir objeto candidato para la UI
        candidate = {
            "nombre": char_data["nombre"],
            "nivel": nivel,
            "raza": raza,
            "clase": clase,
            "costo": int(costo),
            "stats_json": stats,
            "investigado": False # Flag local para controlar reintentos en sesión
        }

        candidates.append(candidate)
        names_in_use.append(char_data["nombre"])

    return candidates


def _render_candidate_card(candidate: Dict[str, Any], index: int, player_credits: int, player_id: int, investigation_active: bool):
    """Renderiza la tarjeta de un candidato con todos sus detalles."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    
    # Rutas seguras a las capacidades
    capacidades = stats.get("capacidades", {})
    atributos = capacidades.get("atributos", {})
    habilidades = capacidades.get("habilidades", {})
    feats = capacidades.get("feats", [])

    can_afford = player_credits >= candidate["costo"]
    can_afford_investigation = player_credits >= INVESTIGATION_COST
    
    # Check si ya fue investigado (flag en session)
    already_investigated = candidate.get("investigado", False)
    
    border_color = "#26de81" if can_afford else "#ff6b6b"

    with st.container(border=True):
        # --- Header ---
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

        # --- Bio ---
        bio_text = bio.get('bio_superficial') or bio.get('biografia_corta') or "Sin datos biométricos."
        if already_investigated:
             st.info(f"🕵️ INTELIGENCIA: {bio.get('bio_conocida', 'Datos adicionales revelados.')}")
        else:
             st.caption(f"*{bio_text}*")

        # --- Atributos ---
        with st.expander("Ver Atributos", expanded=False):
            if atributos:
                cols = st.columns(3)
                for i, (attr, value) in enumerate(atributos.items()):
                    with cols[i % 3]:
                        color = "#26de81" if value >= 12 else "#888"
                        st.markdown(f"<span style='color:{color};'>{attr.upper()}: **{value}**</span>", unsafe_allow_html=True)
            else:
                st.write("Datos de atributos no disponibles.")

        # --- Habilidades (Top 5 con colores) ---
        with st.expander("Ver Habilidades", expanded=False):
            if habilidades:
                sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])
                for skill, val in sorted_skills[:5]:
                    if val >= 25: color = "#ffd700" 
                    elif val >= 18: color = "#45b7d1"
                    elif val >= 12: color = "#26de81"
                    else: color = "#888"
                    st.markdown(f"<span style='color:{color};'>{skill}: **{val}**</span>", unsafe_allow_html=True)
            else:
                st.caption("Sin habilidades especializadas.")

        # --- Rasgos/Feats ---
        if feats:
            with st.expander("Ver Rasgos", expanded=False):
                for feat in feats:
                    st.markdown(f"- {feat}")

        st.markdown("---")

        # --- Footer: Acciones (Investigar / Contratar) ---
        col_cost, col_inv, col_recruit = st.columns([2, 1, 1])

        with col_cost:
            cost_color = "#26de81" if can_afford else "#ff6b6b"
            st.markdown(f"""
                <div style="text-align: center;">
                    <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                    <span style="font-size: 1.8em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                </div>
            """, unsafe_allow_html=True)

        # Botón Investigar
        with col_inv:
            # Lógica de deshabilitado
            disable_inv = False
            inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."
            
            if not can_afford_investigation:
                disable_inv = True
                inv_help = "Créditos insuficientes."
            elif investigation_active:
                disable_inv = True
                inv_help = "Ya hay una investigación en curso. Espere al reporte."
            elif already_investigated:
                disable_inv = True
                inv_help = "Objetivo ya investigado con éxito."

            if st.button("🕵️ Investigar", key=f"inv_{index}", disabled=disable_inv, help=inv_help, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, force_success=False)

            # --- DEBUG: Botón Investigación Exitosa ---
            # Solo visible si se activa modo debug global o para todos (aquí lo ponemos siempre para el usuario)
            if st.checkbox("Debug Mode", key=f"dbg_{index}", value=False):
                 if st.button("✅ Force Success", key=f"force_{index}", use_container_width=True):
                      _handle_investigation(player_id, candidate, player_credits, force_success=True)

        # Botón Contratar
        with col_recruit:
            if can_afford:
                if st.button(f"CONTRATAR", key=f"recruit_{index}", type="primary", use_container_width=True):
                    _process_recruitment(player_id, candidate, player_credits)
            else:
                st.button("SIN FONDOS", key=f"recruit_{index}", disabled=True, use_container_width=True)


def _handle_investigation(player_id: int, candidate: Dict[str, Any], current_credits: int, force_success: bool = False):
    """Maneja la lógica de cobro y encolado de investigación."""
    if update_player_credits(player_id, current_credits - INVESTIGATION_COST):
         # Datos reales ocultos
         stats = candidate.get("stats_json", {})
         bio = stats.get("bio", {})
         real_bio = bio.get('bio_profunda') or bio.get('bio_conocida') or "Sin secretos aparentes."
         
         # Construir comando
         force_flag = "[DEBUG_FORCE_SUCCESS]" if force_success else ""
         cmd = f"Inicia protocolo de investigación de antecedentes (Investigar) sobre el candidato '{candidate['nombre']}'. ID AUTORIZACION: {player_id}. {force_flag} (DATOS OCULTOS REALES: {real_bio})"
         
         if queue_player_action(player_id, cmd):
             if force_success:
                 st.toast(f"✅ [DEBUG] Éxito garantizado para {candidate['nombre']}.")
                 candidate["investigado"] = True # Marcamos localmente como investigado
             else:
                 st.toast(f"⏳ Solicitud enviada. -{INVESTIGATION_COST} C.")
             
             st.rerun()
         else:
             st.error("Error al encolar orden. Se han reembolsado los créditos.")
             update_player_credits(player_id, current_credits)
    else:
         st.error("Error en transacción financiera.")


def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """Procesa la transacción de reclutamiento."""
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
            st.success(f"¡{candidate['nombre']} se ha unido a tu facción!")
            if 'recruitment_pool' in st.session_state:
                st.session_state.recruitment_pool = [
                    c for c in st.session_state.recruitment_pool if c['nombre'] != candidate['nombre']
                ]
            st.rerun()
        else:
            st.error("Error crítico al procesar el reclutamiento.")

    except Exception as e:
        st.error(f"Error inesperado: {e}")


def show_recruitment_center():
    """Página principal del Centro de Reclutamiento."""

    st.title("Centro de Reclutamiento")
    st.caption("Encuentra y contrata nuevos operativos para tu facción")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("Error de sesión.")
        return

    player_id = player.id
    player_credits = get_player_credits(player_id)
    
    # Check global de investigación activa
    investigation_active = has_pending_investigation(player_id)

    # --- Panel de Créditos ---
    col_credits, col_refresh = st.columns([3, 1])

    with col_credits:
        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 16px;
                border-radius: 10px;
                border: 1px solid #333;
            ">
                <span style="color: #888; font-size: 0.85em;">CRÉDITOS DISPONIBLES</span><br>
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
                st.error("Error al actualizar créditos.")

    if investigation_active:
        st.info("🕒 Hay una investigación de antecedentes en curso. Espere al próximo ciclo para iniciar otra.")

    st.markdown("---")

    # --- Filtros ---
    with st.expander("Opciones de Búsqueda"):
        col_min, col_max = st.columns(2)
        with col_min:
            min_level = st.number_input("Nivel Mínimo", min_value=1, max_value=10, value=st.session_state.get('recruit_min_level', 1))
        with col_max:
            max_level = st.number_input("Nivel Máximo", min_value=1, max_value=10, value=st.session_state.get('recruit_max_level', 3))

        if max_level < min_level: max_level = min_level

        if st.button("Aplicar Filtros"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.session_state.recruit_min_level = min_level
            st.session_state.recruit_max_level = max_level
            st.rerun()

    # --- Generación ---
    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        all_chars = get_all_characters_by_player_id(player_id)
        existing_names = []
        if all_chars:
            for c in all_chars:
                if isinstance(c, dict): existing_names.append(c.get('nombre', ''))
                elif hasattr(c, 'nombre'): existing_names.append(c.nombre)

        min_lvl = st.session_state.get('recruit_min_level', 1)
        max_lvl = st.session_state.get('recruit_max_level', 3)

        with st.spinner("Contactando red de informantes..."):
            st.session_state.recruitment_pool = _generate_recruitment_pool(
                player_id=player_id,
                pool_size=3,
                existing_names=existing_names,
                min_level=min_lvl,
                max_level=max_lvl
            )

    candidates = st.session_state.recruitment_pool

    # --- Renderizado ---
    if not candidates:
        st.info("No hay candidatos disponibles.")
        return

    st.subheader(f"Candidatos Disponibles ({len(candidates)})")

    cols = st.columns(len(candidates))
    for i, candidate in enumerate(candidates):
        with cols[i]:
            _render_candidate_card(candidate, i, player_credits, player_id, investigation_active)

    st.markdown("---")
    st.caption("Los candidatos son generados proceduralmente por la IA central.")