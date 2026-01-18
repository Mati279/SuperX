# ui/recruitment_center.py
"""
Centro de Reclutamiento Galactico - Contratacion de nuevos operativos.
Genera candidatos aleatorios con stats completos usando character_engine.
"""

import streamlit as st
from typing import Dict, Any, List
from ui.state import get_player
# IMPORTANTE: Se usa el servicio con IA por defecto, con fallback al motor básico
from services.character_generation_service import generate_random_character_with_ai, RecruitmentContext
from core.recruitment_logic import can_recruit
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id
from config.app_constants import DEFAULT_RECRUIT_RANK, DEFAULT_RECRUIT_STATUS, DEFAULT_RECRUIT_LOCATION


def _generate_recruitment_pool(player_id: int, pool_size: int, existing_names: List[str], min_level: int = 1, max_level: int = 3) -> List[Dict[str, Any]]:
    """
    Genera una piscina de candidatos para reclutamiento usando el servicio de IA (o fallback).

    Args:
        player_id: ID del jugador para contexto.
        pool_size: Cantidad de candidatos a generar.
        existing_names: Nombres existentes para evitar duplicados.
        min_level: Nivel minimo de los candidatos.
        max_level: Nivel maximo de los candidatos.

    Returns:
        Lista de candidatos con stats completos y costo calculado.
    """
    candidates = []
    names_in_use = list(existing_names)

    # Crear contexto para el generador
    context = RecruitmentContext(
        player_id=player_id,
        min_level=min_level,
        max_level=max_level
    )

    for _ in range(pool_size):
        # Generar personaje con el servicio (retorna dict compatible con DB)
        char_data = generate_random_character_with_ai(
            context=context,
            existing_names=names_in_use
        )
        
        # Extraer stats para calcular costo y mostrar en UI
        stats = char_data.get("stats_json", {})
        
        # FIX: Obtener datos de las rutas correctas en stats_json
        # Estructura esperada: stats_json['progresion']['nivel'], stats_json['taxonomia']['raza'], etc.
        try:
            nivel = stats.get("progresion", {}).get("nivel", 1)
            raza = stats.get("taxonomia", {}).get("raza", "Humano")
            clase = stats.get("progresion", {}).get("clase", "Recluta")
        except Exception:
            # Fallback por si la estructura es plana (legacy)
            nivel = char_data.get("nivel", 1)
            raza = char_data.get("raza", "Humano")
            clase = char_data.get("clase", "Recluta")

        # Calcular costo (se necesita pasar un dict con 'nivel' y 'raza' o el objeto completo)
        # La función calculate_recruitment_cost espera un dict con claves planas o acceso a atributos
        # Simulamos un objeto simple para el cálculo de costo
        temp_char_for_cost = {
            "nivel": nivel,
            "raza": raza,
            "stats_json": stats
        }
        
        # Import local para evitar circular si es necesario, o usar la lógica simple
        # Costo base simplificado: (Nivel * 100) + (Suma Atributos * 10)
        attrs = stats.get("capacidades", {}).get("atributos", {})
        total_attrs = sum(attrs.values()) if attrs else 0
        costo = (nivel * 250) + (total_attrs * 5)

        # Preparar candidato para la UI
        candidate = {
            "nombre": char_data["nombre"],
            "nivel": nivel,
            "raza": raza,
            "clase": clase,
            "costo": costo,
            "stats_json": stats
        }

        candidates.append(candidate)
        names_in_use.append(char_data["nombre"])

    return candidates


def _render_candidate_card(candidate: Dict[str, Any], index: int, player_credits: int, player_id: int):
    """Renderiza la tarjeta de un candidato con todos sus detalles."""

    stats = candidate.get("stats_json", {})
    bio = stats.get("bio", {})
    
    # Rutas seguras a los datos en la nueva estructura JSON
    atributos = stats.get("capacidades", {}).get("atributos", {})
    habilidades = stats.get("capacidades", {}).get("habilidades", {})
    feats = stats.get("capacidades", {}).get("feats", [])

    can_afford = player_credits >= candidate["costo"]
    border_color = "#26de81" if can_afford else "#ff6b6b"

    with st.container(border=True):
        # Header
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

        # Descripcion (Bio superficial)
        bio_text = bio.get('bio_superficial') or bio.get('biografia_corta') or "Sin datos biométricos."
        st.caption(f"*{bio_text}*")

        # Atributos en grid compacto
        with st.expander("Ver Atributos", expanded=False):
            cols = st.columns(3)
            for i, (attr, value) in enumerate(atributos.items()):
                with cols[i % 3]:
                    color = "#26de81" if value >= 12 else "#888"
                    st.markdown(f"<span style='color:{color};'>{attr.upper()}: **{value}**</span>", unsafe_allow_html=True)

        # Habilidades
        # Muestra las Top 5 con colores escalados
        with st.expander("Ver Habilidades", expanded=False):
            if habilidades:
                sorted_skills = sorted(habilidades.items(), key=lambda x: -x[1])
                for skill, val in sorted_skills[:5]:  # Top 5 habilidades
                    color = "#ffd700" if val >= 25 else "#45b7d1" if val >= 18 else "#888"
                    st.markdown(f"<span style='color:{color};'>{skill}: **{val}**</span>", unsafe_allow_html=True)
            else:
                st.caption("Sin habilidades calculadas")

        # Feats/Rasgos
        if feats:
            with st.expander("Ver Rasgos", expanded=False):
                for feat in feats:
                    st.markdown(f"- {feat}")

        # Costo y boton de contratacion
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
                if st.button(f"CONTRATAR", key=f"recruit_{index}", type="primary", width='stretch'):
                    _process_recruitment(player_id, candidate, player_credits)
            else:
                st.button("FONDOS INSUFICIENTES", key=f"recruit_{index}", disabled=True, width='stretch')


