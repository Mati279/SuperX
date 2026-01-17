# ui/styles.py
"""
Sistema de Estilos Globales - Terminal de Comando Galactico.
CSS maestro para la interfaz sci-fi de SuperX Engine.
"""

import streamlit as st
from config.app_constants import UI_COLOR_NOMINAL, UI_COLOR_LOCK_IN, UI_COLOR_FROZEN


# --- Paleta de Colores del Terminal ---
class Colors:
    """Paleta de colores del terminal galactico."""
    # Estados del sistema
    NOMINAL = UI_COLOR_NOMINAL      # #56d59f - Verde
    LOCK_IN = UI_COLOR_LOCK_IN      # #f6c45b - Naranja
    FROZEN = UI_COLOR_FROZEN        # #f06464 - Rojo

    # UI Base
    BG_DARK = "#0a0e17"
    BG_PANEL = "#12171f"
    BG_CARD = "#1a1f2e"
    BG_ELEVATED = "#242936"

    # Bordes y lineas
    BORDER_DIM = "#2a3040"
    BORDER_ACTIVE = "#3d4560"

    # Texto
    TEXT_PRIMARY = "#e8eaed"
    TEXT_SECONDARY = "#9aa0a6"
    TEXT_DIM = "#5f6368"

    # Atributos de personaje
    ATTR_FUERZA = "#ff6b6b"
    ATTR_AGILIDAD = "#4ecdc4"
    ATTR_INTELECTO = "#45b7d1"
    ATTR_TECNICA = "#f9ca24"
    ATTR_PRESENCIA = "#a55eea"
    ATTR_VOLUNTAD = "#26de81"

    # Rareza/Calidad
    LEGENDARY = "#ffd700"
    EPIC = "#a55eea"
    RARE = "#45b7d1"
    COMMON = "#888888"

    # Acciones
    SUCCESS = "#26de81"
    WARNING = "#f9ca24"
    DANGER = "#ff6b6b"
    INFO = "#45b7d1"


