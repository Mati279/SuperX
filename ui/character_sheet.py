# ui/character_sheet.py
"""
Ficha de Personaje Profesional - Vista detallada estilo videojuego.
Muestra todos los datos del CharacterSchema V2 de forma interactiva.
"""

import streamlit as st
from typing import Dict, List, Any

from core.models import (
    CommanderData, CharacterSchema, CharacterBio, CharacterTaxonomy,
    CharacterProgression, CharacterAttributes, CharacterCapabilities,
    CharacterBehavior, CharacterLogistics, CharacterDynamicState,
    CharacterRole, BiologicalSex
)
from data.character_repository import get_character_by_id


# =============================================================================
# CONSTANTES
# =============================================================================

COLOR_PALETTE = {
    # Fondos
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_card": "rgba(30, 33, 40, 0.8)",

    # Acentos
    "accent_green": "#26de81",
    "accent_red": "#ff6b6b",
    "accent_blue": "#45b7d1",
    "accent_gold": "#ffd700",
    "accent_purple": "#a55eea",
    "accent_yellow": "#f9ca24",
    "accent_cyan": "#5bc0de",

    # Escala de atributos
    "attr_low": "#ff4b4b",
    "attr_mid": "#f6c45b",
    "attr_high": "#56d59f",
    "attr_elite": "#5bc0de",
}

# Iconos para los 6 atributos del juego
ATTRIBUTE_ICONS = {
    "voluntad": "🔥",
    "tecnica": "🔧",
    "agilidad": "⚡",
    "intelecto": "🧠",
    "presencia": "✨",
    "fuerza": "💪",
    # Compatibilidad con nombres alternativos
    "destreza": "🎯",
    "constitucion": "❤️",
    "sabiduria": "👁️",
    "carisma": "✨",
    "inteligencia": "🧠",
}

# Categorías de habilidades (de core/constants.py SKILL_MAPPING)
SKILL_CATEGORIES: Dict[str, List[str]] = {
    "Pilotaje y Vehiculos": [
        "Piloteo de naves pequeñas", "Piloteo de naves medianas",
        "Piloteo de fragatas y capitales", "Maniobras evasivas espaciales",
        "Navegación en zonas peligrosas"
    ],
    "Combate y Armamento": [
        "Armas de precisión", "Armas pesadas", "Combate cuerpo a cuerpo",
        "Tácticas de escuadra", "Combate defensivo", "Uso de drones de combate"
    ],
    "Ingenieria y Tecnologia": [
        "Reparación mecánica", "Reparación electrónica", "Hackeo de sistemas",
        "Sabotaje tecnológico", "Optimización de sistemas", "Interfaz con sistemas"
    ],
    "Ciencia e Investigacion": [
        "Investigación científica", "Análisis de datos",
        "Ingeniería inversa", "Evaluación de amenazas"
    ],
    "Sigilo e Infiltracion": [
        "Sigilo físico", "Infiltración urbana", "Evasión de sensores",
        "Movimiento silencioso", "Escape táctico"
    ],
    "Diplomacia y Social": [
        "Persuasión", "Engaño", "Intimidación",
        "Negociación", "Liderazgo", "Lectura emocional"
    ],
    "Comando y Estrategia": [
        "Planificación de misiones", "Coordinación de unidades",
        "Gestión de recursos", "Toma de decisiones bajo presión"
    ],
    "Supervivencia y Fisico": [
        "Resistencia física", "Supervivencia en entornos hostiles",
        "Atletismo", "Orientación y exploración"
    ]
}

