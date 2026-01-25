# ui/components/tactical.py
"""
Componentes de UI para el Sistema de Detección, Conflicto y Emboscada V14.1.
Incluye:
- Centro de Alertas Tácticas
- Interfaz de Resolución de Encuentro
- Panel de Debug para Simulación
"""

import streamlit as st
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import random

from core.models import UnitSchema, UnitStatus, UnitMemberSchema
from core.detection_engine import (
    resolve_detection_round,
    resolve_mutual_detection,
    resolve_group_escape,
    prepare_combat_state,
    get_hidden_entities,
    CompetitiveDetectionResult,
    MutualDetectionResult,
    EntityRevealInfo,
    RevealLevel
)
from core.detection_constants import (
    DetectionOutcome,
    SKILL_DETECTION,
    SKILL_STEALTH_GROUND,
    SKILL_SENSOR_EVASION,
    SKILL_TACTICAL_ESCAPE,
    SKILL_HUNT
)
from data.unit_repository import get_units_by_player, get_unit_by_id
from data.database import get_supabase
from data.log_repository import log_event


# --- CSS PARA ALERTAS TÁCTICAS ---

def _inject_tactical_css():
    """Inyecta CSS para el centro de alertas tácticas."""
    st.markdown("""
    <style>
    .alert-conflict {
        background: rgba(231, 76, 60, 0.15);
        border-left: 4px solid #e74c3c;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    .alert-ambush-favor {
        background: rgba(241, 196, 15, 0.15);
        border-left: 4px solid #f1c40f;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    .alert-ambush-contra {
        background: rgba(230, 126, 34, 0.15);
        border-left: 4px solid #e67e22;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    .alert-stealth {
        background: rgba(46, 204, 113, 0.15);
        border-left: 4px solid #2ecc71;
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
    }
    .badge-hidden {
        background: #27ae60;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        font-weight: bold;
    }
    .badge-revealed {
        background: #e74c3c;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        font-weight: bold;
    }
    .badge-disoriented {
        background: #e67e22;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        font-weight: bold;
    }
    .mrg-result-box {
        background: rgba(0, 0, 0, 0.2);
        padding: 8px 12px;
        border-radius: 4px;
        font-family: monospace;
        margin: 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)


# --- ESTRUCTURAS DE DATOS ---

@dataclass
class TacticalContact:
    """Representa un contacto de radar (unidad enemiga detectada en ubicación compartida)."""
    our_unit: UnitSchema
    enemy_unit: UnitSchema
    detection_result: Optional[MutualDetectionResult] = None
    location_description: str = ""


# --- HELPERS ---

def _get_enemy_units_at_location(
    our_unit: UnitSchema,
    player_id: int
) -> List[Dict[str, Any]]:
    """
    Obtiene unidades enemigas en la misma ubicación que nuestra unidad.
    """
    db = get_supabase()

    try:
        # Construir query base
        query = db.table("units").select("*")

        # Filtrar por ubicación (sistema + planeta + sector + ring)
        if our_unit.location_system_id:
            query = query.eq("location_system_id", our_unit.location_system_id)

        if our_unit.location_planet_id:
            query = query.eq("location_planet_id", our_unit.location_planet_id)
        else:
            query = query.is_("location_planet_id", "null")

        if our_unit.location_sector_id:
            query = query.eq("location_sector_id", our_unit.location_sector_id)
        else:
            query = query.is_("location_sector_id", "null")

        # Ring
        ring_val = our_unit.ring.value if hasattr(our_unit.ring, 'value') else our_unit.ring
        query = query.eq("ring", ring_val)

        # Excluir nuestras propias unidades
        query = query.neq("player_id", player_id)

        # Excluir unidades en tránsito
        query = query.neq("status", "TRANSIT")

        response = query.execute()
        return response.data if response.data else []

    except Exception as e:
        print(f"Error obteniendo unidades enemigas: {e}")
        return []


def _hydrate_unit_from_dict(unit_data: Dict[str, Any]) -> UnitSchema:
    """Convierte dict de DB a UnitSchema con members hidratados."""
    # Obtener members si existen
    members_data = unit_data.get("members", [])

    # Convertir a UnitMemberSchema
    members = []
    if members_data:
        for m in members_data:
            members.append(UnitMemberSchema(
                slot_index=m.get("slot_index", 0),
                entity_type=m.get("entity_type", "character"),
                entity_id=m.get("entity_id", 0),
                name=m.get("name", "???"),
                details=m.get("details")
            ))

    unit_data["members"] = members
    return UnitSchema.from_dict(unit_data)


def _format_mrg_result(margin: int, result_type: str, is_total: bool = False) -> str:
    """Formatea resultado MRG para visualización."""
    success = margin >= 0

    if success:
        if is_total:
            icon = "🎯"
            label = "ÉXITO TOTAL"
        else:
            icon = "✅"
            label = "ÉXITO"
    else:
        if margin < -25:
            icon = "💀"
            label = "FRACASO TOTAL"
        else:
            icon = "❌"
            label = "FRACASO"

    return f"{icon} {label} (Margen: {margin:+d})"


def _get_outcome_display(outcome: str) -> Tuple[str, str, str]:
    """
    Retorna (emoji, label, css_class) para un outcome de detección.
    """
    outcome_map = {
        DetectionOutcome.CONFLICT: ("⚔️", "CONFLICTO", "alert-conflict"),
        DetectionOutcome.AMBUSH_A: ("🎯", "EMBOSCADA (Favor)", "alert-ambush-favor"),
        DetectionOutcome.AMBUSH_B: ("⚠️", "EMBOSCADA (Contra)", "alert-ambush-contra"),
        DetectionOutcome.MUTUAL_STEALTH: ("👻", "SIGILO MUTUO", "alert-stealth"),
    }
    return outcome_map.get(outcome, ("❓", "DESCONOCIDO", ""))


# --- COMPONENTES PRINCIPALES ---

def render_tactical_alert_center(
    player_id: int,
    units: List[Dict[str, Any]],
    show_header: bool = True
):
    """
    Renderiza el Centro de Alertas Tácticas.
    Escanea unidades enemigas en las mismas ubicaciones que las del jugador.
    """
    _inject_tactical_css()

    if show_header:
        st.markdown("### 📡 Centro de Alertas Tácticas")

    # Convertir unidades a UnitSchema
    player_units = []
    for u_data in units:
        try:
            unit = _hydrate_unit_from_dict(u_data)
            # Solo unidades no en tránsito
            if unit.status != UnitStatus.TRANSIT:
                player_units.append(unit)
        except Exception as e:
            print(f"Error hidratando unidad {u_data.get('id')}: {e}")

    if not player_units:
        st.info("No hay unidades desplegadas para monitorear.")
        return

    # Buscar contactos enemigos
    contacts: List[TacticalContact] = []

    for our_unit in player_units:
        enemy_units_data = _get_enemy_units_at_location(our_unit, player_id)

        for enemy_data in enemy_units_data:
            try:
                enemy_unit = _hydrate_unit_from_dict(enemy_data)

                # Crear descripción de ubicación
                loc_parts = []
                if our_unit.location_system_id:
                    loc_parts.append(f"Sistema {our_unit.location_system_id}")
                if our_unit.location_planet_id:
                    loc_parts.append(f"Planeta {our_unit.location_planet_id}")
                ring_val = our_unit.ring.value if hasattr(our_unit.ring, 'value') else our_unit.ring
                loc_parts.append(f"Anillo {ring_val}")

                contacts.append(TacticalContact(
                    our_unit=our_unit,
                    enemy_unit=enemy_unit,
                    location_description=" / ".join(loc_parts)
                ))
            except Exception as e:
                print(f"Error procesando unidad enemiga: {e}")

    # Mostrar contactos o mensaje de despejado
    if not contacts:
        st.success("📡 Radar despejado. No se detectan contactos hostiles en ubicaciones activas.")
        return

    st.warning(f"📡 **{len(contacts)} contacto(s) detectado(s)**")

    # Renderizar cada contacto
    for idx, contact in enumerate(contacts):
        _render_contact_card(contact, player_id, idx)


def _render_contact_card(contact: TacticalContact, player_id: int, idx: int):
    """Renderiza una tarjeta de contacto con opciones de acción."""
    key_prefix = f"contact_{contact.our_unit.id}_{contact.enemy_unit.id}_{idx}"

    # Verificar si ya se resolvió la detección
    detection_key = f"detection_result_{key_prefix}"

    with st.container():
        col_info, col_action = st.columns([3, 1])

        with col_info:
            st.markdown(f"""
            **📍 {contact.location_description}**
            🎖️ Nuestra Unidad: **{contact.our_unit.name}** ({len(contact.our_unit.members)} miembros)
            👹 Contacto: **{contact.enemy_unit.name}** (Jugador {contact.enemy_unit.player_id})
            """)

        with col_action:
            # Botón para resolver detección
            if st.button("🔍 Resolver Detección", key=f"resolve_{key_prefix}"):
                # Ejecutar detección mutua
                result = resolve_mutual_detection(
                    contact.our_unit,
                    contact.enemy_unit,
                    player_id,
                    contact.enemy_unit.player_id
                )

                # Guardar resultado en session state
                st.session_state[detection_key] = result

                # Notificar al jugador
                emoji, label, _ = _get_outcome_display(result.outcome)
                st.toast(f"{emoji} Detección: {label}")

        # Mostrar resultado si existe
        if detection_key in st.session_state:
            result: MutualDetectionResult = st.session_state[detection_key]
            _render_detection_result(result, contact, player_id, key_prefix)


def _render_detection_result(
    result: MutualDetectionResult,
    contact: TacticalContact,
    player_id: int,
    key_prefix: str
):
    """Renderiza el resultado de una detección mutua."""
    emoji, label, css_class = _get_outcome_display(result.outcome)

    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
    st.markdown(f"### {emoji} Resultado: {label}")

    # Detalles de las tiradas
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🎖️ Nuestra Detección:**")
        mrg_a = result.details.get("mrg_a_to_b", {})
        st.markdown(f'<div class="mrg-result-box">{_format_mrg_result(mrg_a.get("margin", 0), mrg_a.get("result_type", ""), mrg_a.get("is_total", False))}</div>', unsafe_allow_html=True)

        if result.unit_a_detects_b:
            st.markdown("**Enemigos revelados:**")
            for entity in result.unit_b_revealed:
                level_badge = "COMPLETO" if entity.reveal_level == RevealLevel.FULL else "PARCIAL"
                st.markdown(f"- {entity.name} ({entity.entity_type}) - `{level_badge}`")

            # Mostrar ocultos
            hidden = get_hidden_entities(contact.enemy_unit, result.unit_b_revealed)
            if hidden:
                st.markdown(f"*{len(hidden)} entidad(es) permanecen ocultas*")

    with col2:
        st.markdown("**👹 Detección Enemiga:**")
        mrg_b = result.details.get("mrg_b_to_a", {})
        st.markdown(f'<div class="mrg-result-box">{_format_mrg_result(mrg_b.get("margin", 0), mrg_b.get("result_type", ""), mrg_b.get("is_total", False))}</div>', unsafe_allow_html=True)

        if result.unit_b_detects_a:
            st.markdown("**Nuestros revelados:**")
            for entity in result.unit_a_revealed:
                level_badge = "COMPLETO" if entity.reveal_level == RevealLevel.FULL else "PARCIAL"
                st.markdown(f"- {entity.name} ({entity.entity_type}) - `{level_badge}`")

            hidden = get_hidden_entities(contact.our_unit, result.unit_a_revealed)
            if hidden:
                st.markdown(f"*{len(hidden)} de nuestras entidades permanecen ocultas*")

    st.markdown('</div>', unsafe_allow_html=True)

    # Acciones según outcome
    st.divider()
    _render_encounter_actions(result, contact, player_id, key_prefix)


def _render_encounter_actions(
    result: MutualDetectionResult,
    contact: TacticalContact,
    player_id: int,
    key_prefix: str
):
    """Renderiza las acciones disponibles según el resultado del encuentro."""
    col1, col2, col3 = st.columns(3)

    if result.outcome == DetectionOutcome.AMBUSH_A:
        # Nosotros tenemos ventaja
        with col1:
            if st.button("⚔️ Iniciar Emboscada", key=f"ambush_{key_prefix}", type="primary"):
                st.session_state[f"combat_initiated_{key_prefix}"] = True
                st.toast("🎯 Emboscada iniciada!")
                # Preparar estado de combate
                combat_state = prepare_combat_state(
                    contact.enemy_unit,
                    result.unit_b_revealed,
                    was_ambushed=True
                )
                st.session_state[f"combat_state_{key_prefix}"] = combat_state
                st.info(f"Estado enemigo: {'Desacomodado' if combat_state['disoriented'] else 'Normal'}")

        with col2:
            if st.button("👻 Mantener Sigilo", key=f"stealth_{key_prefix}"):
                st.toast("Permanecemos ocultos...")

    elif result.outcome == DetectionOutcome.AMBUSH_B:
        # Ellos tienen ventaja
        st.warning("⚠️ El enemigo tiene la iniciativa. Debes decidir rápidamente.")

        with col1:
            if st.button("🏃 Intentar Huida", key=f"flee_{key_prefix}", type="primary"):
                _handle_group_escape(contact, result, player_id, key_prefix)

        with col2:
            if st.button("⚔️ Preparar Defensa", key=f"defend_{key_prefix}"):
                # Preparar nuestro estado de combate
                combat_state = prepare_combat_state(
                    contact.our_unit,
                    result.unit_a_revealed,
                    was_ambushed=True
                )
                st.session_state[f"our_combat_state_{key_prefix}"] = combat_state

                if combat_state["disoriented"]:
                    st.error("⚠️ Nuestra unidad está desacomodada (1 mov local/tick)")
                else:
                    st.info("Preparados para el combate.")

    elif result.outcome == DetectionOutcome.CONFLICT:
        # Ambos se detectan
        with col1:
            if st.button("⚔️ Iniciar Combate", key=f"combat_{key_prefix}", type="primary"):
                st.toast("⚔️ Combate iniciado!")

        with col2:
            if st.button("🏃 Intentar Huida", key=f"flee_{key_prefix}"):
                _handle_group_escape(contact, result, player_id, key_prefix)

        with col3:
            if st.button("🕊️ Intentar Negociación", key=f"negotiate_{key_prefix}"):
                st.info("Sistema de diplomacia no implementado aún.")

    else:  # MUTUAL_STEALTH
        st.success("👻 Ambas unidades permanecen sin detectarse. Pueden continuar su camino.")


def _handle_group_escape(
    contact: TacticalContact,
    result: MutualDetectionResult,
    player_id: int,
    key_prefix: str
):
    """Maneja el intento de escape grupal."""
    escaped, captured = resolve_group_escape(
        contact.our_unit,
        contact.enemy_unit,
        result.unit_a_revealed,
        player_id
    )

    st.session_state[f"escape_result_{key_prefix}"] = {
        "escaped": [m.name for m in escaped],
        "captured": [m.name for m in captured]
    }

    # Mostrar resultados
    if escaped:
        st.success(f"🏃 Escaparon: {', '.join([m.name for m in escaped])}")
        st.info("Los que escaparon pueden formar nueva unidad con movimiento libre.")

    if captured:
        st.error(f"❌ Atrapados (entran en combate desacomodados): {', '.join([m.name for m in captured])}")


# --- PANEL DE DEBUG ---

def render_debug_simulation_panel(player_id: int, units: List[Dict[str, Any]]):
    """
    Panel de debug para simular colisiones y testear el sistema de detección.
    """
    _inject_tactical_css()

    with st.expander("🛠️ Debug: Simulador de Colisiones Tácticas", expanded=False):
        st.caption("Herramienta para testear el motor de detección sin afectar el juego.")

        if not units:
            st.warning("No hay unidades para simular.")
            return

        # Seleccionar unidad propia
        unit_options = {u["id"]: f"{u.get('name', 'Unidad')} (ID: {u['id']})" for u in units}
        selected_unit_id = st.selectbox(
            "Seleccionar unidad propia",
            options=list(unit_options.keys()),
            format_func=lambda x: unit_options.get(x, str(x)),
            key="debug_select_unit"
        )

        if selected_unit_id:
            unit_data = next((u for u in units if u["id"] == selected_unit_id), None)
            if unit_data:
                our_unit = _hydrate_unit_from_dict(unit_data)

                st.markdown("---")
                st.markdown("### Configurar Unidad Enemiga Virtual")

                col1, col2 = st.columns(2)

                with col1:
                    enemy_name = st.text_input("Nombre enemigo", value="Patrulla Hostil", key="debug_enemy_name")
                    enemy_members = st.slider("Cantidad de miembros", 1, 8, 4, key="debug_enemy_members")

                with col2:
                    enemy_stealth = st.slider("Nivel de Sigilo promedio", 10, 80, 35, key="debug_enemy_stealth")
                    enemy_in_stealth_mode = st.checkbox("En Modo Sigilo (STEALTH_MODE)", key="debug_stealth_mode")

                # Crear unidad enemiga virtual
                virtual_members = []
                for i in range(enemy_members):
                    virtual_members.append(UnitMemberSchema(
                        slot_index=i,
                        entity_type="character" if i == 0 else "troop",
                        entity_id=9000 + i,  # IDs virtuales
                        name=f"Hostil-{i+1}",
                        details={
                            "habilidades": {
                                SKILL_DETECTION: 30 + random.randint(-10, 10),
                                SKILL_STEALTH_GROUND: enemy_stealth + random.randint(-5, 5),
                                SKILL_SENSOR_EVASION: enemy_stealth + random.randint(-5, 5),
                                SKILL_TACTICAL_ESCAPE: 30 + random.randint(-10, 10),
                                SKILL_HUNT: 30 + random.randint(-10, 10)
                            }
                        }
                    ))

                virtual_enemy = UnitSchema(
                    id=9999,
                    player_id=9999,
                    name=enemy_name,
                    status=UnitStatus.STEALTH_MODE if enemy_in_stealth_mode else UnitStatus.SPACE,
                    members=virtual_members,
                    location_system_id=our_unit.location_system_id,
                    location_planet_id=our_unit.location_planet_id,
                    location_sector_id=our_unit.location_sector_id,
                    ring=our_unit.ring
                )

                st.markdown("---")

                # Botones de simulación
                col_sim1, col_sim2 = st.columns(2)

                with col_sim1:
                    if st.button("🔍 Simular Detección Mutua", type="primary", key="debug_mutual"):
                        with st.spinner("Resolviendo detección..."):
                            result = resolve_mutual_detection(
                                our_unit,
                                virtual_enemy,
                                player_id,
                                9999
                            )

                            st.session_state["debug_detection_result"] = result

                with col_sim2:
                    if st.button("🎯 Simular Solo Nuestra Detección", key="debug_our_detect"):
                        with st.spinner("Resolviendo..."):
                            result = resolve_detection_round(
                                our_unit,
                                virtual_enemy,
                                player_id
                            )
                            st.session_state["debug_single_result"] = result

                # Mostrar resultados de simulación
                if "debug_detection_result" in st.session_state:
                    result = st.session_state["debug_detection_result"]
                    st.markdown("### 📊 Resultado de Simulación (Mutua)")

                    emoji, label, css = _get_outcome_display(result.outcome)
                    st.markdown(f'<div class="{css}"><h4>{emoji} {label}</h4></div>', unsafe_allow_html=True)

                    col_r1, col_r2 = st.columns(2)

                    with col_r1:
                        st.markdown("**Nuestra Detección →**")
                        mrg = result.details.get("mrg_a_to_b", {})
                        st.code(f"""
Margen: {mrg.get('margin', 0):+d}
Tipo: {mrg.get('result_type', 'N/A')}
Éxito Total: {mrg.get('is_total', False)}
Revelados: {len(result.unit_b_revealed)}
                        """)

                    with col_r2:
                        st.markdown("**← Detección Enemiga**")
                        mrg = result.details.get("mrg_b_to_a", {})
                        st.code(f"""
Margen: {mrg.get('margin', 0):+d}
Tipo: {mrg.get('result_type', 'N/A')}
Éxito Total: {mrg.get('is_total', False)}
Revelados: {len(result.unit_a_revealed)}
                        """)

                    # Desglose de entidades
                    with st.expander("📋 Desglose de Entidades Reveladas"):
                        st.markdown("**Enemigos revelados a nosotros:**")
                        for e in result.unit_b_revealed:
                            st.write(f"- {e.name} | Sigilo: {e.stealth_score} | Nivel: {e.reveal_level.value}")

                        st.markdown("**Nuestros revelados al enemigo:**")
                        for e in result.unit_a_revealed:
                            st.write(f"- {e.name} | Sigilo: {e.stealth_score} | Nivel: {e.reveal_level.value}")

                if "debug_single_result" in st.session_state:
                    result: CompetitiveDetectionResult = st.session_state["debug_single_result"]
                    st.markdown("### 📊 Resultado de Simulación (Solo Nuestra Detección)")

                    st.markdown(f'<div class="mrg-result-box">{_format_mrg_result(result.mrg_result.margin, result.mrg_result.result_type.value, result.is_total_success)}</div>', unsafe_allow_html=True)

                    st.code(f"""
Éxito: {result.success}
Éxito Total: {result.is_total_success}
Margen: {result.mrg_result.margin:+d}
Entidades Reveladas: {len(result.entities_revealed)}
                    """)

                    if result.worst_defender_revealed:
                        st.info(f"Peor sigilo (revelado primero): {result.worst_defender_revealed.name} (Sigilo: {result.worst_defender_revealed.stealth_score})")


def render_unit_status_badges(unit: UnitSchema) -> str:
    """Genera HTML con badges de estado para una unidad."""
    badges = []

    if unit.status == UnitStatus.STEALTH_MODE:
        badges.append('<span class="badge-hidden">SIGILO</span>')
    elif unit.status == UnitStatus.HIDDEN:
        badges.append('<span class="badge-hidden">OCULTO</span>')

    if hasattr(unit, 'disoriented') and unit.disoriented:
        badges.append('<span class="badge-disoriented">DESACOMODADO</span>')

    return " ".join(badges)


def render_member_status_badge(
    member: UnitMemberSchema,
    revealed_ids: set
) -> str:
    """Genera badge de estado para un miembro de unidad."""
    member_key = (member.entity_id, member.entity_type)

    if member_key in revealed_ids:
        return '<span class="badge-revealed">REVELADO</span>'
    else:
        return '<span class="badge-hidden">OCULTO</span>'
