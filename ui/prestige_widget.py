# ui/prestige_widget.py
"""
Widgets de Prestigio - Terminal de Comando Galactico.
Visualizacion del balance de poder entre facciones.
"""

import streamlit as st
from typing import Optional
from data.faction_repository import get_all_factions, get_current_hegemon
from core.prestige_constants import (
    HEGEMONY_THRESHOLD,
    HEGEMONY_FALL_THRESHOLD,
    IRRELEVANCE_THRESHOLD,
    COLLAPSE_THRESHOLD
)
from .styles import Colors, render_terminal_header


def _get_faction_state(prestige: float, is_hegemon: bool) -> tuple:
    """Determina el estado visual de una faccion segun su prestigio."""
    if is_hegemon:
        return (Colors.LEGENDARY, "HEGEMON", "&#128081;")
    elif prestige < COLLAPSE_THRESHOLD:
        return (Colors.DANGER, "COLAPSADO", "&#128128;")
    elif prestige < IRRELEVANCE_THRESHOLD:
        return (Colors.WARNING, "IRRELEVANTE", "&#9888;")
    elif prestige >= HEGEMONY_THRESHOLD - 2:
        return (Colors.EPIC, "POTENCIA", "&#9889;")
    else:
        return (Colors.TEXT_SECONDARY, "ACTIVO", "&#9679;")


