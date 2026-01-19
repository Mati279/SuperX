# ui/character_sheet.py
import streamlit as st
import pandas as pd
from core.models import KnowledgeLevel, CharacterRole

# --- CONSTANTES DE COLOR (ESCALA EXTENDIDA) ---
COLOR_LEVEL_0 = "#888888"   # Inepto / Gris (0-19)
COLOR_LEVEL_1 = "#e67e22"   # Novato / Naranja (20-35)
COLOR_LEVEL_2 = "#f1c40f"   # Iniciado / Amarillo (36-50)
COLOR_LEVEL_3 = "#26de81"   # Competente / Esmeralda (51-65)
COLOR_LEVEL_4 = "#45b7d1"   # Experto / Cian (66-80)
COLOR_LEVEL_5 = "#a55eea"   # Maestro / Púrpura (81-95)
COLOR_LEVEL_6 = "#ffd700"   # Legendario / Oro (96-100)

# Colores fijos para otros elementos de UI
COLOR_SKILL_BLUE = "#45b7d1"
COLOR_SKILL_GOLD = "#ffd700"

ATTR_ABBREVIATIONS = {
    "fuerza": "FUE",
    "agilidad": "AGI",
    "tecnica": "TEC",
    "intelecto": "INT",
    "voluntad": "VOL",
    "presencia": "PRE"
}

def _get_attribute_color(value: int) -> str:
    """
    Retorna el color para ATRIBUTOS (Escala típica 1-20).
    Mantenemos la escala de 4 niveles para atributos por ser un rango corto.
    """
    if value < 8:
        return COLOR_LEVEL_0
    elif value <= 12:
        return COLOR_LEVEL_3 # Verde
    elif value <= 16:
        return COLOR_LEVEL_4 # Azul/Cian
    else:
        return COLOR_LEVEL_6 # Oro

def _get_skill_color(value: int) -> str:
    """
    Retorna el color para HABILIDADES (Escala extendida de 7 niveles para 1-100).
    """
    if value < 20:
        return COLOR_LEVEL_0
    elif value <= 35:
        return COLOR_LEVEL_1
    elif value <= 50:
        return COLOR_LEVEL_2
    elif value <= 65:
        return COLOR_LEVEL_3
    elif value <= 80:
        return COLOR_LEVEL_4
    elif value <= 95:
        return COLOR_LEVEL_5
    else:
        return COLOR_LEVEL_6

def _safe_get_data(stats, keys_v2, keys_v1_fallback, default_val=None):
    """
    Intenta recuperar datos buscando primero en la estructura V2 y luego en fallbacks V1.
    """
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

    for key in keys_v1_fallback:
        if isinstance(stats, dict) and key in stats:
            val = stats[key]
            if val: return val
            
    return default_val if default_val is not None else {}