# CSS para toda la ficha
SHEET_CSS = """
<style>
/* Header del personaje */
.char-header {
    background: linear-gradient(90deg, rgba(69,183,209,0.15) 0%, rgba(38,222,129,0.08) 100%);
    border-bottom: 2px solid #45b7d1;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 15px;
}

.char-name {
    font-size: 1.8em;
    font-weight: bold;
    color: #fff;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.char-subtitle {
    color: #888;
    font-size: 0.9em;
    margin-top: 6px;
}

.char-bio-text {
    font-style: italic;
    color: #a0a0a0;
    margin-top: 12px;
    padding: 12px;
    background: rgba(0,0,0,0.2);
    border-left: 3px solid #45b7d1;
    border-radius: 0 8px 8px 0;
    font-size: 0.9em;
}

/* Barras de atributos */
.attr-row {
    display: flex;
    align-items: center;
    margin: 10px 0;
    gap: 10px;
}

.attr-icon {
    font-size: 1.2em;
    width: 30px;
    text-align: center;
}

.attr-name {
    width: 90px;
    color: #ccc;
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.attr-bar-container {
    flex: 1;
    height: 22px;
    background: rgba(255,255,255,0.08);
    border-radius: 11px;
    overflow: hidden;
    position: relative;
}

.attr-bar-fill {
    height: 100%;
    border-radius: 11px;
    transition: width 0.3s ease;
    box-shadow: 0 0 10px rgba(255,255,255,0.1);
}

.attr-value {
    width: 35px;
    text-align: right;
    font-weight: bold;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 1.1em;
}

/* Badges de habilidades */
.skill-badge {
    display: inline-block;
    padding: 5px 12px;
    margin: 4px;
    border-radius: 16px;
    font-size: 0.8em;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.15);
}

.skill-badge-elite {
    background: rgba(91,192,222,0.15);
    border-color: #5bc0de;
}

.skill-badge-high {
    background: rgba(86,213,159,0.15);
    border-color: #56d59f;
}

/* Tags de estado */
.status-tag {
    display: inline-block;
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 0.75em;
    font-weight: bold;
    text-transform: uppercase;
    margin: 3px;
    letter-spacing: 0.5px;
}

.status-available { background: rgba(38,222,129,0.15); color: #26de81; border: 1px solid #26de81; }
.status-mission { background: rgba(249,202,36,0.15); color: #f9ca24; border: 1px solid #f9ca24; }
.status-injured { background: rgba(255,107,107,0.15); color: #ff6b6b; border: 1px solid #ff6b6b; }
.status-training { background: rgba(165,94,234,0.15); color: #a55eea; border: 1px solid #a55eea; }
.status-transit { background: rgba(69,183,209,0.15); color: #45b7d1; border: 1px solid #45b7d1; }

/* Grid de info */
.info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    padding: 10px 0;
}

.info-item {
    background: rgba(0,0,0,0.2);
    padding: 12px;
    border-radius: 8px;
}

.info-label {
    color: #666;
    font-size: 0.7em;
    text-transform: uppercase;
    margin-bottom: 5px;
    letter-spacing: 1px;
}

.info-value {
    color: #fff;
    font-weight: 500;
    font-size: 0.95em;
}

/* Categoria de habilidades */
.skill-category {
    background: rgba(69,183,209,0.08);
    padding: 8px 12px;
    border-radius: 6px;
    margin: 12px 0 8px 0;
    border-left: 3px solid #45b7d1;
}

.skill-category-title {
    color: #45b7d1;
    font-weight: 600;
    font-size: 0.85em;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* Feat badge */
.feat-badge {
    display: inline-block;
    padding: 6px 14px;
    margin: 4px;
    border-radius: 20px;
    font-size: 0.8em;
    background: rgba(255,215,0,0.12);
    color: #ffd700;
    border: 1px solid rgba(255,215,0,0.4);
    font-weight: 500;
}

/* Barra de progreso XP */
.xp-bar-container {
    background: rgba(255,255,255,0.08);
    height: 14px;
    border-radius: 7px;
    overflow: hidden;
    margin: 8px 0;
}

.xp-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #45b7d1, #26de81);
    border-radius: 7px;
    transition: width 0.3s ease;
}

/* Barra de slots */
.slots-bar-container {
    background: rgba(255,255,255,0.08);
    height: 10px;
    border-radius: 5px;
    overflow: hidden;
    margin: 6px 0;
}

.slots-bar-fill {
    height: 100%;
    border-radius: 5px;
}

/* Rasgo de personalidad */
.trait-badge {
    display: inline-block;
    padding: 5px 12px;
    margin: 3px;
    border-radius: 15px;
    font-size: 0.8em;
    background: rgba(165,94,234,0.12);
    color: #a55eea;
    border: 1px solid rgba(165,94,234,0.3);
}

/* Equipo item */
.equip-item {
    background: rgba(0,0,0,0.15);
    padding: 8px 12px;
    border-radius: 6px;
    margin: 5px 0;
    border-left: 2px solid #45b7d1;
}
</style>
"""


# =============================================================================
# FUNCIONES HELPER
# =============================================================================

def _get_color_for_attr(value: int) -> str:
    """Retorna color hex basado en valor de atributo (1-20)."""
    if value <= 8:
        return COLOR_PALETTE["attr_low"]
    elif value <= 12:
        return COLOR_PALETTE["attr_mid"]
    elif value <= 16:
        return COLOR_PALETTE["attr_high"]
    else:
        return COLOR_PALETTE["attr_elite"]