def _process_recruitment(player_id: int, candidate: Dict[str, Any], player_credits: int):
    """Procesa la contratacion de un candidato."""
    try:
        # Verificar fondos
        can_afford, message = can_recruit(player_credits, candidate['costo'])
        if not can_afford:
            st.error(message)
            return

        # Calcular nuevo balance
        new_credits = player_credits - candidate['costo']

        # Preparar datos del personaje para la DB
        new_character_data = {
            "player_id": player_id,
            "nombre": candidate["nombre"],
            "rango": DEFAULT_RECRUIT_RANK,
            "es_comandante": False,
            "stats_json": candidate["stats_json"],
            "estado": DEFAULT_RECRUIT_STATUS,
            "ubicacion": DEFAULT_RECRUIT_LOCATION
        }

        # Ejecutar transacciones
        update_ok = update_player_credits(player_id, new_credits)
        char_ok = create_character(player_id, new_character_data)

        if update_ok and char_ok:
            st.success(f"¡{candidate['nombre']} se ha unido a tu faccion!")

            # Limpiar el candidato de la sesion
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
    """Pagina principal del Centro de Reclutamiento."""

    st.title("Centro de Reclutamiento")
    st.caption("Encuentra y contrata nuevos operativos para tu faccion")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("Error de sesion. Por favor, inicie sesion de nuevo.")
        return

    player_id = player.id

    # --- Header con creditos ---
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
        st.write("")  # Espaciado
        refresh_cost = 50
        can_refresh = player_credits >= refresh_cost

        if st.button(
            f"Buscar Nuevos\n({refresh_cost} C)",
            disabled=not can_refresh,
            type="secondary",
            width='stretch'
        ):
            if update_player_credits(player_id, player_credits - refresh_cost):
                if 'recruitment_pool' in st.session_state:
                    del st.session_state.recruitment_pool
                st.rerun()
            else:
                st.error("Error al actualizar creditos")

    st.markdown("---")

    # --- Opciones de nivel ---
    with st.expander("Opciones de Busqueda"):
        col_min, col_max = st.columns(2)
        with col_min:
            min_level = st.number_input("Nivel Minimo", min_value=1, max_value=10, value=1)
        with col_max:
            max_level = st.number_input("Nivel Maximo", min_value=1, max_value=10, value=3)

        if max_level < min_level:
            max_level = min_level

        # Guardar en session para regenerar con estos parametros
        if st.button("Aplicar Filtros"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.session_state.recruit_min_level = min_level
            st.session_state.recruit_max_level = max_level
            st.rerun()

    # --- Generar/Obtener piscina de candidatos ---
    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        # Obtener nombres existentes
        all_chars = get_all_characters_by_player_id(player_id)
        existing_names = []
        for c in all_chars:
            if hasattr(c, 'nombre'): 
                existing_names.append(c.nombre)
            elif isinstance(c, dict): 
                existing_names.append(c.get('nombre'))

        # Obtener parametros de nivel
        min_lvl = st.session_state.get('recruit_min_level', 1)
        max_lvl = st.session_state.get('recruit_max_level', 3)

        # Generar candidatos usando la función corregida
        st.session_state.recruitment_pool = _generate_recruitment_pool(
            player_id=player_id,
            pool_size=3,
            existing_names=existing_names,
            min_level=min_lvl,
            max_level=max_lvl
        )

    candidates = st.session_state.recruitment_pool

    # --- Mostrar candidatos ---
    if not candidates:
        st.info("No hay candidatos disponibles. Pulsa 'Buscar Nuevos' para generar mas.")
        if st.button("Generar Candidatos Gratis"):
            if 'recruitment_pool' in st.session_state:
                del st.session_state.recruitment_pool
            st.rerun()
        return

    st.subheader(f"Candidatos Disponibles ({len(candidates)})")

    # Mostrar en columnas
    cols = st.columns(len(candidates))

    for i, candidate in enumerate(candidates):
        with cols[i]:
            _render_candidate_card(candidate, i, player_credits, player_id)

    # --- Footer con info ---
    st.markdown("---")
    st.caption("Los candidatos son generados proceduralmente. El costo se basa en nivel y atributos.")