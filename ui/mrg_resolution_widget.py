# ui/mrg_resolution_widget.py (Completo)
"""Widget de UI para mostrar y resolver tiradas MRG."""
import streamlit as st
from core.mrg_engine import MRGResult, ResultType

# Diccionario de configuración visual para los resultados (v2.1)
RESULT_UI_CONFIG = {
    ResultType.CRITICAL_SUCCESS: {
        "title": "¡ÉXITO CRÍTICO!",
        "description": "Ejecución perfecta.",
        "color": "#FFD700"  # Dorado
    },
    ResultType.TOTAL_SUCCESS: {
        "title": "ÉXITO TOTAL",
        "description": "Objetivo cumplido.",
        "color": "#28a745"  # Verde
    },
    ResultType.PARTIAL_SUCCESS: {
        "title": "ÉXITO PARCIAL",
        "description": "Cumplido con complicaciones.",
        "color": "#17a2b8"  # Cyan
    },
    ResultType.PARTIAL_FAILURE: {
        "title": "FALLO PARCIAL",
        "description": "Objetivo no logrado, sin desastre.",
        "color": "#fd7e14"  # Naranja
    },
    ResultType.TOTAL_FAILURE: {
        "title": "FALLO TOTAL",
        "description": "Fracaso completo.",
        "color": "#dc3545"  # Rojo
    },
    ResultType.CRITICAL_FAILURE: {
        "title": "¡PIFIA!",
        "description": "Desastre catastrófico.",
        "color": "#8b0000"  # Rojo oscuro
    }
}


def render_mrg_roll_animation(result: MRGResult):
    """Renderiza la animación de dados y resultado (Versión Compacta V2)."""

    # Contenedor principal con estilo reducido y fuentes más pequeñas
    st.markdown("""
        <style>
        .dice-container {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin: 5px 0;
        }
        .dice {
            font-size: 1.5em; /* Reducido de 2.2em */
            animation: roll 0.5s ease-out;
        }
        @keyframes roll {
            0% { transform: rotate(0deg) scale(0.5); opacity: 0; }
            50% { transform: rotate(180deg) scale(1.1); }
            100% { transform: rotate(360deg) scale(1); opacity: 1; }
        }
        </style>
    """, unsafe_allow_html=True)

    # Mostrar dados
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown(f"""
            <div class="dice-container">
                <span class="dice">🎲</span>
                <span style="font-size: 1.1em; line-height: 2;">+</span>
                <span class="dice">🎲</span>
            </div>
        """, unsafe_allow_html=True)

        # Resultado numérico compacto
        st.markdown(f"""
            <div style="text-align: center; margin: 2px 0;">
                <span style="font-size: 1.0em; font-family: monospace;">
                    {result.roll.die_1} + {result.roll.die_2} =
                    <strong style="font-size: 1.1em;">{result.roll.total}</strong>
                </span>
            </div>
        """, unsafe_allow_html=True)


def render_mrg_calculation(result: MRGResult):
    """
    Muestra el desglose del cálculo (Layout Compacto 2x2).
    Sustituye st.metric por markdown para ahorrar espacio vertical.
    """

    st.markdown("###### 📊 Cálculo")
    
    # Obtener detalles para tooltips, con defaults seguros.
    details = getattr(result, "details", {}) or {}
    
    # Textos de ayuda enriquecidos
    tip_roll = details.get("roll", "Suma natural de 2d50")
    
    # Si viene el nombre de la dificultad, lo mostramos
    diff_name = details.get("difficulty_name", "")
    tip_diff = details.get("difficulty", "Dificultad base")
    if diff_name:
        tip_diff = f"Dificultad {diff_name}: {result.difficulty}"

    # Si viene explicación del bono, la usamos
    tip_bonus = details.get("bonus", "Bono derivado de habilidades")
    if "bonus_explanation" in details:
        tip_bonus = details["bonus_explanation"]
        
    tip_margin = "Margen = (Tirada + Bono) - Dificultad"

    # Usamos 2 columnas para apilar verticalmente y ahorrar ancho
    col_a, col_b = st.columns(2)

    # Renderizado compacto estilo clave: valor
    with col_a:
        st.markdown(f"**Tirada:** {result.roll.total}", help=tip_roll)
        st.markdown(f"**Dificultad:** {result.difficulty}", help=tip_diff)
        
    with col_b:
        st.markdown(f"**Bono:** +{result.bonus_applied}", help=tip_bonus)
        margin_delta = "+" if result.margin >= 0 else ""
        st.markdown(f"**Margen:** {margin_delta}{result.margin}", help=tip_margin)

    # Fórmula simplificada al pie
    st.caption(f"**F:** {result.roll.total} + {result.bonus_applied} - {result.difficulty} = **{result.margin}**")


def render_mrg_result(result: MRGResult):
    """Muestra el resultado con estilo apropiado (Compacto)."""

    config = RESULT_UI_CONFIG.get(result.result_type, {
        "title": "DESCONOCIDO",
        "description": "Error de estado",
        "color": "#808080"
    })

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {config['color']}22, {config['color']}11);
            border: 1px solid {config['color']};
            border-radius: 6px;
            padding: 8px;
            text-align: center;
            margin: 5px 0;
        ">
            <h5 style="color: {config['color']}; margin: 0; font-size: 1.0em;">{config['title']}</h5>
            <p style="margin: 2px 0 0 0; color: #ccc; font-size: 0.75em; line-height: 1.1;">{config['description']}</p>
        </div>
    """, unsafe_allow_html=True)


def render_full_mrg_resolution(result: MRGResult):
    """
    Renderiza el flujo completo de resolución MRG.
    Versión Ultracompacta para Sidebar o Columna Lateral.
    Eliminados los bordes y dividers pesados.
    """
    
    # Renderizado directo sin contenedor externo para mejor integración
    st.markdown(f"**🎲 Acción:** {result.action_description or 'Resolución'}")

    st.write("---")

    # 1. Animación de dados (Compacta)
    render_mrg_roll_animation(result)

    # 2. Resultado (Compacto)
    render_mrg_result(result)

    st.write("---")

    # 3. Cálculo (Compacto markdown)
    render_mrg_calculation(result)