def render_prestige_leaderboard():
    """
    Renderiza el ranking completo de prestigio de facciones.
    Estilo: Panel de inteligencia tactica.
    """
    factions = get_all_factions()

    if not factions:
        st.warning("No hay facciones en el sistema")
        return

    render_terminal_header(
        title="BALANCE DE PODER",
        subtitle="ANALISIS DE INTELIGENCIA GALACTICO",
        icon="&#127963;"
    )

    # Panel contenedor
    st.markdown(f"""
        <div style="
            background: {Colors.BG_CARD};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                padding-bottom: 10px;
                border-bottom: 1px solid {Colors.BORDER_DIM};
                margin-bottom: 12px;
            ">
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.7em;
                    color: {Colors.TEXT_DIM};
                    letter-spacing: 1px;
                ">FACCION</span>
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.7em;
                    color: {Colors.TEXT_DIM};
                    letter-spacing: 1px;
                ">PRESTIGIO</span>
            </div>
    """, unsafe_allow_html=True)

    for faction in factions:
        prestige = float(faction.get("prestigio", 0))
        is_hegemon = faction.get("es_hegemon", False)
        counter = faction.get("hegemonia_contador", 0)
        faction_color = faction.get("color_hex", Colors.TEXT_SECONDARY)

        state_color, state_text, state_icon = _get_faction_state(prestige, is_hegemon)
        percentage = min(100, prestige)

        # Mostrar contador de victoria si es hegemon
        counter_html = ""
        if is_hegemon and counter > 0:
            counter_html = f"""
                <div style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 0.7em;
                    color: {Colors.LEGENDARY};
                    margin-top: 4px;
                ">VICTORIA EN {counter} TICKS</div>
            """

        st.markdown(f"""
            <div style="
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid {Colors.BORDER_DIM}20;
            ">
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                        <span style="
                            width: 10px;
                            height: 10px;
                            background: {faction_color};
                            border-radius: 2px;
                            box-shadow: 0 0 6px {faction_color}60;
                        "></span>
                        <span style="
                            font-family: 'Rajdhani', sans-serif;
                            font-size: 1em;
                            font-weight: 600;
                            color: {Colors.TEXT_PRIMARY};
                        ">{faction['nombre']}</span>
                        <span style="
                            font-family: 'Orbitron', sans-serif;
                            font-size: 0.6em;
                            color: {state_color};
                            padding: 2px 6px;
                            background: {state_color}15;
                            border: 1px solid {state_color}40;
                            border-radius: 3px;
                        ">{state_icon} {state_text}</span>
                    </div>

                    <div style="
                        background: {Colors.BG_DARK};
                        border: 1px solid {Colors.BORDER_DIM};
                        border-radius: 3px;
                        height: 8px;
                        overflow: hidden;
                        width: 100%;
                    ">
                        <div style="
                            background: linear-gradient(90deg, {faction_color} 0%, {faction_color}80 100%);
                            width: {percentage}%;
                            height: 100%;
                            box-shadow: 0 0 8px {faction_color}40;
                            transition: width 0.5s ease;
                        "></div>
                    </div>
                    {counter_html}
                </div>

                <div style="
                    text-align: right;
                    min-width: 80px;
                    margin-left: 16px;
                ">
                    <span style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 1.2em;
                        font-weight: 700;
                        color: {state_color};
                    ">{prestige:.1f}%</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Cierre del panel y leyenda
    st.markdown(f"""
        </div>

        <div style="
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            padding: 10px;
            background: {Colors.BG_DARK};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 6px;
        ">
            <span style="font-family: 'Share Tech Mono', monospace; font-size: 0.7em; color: {Colors.LEGENDARY};">
                &#128081; Hegemonia: >={HEGEMONY_THRESHOLD}%
            </span>
            <span style="font-family: 'Share Tech Mono', monospace; font-size: 0.7em; color: {Colors.WARNING};">
                &#128148; Caida: <{HEGEMONY_FALL_THRESHOLD}%
            </span>
            <span style="font-family: 'Share Tech Mono', monospace; font-size: 0.7em; color: {Colors.WARNING};">
                &#9888; Irrelevancia: <{IRRELEVANCE_THRESHOLD}%
            </span>
            <span style="font-family: 'Share Tech Mono', monospace; font-size: 0.7em; color: {Colors.DANGER};">
                &#128128; Colapso: <{COLLAPSE_THRESHOLD}%
            </span>
        </div>
    """, unsafe_allow_html=True)


def render_prestige_mini_widget():
    """
    Widget compacto de prestigio para el sidebar.
    Muestra estado de hegemonia o lider actual.
    """
    hegemon = get_current_hegemon()

    if hegemon:
        counter = hegemon.get("hegemonia_contador", 0)
        prestige = float(hegemon.get("prestigio", 0))
        faction_color = hegemon.get("color_hex", Colors.LEGENDARY)

        progress = 1.0 - (counter / 20) if counter > 0 else 0

        st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.LEGENDARY}10 100%);
                border: 1px solid {Colors.LEGENDARY}40;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 12px;
            ">
                <div style="
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 8px;
                ">
                    <span style="font-size: 1.2em;">&#128081;</span>
                    <div>
                        <div style="
                            font-family: 'Orbitron', sans-serif;
                            font-size: 0.6em;
                            color: {Colors.LEGENDARY};
                            letter-spacing: 1px;
                        ">HEGEMON GALACTICO</div>
                        <div style="
                            font-family: 'Rajdhani', sans-serif;
                            font-size: 1.1em;
                            font-weight: 600;
                            color: {Colors.TEXT_PRIMARY};
                        ">{hegemon['nombre']}</div>
                    </div>
                </div>

                <div style="
                    display: flex;
                    justify-content: space-between;
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 0.75em;
                    color: {Colors.TEXT_SECONDARY};
                    margin-bottom: 4px;
                ">
                    <span>Prestigio: {prestige:.1f}%</span>
                    <span style="color: {Colors.LEGENDARY};">Victoria en {counter} ticks</span>
                </div>

                <div style="
                    background: {Colors.BG_DARK};
                    border: 1px solid {Colors.BORDER_DIM};
                    border-radius: 3px;
                    height: 6px;
                    overflow: hidden;
                ">
                    <div style="
                        background: linear-gradient(90deg, {Colors.LEGENDARY} 0%, {Colors.WARNING} 100%);
                        width: {progress * 100}%;
                        height: 100%;
                        box-shadow: 0 0 8px {Colors.LEGENDARY}60;
                    "></div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    else:
        factions = get_all_factions()
        if factions:
            top = factions[0]
            prestige = float(top.get("prestigio", 0))
            faction_color = top.get("color_hex", Colors.INFO)

            # Determinar nivel de alerta
            if prestige >= HEGEMONY_THRESHOLD - 2:
                alert_color = Colors.DANGER
                alert_text = "ALERTA"
                alert_icon = "&#128680;"
            elif prestige >= HEGEMONY_THRESHOLD - 5:
                alert_color = Colors.WARNING
                alert_text = "POTENCIA"
                alert_icon = "&#9889;"
            else:
                alert_color = Colors.INFO
                alert_text = "LIDER"
                alert_icon = "&#127942;"

            distance = HEGEMONY_THRESHOLD - prestige

            st.markdown(f"""
                <div style="
                    background: {Colors.BG_CARD};
                    border: 1px solid {alert_color}40;
                    border-left: 3px solid {alert_color};
                    border-radius: 6px;
                    padding: 12px;
                    margin-bottom: 12px;
                ">
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        margin-bottom: 6px;
                    ">
                        <span style="
                            font-family: 'Orbitron', sans-serif;
                            font-size: 0.6em;
                            color: {alert_color};
                            letter-spacing: 1px;
                        ">{alert_icon} {alert_text}</span>
                        <span style="
                            font-family: 'Share Tech Mono', monospace;
                            font-size: 0.9em;
                            color: {alert_color};
                        ">{prestige:.1f}%</span>
                    </div>

                    <div style="
                        font-family: 'Rajdhani', sans-serif;
                        font-size: 1em;
                        font-weight: 600;
                        color: {Colors.TEXT_PRIMARY};
                    ">{top['nombre']}</div>

                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 0.7em;
                        color: {Colors.TEXT_DIM};
                        margin-top: 4px;
                    ">A {distance:.1f}% de hegemonia</div>
                </div>
            """, unsafe_allow_html=True)


def render_faction_badge(faction_name: str, show_prestige: bool = True):
    """
    Renderiza un badge compacto de faccion.
    """
    from data.faction_repository import get_faction_by_name

    faction = get_faction_by_name(faction_name)
    if not faction:
        st.markdown(f"""
            <span style="
                font-family: 'Share Tech Mono', monospace;
                color: {Colors.TEXT_DIM};
            ">? {faction_name}</span>
        """, unsafe_allow_html=True)
        return

    prestige = float(faction.get("prestigio", 0))
    is_hegemon = faction.get("es_hegemon", False)
    color = faction.get("color_hex", Colors.TEXT_SECONDARY)

    icon = "&#128081;" if is_hegemon else "&#9733;"
    prestige_text = f" ({prestige:.1f}%)" if show_prestige else ""

    st.markdown(f"""
        <span style="
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            background: {color}15;
            border: 1px solid {color}40;
            border-radius: 4px;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 600;
            color: {color};
        ">{icon} {faction_name}{prestige_text}</span>
    """, unsafe_allow_html=True)


def render_prestige_chart():
    """
    Renderiza un grafico de distribucion de prestigio.
    """
    import pandas as pd

    factions = get_all_factions()
    if not factions:
        return

    render_terminal_header(
        title="DISTRIBUCION DE PODER",
        subtitle="ANALISIS GRAFICO",
        icon="&#128200;"
    )

    data = {
        "Faccion": [f["nombre"] for f in factions],
        "Prestigio": [float(f["prestigio"]) for f in factions]
    }
    df = pd.DataFrame(data)
    df = df.set_index("Faccion")

    st.bar_chart(df)


def render_faction_comparison(faction_a_name: str, faction_b_name: str):
    """
    Compara dos facciones lado a lado con estilo terminal.
    """
    from data.faction_repository import get_faction_by_name, get_faction_statistics

    faction_a = get_faction_by_name(faction_a_name)
    faction_b = get_faction_by_name(faction_b_name)

    if not faction_a or not faction_b:
        st.error("Una o ambas facciones no existen")
        return

    render_terminal_header(
        title="ANALISIS COMPARATIVO",
        subtitle=f"{faction_a_name} vs {faction_b_name}",
        icon="&#9878;"
    )

    col1, col2 = st.columns(2)

    for col, faction in [(col1, faction_a), (col2, faction_b)]:
        with col:
            prestige = float(faction.get("prestigio", 0))
            is_hegemon = faction.get("es_hegemon", False)
            color = faction.get("color_hex", Colors.TEXT_SECONDARY)
            stats = get_faction_statistics(faction["id"])

            state_color, state_text, _ = _get_faction_state(prestige, is_hegemon)

            st.markdown(f"""
                <div style="
                    background: {Colors.BG_CARD};
                    border: 1px solid {color}40;
                    border-top: 3px solid {color};
                    border-radius: 8px;
                    padding: 16px;
                ">
                    <div style="
                        font-family: 'Orbitron', sans-serif;
                        font-size: 1.1em;
                        color: {Colors.TEXT_PRIMARY};
                        margin-bottom: 12px;
                    ">{faction['nombre']}</div>

                    <div style="
                        font-family: 'Share Tech Mono', monospace;
                        font-size: 2em;
                        color: {state_color};
                        margin-bottom: 8px;
                    ">{prestige:.1f}%</div>

                    {"<div style='color: " + Colors.LEGENDARY + "; font-size: 0.8em;'>&#128081; HEGEMON</div>" if is_hegemon else ""}

                    <div style="
                        margin-top: 12px;
                        padding-top: 12px;
                        border-top: 1px solid {Colors.BORDER_DIM};
                    ">
                        <div style="
                            display: flex;
                            justify-content: space-between;
                            font-family: 'Share Tech Mono', monospace;
                            font-size: 0.75em;
                            color: {Colors.TEXT_SECONDARY};
                            margin-bottom: 4px;
                        ">
                            <span>Ganado:</span>
                            <span style="color: {Colors.SUCCESS};">+{stats['total_gained']:.1f}%</span>
                        </div>
                        <div style="
                            display: flex;
                            justify-content: space-between;
                            font-family: 'Share Tech Mono', monospace;
                            font-size: 0.75em;
                            color: {Colors.TEXT_SECONDARY};
                            margin-bottom: 4px;
                        ">
                            <span>Perdido:</span>
                            <span style="color: {Colors.DANGER};">-{stats['total_lost']:.1f}%</span>
                        </div>
                        <div style="
                            display: flex;
                            justify-content: space-between;
                            font-family: 'Share Tech Mono', monospace;
                            font-size: 0.75em;
                            color: {Colors.TEXT_PRIMARY};
                            font-weight: 600;
                        ">
                            <span>Neto:</span>
                            <span>{stats['net_change']:+.1f}%</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # Resultado de la comparacion
    prestige_a = float(faction_a.get("prestigio", 0))
    prestige_b = float(faction_b.get("prestigio", 0))
    difference = prestige_a - prestige_b

    st.markdown("<br>", unsafe_allow_html=True)

    if difference > 0:
        result_text = f"{faction_a['nombre']} domina con +{abs(difference):.1f}%"
        result_color = faction_a.get("color_hex", Colors.INFO)
    elif difference < 0:
        result_text = f"{faction_b['nombre']} domina con +{abs(difference):.1f}%"
        result_color = faction_b.get("color_hex", Colors.INFO)
    else:
        result_text = "Equilibrio de poder"
        result_color = Colors.WARNING

    st.markdown(f"""
        <div style="
            text-align: center;
            background: {result_color}15;
            border: 1px solid {result_color}40;
            border-radius: 6px;
            padding: 12px;
        ">
            <span style="
                font-family: 'Orbitron', sans-serif;
                font-size: 0.9em;
                color: {result_color};
            ">&#9878; {result_text}</span>
        </div>
    """, unsafe_allow_html=True)


def render_prestige_history_feed(limit: int = 10):
    """
    Muestra un feed de transferencias recientes de prestigio.
    """
    from data.faction_repository import get_prestige_history, get_faction_by_id

    history = get_prestige_history(limit=limit)

    if not history:
        st.info("No hay historial de transferencias de prestigio")
        return

    render_terminal_header(
        title="REGISTRO DE CONFLICTOS",
        subtitle="TRANSFERENCIAS DE PRESTIGIO RECIENTES",
        icon="&#128220;"
    )

    for event in history:
        attacker = get_faction_by_id(event.get("attacker_faction_id"))
        defender = get_faction_by_id(event.get("defender_faction_id"))
        amount = float(event.get("amount", 0))
        idp = float(event.get("idp_multiplier", 1.0))
        reason = event.get("reason", "Evento desconocido")
        tick = event.get("tick", "?")

        if attacker and defender:
            attacker_color = attacker.get("color_hex", Colors.SUCCESS)
            defender_color = defender.get("color_hex", Colors.DANGER)

            with st.expander(f"TICK {tick}: {attacker['nombre']} vs {defender['nombre']}", expanded=False):
                st.markdown(f"""
                    <div style="
                        background: {Colors.BG_DARK};
                        border-radius: 6px;
                        padding: 12px;
                    ">
                        <div style="
                            font-family: 'Rajdhani', sans-serif;
                            font-size: 1em;
                            color: {Colors.TEXT_PRIMARY};
                            margin-bottom: 10px;
                        ">&#9876; {reason}</div>

                        <div style="
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            gap: 12px;
                            margin: 12px 0;
                        ">
                            <span style="
                                font-family: 'Rajdhani', sans-serif;
                                font-weight: 600;
                                color: {attacker_color};
                            ">{attacker['nombre']}</span>
                            <span style="
                                font-family: 'Share Tech Mono', monospace;
                                color: {Colors.SUCCESS};
                            ">+{amount:.2f}%</span>
                            <span style="color: {Colors.TEXT_DIM};">&#8592;</span>
                            <span style="
                                font-family: 'Share Tech Mono', monospace;
                                color: {Colors.DANGER};
                            ">-{amount:.2f}%</span>
                            <span style="
                                font-family: 'Rajdhani', sans-serif;
                                font-weight: 600;
                                color: {defender_color};
                            ">{defender['nombre']}</span>
                        </div>

                        <div style="
                            font-family: 'Share Tech Mono', monospace;
                            font-size: 0.75em;
                            color: {Colors.TEXT_DIM};
                            text-align: center;
                        ">Multiplicador IDP: x{idp:.2f}</div>
                    </div>
                """, unsafe_allow_html=True)