def _render_attribute_bar_html(name: str, value: int, icon: str = "") -> str:
    """Genera HTML para una barra de atributo."""
    color = _get_color_for_attr(value)
    percent = min(100, (value / 20) * 100)

    return f"""
    <div class="attr-row">
        <span class="attr-icon">{icon}</span>
        <span class="attr-name">{name}</span>
        <div class="attr-bar-container">
            <div class="attr-bar-fill" style="width: {percent}%; background: {color};"></div>
        </div>
        <span class="attr-value" style="color: {color};">{value}</span>
    </div>
    """


def _get_status_css_class(status: str) -> str:
    """Determina la clase CSS del tag de estado."""
    status_lower = status.lower()

    if "disponible" in status_lower or "available" in status_lower:
        return "status-available"
    elif "misi" in status_lower:
        return "status-mission"
    elif "herido" in status_lower or "injured" in status_lower:
        return "status-injured"
    elif "entren" in status_lower or "training" in status_lower:
        return "status-training"
    elif "tránsito" in status_lower or "transit" in status_lower:
        return "status-transit"

    return "status-available"


def _render_status_tag_html(status: str) -> str:
    """Genera HTML para un tag de estado."""
    css_class = _get_status_css_class(status)
    return f'<span class="status-tag {css_class}">{status}</span>'


def _get_skill_badge_class(value: int) -> str:
    """Determina la clase CSS del badge según valor."""
    if value >= 17:
        return "skill-badge skill-badge-elite"
    elif value >= 13:
        return "skill-badge skill-badge-high"
    return "skill-badge"


# =============================================================================
# SECCIONES DE LA FICHA
# =============================================================================

