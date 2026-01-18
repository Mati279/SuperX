# ui/character_sheet.py
import streamlit as st
import pandas as pd
from core.models import KnowledgeLevel, CharacterRole

def _safe_get_data(stats, keys_v2, keys_v1_fallback, default_val=None):
    """
    Intenta recuperar datos buscando primero en la estructura V2 y luego en fallbacks V1.
    """
    # 1. Intentar ruta V2 (anidada)
    data = stats
    found_v2 = True
    for k in keys_v2:
        if isinstance(data, dict) and k in data:
            data = data[k]
        else:
            found_v2 = False
            break
    
    if found_v2 and data:
        return data

    # 2. Intentar ruta V1 (directa o alternativa)
    # A veces los datos antiguos están en la raíz o en 'stats'
    for key in keys_v1_fallback:
        if isinstance(stats, dict) and key in stats:
            val = stats[key]
            if val: return val
            
    return default_val if default_val is not None else {}

def render_character_sheet(character_data, player_id):
    """
    Renderiza la ficha de personaje adaptándose al nivel de conocimiento.
    Intenta ser tolerante a fallos de estructura en el JSON.
    
    Args:
        character_data (dict): Datos crudos del personaje (incluye 'stats_json').
        player_id (int): ID del jugador que observa.
    """
    from data.character_repository import get_character_knowledge_level
    
    char_id = character_data['id']
    stats = character_data.get('stats_json', {})
    
    # Determinar nivel de conocimiento REAL
    # NOTA: Ya no forzamos KnowledgeLevel.FRIEND si es el dueño, 
    # para respetar la mecánica de "conocer a tu tripulación".
    knowledge_level = get_character_knowledge_level(char_id, player_id)

    # --- ENCABEZADO (Siempre visible) ---
    col_avatar, col_basic = st.columns([1, 3])
    
    with col_avatar:
        # Placeholder para avatar
        rango = character_data.get('rango', 'Agente')
        st.image(f"https://ui-avatars.com/api/?name={character_data['nombre'].replace(' ', '+')}&background=random", caption=rango)

    with col_basic:
        st.subheader(f"{character_data['nombre']}")
        
        # Extracción segura de datos básicos
        bio = stats.get('bio', {})
        tax = stats.get('taxonomia', {})
        if not tax: tax = {'raza': stats.get('raza', 'Desconocido')} # Fallback V1
        
        prog = stats.get('progresion', {})
        if not prog: prog = {'clase': stats.get('clase', 'Novato'), 'nivel': stats.get('nivel', 1)} # Fallback V1
        
        # Muestra limitada para desconocidos
        if knowledge_level == KnowledgeLevel.UNKNOWN:
            st.write(f"**Raza:** {tax.get('raza', 'Desconocido')}")
            st.write(f"**Clase:** {prog.get('clase', 'Desconocido')}")
            st.info("ℹ️ Datos detallados restringidos. Se requiere mayor nivel de acceso.")
            return # Salimos temprano si es desconocido
            
        # Muestra completa para Conocido/Amigo
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Raza:** {tax.get('raza', 'Humano')}")
            st.write(f"**Sexo:** {bio.get('sexo', 'Desconocido')}")
            st.write(f"**Edad:** {bio.get('edad', '??')} años")
        with c2:
            st.write(f"**Clase:** {prog.get('clase', 'Novato')}")
            st.write(f"**Nivel:** {prog.get('nivel', 1)}")
            st.write(f"**XP:** {prog.get('xp', 0)} / {prog.get('xp_next', 500)}")

    st.divider()

    # --- PESTAÑAS DE DETALLE ---
    # Solo accesibles si es KNOWN o FRIEND (Ya filtrado arriba por el return temprano)
    
    tab_attrs, tab_skills, tab_bio, tab_debug = st.tabs(["📊 Capacidades", "🛠️ Habilidades", "📝 Biografía", "🕷️ Debug"])
    
    with tab_attrs:
        # ATRIBUTOS
        # Búsqueda robusta: capacidades.atributos -> atributos -> stats.atributos
        attrs = _safe_get_data(stats, ['capacidades', 'atributos'], ['atributos'])
        
        # Si sigue vacío, defaults visuales en 5 para no romper la UI, pero avisando
        if not attrs:
            st.warning("⚠️ No se encontraron atributos en la ficha.")
            attrs = {k: 5 for k in ["fuerza", "agilidad", "tecnica", "intelecto", "voluntad", "presencia"]}

        # Renderizar Métricas
        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("Fuerza", attrs.get("fuerza", 5))
        ac1.metric("Intelecto", attrs.get("intelecto", 5))
        
        ac2.metric("Agilidad", attrs.get("agilidad", 5))
        ac2.metric("Voluntad", attrs.get("voluntad", 5))
        
        ac3.metric("Técnica", attrs.get("tecnica", 5))
        ac3.metric("Presencia", attrs.get("presencia", 5))
        
        # Feats
        st.markdown("##### Talentos (Feats)")
        feats = _safe_get_data(stats, ['capacidades', 'feats'], ['feats'])
        
        if feats:
            for feat in feats:
                feat_name = feat['nombre'] if isinstance(feat, dict) else feat
                st.caption(f"🔸 {feat_name}")
        else:
            st.caption("Sin talentos registrados.")

    with tab_skills:
        # HABILIDADES
        skills = _safe_get_data(stats, ['capacidades', 'habilidades'], ['habilidades'])

        if skills:
            # Ordenar por valor
            sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
            
            # Mostrar top destacado
            st.write("**Especialidades:**")
            cols = st.columns(2)
            for idx, (sk, val) in enumerate(sorted_skills):
                with cols[idx % 2]:
                    st.progress(min(val, 100) / 100, text=f"{sk}: {val}%")
        else:
            st.info("No hay datos de habilidades disponibles.")

    with tab_bio:
        # BIOGRAFIA
        st.markdown("**Perfil Público:**")
        # Busca en múltiples lugares la bio corta
        bio_text = bio.get('biografia_corta') or bio.get('bio_superficial') or "Sin datos."
        st.write(bio_text)
        
        # Bio Conocida (Solo si es KNOWN o superior)
        if knowledge_level in [KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND]:
            if 'bio_conocida' in bio and bio['bio_conocida']:
                st.markdown("**Expediente de Servicio:**")
                st.info(bio['bio_conocida'])
            
        # Bio Profunda (Solo FRIEND)
        if knowledge_level == KnowledgeLevel.FRIEND:
            if 'bio_profunda' in bio and bio['bio_profunda']:
                st.markdown("🔒 **Información Clasificada (Nivel Amigo):**")
                st.warning(bio['bio_profunda'])
            else:
                st.caption("No hay secretos profundos revelados.")
        else:
            # Mensaje para KNOWN que no es FRIEND
            if knowledge_level == KnowledgeLevel.KNOWN:
                st.caption("🔒 *Información confidencial encriptada. Requiere mayor nivel de confianza (FRIEND).*")

    with tab_debug:
        # Solo el dueño real puede ver debug, independientemente del nivel de conocimiento simulado
        if character_data.get('player_id') == player_id:
            st.caption(f"Nivel de Conocimiento Actual: {knowledge_level.name}")
            st.caption("Vista de depuración (Dueño)")
            st.json(stats)
        else:
            st.caption("Acceso denegado.")