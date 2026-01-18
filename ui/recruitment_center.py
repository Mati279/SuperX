# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine o IA.

Sistema de Investigacion:
- Solo una investigacion a la vez por jugador
- Cuesta 150 creditos y tarda 1 Tick
- Resultados: Exito Critico (bio + 30% desc), Exito (bio), Fallo (reintentar), Pifia (desaparece)
"""

import streamlit as st
import re
from typing import Dict, Any, List, Optional
from ui.state import get_player
from services.character_generation_service import generate_random_character_with_ai, RecruitmentContext
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from data.world_repository import queue_player_action, has_pending_investigation, get_world_state
from data.database import get_supabase
from data.log_repository import log_event
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION
from core.character_engine import (
    BIO_ACCESS_UNKNOWN,
    BIO_ACCESS_KNOWN,
    BIO_ACCESS_DEEP,
)

# --- CONSTANTES ---
INVESTIGATION_COST = 150
CRITICAL_SUCCESS_DISCOUNT = 0.30
CANDIDATE_LIFESPAN_TICKS = 3  # Duracion de un candidato en el roster

# --- COLORES PARA HABILIDADES (escala de la ficha) ---
COLOR_SKILL_GRAY = "#888888"   # < 8 (Basico)
COLOR_SKILL_GREEN = "#26de81"  # 8-12 (Competente)
COLOR_SKILL_BLUE = "#45b7d1"   # 13-16 (Profesional)
COLOR_SKILL_GOLD = "#ffd700"   # > 16 (Elite)


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


def _get_system_logs(player_id: int, limit: int = 15):
    """Recupera logs recientes para buscar resultados de investigacion."""
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


def _get_investigating_target(player_id: int) -> Optional[str]:
    """
    Determina cual candidato esta siendo investigado activamente.
    Retorna el nombre del candidato o None si no hay investigacion activa.
    """
    try:
        db = get_supabase()
        response = db.table("action_queue")\
            .select("action_text")\
            .eq("player_id", player_id)\
            .eq("status", "PENDING")\
            .execute()

        if not response.data:
            return None

        for action in response.data:
            text = action.get("action_text", "")
            # Buscar el nombre del objetivo en el comando
            match = re.search(r"sobre '([^']+)'", text)
            if match and "investigación" in text.lower():
                return match.group(1)
        return None
    except Exception:
        return None


def _update_pool_from_investigations(player_id: int):
    """
    Sincroniza el estado visual de los candidatos con los resultados de la IA (Logs).
    Actualiza el nivel de acceso cuando la investigacion es exitosa.
    """
    if 'recruitment_pool' not in st.session_state:
        return

    logs = _get_system_logs(player_id)
    results_map = {}

    # Parsear logs: "SYSTEM_EVENT: INVESTIGATION_RESULT | target={name} | outcome={code}"
    for log in logs:
        text = log.get("event_description", "")
        if "SYSTEM_EVENT: INVESTIGATION_RESULT" in text:
            match = re.search(r"target=(.*?) \| outcome=(.*?)$", text)
            if match:
                target = match.group(1).strip()
                outcome = match.group(2).strip()
                if target not in results_map:
                    results_map[target] = outcome

    # Aplicar efectos a la sesion actual
    indices_to_remove = []

    for i, candidate in enumerate(st.session_state.recruitment_pool):
        name = candidate["nombre"]

        if name in results_map:
            outcome = results_map[name]

            # Si ya procesamos este resultado, saltar (excepto FAIL que permite reintentar)
            if candidate.get("last_outcome") == outcome and outcome != "FAILURE":
                continue

            candidate["last_outcome"] = outcome
            stats = candidate.get("stats_json", {})
            bio_data = stats.get("bio", {})

            if outcome == "CRITICAL_SUCCESS":
                candidate["investigado"] = True
                candidate["discounted"] = True
                # Actualizar nivel de acceso a 'conocido'
                bio_data["nivel_acceso"] = BIO_ACCESS_KNOWN
                # Aplicar descuento si no esta aplicado
                if not candidate.get("original_cost"):
                    candidate["original_cost"] = candidate["costo"]
                    candidate["costo"] = int(candidate["costo"] * (1 - CRITICAL_SUCCESS_DISCOUNT))
                log_event(f"INTEL: Se descubrio informacion critica sobre {name}. Vulnerabilidad detectada.", player_id)

            elif outcome == "SUCCESS":
                candidate["investigado"] = True
                # Actualizar nivel de acceso a 'conocido'
                bio_data["nivel_acceso"] = BIO_ACCESS_KNOWN
                log_event(f"INTEL: Expediente de {name} actualizado con informacion de contactos.", player_id)

            elif outcome == "CRITICAL_FAILURE":
                indices_to_remove.append(i)
                st.toast(f"El candidato {name} ha abandonado la estacion.", icon="🏃")
                log_event(f"INTEL: {name} detecto la investigacion y huyo. Ya no esta disponible.", player_id)

            elif outcome == "FAILURE":
                candidate["investigado"] = False
                # No se encontro informacion, pero permite reintentar

    # Eliminar candidatos (orden inverso)
    for i in sorted(indices_to_remove, reverse=True):
        del st.session_state.recruitment_pool[i]


def _manage_pool_expiration(player_id: int, current_tick: int, investigation_active: bool):
    """
    Gestiona la rotacion de candidatos cada 3 Ticks.
    Protege a los candidatos que esten siendo investigados activamente.
    """
    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        return

    # Si hay investigacion activa, pausamos la expiracion para evitar que el target desaparezca
    if investigation_active:
        return

    # Identificar expirados
    indices_expired = []
    for i, candidate in enumerate(st.session_state.recruitment_pool):
        created_at = candidate.get("tick_created", 0)
        # Si la diferencia es mayor o igual a 3, expira
        if (current_tick - created_at) >= CANDIDATE_LIFESPAN_TICKS:
            indices_expired.append(i)

    # Si todos expiraron, limpiamos todo el pool para regenerar uno nuevo completo
    if len(indices_expired) == len(st.session_state.recruitment_pool):
        st.session_state.recruitment_pool = []  # Forzara regeneracion

    elif indices_expired:
        # Eliminamos selectivamente y agregamos reemplazos en el siguiente ciclo de render
        for i in sorted(indices_expired, reverse=True):
            del st.session_state.recruitment_pool[i]


def _generate_recruitment_pool(player_id: int, pool_size: int, existing_names: List[str], min_level: int, max_level: int, current_tick: int) -> List[Dict[str, Any]]:
    candidates = []
    names_in_use = list(existing_names)
    context = RecruitmentContext(player_id=player_id, min_level=min_level, max_level=max_level)

    for _ in range(pool_size):
        char_data = generate_random_character_with_ai(context=context, existing_names=names_in_use)
        stats = char_data.get("stats_json", {})

        nivel = stats.get("progresion", {}).get("nivel", char_data.get("nivel", 1))
        raza = stats.get("taxonomia", {}).get("raza", char_data.get("raza", "Desconocido"))
        clase = stats.get("progresion", {}).get("clase", char_data.get("clase", "Recluta"))

        atributos = stats.get("capacidades", {}).get("atributos", {})
        total_attrs = sum(atributos.values()) if atributos else 0
        costo = (nivel * 250) + (total_attrs * 5)
        if costo < 100:
            costo = 100

        candidate = {
            "nombre": char_data["nombre"],
            "nivel": nivel,
            "raza": raza,
            "clase": clase,
            "costo": int(costo),
            "stats_json": stats,
            "investigado": False,
            "discounted": False,
            "tick_created": current_tick  # Marca de tiempo para expiracion
        }
        candidates.append(candidate)
        names_in_use.append(char_data["nombre"])

    return candidates


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
    index: int,
    player_credits: int,
    player_id: int,
    investigation_active: bool,
    current_tick: int,
    investigating_target: Optional[str]
):
    """Renderiza la tarjeta de un candidato."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    atributos = stats.get("capacidades", {}).get("atributos", {})
    habilidades = stats.get("capacidades", {}).get("habilidades", {})
    comportamiento = stats.get("comportamiento", {})
    rasgos = comportamiento.get("rasgos_personalidad", [])

    can_afford = player_credits >= candidate["costo"]
    can_afford_investigation = player_credits >= INVESTIGATION_COST

    already_investigated = candidate.get("investigado", False)
    is_discounted = candidate.get("discounted", False)
    is_being_investigated = investigating_target == candidate["nombre"]

    # Nivel de acceso para mostrar rasgos
    nivel_acceso = bio.get("nivel_acceso", BIO_ACCESS_UNKNOWN)
    show_traits = nivel_acceso in [BIO_ACCESS_KNOWN, BIO_ACCESS_DEEP]

    # Info de expiracion
    ticks_left = CANDIDATE_LIFESPAN_TICKS - (current_tick - candidate.get("tick_created", current_tick))

    border_color = "#26de81" if can_afford else "#ff6b6b"
    if is_being_investigated:
        border_color = "#45b7d1"  # Azul para investigacion en curso

    with st.container(border=True):
        # Header badges
        investigating_badge = ""
        knowledge_badge = ""

        if is_being_investigated:
            investigating_badge = '<span style="background: #45b7d1; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px;">INVESTIGANDO</span>'

        # Badge de nivel de conocimiento
        if already_investigated or nivel_acceso == BIO_ACCESS_KNOWN:
            knowledge_badge = '<span style="background: rgba(69,183,209,0.2); color: #45b7d1; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #45b7d1;">CONOCIDO</span>'
        elif nivel_acceso == BIO_ACCESS_DEEP:
            knowledge_badge = '<span style="background: rgba(38,222,129,0.2); color: #26de81; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #26de81;">AMIGO</span>'
        else:
            knowledge_badge = '<span style="background: rgba(255,107,107,0.15); color: #ff6b6b; padding: 2px 8px; border-radius: 10px; font-size: 0.7em; margin-left: 8px; border: 1px solid #ff6b6b;">DESCONOCIDO</span>'

        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-left: 4px solid {border_color};
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 12px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.1em; font-weight: bold; color: #fff;">{candidate['nombre']}{knowledge_badge}{investigating_badge}</span>
                    <span style="font-size: 1.3em; font-weight: bold; color: #45b7d1;">Nv. {candidate['nivel']}</span>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85em; margin-top: 4px;">
                    <div><span style="color: #a55eea;">{candidate['raza']}</span> | <span style="color: #f9ca24;">{candidate['clase']}</span></div>
                    <div style="color: #ff6b6b;">Expira en: {max(0, ticks_left)} Ticks</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Bio - muestra la apropiada segun el nivel de acceso
        if already_investigated or nivel_acceso in [BIO_ACCESS_KNOWN, BIO_ACCESS_DEEP]:
            bio_text = bio.get('bio_conocida', bio.get('bio_superficial', 'Datos revelados.'))
            st.success(f"🕵️ INTELIGENCIA: {bio_text}")
            if is_discounted:
                st.caption("✅ Vulnerabilidad explotable detectada (Descuento aplicado).")
        else:
            bio_text = bio.get('bio_superficial') or bio.get('biografia_corta') or "Sin datos biometricos."
            st.caption(f"*{bio_text}*")

        # Top 5 Habilidades con colores
        st.markdown("**Habilidades Destacadas:**")
        _render_top_skills(habilidades, count=5)

        # Rasgos de personalidad (solo si nivel conocido o superior)
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
        col_cost, col_inv, col_recruit = st.columns([2, 1, 1])

        with col_cost:
            cost_color = "#26de81" if can_afford else "#ff6b6b"
            if is_discounted and candidate.get("original_cost"):
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                        <span style="text-decoration: line-through; color: #888; font-size: 1.1em;">{candidate['original_cost']:,}</span>
                        <span style="font-size: 1.6em; font-weight: bold; color: #ffd700;"> {candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="text-align: center;">
                        <span style="color: #888; font-size: 0.85em;">COSTO DE CONTRATACION</span><br>
                        <span style="font-size: 1.6em; font-weight: bold; color: {cost_color};">{candidate['costo']:,} C</span>
                    </div>
                """, unsafe_allow_html=True)

        # Boton Investigar (Bloqueo Global)
        with col_inv:
            disable_inv = False
            inv_label = "🕵️ Investigar"
            inv_help = f"Costo: {INVESTIGATION_COST} C. Tarda 1 Tick."
            button_type = "secondary"

            if is_being_investigated:
                disable_inv = True
                inv_label = "🔄 Investigando..."
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
                inv_label = "✓ Investigado"
                inv_help = "Objetivo ya investigado con exito."

            st.button(
                inv_label,
                key=f"inv_{index}",
                disabled=disable_inv,
                help=inv_help,
                use_container_width=True,
                type=button_type,
                on_click=lambda c=candidate, cr=player_credits: _handle_investigation(player_id, c, cr) if not disable_inv else None
            )

            # --- DEBUG MENU ---
            with st.popover("🛠️ Debug"):
                st.caption("Forzar resultado (proximo tick):")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✨ Critico", key=f"d_cs_{index}", help="Exito Critico: Bio + 30% descuento"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_SUCCESS")
                    if st.button("❌ Fallo", key=f"d_f_{index}", help="Fallo: Sin info, puede reintentar"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="FAIL")
                with col2:
                    if st.button("✅ Exito", key=f"d_s_{index}", help="Exito: Revela biografia conocida"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="SUCCESS")
                    if st.button("💀 Pifia", key=f"d_cf_{index}", help="Pifia: El candidato huye"):
                        _handle_investigation(player_id, candidate, player_credits, debug_outcome="CRIT_FAIL")

        # Boton Contratar
        with col_recruit:
            if can_afford:
                if st.button("CONTRATAR", key=f"recruit_{index}", type="primary", use_container_width=True):
                    _process_recruitment(player_id, candidate, player_credits)
            else:
                st.button("SIN FONDOS", key=f"recruit_{index}", disabled=True, use_container_width=True)


def _handle_investigation(player_id: int, candidate: Dict[str, Any], current_credits: int, debug_outcome: str = None):
    """Maneja el cobro y encolado. Acepta override de debug."""
    if update_player_credits(player_id, current_credits - INVESTIGATION_COST):
        stats = candidate.get("stats_json", {})
        bio = stats.get("bio", {})
        real_bio = bio.get('bio_profunda') or bio.get('bio_conocida') or "Sin secretos."

        debug_param = f" debug_outcome='{debug_outcome}'" if debug_outcome else ""

        cmd = f"[INTERNAL_EXECUTE_INVESTIGATION] Inicia protocolo de investigacion sobre '{candidate['nombre']}'. ID AUTORIZACION: {player_id}.{debug_param} (DATA: {real_bio})"

        if queue_player_action(player_id, cmd):
            log_event(f"INTEL: Iniciando investigacion sobre {candidate['nombre']}...", player_id)
            st.toast(f"Investigacion iniciada. -{INVESTIGATION_COST} C.", icon="🕵️")
            st.rerun()
        else:
            st.error("Error al encolar orden.")
            update_player_credits(player_id, current_credits)
    else:
        st.error("Error en transaccion financiera.")


def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """Procesa el reclutamiento final."""
    try:
        can_afford, message = can_recruit(player_credits, candidate['costo'])
        if not can_afford:
            st.error(message)
            return

        new_credits = player_credits - candidate['costo']

        # Si fue investigado exitosamente, actualizar nivel de acceso antes de guardar
        stats = candidate.get("stats_json", {})
        if candidate.get("investigado", False):
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
            st.success(f"¡{candidate['nombre']} se ha unido a tu faccion!")
            if 'recruitment_pool' in st.session_state:
                st.session_state.recruitment_pool = [
                    c for c in st.session_state.recruitment_pool if c['nombre'] != candidate['nombre']
                ]
            st.rerun()
        else:
            st.error("Error critico al procesar el reclutamiento.")

    except Exception as e:
        st.error(f"Error inesperado: {e}")


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

    # 1. Obtener Estado del Mundo (Ticks)
    world_state = get_world_state()
    current_tick = world_state.get('current_tick', 1)

    # 2. Check de bloqueo global y objetivo siendo investigado
    investigation_active = has_pending_investigation(player_id)
    investigating_target = _get_investigating_target(player_id) if investigation_active else None

    # 3. Procesar Consecuencias (Logs)
    _update_pool_from_investigations(player_id)

    # 4. Gestionar Expiracion (Solo si no hay inv activa)
    _manage_pool_expiration(player_id, current_tick, investigation_active)

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
                st.error("Error al actualizar creditos.")

    if investigation_active:
        target_msg = f" sobre **{investigating_target}**" if investigating_target else ""
        st.info(f"🔍 Investigacion en curso{target_msg}. Los canales de inteligencia estan ocupados hasta el proximo Tick.")

    st.markdown("---")

    # Filtros
    with st.expander("Opciones de Busqueda"):
        col_min, col_max = st.columns(2)
        with col_min:
            min_level = st.number_input("Nivel Minimo", min_value=1, max_value=10, value=st.session_state.get('recruit_min_level', 1))
        with col_max:
            max_level = st.number_input("Nivel Maximo", min_value=1, max_value=10, value=st.session_state.get('recruit_max_level', 3))

        if max_level < min_level:
            max_level = min_level

        if st.button("Aplicar Filtros"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.session_state.recruit_min_level = min_level
            st.session_state.recruit_max_level = max_level
            st.rerun()

    # Generacion / Rellenado de Huecos
    if 'recruitment_pool' not in st.session_state:
        st.session_state.recruitment_pool = []

    # Si se han eliminado candidatos (por expiracion o pifia), rellenar hasta 3
    TARGET_POOL_SIZE = 3
    current_pool_size = len(st.session_state.recruitment_pool)

    if current_pool_size < TARGET_POOL_SIZE:
        all_chars = get_all_characters_by_player_id(player_id)
        existing_names = []
        if all_chars:
            for c in all_chars:
                if isinstance(c, dict):
                    existing_names.append(c.get('nombre', ''))
                elif hasattr(c, 'nombre'):
                    existing_names.append(c.nombre)

        # Agregar tambien los nombres actuales del pool para no repetir en la misma tanda
        for c in st.session_state.recruitment_pool:
            existing_names.append(c['nombre'])

        min_lvl = st.session_state.get('recruit_min_level', 1)
        max_lvl = st.session_state.get('recruit_max_level', 3)

        needed = TARGET_POOL_SIZE - current_pool_size

        with st.spinner(f"Contactando {needed} nuevos operativos..."):
            new_candidates = _generate_recruitment_pool(
                player_id=player_id,
                pool_size=needed,
                existing_names=existing_names,
                min_level=min_lvl,
                max_level=max_lvl,
                current_tick=current_tick
            )
            st.session_state.recruitment_pool.extend(new_candidates)

    candidates = st.session_state.recruitment_pool

    if not candidates:
        st.info("No hay candidatos disponibles.")
        return

    st.subheader(f"Candidatos Disponibles ({len(candidates)})")

    cols = st.columns(len(candidates))
    for i, candidate in enumerate(candidates):
        with cols[i]:
            _render_candidate_card(
                candidate,
                i,
                player_credits,
                player_id,
                investigation_active,
                current_tick,
                investigating_target
            )

    st.markdown("---")
    st.caption("Los candidatos son generados proceduralmente por la IA central. Expiran cada 3 Ticks si no son reclutados.")
