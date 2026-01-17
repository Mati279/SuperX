# ui/faction_roster.py
import streamlit as st
from .state import get_player
from data.character_repository import get_all_characters_by_player_id

class CharacterAdapter:
    """
    Adapta el diccionario crudo de la base de datos a un objeto estructurado
    para facilitar el acceso en la UI (dot notation) y manejar datos anidados.
    """
    def __init__(self, data):
        self.raw_data = data
        self.id = data.get('id')
        self.nombre = data.get('nombre', 'Sin Nombre')
        self.rango = data.get('rango', 'Recluta')
        self.estado = data.get('estado', 'Activo')
        
        # Extraer datos anidados de stats_json
        stats = data.get('stats_json') or {}
        
        self.nivel = stats.get('nivel', 1)
        self.experiencia = stats.get('xp', 0)
        self.hp_actual = stats.get('hp_actual', 100)
        self.hp_maximo = stats.get('hp_maximo', 100)
        self.energia = stats.get('energia', 10)
        
        # Acciones (valores por defecto si no existen)
        self.acciones_actuales = stats.get('acciones_actuales', 2)
        self.acciones_maximas = stats.get('acciones_maximas', 3)
        
        self.habilidades = stats.get('habilidades', {})
        
        # Atributos (dentro de stats_json -> atributos)
        atributos = stats.get('atributos', {})
        self.fuerza = atributos.get('Fuerza', 0)
        self.destreza = atributos.get('Destreza', 0)
        self.inteligencia = atributos.get('Inteligencia', 0)
        self.constitucion = atributos.get('Constitución', 0)
        
        # Biografía (dentro de stats_json -> bio)
        bio = stats.get('bio', {})
        self.clase = bio.get('clase', 'Especialista')
        self.trasfondo = bio.get('trasfondo', '')

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

    # Obtener personajes del jugador usando la función correcta del repositorio
    raw_characters = get_all_characters_by_player_id(player.id)

    if not raw_characters:
        st.info("No tienes miembros en tu cuadrilla actualmente.")
        return

    # Adaptar los diccionarios a objetos
    characters = [CharacterAdapter(c) for c in raw_characters]

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
        
        # Estado con color
        estado_color = "green" if char.estado == "Activo" else "orange" if char.estado == "Misión" else "red"
        
        # Acciones (AP)
        ap_display = f"{char.acciones_actuales}/{char.acciones_maximas}"
        
        # Resumen
        trasfondo_str = f" ({char.trasfondo})" if char.trasfondo else ""
        resumen_display = f"{char.clase}{trasfondo_str}"

        with c1:
            st.write(f"🎖️ {char.rango}")
        with c2:
            st.write(f"{char.nivel}")
        with c3:
            st.write(f"**{char.nombre}**")
        with c4:
            st.markdown(f":{estado_color}[{char.estado}]")
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
    if char.habilidades:
        st.json(char.habilidades)
    else:
        st.caption("Sin habilidades registradas.")