# ui/prestige_widget.py
"""
Widgets de visualización de prestigio para la interfaz de usuario.

Este módulo proporciona componentes visuales para mostrar:
- Ranking de facciones por prestigio
- Estado de hegemonía
- Indicadores de poder
"""

import streamlit as st
from data.faction_repository import get_all_factions, get_current_hegemon
from core.prestige_constants import (
    HEGEMONY_THRESHOLD,
    HEGEMONY_FALL_THRESHOLD,
    IRRELEVANCE_THRESHOLD,
    COLLAPSE_THRESHOLD
)


def render_prestige_leaderboard():
    """
    Renderiza el ranking completo de prestigio de facciones.

    Muestra:
    - Barra de progreso con color de facción
    - Indicadores de estado (👑 Hegemón, ⚠️ Irrelevante, 💀 Colapsado)
    - Contador de victoria para hegemones
    - Número de jugadores activos
    """
    factions = get_all_factions()

    if not factions:
        st.warning("No hay facciones en el sistema")
        return

    st.subheader("🏛️ Balance de Poder Galáctico")

    for faction in factions:
        prestige = float(faction.get("prestigio", 0))
        is_hegemon = faction.get("es_hegemon", False)
        counter = faction.get("hegemonia_contador", 0)
        color = faction.get("color_hex", "#888888")

        # Determinar prefijo según estado
        prefix = ""
        if is_hegemon:
            prefix = "👑 "
        elif prestige < COLLAPSE_THRESHOLD:
            prefix = "💀 "
        elif prestige < IRRELEVANCE_THRESHOLD:
            prefix = "⚠️ "

        # Layout: Nombre + Barra | Métrica
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**{prefix}{faction['nombre']}**")
            # Barra de progreso con color personalizado
            st.progress(
                min(prestige / 100, 1.0),
                text=f"{prestige:.1f}%"
            )

        with col2:
            if is_hegemon and counter > 0:
                st.metric("Victoria en", f"{counter} ticks", delta=None)
            else:
                st.caption(f"{prestige:.1f}%")

    # Líneas de referencia
    st.caption("---")
    st.caption(f"👑 Hegemonía: ≥{HEGEMONY_THRESHOLD}% | 💔 Caída: <{HEGEMONY_FALL_THRESHOLD}%")
    st.caption(f"⚠️ Irrelevancia: <{IRRELEVANCE_THRESHOLD}% | 💀 Colapso: <{COLLAPSE_THRESHOLD}%")


def render_prestige_mini_widget():
    """
    Widget compacto de prestigio para el sidebar.

    Muestra:
    - Hegemón actual (si existe) con contador de victoria
    - Líder actual (si no hay hegemón)
    - Estado de urgencia
    """
    hegemon = get_current_hegemon()

    if hegemon:
        # Hay un hegemón activo
        counter = hegemon.get("hegemonia_contador", 0)
        prestige = float(hegemon.get("prestigio", 0))

        st.warning(f"👑 **HEGEMÓN**: {hegemon['nombre']}")
        st.caption(f"Prestigio: {prestige:.1f}% | Victoria en {counter} ticks")

        # Barra de progreso del contador
        if counter > 0:
            progress = 1.0 - (counter / 20)  # 20 es el máximo
            st.progress(progress, text=f"Progreso: {int(progress * 100)}%")
    else:
        # No hay hegemón, mostrar líder
        factions = get_all_factions()
        if factions:
            top = factions[0]
            prestige = float(top.get("prestigio", 0))

            # Color según proximidad a hegemonía
            if prestige >= 23:
                st.error(f"🚨 **ALERTA**: {top['nombre']}")
                st.caption(f"¡A {25 - prestige:.1f}% de la Hegemonía!")
            elif prestige >= 20:
                st.warning(f"⚡ **Potencia**: {top['nombre']}")
                st.caption(f"Prestigio: {prestige:.1f}%")
            else:
                st.info(f"🥇 **Líder**: {top['nombre']}")
                st.caption(f"Prestigio: {prestige:.1f}%")


