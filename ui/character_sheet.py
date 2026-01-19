# ui/character_sheet.py
import streamlit as st
import pandas as pd
from core.models import KnowledgeLevel, CharacterRole

# --- ESTILOS VISUALES (REPLICADOS DE RECRUITMENT_CENTER) ---
COLOR_SKILL_GRAY = "#888888"
COLOR_SKILL_GREEN = "#26de81"
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

def _get_skill_color(value: int) -> str:
    """Retorna el color apropiado segun el valor de la habilidad/atributo."""
    if value < 8:
        return COLOR_SKILL_GRAY
    elif value <= 12:
        return COLOR_SKILL_GREEN
    elif value <= 16:
        return COLOR_SKILL_BLUE
    else:
        return COLOR_SKILL_GOLD

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
    Refactorizado para coincidir con la UI/UX de Recruitment Center (Badges, colores HTML, Headers).
    """
    from data.character_repository import get_character_knowledge_level
    
    char_id = character_data['id']
    stats = character_data.get('stats_json', {})
    
    # Determinar nivel de conocimiento REAL
    knowledge_level = get_character_knowledge_level(char_id, player_id)

    # --- DATOS BÁSICOS ---
    bio_data = stats.get('bio', {})
    tax = stats.get('taxonomia', {})
    if not tax: tax = {'raza': stats.get('raza', 'Desconocido')}
    
    prog = stats.get('progresion', {})
    if not prog: prog = {'clase': stats.get('clase', 'Novato'), 'nivel': stats.get('nivel', 1)}

    nombre = character_data['nombre']
    raza = tax.get('raza', 'Humano')
    clase = prog.get('clase', 'Novato')
    nivel = prog.get('nivel', 1)
    edad = bio_data.get('edad', '??')
    rango = character_data.get('rango', 'Agente')

    # --- HEADER UNIFICADO (Estilo Recruitment) ---
    col_avatar, col_basic = st.columns([1, 3])
    
    with col_avatar:
        st.image(f"https://ui-avatars.com/api/?name={nombre.replace(' ', '+')}&background=random", caption=rango)

    with col_basic:
        # Renderizado HTML para título y subtítulos
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
        
        # XP info (Solo KNOWN+)
        if knowledge_level != KnowledgeLevel.UNKNOWN:
            st.caption(f"**XP:** {prog.get('xp', 0)} / {prog.get('xp_next', 500)}")

    st.divider()

    # --- TABS DE DETALLE ---
    tab_attrs, tab_skills, tab_bio, tab_debug = st.tabs(["📊 Capacidades", "🛠️ Habilidades", "📝 Biografía", "🕷️ Debug"])
    
    with tab_attrs:
        # ATRIBUTOS: Estilo "Pills" (Visible para TODOS)
        attrs = _safe_get_data(stats, ['capacidades', 'atributos'], ['atributos'])
        if not attrs:
            st.warning("⚠️ Sin datos de atributos.")
            attrs = {k: 5 for k in ["fuerza", "agilidad", "tecnica", "intelecto", "voluntad", "presencia"]}

        st.markdown("##### Atributos Físicos y Mentales")
        
        # Layout de 3 columnas para atributos
        acols = st.columns(3)
        attr_items = list(attrs.items())
        
        for i, (key, val) in enumerate(attr_items):
            color = _get_skill_color(val)
            # HTML Pill para atributo compactado
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
        
        # FEATS (Talentos)
        st.markdown("##### Talentos (Feats)")
        feats = _safe_get_data(stats, ['capacidades', 'feats'], ['feats'])
        
        if knowledge_level == KnowledgeLevel.UNKNOWN:
            st.caption("👁️ *Sólo rasgos visibles a simple vista:*")
            st.write("No se observan rasgos físicos distintivos evidentes.")
        else:
            if feats:
                feat_html_list = ""
                for feat in feats:
                    feat_name = feat['nombre'] if isinstance(feat, dict) else feat
                    feat_html_list += f'<span style="display:inline-block; padding:4px 10px; margin:4px; border-radius:15px; background:#333; color:#eee; border:1px solid #555;">🔸 {feat_name}</span>'
                st.markdown(feat_html_list, unsafe_allow_html=True)
            else:
                st.caption("Sin talentos registrados.")

    with tab_skills:
        # HABILIDADES (Estilo Badges/Pills corregido para evitar problemas de Markdown)
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

            # Renderizado HTML en Bloque (Flow layout)
            # NOTA: Se construye el HTML sin indentación interna para evitar que Streamlit lo interprete como Code Block
            skills_html_parts = ['<div style="line-height: 2.2;">']
            
            for sk, val in display_skills:
                color = _get_skill_color(val)
                pill = (
                    f'<span style="display: inline-block; padding: 4px 12px; margin: 3px; '
                    f'border-radius: 12px; background: rgba(255,255,255,0.05); '
                    f'border: 1px solid {color}40; color: {color}; font-size: 0.9em;">'
                    f'{sk}: <b>{val}</b></span>'
                )
                skills_html_parts.append(pill)
            
            skills_html_parts.append('</div>')
            
            full_skills_html = "".join(skills_html_parts)
            st.markdown(full_skills_html, unsafe_allow_html=True)
            
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
                traits_html = " ".join([f'<span style="background:#2d3436; color:#a55eea; padding:3px 8px; border-radius:4px; margin-right:5px; border:1px solid #a55eea40;">{t}</span>' for t in traits])
                st.markdown(traits_html, unsafe_allow_html=True)
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