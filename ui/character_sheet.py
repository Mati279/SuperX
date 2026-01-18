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
    for key in keys_v1_fallback:
        if isinstance(stats, dict) and key in stats:
            val = stats[key]
            if val: return val
            
    return default_val if default_val is not None else {}

def render_character_sheet(character_data, player_id):
    """
    Renderiza la ficha de personaje adaptándose estrictamente a las reglas de visibilidad por Nivel.
    
    Reglas:
    - UNKNOWN: Datos básicos, Atributos, Top 5 Skills. Bio = Bio Corta. (Feats 'visibles').
    - KNOWN: Todo lo anterior + All Skills, All Feats, Personalidad. Bio = Bio Corta + Bio Conocida.
    - FRIEND: Todo lo anterior. Bio = Bio Corta + Bio Conocida + Bio Profunda.
    """
    from data.character_repository import get_character_knowledge_level
    
    char_id = character_data['id']
    stats = character_data.get('stats_json', {})
    
    # Determinar nivel de conocimiento REAL
    knowledge_level = get_character_knowledge_level(char_id, player_id)

    # --- ENCABEZADO (Siempre visible para todos los niveles) ---
    col_avatar, col_basic = st.columns([1, 3])
    
    with col_avatar:
        rango = character_data.get('rango', 'Agente')
        st.image(f"https://ui-avatars.com/api/?name={character_data['nombre'].replace(' ', '+')}&background=random", caption=rango)

    with col_basic:
        st.subheader(f"{character_data['nombre']}")
        
        # Extracción segura de datos
        bio_data = stats.get('bio', {})
        tax = stats.get('taxonomia', {})
        if not tax: tax = {'raza': stats.get('raza', 'Desconocido')}
        
        prog = stats.get('progresion', {})
        if not prog: prog = {'clase': stats.get('clase', 'Novato'), 'nivel': stats.get('nivel', 1)}
        
        # Datos visibles en TODOS los niveles (incluso UNKNOWN)
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"**Raza:** {tax.get('raza', 'Humano')}")
            st.write(f"**Sexo:** {bio_data.get('sexo', 'Desconocido')}")
            st.write(f"**Edad:** {bio_data.get('edad', '??')} años")
        with c2:
            st.write(f"**Clase:** {prog.get('clase', 'Novato')}")
            st.write(f"**Nivel:** {prog.get('nivel', 1)}")
            # XP solo visible si es KNOWN o superior
            if knowledge_level != KnowledgeLevel.UNKNOWN:
                st.write(f"**XP:** {prog.get('xp', 0)} / {prog.get('xp_next', 500)}")

    st.divider()

    # --- TABS DE DETALLE ---
    tab_attrs, tab_skills, tab_bio, tab_debug = st.tabs(["📊 Capacidades", "🛠️ Habilidades", "📝 Biografía", "🕷️ Debug"])
    
    with tab_attrs:
        # ATRIBUTOS: Visible para TODOS (UNKNOWN incluido)
        attrs = _safe_get_data(stats, ['capacidades', 'atributos'], ['atributos'])
        if not attrs:
            st.warning("⚠️ Sin datos de atributos.")
            attrs = {k: 5 for k in ["fuerza", "agilidad", "tecnica", "intelecto", "voluntad", "presencia"]}

        ac1, ac2, ac3 = st.columns(3)
        ac1.metric("Fuerza", attrs.get("fuerza", 5))
        ac1.metric("Intelecto", attrs.get("intelecto", 5))
        
        ac2.metric("Agilidad", attrs.get("agilidad", 5))
        ac2.metric("Voluntad", attrs.get("voluntad", 5))
        
        ac3.metric("Técnica", attrs.get("tecnica", 5))
        ac3.metric("Presencia", attrs.get("presencia", 5))
        
        # FEATS (Talentos)
        st.markdown("##### Talentos (Feats)")
        feats = _safe_get_data(stats, ['capacidades', 'feats'], ['feats'])
        
        if knowledge_level == KnowledgeLevel.UNKNOWN:
            # UNKNOWN: "Se conocen sólo los Feats visibles".
            st.caption("👁️ *Sólo rasgos visibles a simple vista:*")
            st.write("No se observan rasgos físicos distintivos evidentes.")
        else:
            # KNOWN / FRIEND: Todos los feats
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
            sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
            
            # UNKNOWN: Solo las mejores 5
            if knowledge_level == KnowledgeLevel.UNKNOWN:
                st.info("🔍 Observación preliminar (Top 5 Habilidades):")
                display_skills = sorted_skills[:5]
            else:
                # KNOWN / FRIEND: Todas
                display_skills = sorted_skills

            cols = st.columns(2)
            for idx, (sk, val) in enumerate(display_skills):
                with cols[idx % 2]:
                    st.progress(min(val, 100) / 100, text=f"{sk}: {val}%")
            
            if knowledge_level == KnowledgeLevel.UNKNOWN and len(skills) > 5:
                st.caption(f"... y {len(skills) - 5} habilidades más no evaluadas.")
        else:
            st.info("No hay datos de habilidades disponibles.")

    with tab_bio:
        # Lógica de Biografía Acumulativa
        
        bio_corta = bio_data.get('biografia_corta') or bio_data.get('bio_superficial') or "Sin datos."
        bio_conocida = bio_data.get('bio_conocida', '')
        bio_profunda = bio_data.get('bio_profunda', '')

        st.markdown("### Expediente Personal")

        # 1. PERFIL PÚBLICO (Visible siempre)
        st.markdown("**Perfil Público:**")
        st.write(bio_corta)
        
        # 2. EXPEDIENTE DE SERVICIO (Known+)
        if knowledge_level in [KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND]:
            st.divider()
            st.markdown("**Expediente de Servicio (Conocido):**")
            if bio_conocida:
                st.info(bio_conocida)
            else:
                st.caption("Investigación en curso... (Sin datos adicionales)")
                
            # Personalidad (Known+)
            st.markdown("---")
            st.markdown("**Perfil Psicológico:**")
            traits = _safe_get_data(stats, ['comportamiento', 'rasgos_personalidad'], ['rasgos', 'personalidad'])
            if traits:
                st.write(", ".join([f"`{t}`" for t in traits]))
            else:
                st.caption("Sin datos psicológicos.")

        elif knowledge_level == KnowledgeLevel.UNKNOWN:
            st.divider()
            st.caption("🔒 *Información clasificada. Requiere mayor nivel de confianza o investigación.*")

        # 3. SECRETOS (Friend Only)
        if knowledge_level == KnowledgeLevel.FRIEND:
            st.divider()
            st.markdown("🔒 **Vínculo de Confianza (Secretos):**")
            if bio_profunda:
                st.warning(bio_profunda)
            else:
                st.caption("No hay secretos profundos revelados.")

    with tab_debug:
        # Solo el dueño ve esto para depurar
        if character_data.get('player_id') == player_id:
            st.caption(f"Nivel de Conocimiento: {knowledge_level.name}")
            st.json(stats)
        else:
            st.caption("Acceso denegado.")