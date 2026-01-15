# ui/faction_roster.py
import streamlit as st
from typing import Dict, Any, List
from data.character_repository import get_all_characters_by_player_id, update_character
from ui.state import get_player

# --- Constantes de Estado ---
POSIBLES_ESTADOS = ["Disponible", "En Misión", "Descansando", "Herido", "Entrenando"]

def render_character_card(char: Dict[str, Any]):
    """Muestra la tarjeta de un personaje individual."""
    
    stats = char.get('stats_json', {})
    bio = stats.get('bio', {})
    atributos = stats.get('atributos', {})
    
    # Nivel: Suma de atributos (o un campo 'nivel' si lo tienes)
    nivel = sum(atributos.values()) if atributos else 0
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.caption(f"ID: {char['id']}")
        st.metric(label="Nivel", value=nivel)

    with col2:
        st.subheader(f"{char['nombre']}")
        st.write(f"**Rango:** {char.get('rango', 'N/A')}")
        st.write(f"**Clase:** {bio.get('clase', 'N/A')}")
    
    with st.expander("Ver detalles y asignar estado"):
        st.write("---")
        
        # --- Asignación de Estado ---
        current_status_index = POSIBLES_ESTADOS.index(char['estado']) if char['estado'] in POSIBLES_ESTADOS else 0
        
        new_status = st.selectbox(
            "Asignar Estado:",
            options=POSIBLES_ESTADOS,
            index=current_status_index,
            key=f"status_{char['id']}" # Clave única para cada selectbox
        )
        
        if new_status != char['estado']:
            if st.button("Confirmar Cambio de Estado", key=f"btn_status_{char['id']}"):
                try:
                    update_character(char['id'], {'estado': new_status})
                    st.success(f"Estado de {char['nombre']} actualizado a '{new_status}'.")
                    st.rerun() # Refresca la página para mostrar el cambio
                except Exception as e:
                    st.error(f"No se pudo actualizar el estado: {e}")

        st.write("---")
        st.write("**Atributos:**")
        attr_cols = st.columns(len(atributos))
        for i, (attr, value) in enumerate(atributos.items()):
            attr_cols[i].metric(label=attr.capitalize(), value=value)

def show_faction_roster():
    """Página principal para mostrar la lista de personajes de la facción."""
    st.title("Comando de Facción")
    st.markdown("---")

    player = get_player()
    if not player:
        st.warning("No se ha podido identificar al jugador. Por favor, vuelve a iniciar sesión.")
        return

    try:
        characters: List[Dict[str, Any]] = get_all_characters_by_player_id(player['id'])
        
        if not characters:
            st.info("No tienes personal en tu facción más allá de tu comandante. ¡Es hora de reclutar!")
            return

        st.header("Miembros de la Tripulación")
        
        # Separar comandante del resto
        commander = next((c for c in characters if c.get('es_comandante')), None)
        crew = [c for c in characters if not c.get('es_comandante')]

        if commander:
            st.subheader("Comandante")
            render_character_card(commander)
            st.markdown("---")

        if crew:
            st.subheader("Operativos")
            for char in sorted(crew, key=lambda x: x['nombre']):
                 with st.container(border=True):
                    render_character_card(char)
                    st.write("") # Espacio

    except Exception as e:
        st.error(f"Error al cargar la lista de personajes: {e}")
        st.exception(e)