def render_faction_badge(faction_name: str, show_prestige: bool = True):
    """
    Renderiza un badge compacto de facción con su prestigio.

    Args:
        faction_name: Nombre de la facción
        show_prestige: Si debe mostrar el prestigio (default: True)
    """
    from data.faction_repository import get_faction_by_name

    faction = get_faction_by_name(faction_name)
    if not faction:
        st.caption(f"❓ {faction_name}")
        return

    prestige = float(faction.get("prestigio", 0))
    is_hegemon = faction.get("es_hegemon", False)
    color = faction.get("color_hex", "#888888")

    # Icono según estado
    icon = "👑" if is_hegemon else "⭐"

    if show_prestige:
        st.markdown(
            f'<span style="color: {color}; font-weight: bold;">'
            f'{icon} {faction_name} ({prestige:.1f}%)</span>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<span style="color: {color}; font-weight: bold;">'
            f'{icon} {faction_name}</span>',
            unsafe_allow_html=True
        )


def render_prestige_chart():
    """
    Renderiza un gráfico de distribución de prestigio.

    Usa st.bar_chart para mostrar el prestigio de todas las facciones.
    """
    import pandas as pd
    from data.faction_repository import get_all_factions

    factions = get_all_factions()
    if not factions:
        return

    # Preparar datos para el gráfico
    data = {
        "Facción": [f["nombre"] for f in factions],
        "Prestigio": [float(f["prestigio"]) for f in factions]
    }
    df = pd.DataFrame(data)
    df = df.set_index("Facción")

    st.bar_chart(df)


def render_faction_comparison(faction_a_name: str, faction_b_name: str):
    """
    Compara dos facciones lado a lado.

    Args:
        faction_a_name: Nombre de la primera facción
        faction_b_name: Nombre de la segunda facción
    """
    from data.faction_repository import get_faction_by_name, get_faction_statistics

    faction_a = get_faction_by_name(faction_a_name)
    faction_b = get_faction_by_name(faction_b_name)

    if not faction_a or not faction_b:
        st.error("Una o ambas facciones no existen")
        return

    col1, col2 = st.columns(2)

    # Facción A
    with col1:
        st.subheader(faction_a["nombre"])
        prestige_a = float(faction_a.get("prestigio", 0))
        st.metric("Prestigio", f"{prestige_a:.1f}%")

        if faction_a.get("es_hegemon"):
            st.success("👑 HEGEMÓN")

        # Estadísticas
        stats_a = get_faction_statistics(faction_a["id"])
        st.caption(f"Ganado total: {stats_a['total_gained']:.1f}%")
        st.caption(f"Perdido total: {stats_a['total_lost']:.1f}%")
        st.caption(f"Neto: {stats_a['net_change']:.1f}%")

    # Facción B
    with col2:
        st.subheader(faction_b["nombre"])
        prestige_b = float(faction_b.get("prestigio", 0))
        st.metric("Prestigio", f"{prestige_b:.1f}%")

        if faction_b.get("es_hegemon"):
            st.success("👑 HEGEMÓN")

        # Estadísticas
        stats_b = get_faction_statistics(faction_b["id"])
        st.caption(f"Ganado total: {stats_b['total_gained']:.1f}%")
        st.caption(f"Perdido total: {stats_b['total_lost']:.1f}%")
        st.caption(f"Neto: {stats_b['net_change']:.1f}%")

    # Diferencia
    difference = prestige_a - prestige_b
    st.divider()

    if difference > 0:
        st.info(f"⚖️ {faction_a['nombre']} tiene {abs(difference):.1f}% más de prestigio")
    elif difference < 0:
        st.info(f"⚖️ {faction_b['nombre']} tiene {abs(difference):.1f}% más de prestigio")
    else:
        st.info("⚖️ Ambas facciones están empatadas")


def render_prestige_history_feed(limit: int = 10):
    """
    Muestra un feed de transferencias recientes de prestigio.

    Args:
        limit: Número de eventos a mostrar
    """
    from data.faction_repository import get_prestige_history, get_faction_by_id

    history = get_prestige_history(limit=limit)

    if not history:
        st.info("No hay historial de transferencias de prestigio")
        return

    st.subheader("📜 Transferencias Recientes")

    for event in history:
        attacker = get_faction_by_id(event.get("attacker_faction_id"))
        defender = get_faction_by_id(event.get("defender_faction_id"))
        amount = float(event.get("amount", 0))
        idp = float(event.get("idp_multiplier", 1.0))
        reason = event.get("reason", "Evento desconocido")
        tick = event.get("tick", "?")

        if attacker and defender:
            with st.expander(f"Tick {tick}: {attacker['nombre']} vs {defender['nombre']}", expanded=False):
                st.markdown(f"**⚔️ {reason}**")
                st.caption(f"Transferencia: {amount:.2f}% (IDP: {idp:.2f}x)")
                st.caption(f"{attacker['nombre']} ➡️ {defender['nombre']}")
