# ui/diplomacy_page.py
"""
Página de diplomacia y visualización de facciones.

Esta página muestra:
- Información de la facción del jugador
- Ranking de todas las facciones
- Estado de hegemonía
- Historial de prestigio
"""

import streamlit as st
from ui.prestige_widget import (
    render_prestige_leaderboard,
    render_faction_badge,
    render_prestige_chart,
    render_prestige_history_feed
)
from data.faction_repository import (
    get_faction_by_name,
    get_all_factions,
    get_faction_statistics,
    get_current_hegemon
)
from ui.state import get_player
from core.prestige_constants import (
    HEGEMONY_THRESHOLD,
    IRRELEVANCE_THRESHOLD,
    COLLAPSE_THRESHOLD
)


def render_diplomacy_page():
    """
    Página principal de diplomacia y facciones.

    Layout:
    - Columna izquierda: Información de tu facción
    - Columna derecha: Ranking galáctico
    - Sección inferior: Tabs con historial, gráficos, etc.
    """
    st.title("🏛️ Diplomacia Galáctica")

    player = get_player()
    if not player:
        st.error("Error: No se pudo cargar la información del jugador")
        return

    player_faction = get_faction_by_name(player.get("faccion_nombre", ""))

    # ============================================================
    # SECCIÓN SUPERIOR: TU FACCIÓN VS RANKING
    # ============================================================

    col1, col2 = st.columns([2, 1])

    with col1:
        _render_player_faction_panel(player_faction, player)

    with col2:
        render_prestige_leaderboard()

    st.divider()

    # ============================================================
    # SECCIÓN INFERIOR: TABS DE INFORMACIÓN
    # ============================================================

    tab_overview, tab_history, tab_stats = st.tabs([
        "📊 Panorama General",
        "📜 Historial",
        "📈 Estadísticas"
    ])

    with tab_overview:
        _render_overview_tab()

    with tab_history:
        _render_history_tab()

    with tab_stats:
        _render_stats_tab(player_faction)


def _render_player_faction_panel(player_faction, player):
    """Renderiza el panel de información de la facción del jugador."""
    if not player_faction:
        st.warning("No se pudo cargar la información de tu facción")
        return

    st.subheader("Tu Facción")

    # Banner de facción (si existe)
    if player_faction.get("banner_url"):
        st.image(player_faction["banner_url"], use_container_width=True)

    # Nombre y descripción
    st.markdown(f"### {player_faction['nombre']}")
    st.write(player_faction.get("descripcion", "Sin descripción disponible"))

    # Métricas principales
    prestige = float(player_faction.get("prestigio", 0))
    is_hegemon = player_faction.get("es_hegemon", False)
    counter = player_faction.get("hegemonia_contador", 0)

    col_metric1, col_metric2 = st.columns(2)

    with col_metric1:
        st.metric("Prestigio Actual", f"{prestige:.2f}%")

    with col_metric2:
        # Calcular posición en el ranking
        all_factions = get_all_factions()
        position = next(
            (i + 1 for i, f in enumerate(all_factions) if f["id"] == player_faction["id"]),
            "?"
        )
        st.metric("Posición", f"#{position}")

    # Alertas según estado
    if is_hegemon:
        st.success(f"👑 ¡ERES EL HEGEMÓN! Victoria en {counter} ticks")
        st.progress(1.0 - (counter / 20), text=f"Progreso hacia victoria: {int((1 - counter/20) * 100)}%")
    elif prestige >= HEGEMONY_THRESHOLD - 3:
        st.warning(f"⚡ ¡Estás CERCA de la Hegemonía! (Faltan {HEGEMONY_THRESHOLD - prestige:.2f}%)")
    elif prestige < COLLAPSE_THRESHOLD:
        st.error(f"💀 ¡Tu facción está en COLAPSO! (Prestigio: {prestige:.1f}%)")
    elif prestige < IRRELEVANCE_THRESHOLD:
        st.warning(f"⚠️ Tu facción está en estado de IRRELEVANCIA (Prestigio: {prestige:.1f}%)")

    # Estadísticas históricas
    stats = get_faction_statistics(player_faction["id"])
    if stats["transfers_as_attacker"] + stats["transfers_as_defender"] > 0:
        st.divider()
        st.caption("**Historial de Combate**")

        stat_col1, stat_col2, stat_col3 = st.columns(3)
        with stat_col1:
            st.metric("Ganado", f"{stats['total_gained']:.1f}%", delta=None)
        with stat_col2:
            st.metric("Perdido", f"{stats['total_lost']:.1f}%", delta=None)
        with stat_col3:
            delta_color = "normal" if stats['net_change'] >= 0 else "inverse"
            st.metric("Neto", f"{stats['net_change']:.1f}%", delta_color=delta_color)