def get_master_css() -> str:
    """
    Retorna el CSS maestro global para inyectar en la aplicacion.
    Estilo: Terminal de Comando Galactico (Cyberpunk/Stellaris).
    """
    return f"""
    <style>
    /* === GOOGLE FONTS === */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Share+Tech+Mono&family=Rajdhani:wght@300;400;500;600;700&display=swap');

    /* === ROOT VARIABLES === */
    :root {{
        --color-nominal: {Colors.NOMINAL};
        --color-lock-in: {Colors.LOCK_IN};
        --color-frozen: {Colors.FROZEN};
        --bg-dark: {Colors.BG_DARK};
        --bg-panel: {Colors.BG_PANEL};
        --bg-card: {Colors.BG_CARD};
        --border-dim: {Colors.BORDER_DIM};
        --text-primary: {Colors.TEXT_PRIMARY};
        --text-secondary: {Colors.TEXT_SECONDARY};
        --glow-nominal: 0 0 10px {Colors.NOMINAL}40, 0 0 20px {Colors.NOMINAL}20;
        --glow-warning: 0 0 10px {Colors.LOCK_IN}40, 0 0 20px {Colors.LOCK_IN}20;
        --glow-danger: 0 0 10px {Colors.FROZEN}40, 0 0 20px {Colors.FROZEN}20;
    }}

    /* === GLOBAL RESET === */
    .stApp {{
        background: linear-gradient(180deg, {Colors.BG_DARK} 0%, #0d1117 100%);
    }}

    /* === TYPOGRAPHY === */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
        font-family: 'Orbitron', sans-serif !important;
        letter-spacing: 1px;
        color: {Colors.TEXT_PRIMARY} !important;
    }}

    h1 {{ text-shadow: 0 0 20px {Colors.NOMINAL}40; }}

    p, span, div, .stMarkdown p {{
        font-family: 'Rajdhani', sans-serif;
    }}

    code, .stCodeBlock, pre {{
        font-family: 'Share Tech Mono', monospace !important;
    }}

    /* === SCROLLBAR PERSONALIZADO === */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}

    ::-webkit-scrollbar-track {{
        background: {Colors.BG_DARK};
        border-radius: 4px;
    }}

    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, {Colors.BORDER_ACTIVE} 0%, {Colors.BORDER_DIM} 100%);
        border-radius: 4px;
        border: 1px solid {Colors.BORDER_DIM};
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: {Colors.NOMINAL};
        box-shadow: var(--glow-nominal);
    }}

    /* === SIDEBAR === */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {Colors.BG_PANEL} 0%, {Colors.BG_DARK} 100%) !important;
        border-right: 1px solid {Colors.BORDER_DIM} !important;
    }}

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        font-family: 'Rajdhani', sans-serif;
    }}

    /* === BOTONES === */
    .stButton > button {{
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 500;
        letter-spacing: 0.5px;
        border-radius: 4px !important;
        border: 1px solid {Colors.BORDER_DIM} !important;
        background: linear-gradient(180deg, {Colors.BG_ELEVATED} 0%, {Colors.BG_CARD} 100%) !important;
        color: {Colors.TEXT_PRIMARY} !important;
        transition: all 0.2s ease !important;
        text-transform: uppercase;
        font-size: 0.85em !important;
    }}

    .stButton > button:hover {{
        border-color: {Colors.NOMINAL} !important;
        box-shadow: var(--glow-nominal) !important;
        color: {Colors.NOMINAL} !important;
    }}

    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {Colors.NOMINAL}20 0%, {Colors.NOMINAL}10 100%) !important;
        border-color: {Colors.NOMINAL} !important;
        color: {Colors.NOMINAL} !important;
    }}

    .stButton > button[kind="primary"]:hover {{
        background: linear-gradient(135deg, {Colors.NOMINAL}40 0%, {Colors.NOMINAL}20 100%) !important;
        box-shadow: var(--glow-nominal) !important;
    }}

    /* === CONTAINERS & CARDS === */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: {Colors.BG_CARD} !important;
        border: 1px solid {Colors.BORDER_DIM} !important;
        border-radius: 8px !important;
    }}

    .stExpander {{
        background: {Colors.BG_CARD} !important;
        border: 1px solid {Colors.BORDER_DIM} !important;
        border-radius: 6px !important;
    }}

    .stExpander:hover {{
        border-color: {Colors.BORDER_ACTIVE} !important;
    }}

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
        background: {Colors.BG_DARK};
        border-radius: 8px;
        padding: 4px;
    }}

    .stTabs [data-baseweb="tab"] {{
        font-family: 'Orbitron', sans-serif !important;
        font-size: 0.8em;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        color: {Colors.TEXT_SECONDARY} !important;
        background: transparent !important;
        border-radius: 4px !important;
        padding: 8px 16px !important;
    }}

    .stTabs [aria-selected="true"] {{
        background: {Colors.BG_ELEVATED} !important;
        color: {Colors.NOMINAL} !important;
        border: 1px solid {Colors.NOMINAL}40 !important;
    }}

    /* === INPUTS === */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div {{
        font-family: 'Share Tech Mono', monospace !important;
        background: {Colors.BG_DARK} !important;
        border: 1px solid {Colors.BORDER_DIM} !important;
        color: {Colors.TEXT_PRIMARY} !important;
        border-radius: 4px !important;
    }}

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {{
        border-color: {Colors.NOMINAL} !important;
        box-shadow: var(--glow-nominal) !important;
    }}

    /* === METRICS === */
    [data-testid="stMetricValue"] {{
        font-family: 'Orbitron', sans-serif !important;
        color: {Colors.NOMINAL} !important;
    }}

    [data-testid="stMetricLabel"] {{
        font-family: 'Rajdhani', sans-serif !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: {Colors.TEXT_SECONDARY} !important;
    }}

    /* === ALERTS === */
    .stAlert {{
        font-family: 'Rajdhani', sans-serif;
        border-radius: 6px !important;
    }}

    /* === CHAT === */
    .stChatMessage {{
        background: {Colors.BG_CARD} !important;
        border: 1px solid {Colors.BORDER_DIM} !important;
        border-radius: 8px !important;
    }}

    .stChatInputContainer {{
        border: 1px solid {Colors.BORDER_DIM} !important;
        background: {Colors.BG_DARK} !important;
    }}

    .stChatInputContainer:focus-within {{
        border-color: {Colors.NOMINAL} !important;
        box-shadow: var(--glow-nominal) !important;
    }}

    /* === PROGRESS BARS === */
    .stProgress > div > div > div {{
        background: linear-gradient(90deg, {Colors.NOMINAL} 0%, {Colors.NOMINAL}80 100%) !important;
    }}

    /* === DIVIDERS === */
    hr {{
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent 0%, {Colors.BORDER_DIM} 50%, transparent 100%) !important;
    }}

    /* === DIALOG/MODAL === */
    [data-testid="stDialog"] {{
        background: {Colors.BG_PANEL} !important;
        border: 1px solid {Colors.NOMINAL}40 !important;
        box-shadow: 0 0 40px {Colors.NOMINAL}20, 0 20px 60px rgba(0,0,0,0.5) !important;
    }}

    </style>
    """


def get_world_state_css(is_frozen: bool = False, is_lock_in: bool = False) -> str:
    """
    Retorna CSS adicional segun el estado del mundo.
    Cambia el tono de toda la UI.
    """
    if is_frozen:
        return f"""
        <style>
        .stApp {{
            background: linear-gradient(180deg, #1a0a0a 0%, #0d0505 100%) !important;
        }}

        h1 {{
            text-shadow: 0 0 20px {Colors.FROZEN}60 !important;
            color: {Colors.FROZEN} !important;
        }}

        [data-testid="stSidebar"] {{
            border-right-color: {Colors.FROZEN}60 !important;
        }}

        .stButton > button:hover {{
            border-color: {Colors.FROZEN} !important;
            box-shadow: var(--glow-danger) !important;
        }}
        </style>
        """
    elif is_lock_in:
        return f"""
        <style>
        .stApp {{
            background: linear-gradient(180deg, #1a1508 0%, #0d0b05 100%) !important;
        }}

        h1 {{
            text-shadow: 0 0 20px {Colors.LOCK_IN}60 !important;
        }}

        [data-testid="stSidebar"] {{
            border-right-color: {Colors.LOCK_IN}60 !important;
        }}
        </style>
        """
    return ""


