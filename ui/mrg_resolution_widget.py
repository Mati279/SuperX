# ui/mrg_resolution_widget.py
"""Widget de UI para mostrar y resolver tiradas MRG."""
import streamlit as st
from core.mrg_engine import MRGResult, ResultType

# Diccionario de configuración visual para los resultados (v2.1)
# Desacoplado del motor para facilitar cambios de texto/color en la UI
RESULT_UI_CONFIG = {
    ResultType.CRITICAL_SUCCESS: {
        "title": "¡ÉXITO CRÍTICO!",
        "description": "Una ejecución perfecta e impecable. El margen es irrelevante.",
        "color": "#FFD700"  # Dorado
    },
    ResultType.TOTAL_SUCCESS: {
        "title": "ÉXITO TOTAL",
        "description": "El objetivo se ha cumplido sin contratiempos.",
        "color": "#28a745"  # Verde
    },
    ResultType.PARTIAL_SUCCESS: {
        "title": "ÉXITO PARCIAL",
        "description": "Objetivo cumplido, pero con posibles complicaciones menores.",
        "color": "#17a2b8"  # Cyan
    },
    ResultType.PARTIAL_FAILURE: {
        "title": "FALLO PARCIAL",
        "description": "No se logró el objetivo principal, pero se evitaron desastres mayores.",
        "color": "#fd7e14"  # Naranja
    },
    ResultType.TOTAL_FAILURE: {
        "title": "FALLO TOTAL",
        "description": "La acción ha fracasado completamente.",
        "color": "#dc3545"  # Rojo
    },
    ResultType.CRITICAL_FAILURE: {
        "title": "¡PIFIA!",
        "description": "Un desastre catastrófico. El margen es irrelevante.",
        "color": "#8b0000"  # Rojo oscuro
    }
}


def render_mrg_roll_animation(result: MRGResult):
    """Renderiza la animación de dados y resultado."""

    # Contenedor principal con estilo
    st.markdown("""
        <style>
        .dice-container {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
        }
        .dice {
            font-size: 4em;
            animation: roll 0.5s ease-out;
        }
        @keyframes roll {
            0% { transform: rotate(0deg) scale(0.5); opacity: 0; }
            50% { transform: rotate(180deg) scale(1.2); }
            100% { transform: rotate(360deg) scale(1); opacity: 1; }
        }
        </style>
    """, unsafe_allow_html=True)

    # Mostrar dados
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
            <div class="dice-container">
                <span class="dice">🎲</span>
                <span style="font-size: 3em; line-height: 1.5;">+</span>
                <span class="dice">🎲</span>
            </div>
        """, unsafe_allow_html=True)

        # Resultado numérico
        st.markdown(f"""
            <div style="text-align: center; margin: 10px 0;">
                <span style="font-size: 2em; font-family: monospace;">
                    {result.roll.die_1} + {result.roll.die_2} =
                    <strong style="font-size: 1.2em;">{result.roll.total}</strong>
                </span>
            </div>
        """, unsafe_allow_html=True)


def render_mrg_calculation(result: MRGResult):
    """Muestra el desglose del cálculo."""

    st.markdown("### 📊 Cálculo")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Tirada", result.roll.total)
    with col2:
        st.metric("Bono", f"+{result.bonus_applied}",
                  help=f"Mérito: {result.merit_points} → Bono asintótico: {result.bonus_applied}")
    with col3:
        st.metric("Dificultad", result.difficulty)
    with col4:
        margin_delta = "+" if result.margin >= 0 else ""
        st.metric("Margen", f"{margin_delta}{result.margin}")

    # Fórmula
    st.caption(f"**Fórmula:** {result.roll.total} (tirada) + {result.bonus_applied} (bono) - {result.difficulty} (dificultad) = **{result.margin}**")


def render_mrg_result(result: MRGResult):
    """Muestra el resultado con estilo apropiado."""

    config = RESULT_UI_CONFIG.get(result.result_type, {
        "title": "RESULTADO DESCONOCIDO",
        "description": "",
        "color": "#808080"
    })

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {config['color']}22, {config['color']}11);
            border: 2px solid {config['color']};
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        ">
            <h2 style="color: {config['color']}; margin: 0;">{config['title']}</h2>
            <p style="margin: 10px 0 0 0; color: #ccc;">{config['description']}</p>
        </div>
    """, unsafe_allow_html=True)


def render_full_mrg_resolution(result: MRGResult):
    """
    Renderiza el flujo completo de resolución MRG.
    Incluye animación, cálculo y resultado.
    """

    with st.container(border=True):
        st.markdown(f"## 🎲 Resolución: {result.action_description or 'Acción'}")

        st.divider()

        # 1. Animación de dados
        render_mrg_roll_animation(result)

        # 2. Cálculo
        render_mrg_calculation(result)

        st.divider()

        # 3. Resultado
        render_mrg_result(result)