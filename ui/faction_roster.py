# ui/faction_roster.py
import streamlit as st
from .state import get_player
from data.character_repository import get_characters_by_player_id

def show_faction_roster():
    """
    Muestra la lista de miembros de la cuadrilla (facción).
    Formato: Rango - Nv. - Nombre - Estado - Acciones - Resumen - Botón Detalle.
    """
    player = get_player()
    if not player:
        st.error("No se pudo identificar al jugador.")
        return

    st.markdown("## 👥 Cuadrilla Operativa")
    st.caption("Personal bajo su mando directo.")
    st.write("")

    # Obtener personajes del jugador
    # Asumimos que existe esta función en el repositorio (patrón estándar)
    characters = get_characters_by_player_id(player.id)

    if not characters:
        st.info("No tienes miembros en tu cuadrilla actualmente.")
        return

    # --- ENCABEZADOS DE LA TABLA ---
    # Ajustamos las proporciones de las columnas para que quepan los datos
    # Rango(1.5) - Nv(0.8) - Nombre(2) - Estado(1.2) - Acciones(1) - Resumen(2.5) - Botón(1)
    cols = st.columns([1.5, 0.8, 2, 1.2, 1, 2.5, 1])
    
    headers = ["RANGO", "NV.", "NOMBRE", "ESTADO", "AP", "RESUMEN", "FICHA"]
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    
    st.divider()

    # --- LISTADO DE PERSONAJES ---
    for char in characters:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 0.8, 2, 1.2, 1, 2.5, 1])
        
        # Procesar datos para visualización
        rango_display = char.rango if char.rango else "Recluta"
        
        # Estado con color
        estado = char.estado if char.estado else "Activo"
        estado_color = "green" if estado == "Activo" else "orange" if estado == "Misión" else "red"
        
        # Acciones (AP)
        ap_display = f"{char.acciones_actuales}/{char.acciones_maximas}"
        
        # Resumen (Clase / Arquetipo / Trasfondo)
        # Concatenamos clase y trasfondo si existen, o usamos "Personal" por defecto
        clase = char.clase if hasattr(char, 'clase') and char.clase else "Especialista"
        trasfondo = f" ({char.trasfondo})" if hasattr(char, 'trasfondo') and char.trasfondo else ""
        resumen_display = f"{clase}{trasfondo}"

        with c1:
            st.write(f"🎖️ {rango_display}")
        with c2:
            st.write(f"{char.nivel}")
        with c3:
            st.write(f"**{char.nombre}**")
        with c4:
            st.markdown(f":{estado_color}[{estado}]")
        with c5:
            st.write(ap_display)
        with c6:
            st.caption(resumen_display)
        with c7:
            if st.button("Ver", key=f"btn_char_{char.id}"):
                _show_character_detail_modal(char)

        st.markdown("---")


@st.dialog("Expediente de Personal")
def _show_character_detail_modal(char):
    """Muestra un modal con los detalles completos del personaje."""
    st.header(f"{char.nombre}")
    st.caption(f"ID: {char.id} | Rango: {char.rango}")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Atributos")
        # Asumiendo que el objeto char tiene estos atributos
        st.write(f"**Fuerza:** {char.fuerza}")
        st.write(f"**Destreza:** {char.destreza}")
        st.write(f"**Inteligencia:** {char.inteligencia}")
        st.write(f"**Constitución:** {char.constitucion}")
    
    with c2:
        st.markdown("#### Estado")
        st.write(f"**Nivel:** {char.nivel}")
        st.write(f"**XP:** {char.experiencia}")
        st.write(f"**Salud:** {char.hp_actual}/{char.hp_maximo}")
        st.write(f"**Energía:** {char.energia}")

    st.divider()
    st.markdown("#### Habilidades")
    if hasattr(char, 'habilidades') and char.habilidades:
        # Si es un dict o lista, renderizarlo bonito
        st.json(char.habilidades)
    else:
        st.caption("Sin habilidades registradas.")