# === COMPONENTES REUTILIZABLES ===

def render_terminal_header(title: str, subtitle: str = "", icon: str = "") -> None:
    """Renderiza un header estilo terminal."""
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {Colors.BG_CARD} 0%, {Colors.BG_PANEL} 100%);
            border: 1px solid {Colors.BORDER_DIM};
            border-left: 3px solid {Colors.NOMINAL};
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 20px;
        ">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.8em;">{icon}</span>
                <div>
                    <h2 style="
                        font-family: 'Orbitron', sans-serif;
                        color: {Colors.TEXT_PRIMARY};
                        margin: 0;
                        font-size: 1.4em;
                        letter-spacing: 2px;
                    ">{title}</h2>
                    <span style="
                        font-family: 'Share Tech Mono', monospace;
                        color: {Colors.TEXT_DIM};
                        font-size: 0.8em;
                    ">{subtitle}</span>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_stat_bar(
    label: str,
    value: int,
    max_value: int = 20,
    color: str = Colors.NOMINAL,
    show_value: bool = True
) -> None:
    """Renderiza una barra de stat estilo terminal."""
    percentage = min(100, (value / max_value) * 100)

    st.markdown(f"""
        <div style="margin-bottom: 10px;">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 4px;
            ">
                <span style="
                    font-family: 'Orbitron', sans-serif;
                    font-size: 0.7em;
                    letter-spacing: 1px;
                    color: {Colors.TEXT_SECONDARY};
                    text-transform: uppercase;
                ">{label}</span>
                {"<span style='font-family: Share Tech Mono, monospace; font-weight: 600; color: " + color + ";'>" + str(value) + "</span>" if show_value else ""}
            </div>
            <div style="
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER_DIM};
                border-radius: 2px;
                height: 6px;
                overflow: hidden;
            ">
                <div style="
                    background: linear-gradient(90deg, {color} 0%, {color}80 100%);
                    width: {percentage}%;
                    height: 100%;
                    box-shadow: 0 0 8px {color}40;
                    transition: width 0.3s ease;
                "></div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_data_chip(label: str, value: str, color: str = Colors.NOMINAL) -> str:
    """Retorna HTML para un chip de datos."""
    return f"""
        <span style="
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            margin: 2px;
            background: {color}15;
            border: 1px solid {color}40;
            border-radius: 4px;
            font-family: 'Share Tech Mono', monospace;
            font-size: 0.75em;
        ">
            <span style="color: {Colors.TEXT_SECONDARY};">{label}:</span>
            <span style="color: {color}; font-weight: 600;">{value}</span>
        </span>
    """


def render_status_badge(status: str) -> str:
    """Retorna HTML para un badge de estado."""
    status_config = {
        "Disponible": (Colors.SUCCESS, "ONLINE"),
        "En Mision": (Colors.WARNING, "DEPLOYED"),
        "Descansando": (Colors.INFO, "STANDBY"),
        "Herido": (Colors.DANGER, "CRITICAL"),
        "Entrenando": (Colors.EPIC, "TRAINING"),
    }

    color, text = status_config.get(status, (Colors.TEXT_DIM, status.upper()))

    return f"""
        <span style="
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            background: {color}20;
            border: 1px solid {color};
            border-radius: 3px;
            font-family: 'Orbitron', sans-serif;
            font-size: 0.65em;
            letter-spacing: 1px;
            color: {color};
            text-transform: uppercase;
        ">
            <span style="
                width: 6px;
                height: 6px;
                background: {color};
                border-radius: 50%;
                box-shadow: 0 0 6px {color};
            "></span>
            {text}
        </span>
    """


def render_resource_display(icon: str, label: str, value: int, color: str = Colors.NOMINAL) -> str:
    """Retorna HTML para mostrar un recurso."""
    return f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: {Colors.BG_CARD};
            border: 1px solid {Colors.BORDER_DIM};
            border-radius: 6px;
        ">
            <span style="font-size: 1.2em;">{icon}</span>
            <div>
                <div style="
                    font-family: 'Rajdhani', sans-serif;
                    font-size: 0.7em;
                    color: {Colors.TEXT_DIM};
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">{label}</div>
                <div style="
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 1.1em;
                    font-weight: 600;
                    color: {color};
                ">{value:,}</div>
            </div>
        </div>
    """


def inject_global_styles() -> None:
    """Inyecta los estilos globales en la pagina actual."""
    st.markdown(get_master_css(), unsafe_allow_html=True)


def inject_world_state_styles(is_frozen: bool = False, is_lock_in: bool = False) -> None:
    """Inyecta estilos adicionales segun el estado del mundo."""
    css = get_world_state_css(is_frozen, is_lock_in)
    if css:
        st.markdown(css, unsafe_allow_html=True)
