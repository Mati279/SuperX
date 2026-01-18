import streamlit as st
from data.character_repository import (
    get_all_player_characters, 
    update_character_stats, 
    get_character_knowledge_level,
    set_character_knowledge_level,
    recruit_random_character_with_ai
)
from core.models import CharacterRole, KnowledgeLevel
from core.constants import SKILL_MAPPING
from core.mrg_engine import resolve_action, ResultType
from core.mrg_constants import DIFFICULTY_NORMAL
from ui.character_sheet import render_character_sheet
from data.player_repository import get_player_by_id

def render_faction_roster():
    from .state import get_player

    st.title("📋 Personal de la Facción")

    player = get_player()
    if not player:
        st.warning("Error de sesión.")
        return

    player_id = player.id

    # Obtener personajes
    characters = get_all_player_characters(player_id)
    
    # Obtener datos del jugador para tiradas (Intelecto/Técnica)
    player_data = get_player_by_id(player_id)
    # Valor base competente (60) si no hay stat, o promedio de Int/Tec del jugador
    # Asumimos que el jugador actúa como 'Director' usando la red de inteligencia de la facción
    player_intellect = 60 # Default
    # Si tuviéramos stats del jugador (PlayerData), los usaríamos aquí. 
    # Por ahora usamos un valor fijo competente para la acción de gestión.

    # --- LÓGICA DE BIENVENIDA / STARTER PACK ---
    # Contamos los personajes que NO son comandantes.
    # Si la cuenta es 0, mostramos el botón de "Conocer a la tripulación".
    non_commander_count = sum(1 for c in characters if not c.get("es_comandante", False))

    if non_commander_count == 0:
        st.info("👋 Parece que tu facción recién se está estableciendo. Reúne a tu equipo inicial.")
        
        if st.button("👋 Conocer a la tripulación", type="primary", help="Genera tu equipo inicial con ayuda de la IA"):
            try:
                with st.spinner("🛰️ Convocando personal y estableciendo enlaces neuronales..."):
                    # 1. Un personaje Nivel 5 (Conocido) - El veterano
                    vet = recruit_random_character_with_ai(player_id, min_level=5, max_level=5)
                    if vet:
                        set_character_knowledge_level(vet['id'], player_id, KnowledgeLevel.KNOWN)
                    
                    # 2. Dos personajes Nivel 3 (Conocidos) - Los oficiales
                    for _ in range(2):
                        off = recruit_random_character_with_ai(player_id, min_level=3, max_level=3)
                        if off:
                            set_character_knowledge_level(off['id'], player_id, KnowledgeLevel.KNOWN)

                    # 3. Tres personajes Nivel 1 (Desconocidos) - Los reclutas
                    for _ in range(3):
                        # Por defecto nacen UNKNOWN, no hace falta setearlo explícitamente,
                        # pero el sistema lo maneja.
                        recruit_random_character_with_ai(player_id, min_level=1, max_level=1)
                
                st.success("¡La tripulación se ha reportado en el puente!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Error durante el proceso de reclutamiento inicial: {e}")

    if not characters:
        st.info("No hay personal reclutado en tu facción.")
        return

    # Filtros y Ordenamiento
    col1, col2 = st.columns(2)
    with col1:
        sort_by = st.selectbox("Ordenar por", ["Rango", "Clase", "Nombre", "Nivel"])
    with col2:
        filter_role = st.selectbox("Filtrar por Rol", ["Todos"] + [r.value for r in CharacterRole])

    # Aplicar filtros
    filtered_chars = characters
    if filter_role != "Todos":
        filtered_chars = [c for c in filtered_chars if c.get("stats_json", {}).get("estado", {}).get("rol_asignado") == filter_role]

    # Aplicar orden
    if sort_by == "Nombre":
        filtered_chars.sort(key=lambda x: x["nombre"])
    elif sort_by == "Nivel":
        filtered_chars.sort(key=lambda x: x.get("stats_json", {}).get("progresion", {}).get("nivel", 0), reverse=True)
    elif sort_by == "Clase":
        filtered_chars.sort(key=lambda x: x.get("stats_json", {}).get("progresion", {}).get("clase", ""))

    # Mostrar lista
    for char in filtered_chars:
        with st.expander(f"{char['rango']} {char['nombre']} - {char.get('stats_json', {}).get('progresion', {}).get('clase', 'Sin Clase')}"):
            
            # --- SECCIÓN DE GESTIÓN DE CONOCIMIENTO ---
            char_id = char['id']
            knowledge_level = get_character_knowledge_level(char_id, player_id)
            
            # Botón de Investigar (Solo para UNKNOWN)
            if knowledge_level == KnowledgeLevel.UNKNOWN:
                st.warning(f"⚠️ Nivel de Conocimiento: {knowledge_level.value.upper()}")
                st.write("No tienes acceso a los datos completos de este personal. Puedes ordenar una investigación interna.")
                
                col_btn, col_info = st.columns([1, 3])
                with col_btn:
                    if st.button(f"🕵️ Investigar", key=f"investigate_{char_id}", help="Realiza una tirada de Inteligencia para desbloquear la ficha completa."):
                        # Tirada MRG sin efectos críticos (House Rule para Roster)
                        result = resolve_action(merit_points=player_intellect, difficulty=DIFFICULTY_NORMAL)

                        if result.success:
                            # Éxito (Crítico o Normal) -> Pasa a Conocido
                            success = set_character_knowledge_level(char_id, player_id, KnowledgeLevel.KNOWN)
                            if success:
                                st.toast(f"✅ Investigación exitosa: Datos de {char['nombre']} actualizados.", icon="📂")
                                st.rerun()
                        else:
                            # Fallo (Crítico o Normal) -> Solo falla, no se va.
                            is_critical = result.result_type == ResultType.CRITICAL_FAILURE
                            msg = "Fallo Crítico: La investigación atrajo atención no deseada, pero no se obtuvo información." if is_critical else "Fallo: No se encontró información relevante."
                            st.error(msg)
            else:
                # Si ya es Conocido o Amigo, mostramos el indicador discreto
                color = "blue" if knowledge_level == KnowledgeLevel.KNOWN else "gold"
                st.markdown(f"**Nivel de Acceso:** :{color}[{knowledge_level.value.upper()}]")

            # --- FICHA DE PERSONAJE ---
            # Renderizamos la ficha completa (que internamente decide qué mostrar según el nivel)
            render_character_sheet(char, player_id)

            st.divider()
            
            # --- ACCIONES DE GESTIÓN (Roles, Despido, etc.) ---
            c1, c2 = st.columns(2)
            with c1:
                current_role = char.get("stats_json", {}).get("estado", {}).get("rol_asignado", "Sin Asignar")
                new_role = st.selectbox(
                    "Asignar Rol", 
                    [r.value for r in CharacterRole], 
                    index=[r.value for r in CharacterRole].index(current_role) if current_role in [r.value for r in CharacterRole] else 0,
                    key=f"role_{char['id']}"
                )
                
                if new_role != current_role:
                    if st.button("Confirmar Cambio de Rol", key=f"btn_role_{char['id']}"):
                        stats = char.get("stats_json", {})
                        stats["estado"]["rol_asignado"] = new_role
                        update_character_stats(char['id'], stats)
                        st.success(f"Rol actualizado a {new_role}")
                        st.rerun()