def render_character_sheet(character_data, player_id):
    """
    Renderiza la ficha de personaje con estética unificada y escala de color de 7 niveles.
    """
    from data.character_repository import get_character_knowledge_level
    
    char_id = character_data['id']
    stats = character_data.get('stats_json', {})
    knowledge_level = get_character_knowledge_level(char_id, player_id)

    # --- DATOS BÁSICOS ---
    bio_data = stats.get('bio', {})
    tax = stats.get('taxonomia', {}) or {'raza': stats.get('raza', 'Humano')}
    prog = stats.get('progresion', {}) or {'clase': stats.get('clase', 'Novato'), 'nivel': stats.get('nivel', 1)}

    nombre = character_data['nombre']
    raza = tax.get('raza', 'Humano')
    clase = prog.get('clase', 'Novato')
    nivel = prog.get('nivel', 1)
    edad = bio_data.get('edad', '??')
    rango = character_data.get('rango', 'Agente')

    # --- HEADER ---
    col_avatar, col_basic = st.columns([1, 3])
    
    with col_avatar:
        st.image(f"https://ui-avatars.com/api/?name={nombre.replace(' ', '+')}&background=random", caption=rango)

    with col_basic:
        header_html = f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #45b7d1;
            margin-bottom: 10px;
        ">
            <div style="font-size: 1.8em; font-weight: bold; color: #fff; margin-bottom: 5px;">
                {nombre}
            </div>
            <div style="font-size: 1em; color: #ccc;">
                <span style="color: #a55eea; font-weight: bold;">{raza}</span> | 
                <span style="color: #ffd700; font-weight: bold;">Nivel {nivel}</span> | 
                <span style="color: #ccc;">{clase}</span> |
                <span style="color: #888;">{edad} años</span>
            </div>
        </div>
        """
        st.markdown(header_html, unsafe_allow_html=True)
        
        if knowledge_level != KnowledgeLevel.UNKNOWN:
            st.caption(f"**XP:** {prog.get('xp', 0)} / {prog.get('xp_next', 500)}")

    st.divider()

    # --- TABS ---
    tab_attrs, tab_skills, tab_bio, tab_debug = st.tabs(["📊 Capacidades", "🛠️ Habilidades", "📝 Biografía", "🕷️ Debug"])
    
    with tab_attrs:
        attrs = _safe_get_data(stats, ['capacidades', 'atributos'], ['atributos'])
        if not attrs:
            attrs = {k: 5 for k in ["fuerza", "agilidad", "tecnica", "intelecto", "voluntad", "presencia"]}

        st.markdown("##### Atributos")
        acols = st.columns(3)
        attr_items = list(attrs.items())
        
        for i, (key, val) in enumerate(attr_items):
            color = _get_attribute_color(val)
            attr_html = (
                f'<div style="background: rgba(255,255,255,0.05); border: 1px solid {color}40; '
                f'padding: 10px; border-radius: 6px; text-align: center; margin-bottom: 8px;">'
                f'<div style="color: #aaa; font-size: 0.8em; text-transform: uppercase;">{key}</div>'
                f'<div style="color: {color}; font-size: 1.5em; font-weight: bold;">{val}</div>'
                f'</div>'
            )
            with acols[i % 3]:
                st.markdown(attr_html, unsafe_allow_html=True)

        st.divider()
        st.markdown("##### Talentos (Feats)")
        feats = _safe_get_data(stats, ['capacidades', 'feats'], ['feats'])
        if knowledge_level == KnowledgeLevel.UNKNOWN:
            st.caption("👁️ *Sólo rasgos visibles a simple vista.*")
        elif feats:
            feat_html = "".join([f'<span style="display:inline-block; padding:4px 10px; margin:4px; border-radius:15px; background:#333; color:#eee; border:1px solid #555;">🔸 {f["nombre"] if isinstance(f, dict) else f}</span>' for f in feats])
            st.markdown(feat_html, unsafe_allow_html=True)

    with tab_skills:
        skills = _safe_get_data(stats, ['capacidades', 'habilidades'], ['habilidades'])
        if skills:
            sorted_skills = sorted(skills.items(), key=lambda x: x[1], reverse=True)
            display_skills = sorted_skills[:5] if knowledge_level == KnowledgeLevel.UNKNOWN else sorted_skills

            skills_html_parts = ['<div style="line-height: 2.5;">']
            for sk, val in display_skills:
                color = _get_skill_color(val)
                pill = (
                    f'<span style="display: inline-block; padding: 4px 12px; margin: 3px; '
                    f'border-radius: 12px; background: rgba(255,255,255,0.05); '
                    f'border: 1px solid {color}60; color: {color}; font-size: 0.9em; font-weight: 500;">'
                    f'{sk}: <b style="font-size: 1.1em;">{val}</b></span>'
                )
                skills_html_parts.append(pill)
            skills_html_parts.append('</div>')
            st.markdown("".join(skills_html_parts), unsafe_allow_html=True)
            
            if knowledge_level == KnowledgeLevel.UNKNOWN and len(skills) > 5:
                st.caption(f"... y {len(skills) - 5} habilidades más no evaluadas.")
        else:
            st.info("No hay datos de habilidades.")

    with tab_bio:
        bio_corta = bio_data.get('biografia_corta') or bio_data.get('bio_superficial') or "Sin datos."
        st.markdown("### Expediente Personal")
        st.markdown("**Perfil Público:**")
        st.write(bio_corta)
        
        if knowledge_level in [KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND]:
            st.divider()
            st.markdown("**Expediente de Servicio:**")
            st.info(bio_data.get('bio_conocida', 'Investigación en curso...'))
            st.markdown("---")
            st.markdown("**Perfil Psicológico:**")
            traits = _safe_get_data(stats, ['comportamiento', 'rasgos_personalidad'], ['rasgos', 'personalidad'])
            if traits:
                st.markdown(" ".join([f'<span style="background:#2d3436; color:#a55eea; padding:3px 8px; border-radius:4px; margin-right:5px; border:1px solid #a55eea40;">{t}</span>' for t in traits]), unsafe_allow_html=True)
        
        if knowledge_level == KnowledgeLevel.FRIEND:
            st.divider()
            st.markdown("🔒 **Vínculo de Confianza:**")
            st.warning(bio_data.get('bio_profunda', 'No hay secretos revelados.'))

    with tab_debug:
        if character_data.get('player_id') == player_id:
            st.caption(f"Nivel de Conocimiento: {knowledge_level.name}")
            st.json(stats)