"""Widget de UI para mostrar y resolver tiradas MRG."""
import streamlit as st
from typing import Optional, Callable
from core.mrg_engine import (
    MRGResult,
    ResultType,
    BenefitType,
    MalusType,
    get_result_description,
    get_benefit_description,
    get_malus_description
)
from core.mrg_effects import apply_benefit, apply_malus


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

    desc = get_result_description(result.result_type)

    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {desc['color']}22, {desc['color']}11);
            border: 2px solid {desc['color']};
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        ">
            <h2 style="color: {desc['color']}; margin: 0;">{desc['title']}</h2>
            <p style="margin: 10px 0 0 0; color: #ccc;">{desc['description']}</p>
        </div>
    """, unsafe_allow_html=True)

    # Instrucción si requiere selección
    if result.requires_player_choice:
        st.info(f"👆 {desc['instruction']}")


def render_benefit_selection(
    result: MRGResult,
    player_id: int,
    faction_id: Optional[int] = None,
    energy_spent: int = 0,
    on_selection: Optional[Callable] = None
):
    """Renderiza los botones de selección de beneficio."""

    st.markdown("### 🎁 Elige tu Beneficio")

    cols = st.columns(len(result.available_benefits))

    for i, benefit in enumerate(result.available_benefits):
        info = get_benefit_description(benefit)
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{info['name']}**")
                st.caption(info['description'])

                if st.button(
                    f"Elegir {benefit.value.title()}",
                    key=f"benefit_{benefit.value}",
                    use_container_width=True,
                    type="primary"
                ):
                    # Aplicar beneficio
                    effect = apply_benefit(result, benefit, player_id, faction_id, energy_spent)

                    result.selected_benefit = benefit
                    st.success(f"✅ {info['effect']}")

                    if on_selection:
                        on_selection(benefit, effect)

                    st.rerun()


def render_malus_selection(
    result: MRGResult,
    player_id: int,
    faction_id: Optional[int] = None,
    on_selection: Optional[Callable] = None
):
    """Renderiza los botones de selección de malus."""

    st.markdown("### ⚠️ Elige tu Consecuencia")
    st.caption("Debes elegir una. No hay escape.")

    cols = st.columns(len(result.available_malus))

    for i, malus in enumerate(result.available_malus):
        info = get_malus_description(malus)
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"**{info['name']}**")
                st.caption(info['description'])

                if st.button(
                    f"Aceptar {malus.value.replace('_', ' ').title()}",
                    key=f"malus_{malus.value}",
                    use_container_width=True,
                    type="secondary"
                ):
                    # Aplicar malus
                    effect = apply_malus(result, malus, player_id, faction_id)

                    result.selected_malus = malus
                    st.warning(f"💔 {info['effect']}")

                    if on_selection:
                        on_selection(malus, effect)

                    st.rerun()


def render_full_mrg_resolution(
    result: MRGResult,
    player_id: int,
    faction_id: Optional[int] = None,
    energy_spent: int = 0
):
    """
    Renderiza el flujo completo de resolución MRG.
    Incluye animación, cálculo, resultado y selección si aplica.
    """

    with st.container(border=True):
        st.markdown(f"## 🎲 Resolución: {result.action_description or 'Acción'}")

        if result.entity_name:
            st.caption(f"Entidad: **{result.entity_name}**")

        st.divider()

        # 1. Animación de dados
        render_mrg_roll_animation(result)

        # 2. Cálculo
        render_mrg_calculation(result)

        st.divider()

        # 3. Resultado
        render_mrg_result(result)

        # 4. Selección si es necesaria
        if result.requires_player_choice:
            st.divider()

            if result.available_benefits:
                render_benefit_selection(result, player_id, faction_id, energy_spent)
            elif result.available_malus:
                render_malus_selection(result, player_id, faction_id)
