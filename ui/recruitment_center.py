# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine o IA.
"""

import streamlit as st
import re
from typing import Dict, Any, List
from ui.state import get_player
from services.character_generation_service import generate_random_character_with_ai, RecruitmentContext
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from data.world_repository import queue_player_action, has_pending_investigation
from data.database import get_supabase
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION

# --- CONSTANTES ---
INVESTIGATION_COST = 150
CRITICAL_SUCCESS_DISCOUNT = 0.30  # 30% descuento

def _get_system_logs(player_id: int, limit: int = 10):
    """Recupera logs recientes para buscar resultados de investigación."""
    try:
        db = get_supabase()
        response = db.table("game_logs")\
            .select("event_description")\
            .eq("player_id", player_id)\
            .order("created_at", desc=True)\
            .limit(limit)\
            .execute()
        return response.data if response.data else []
    except Exception:
        return []

def _update_pool_from_investigations(player_id: int):
    """
    Escanea logs recientes para actualizar el estado de los candidatos en sesión.
    Busca patrones: SYSTEM_EVENT: INVESTIGATION_RESULT | target={name} | outcome={code}
    """
    if 'recruitment_pool' not in st.session_state:
        return

    logs = _get_system_logs(player_id, limit=20)
    
    # Mapeo de resultados encontrados
    results_map = {} 
    
    for log in logs:
        text = log.get("event_description", "")
        if "SYSTEM_EVENT: INVESTIGATION_RESULT" in text:
            # Parsear target y outcome
            match = re.search(r"target=(.*?) \| outcome=(.*?)$", text)
            if match:
                target = match.group(1).strip()
                outcome = match.group(2).strip()
                # Solo guardamos el más reciente si hay duplicados (por el orden desc)
                if target not in results_map:
                    results_map[target] = outcome

    # Aplicar efectos a la piscina
    # Iteramos con índice para poder borrar si es necesario
    indices_to_remove = []
    
    for i, candidate in enumerate(st.session_state.recruitment_pool):
        name = candidate["nombre"]
        
        if name in results_map:
            outcome = results_map[name]
            
            # Evitar re-procesar si ya tiene el flag (excepto fail que permite retry)
            if candidate.get("last_outcome") == outcome:
                continue
                
            candidate["last_outcome"] = outcome # Marcamos para no repetir lógica
            
            if outcome == "CRITICAL_SUCCESS":
                candidate["investigado"] = True
                candidate["discounted"] = True
                # Aplicar descuento si no se aplicó
                if not candidate.get("original_cost"):
                    candidate["original_cost"] = candidate["costo"]
                    candidate["costo"] = int(candidate["costo"] * (1 - CRITICAL_SUCCESS_DISCOUNT))
                
            elif outcome == "SUCCESS":
                candidate["investigado"] = True
                # Solo bio, sin descuento
                
            elif outcome == "CRITICAL_FAILURE":
                indices_to_remove.append(i)
                st.toast(f"❌ {name} ha retirado su solicitud tras detectar la investigación.")
                
            elif outcome == "FAILURE":
                candidate["investigado"] = False # Permite reintentar
                # No hacemos nada más, el botón se reactiva

    # Eliminar candidatos (en orden inverso para no romper índices)
    for i in sorted(indices_to_remove, reverse=True):
        del st.session_state.recruitment_pool[i]


def _generate_recruitment_pool(player_id: int, pool_size: int, existing_names: List[str], min_level: int = 1, max_level: int = 3) -> List[Dict[str, Any]]:
    candidates = []
    names_in_use = list(existing_names)
    context = RecruitmentContext(player_id=player_id, min_level=min_level, max_level=max_level)

    for _ in range(pool_size):
        char_data = generate_random_character_with_ai(context=context, existing_names=names_in_use)
        stats = char_data.get("stats_json", {})
        
        nivel = stats.get("progresion", {}).get("nivel")
        if nivel is None: nivel = char_data.get("nivel", 1)

        raza = stats.get("taxonomia", {}).get("raza")
        if raza is None: raza = char_data.get("raza", "Desconocido")

        clase = stats.get("progresion", {}).get("clase")
        if clase is None: clase = char_data.get("clase", "Recluta")

        atributos = stats.get("capacidades", {}).get("atributos", {})
        total_attrs = sum(atributos.values()) if atributos else 0
        costo = (nivel * 250) + (total_attrs * 5)
        if costo < 100: costo = 100

        candidate = {
            "nombre": char_data["nombre"],
            "nivel": nivel,
            "raza": raza,
            "clase": clase,
            "costo": int(costo),
            "stats_json": stats,
            "investigado": False,
            "discounted": False
        }
        candidates.append(candidate)
        names_in_use.append(char_data["nombre"])

    return candidates


def _render_candidate_card(candidate: Dict[str, Any], index: int, player_credits: int, player_id: int, investigation_active: bool):
    """Renderiza la tarjeta de un candidato con todos sus detalles."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    
    capacidades = stats.get("capacidades", {})
    atributos = capacidades.get("atributos", {})
    habilidades = capacidades.get("habilidades", {})
    feats = capacidades.get("feats", [])

    can_afford = player_credits >= candidate["costo"]
    can_afford_investigation = player_credits >= INVESTIGATION_COST
    
    already_investigated = candidate.get("investigado", False)
    is_discounted = candidate.get("discounted", False)
    
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
             st.success(f"🕵️ DATOS REVELADOS: {bio.get('bio_conocida', 'Perfil psicológico detallado disponible.')}")
             if is_discounted:
                 st.caption("✅ Puntos de influencia detectados (Descuento aplicado).")
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

        # --- Habilidades ---
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

        # --- Rasgos ---
        if feats:
            with st.expander("Ver Rasgos", expanded=False):
                for feat in feats:
                    st.markdown(f"- {feat}")

        st.markdown("---")

        # --- Footer: Acciones ---
        col_cost, col_inv, col_recruit = st.columns([2, 1, 1])

        with col_cost:
            cost_color = "#26de81" if can_afford else "#ff6b6b"
            
            if is_discounted and candidate.get("original_cost"):
                # Mostrar precio tachado y nuevo
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                        <span style="text-decoration: line-through; color: #888; font-size: 1.2em;">{candidate['original_cost']:,} C</span>
                        <span style="font-size: 1.8em; font-weight: bold; color: #ffd700;"> {candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                        <span style="font-size: 1.8em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)

        # Botón Investigar
        with col_inv:
            disable_inv = False
            inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."
            
            if not can_afford_investigation:
                disable_inv = True
                inv_help = "Créditos insuficientes."
            elif investigation_active:
                disable_inv = True
                inv_help = "Ya hay una investigación en curso."
            elif already_investigated:
                disable_inv = True
                inv_help = "Objetivo ya investigado con éxito."

            if st.button("🕵️ Investigar", key=f"inv_{index}", disabled=disable_inv, help=inv_help, use_container_width=True):
                 _handle_investigation(player_id, candidate, player_credits, force_success=False)

            # DEBUG
            if st.checkbox("Debug", key=f"dbg_{index}", value=False):
                 if st.button("✅ Force", key=f"force_{index}", use_container_width=True):
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
         stats = candidate.get("stats_json", {})
         bio = stats.get("bio", {})
         real_bio = bio.get('bio_profunda') or bio.get('bio_conocida') or "Sin secretos aparentes."
         
         force_flag = "[DEBUG_FORCE_SUCCESS]" if force_success else ""
         # Pasamos 'force_success' si es True para el parámetro de la tool también
         force_param = " force_success=True" if force_success else ""
         
         cmd = f"Inicia protocolo de investigación de antecedentes sobre '{candidate['nombre']}'. ID AUTORIZACION: {player_id}. {force_flag} (DATA: {real_bio})"
         
         # Si es force, podemos intentar meterlo en la cola de una forma que la IA lo entienda o simplemente confiar en el prompt
         if queue_player_action(player_id, cmd):
             st.toast(f"⏳ Solicitud enviada. -{INVESTIGATION_COST} C.")
             st.rerun()
         else:
             st.error("Error al encolar orden.")
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
    
    # 1. Actualizar estado basado en logs recientes (Sync asíncrono)
    _update_pool_from_investigations(player_id)
    
    player_credits = get_player_credits(player_id)
    investigation_active = has_pending_investigation(player_id)

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
        st.info("🕒 Investigación en curso...")

    st.markdown("---")

    # Filtros
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

    # Generación
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