def _render_overview_tab():
    """Renderiza el tab de panorama general."""
    st.subheader("Panorama General del Poder Galáctico")

    hegemon = get_current_hegemon()

    if hegemon:
        st.info(f"👑 **Estado del Sistema**: Hegemonía Activa - {hegemon['nombre']}")
        counter = hegemon.get("hegemonia_contador", 0)
        st.caption(f"El hegemón debe mantener su posición por {counter} ticks más para ganar la partida.")
    else:
        st.success("🌌 **Estado del Sistema**: Equilibrio de Poder")
        st.caption("No hay ningún hegemón activo. Todas las facciones compiten por el control.")

    st.divider()

    # Gráfico de distribución
    st.subheader("Distribución de Prestigio")
    render_prestige_chart()

    st.divider()

    # Información del sistema
    st.subheader("Mecánicas del Sistema")

    with st.expander("📖 Reglas de Hegemonía", expanded=False):
        st.markdown(f"""
        **Ascenso a Hegemón:**
        - Una facción debe alcanzar ≥{HEGEMONY_THRESHOLD}% de prestigio
        - Al ascender, inicia un contador de victoria de 20 ticks

        **Condición de Victoria:**
        - Mantener el estatus de hegemón durante 20 ticks consecutivos

        **Caída de Hegemonía (Buffer 25/20):**
        - El hegemón mantiene su estatus entre 20-25% (zona de amortiguación)
        - Solo pierde el estatus si cae por debajo del 20%
        """)

    with st.expander("⚖️ Sistema de Fricción Galáctica", expanded=False):
        st.markdown("""
        **Impuesto Imperial:**
        - Facciones con >20% de prestigio pierden 0.5% por tick
        - Previene dominación descontrolada

        **Subsidio de Supervivencia:**
        - Facciones con <5% de prestigio reciben subsidio
        - El subsidio proviene del impuesto imperial
        - Permite recuperación de facciones débiles
        """)

    with st.expander("⚔️ Sistema de Combate (IDP)", expanded=False):
        st.markdown("""
        **Índice de Disparidad de Poder (IDP):**
        ```
        IDP = max(0, 1 + (P_Defensor - P_Atacante) / 20)
        Transferencia = Base_Evento × IDP
        ```

        **Riesgo Asimétrico:**
        - Atacar "hacia arriba" (a alguien más fuerte) = mayor ganancia
        - Atacar "hacia abajo" (a alguien más débil) = menor o nula ganancia

        **Hard Cap Anti-Bullying:**
        - Si IDP = 0, NO hay transferencia de prestigio
        - Puedes ganar recursos/posiciones, pero no prestigio
        """)


def _render_history_tab():
    """Renderiza el tab de historial de transferencias."""
    st.subheader("Historial de Transferencias de Prestigio")

    # Selector de cantidad de eventos
    limit = st.slider("Eventos a mostrar", min_value=5, max_value=50, value=10, step=5)

    render_prestige_history_feed(limit=limit)


def _render_stats_tab(player_faction):
    """Renderiza el tab de estadísticas avanzadas."""
    st.subheader("Estadísticas Avanzadas")

    # Comparador de facciones
    st.markdown("### Comparar Facciones")

    all_factions = get_all_factions()
    faction_names = [f["nombre"] for f in all_factions]

    col_select1, col_select2 = st.columns(2)

    with col_select1:
        faction_a = st.selectbox(
            "Facción A",
            faction_names,
            index=0 if not player_faction else next(
                (i for i, name in enumerate(faction_names) if name == player_faction["nombre"]),
                0
            )
        )

    with col_select2:
        faction_b = st.selectbox(
            "Facción B",
            faction_names,
            index=1 if len(faction_names) > 1 else 0
        )

    if faction_a and faction_b:
        from ui.prestige_widget import render_faction_comparison
        render_faction_comparison(faction_a, faction_b)

    st.divider()

    # Estadísticas de tu facción
    if player_faction:
        st.markdown("### Análisis de tu Facción")

        stats = get_faction_statistics(player_faction["id"])

        # Métricas en grid
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

        with metric_col1:
            st.metric("Victorias", stats["transfers_as_attacker"])
        with metric_col2:
            st.metric("Derrotas", stats["transfers_as_defender"])
        with metric_col3:
            st.metric("Prestigio Ganado", f"{stats['total_gained']:.1f}%")
        with metric_col4:
            st.metric("Prestigio Perdido", f"{stats['total_lost']:.1f}%")

        # Análisis de rendimiento
        if stats["transfers_as_attacker"] + stats["transfers_as_defender"] > 0:
            win_rate = stats["transfers_as_attacker"] / (
                stats["transfers_as_attacker"] + stats["transfers_as_defender"]
            ) * 100

            st.markdown(f"**Tasa de Victoria**: {win_rate:.1f}%")

            if stats["net_change"] > 0:
                st.success(f"✅ Balance positivo: +{stats['net_change']:.1f}% de prestigio neto")
            elif stats["net_change"] < 0:
                st.error(f"⚠️ Balance negativo: {stats['net_change']:.1f}% de prestigio neto")
            else:
                st.info("⚖️ Balance neutro: Sin cambio neto de prestigio")
