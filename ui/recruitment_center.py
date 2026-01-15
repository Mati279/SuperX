# ui/recruitment_center.py
import streamlit as st
from typing import Dict, Any
from ui.state import get_player
from core.generator import generate_candidate_pool
from core.recruitment_logic import can_recruit, process_recruitment
from data.player_repository import get_player_credits, update_player_credits
from data.character_repository import create_character, get_all_characters_by_player_id

def handle_recruitment(player: Dict[str, Any], candidate: Dict[str, Any], player_credits: int):
    """Lógica para procesar el click en el botón de reclutar."""
    can_afford, message = can_recruit(player_credits, candidate['costo'])
    
    if not can_afford:
        st.error(message)
        return

    try:
        # Usar la lógica de negocio para preparar los datos
        new_credits, new_character_data = process_recruitment(
            player_id=player['id'],
            player_credits=player_credits,
            candidate=candidate
        )
        
        # Realizar las operaciones en la base de datos
        update_ok = update_player_credits(player['id'], new_credits)
        char_ok = create_character(player['id'], new_character_data)

        if update_ok and char_ok:
            st.success(f"¡{candidate['nombre']} ha sido reclutado para tu facción!")
            # Limpiar el candidato de la sesión para generar uno nuevo
            if 'recruitment_pool' in st.session_state:
                st.session_state.recruitment_pool = [
                    c for c in st.session_state.recruitment_pool if c['nombre'] != candidate['nombre']
                ]
            st.rerun()
        else:
            st.error("Error crítico: No se pudo completar el reclutamiento en la base de datos.")
            # Aquí habría que manejar la posible inconsistencia de datos (ej. se restaron créditos pero no se creó el pj)
            
    except Exception as e:
        st.error(f"Ocurrió un error inesperado durante el reclutamiento: {e}")

def show_recruitment_center():
    """Página para reclutar nuevos miembros para la facción."""
    st.title("Centro de Reclutamiento Galáctico")
    
    player = get_player()
    if not player:
        st.warning("Error de sesión. Por favor, inicie sesión de nuevo.")
        return

    # --- Mostrar Créditos del Jugador ---
    player_credits = get_player_credits(player['id'])
    st.header(f"Créditos Disponibles: {player_credits} C")
    st.markdown("---")

    # --- Generar y mostrar piscina de candidatos ---
    if 'recruitment_pool' not in st.session_state or not st.session_state.recruitment_pool:
        # Obtener nombres existentes para evitar duplicados
        all_chars = get_all_characters_by_player_id(player['id'])
        existing_names = [c['nombre'] for c in all_chars]
        st.session_state.recruitment_pool = generate_candidate_pool(3, existing_names)

    candidates = st.session_state.recruitment_pool

    if not candidates:
        st.info("No hay nuevos candidatos disponibles en este momento. Vuelve más tarde.")
        if st.button("Buscar nuevos candidatos"):
            del st.session_state.recruitment_pool
            st.rerun()
        return

    st.subheader("Candidatos Disponibles para Reclutar")
    
    cols = st.columns(len(candidates))

    for i, candidate in enumerate(candidates):
        with cols[i]:
            with st.container(border=True):
                st.subheader(candidate['nombre'])
                st.markdown(f"**Raza:** {candidate['raza']} | **Clase:** {candidate['clase']}")
                st.metric(label="Nivel Estimado", value=candidate['nivel'])
                
                stats = candidate.get('stats_json', {}).get('atributos', {})
                with st.expander("Ver Atributos"):
                    for attr, value in stats.items():
                        st.write(f"- {attr.capitalize()}: {value}")

                st.markdown(f"**Costo de Contratación:**")
                st.subheader(f"{candidate['costo']} C")

                # El botón para reclutar
                if st.button(f"Contratar a {candidate['nombre']}", key=f"recruit_{i}"):
                    handle_recruitment(player, candidate, player_credits)
    
    st.markdown("---")
    if st.button("Actualizar lista de Candidatos (costo: 50 C)"):
        can_afford, _ = can_recruit(player_credits, 50)
        if can_afford and update_player_credits(player['id'], player_credits - 50):
            del st.session_state.recruitment_pool
            st.rerun()
        else:
            st.error("No tienes suficientes créditos para actualizar la lista.")