def _render_header(sheet: CharacterSchema) -> None:
    """Renderiza el header principal con nombre y resumen."""
    bio = sheet.bio
    prog = sheet.progresion
    tax = sheet.taxonomia

    full_name = f"{bio.nombre} {bio.apellido}".strip()

    # Obtener valor del sexo (puede ser enum o string)
    sexo_val = bio.sexo.value if hasattr(bio.sexo, 'value') else str(bio.sexo)

    header_html = f"""
    <div class="char-header">
        <h2 class="char-name">{full_name}</h2>
        <div class="char-subtitle">
            <span style="color: #ffd700;">{prog.rango}</span> |
            <span style="color: #45b7d1;">Nivel {prog.nivel}</span>
            <span style="color: #f9ca24;">{prog.clase}</span> |
            <span style="color: #a55eea;">{tax.raza}</span> |
            <span style="color: #888;">{bio.edad} años, {sexo_val}</span>
        </div>
        <div class="char-bio-text">"{bio.biografia_corta}"</div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def _render_bio_section(bio: CharacterBio, tax: CharacterTaxonomy) -> None:
    """Seccion de identificadores y taxonomia."""
    with st.expander("Identificadores de Entidad", expanded=False):
        # Obtener valor del sexo
        sexo_val = bio.sexo.value if hasattr(bio.sexo, 'value') else str(bio.sexo)

        # Transformaciones
        trans = tax.transformaciones if tax.transformaciones else ["Ninguna"]
        trans_str = ", ".join(trans)

        st.markdown(f"""
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Nombre</div>
                <div class="info-value">{bio.nombre}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Apellido</div>
                <div class="info-value">{bio.apellido or "---"}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Edad</div>
                <div class="info-value">{bio.edad} años</div>
            </div>
            <div class="info-item">
                <div class="info-label">Sexo</div>
                <div class="info-value">{sexo_val}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Raza</div>
                <div class="info-value" style="color: #a55eea;">{tax.raza}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Transformaciones</div>
                <div class="info-value">{trans_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_progression_section(prog: CharacterProgression) -> None:
    """Seccion de progresion con barra de XP."""
    with st.expander("Progresion y Jerarquia", expanded=False):
        # Calcular porcentaje XP
        xp_current = prog.xp
        xp_next = prog.xp_next if prog.xp_next > 0 else 500

        if prog.nivel >= 20:
            xp_percent = 100
        else:
            xp_percent = min(100, max(0, (xp_current / xp_next) * 100))

        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 3em; font-weight: bold; color: #45b7d1; text-shadow: 0 0 20px rgba(69,183,209,0.3);">
                NIVEL {prog.nivel}
            </span>
        </div>
        <div style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8em; color: #888; margin-bottom: 4px;">
                <span>XP: {xp_current:,}</span>
                <span>Siguiente: {xp_next:,}</span>
            </div>
            <div class="xp-bar-container">
                <div class="xp-bar-fill" style="width: {xp_percent}%;"></div>
            </div>
            <div style="text-align: center; font-size: 0.75em; color: #666; margin-top: 4px;">
                {xp_percent:.0f}% completado
            </div>
        </div>
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Clase</div>
                <div class="info-value" style="color: #f9ca24; font-size: 1.1em;">{prog.clase}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Rango</div>
                <div class="info-value" style="color: #ffd700; font-size: 1.1em;">{prog.rango}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_attributes_section(attrs: CharacterAttributes) -> None:
    """Seccion de atributos con barras visuales."""
    with st.expander("Atributos Primarios", expanded=True):
        # Obtener atributos como dict
        if hasattr(attrs, 'model_dump'):
            attrs_dict = attrs.model_dump()
        else:
            attrs_dict = {k: v for k, v in vars(attrs).items() if not k.startswith('_')}

        # Generar HTML de barras
        html_bars = ""
        total = 0
        for attr_name, value in attrs_dict.items():
            if isinstance(value, int):
                icon = ATTRIBUTE_ICONS.get(attr_name.lower(), "")
                display_name = attr_name.replace("_", " ").capitalize()
                html_bars += _render_attribute_bar_html(display_name, value, icon)
                total += value

        st.markdown(html_bars, unsafe_allow_html=True)

        # Total de puntos de merito
        st.markdown(f"""
        <div style="text-align: right; color: #888; font-size: 0.85em; margin-top: 15px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1);">
            Puntos de Merito Total: <span style="color: #ffd700; font-weight: bold; font-size: 1.1em;">{total}</span>
        </div>
        """, unsafe_allow_html=True)


def _render_skills_section(caps: CharacterCapabilities) -> None:
    """Seccion de habilidades organizadas por categoria."""
    with st.expander("Habilidades y Rasgos", expanded=False):
        skills = caps.habilidades or {}
        feats = caps.feats or []

        has_skills = False

        # Mostrar por categorias
        for category, skill_list in SKILL_CATEGORIES.items():
            # Filtrar skills que el personaje tiene
            cat_skills = {s: skills.get(s, 0) for s in skill_list if s in skills and skills.get(s, 0) > 0}

            if cat_skills:
                has_skills = True
                st.markdown(f"""
                <div class="skill-category">
                    <span class="skill-category-title">{category}</span>
                </div>
                """, unsafe_allow_html=True)

                # Ordenar por valor descendente
                sorted_skills = sorted(cat_skills.items(), key=lambda x: -x[1])

                badges_html = ""
                for skill_name, value in sorted_skills:
                    badge_class = _get_skill_badge_class(value)
                    color = _get_color_for_attr(value)
                    badges_html += f'<span class="{badge_class}" style="color: {color};">{skill_name}: {value}</span>'

                st.markdown(badges_html, unsafe_allow_html=True)

        if not has_skills:
            st.caption("Sin habilidades calculadas.")

        # Feats/Rasgos
        if feats:
            st.markdown("---")
            st.markdown("**Rasgos Especiales (Feats)**")
            feats_html = "".join([f'<span class="feat-badge">{feat}</span>' for feat in feats])
            st.markdown(feats_html, unsafe_allow_html=True)


def _render_behavior_section(behavior: CharacterBehavior) -> None:
    """Seccion de personalidad y relaciones."""
    with st.expander("Comportamiento y Relaciones", expanded=False):
        # Rasgos de personalidad
        traits = behavior.rasgos_personalidad or []
        if traits:
            st.markdown("**Rasgos de Personalidad**")
            traits_html = "".join([f'<span class="trait-badge">{t}</span>' for t in traits])
            st.markdown(traits_html, unsafe_allow_html=True)
        else:
            st.caption("Sin rasgos de personalidad registrados.")

        st.write("")

        # Relaciones
        relations = behavior.relaciones or []
        if relations:
            st.markdown("**Relaciones de Parentesco**")
            for rel in relations:
                nombre = rel.get("nombre", "Desconocido")
                tipo = rel.get("tipo", "Neutral")
                nivel = rel.get("nivel", "")
                nivel_str = f" - {nivel}" if nivel else ""
                st.markdown(f"""
                <div class="equip-item">
                    <span style="color: #fff;">{nombre}</span>
                    <span style="color: #888; font-size: 0.85em;"> ({tipo}{nivel_str})</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("Sin relaciones registradas.")


def _render_logistics_section(logistics: CharacterLogistics) -> None:
    """Seccion de equipo e inventario."""
    with st.expander("Logistica y Equipamiento", expanded=False):
        # Slots
        slots_used = logistics.slots_ocupados
        slots_max = logistics.slots_maximos if logistics.slots_maximos > 0 else 10
        slots_percent = (slots_used / slots_max * 100) if slots_max > 0 else 0

        # Color segun uso
        if slots_percent < 70:
            slots_color = COLOR_PALETTE["accent_green"]
        elif slots_percent < 90:
            slots_color = COLOR_PALETTE["accent_yellow"]
        else:
            slots_color = COLOR_PALETTE["accent_red"]

        st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85em; color: #888; margin-bottom: 6px;">
                <span>Capacidad de Carga</span>
                <span style="color: {slots_color}; font-weight: bold;">{slots_used} / {slots_max} slots</span>
            </div>
            <div class="slots-bar-container">
                <div class="slots-bar-fill" style="width: {slots_percent}%; background: {slots_color};"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Equipo
        equipo = logistics.equipo or []
        if equipo:
            st.markdown("**Equipo Asignado**")
            for item in equipo:
                nombre = item.get("nombre", "Item desconocido")
                tipo = item.get("tipo", "")
                slots = item.get("slots", 1)
                tipo_str = f" ({tipo})" if tipo else ""
                st.markdown(f"""
                <div class="equip-item">
                    <span style="color: #fff;">{nombre}</span>
                    <span style="color: #888; font-size: 0.85em;">{tipo_str}</span>
                    <span style="color: #45b7d1; font-size: 0.8em; float: right;">{slots} slot(s)</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("Sin equipo asignado.")


def _render_state_section(state: CharacterDynamicState) -> None:
    """Seccion de estado dinamico actual."""
    with st.expander("Estado Actual y Ubicacion", expanded=False):
        # Estados activos
        estados = state.estados_activos or []
        if estados:
            st.markdown("**Estados Activos**")
            estados_html = "".join([_render_status_tag_html(e) for e in estados])
            st.markdown(estados_html, unsafe_allow_html=True)
        else:
            st.markdown(_render_status_tag_html("Disponible"), unsafe_allow_html=True)

        st.write("")

        # Ubicacion
        loc = state.ubicacion

        # Rol asignado (puede ser enum o string)
        rol_val = state.rol_asignado.value if hasattr(state.rol_asignado, 'value') else str(state.rol_asignado)

        st.markdown(f"""
        <div class="info-grid">
            <div class="info-item">
                <div class="info-label">Sistema Estelar</div>
                <div class="info-value">{loc.sistema_actual}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Ubicacion Local</div>
                <div class="info-value">{loc.ubicacion_local}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Rol Asignado</div>
                <div class="info-value" style="color: #45b7d1;">{rol_val}</div>
            </div>
            <div class="info-item">
                <div class="info-label">Accion Actual</div>
                <div class="info-value">{state.accion_actual}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Coordenadas si existen
        if loc.coordenadas:
            coords = loc.coordenadas
            st.markdown(f"""
            <div style="margin-top: 10px; padding: 8px; background: rgba(0,0,0,0.2); border-radius: 6px;">
                <span style="color: #666; font-size: 0.75em;">COORDENADAS: </span>
                <span style="color: #45b7d1; font-family: monospace;">
                    X:{coords.get('x', 0):.2f} Y:{coords.get('y', 0):.2f} Z:{coords.get('z', 0):.2f}
                </span>
            </div>
            """, unsafe_allow_html=True)


# =============================================================================
# FUNCION PRINCIPAL
# =============================================================================

@st.dialog("Expediente de Personal", width="large")
def show_character_sheet(character_id: int) -> None:
    """
    Modal principal que muestra la ficha completa del personaje.

    Args:
        character_id: ID del personaje en la base de datos
    """
    # Inyectar CSS
    st.markdown(SHEET_CSS, unsafe_allow_html=True)

    # Obtener datos del personaje
    char_data = get_character_by_id(character_id)

    if not char_data:
        st.error("No se pudo cargar el expediente del personaje.")
        return

    # Parsear a CharacterSchema usando el wrapper de CommanderData
    try:
        commander = CommanderData.from_dict(char_data)
        sheet = commander.sheet  # Usa la propiedad que valida y migra datos
    except Exception as e:
        st.error(f"Error al procesar datos del personaje: {e}")
        return

    # Renderizar todas las secciones
    _render_header(sheet)
    _render_bio_section(sheet.bio, sheet.taxonomia)
    _render_progression_section(sheet.progresion)
    _render_attributes_section(sheet.capacidades.atributos)
    _render_skills_section(sheet.capacidades)
    _render_behavior_section(sheet.comportamiento)
    _render_logistics_section(sheet.logistica)
    _render_state_section(sheet.estado)
