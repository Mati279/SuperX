# ui/base_management.py (Completo)
"""
Gestión de Bases Militares.
Interfaz para construcción, mejora y gestión de módulos de bases.
v1.0.0: Implementación inicial.
v1.0.1: Fix TypeError en target_tier None.
Refactor v12.0: Soporte para renombrado de base y demolición externa.
"""

import streamlit as st
from data.database import get_supabase
from data.planet_repository import get_planet_by_id, get_planet_sectors_status
from data.planets.buildings import update_base_name
from data.world_repository import get_world_state
from core.base_engine import (
    build_base,
    upgrade_base,
    upgrade_module,
    get_base_by_id,
    get_base_by_sector,
    get_player_bases,
    get_base_module_status,
    get_sector_eligible_for_base,
    can_build_base_in_sector,
    can_upgrade_base
)
from core.world_constants import (
    BASE_CONSTRUCTION_COST,
    BASE_UPGRADE_COSTS,
    BASE_MODULES,
    BASE_MODULES_BY_TIER,
    BASE_EXTRA_SLOTS,
    SECTOR_TYPE_URBAN,
    get_base_upgrade_time,
    get_max_module_level
)
from ui.state import get_player_id


def render_base_management_panel(sector_id: int, planet_id: int):
    """
    Renderiza el panel de gestión de base para un sector urbano.
    Si no hay base, muestra opción de construir.
    Si hay base, muestra opciones de mejora y módulos.
    """
    player_id = get_player_id()
    if not player_id:
        st.error("Sesión no detectada.")
        return

    base = get_base_by_sector(sector_id)
    world_state = get_world_state()
    current_tick = world_state.get("current_tick", 1)

    if not base:
        _render_build_base_panel(sector_id, planet_id, player_id)
    else:
        _render_base_details(base, player_id, current_tick)


def _render_build_base_panel(sector_id: int, planet_id: int, player_id: int):
    """Renderiza el panel para construir una nueva base."""
    st.markdown("### :shield: Construir Base Militar")

    # Verificar si se puede construir
    can_build, error_msg = can_build_base_in_sector(sector_id, player_id)

    if not can_build:
        st.warning(f"No se puede construir una base aquí: {error_msg}")
        return

    # Mostrar costes
    cost_c = BASE_CONSTRUCTION_COST.get("creditos", 1000)
    cost_m = BASE_CONSTRUCTION_COST.get("materiales", 110)
    build_time = get_base_upgrade_time(1)

    st.info(f"""
    **Base Militar Nv.1**

    Las bases permiten defender sectores urbanos y desbloquean módulos de defensa avanzados.

    **Coste:** {cost_c} Creditos, {cost_m} Materiales
    **Tiempo de construccion:** {build_time} ciclos
    """)

    # Módulos iniciales
    st.markdown("**Modulos incluidos (Nv.1):**")
    for module_key in BASE_MODULES_BY_TIER.get(1, []):
        module_def = BASE_MODULES.get(module_key, {})
        st.markdown(f"- {module_def.get('name', module_key)}: {module_def.get('desc', '')}")

    if st.button("Construir Base", key=f"build_base_{sector_id}", use_container_width=True, type="primary"):
        result = build_base(sector_id, player_id)
        if result.get("success"):
            st.success(result.get("message", "Base en construccion."))
            st.rerun()
        else:
            st.error(result.get("error", "Error desconocido."))


def _render_base_details(base: dict, player_id: int, current_tick: int):
    """Renderiza los detalles de una base existente."""
    base_tier = base.get("tier", 1)
    base_id = base.get("id")
    current_name = base.get("name") or f"Base Militar {base_id}"
    
    is_upgrading = base.get("upgrade_in_progress", False)
    completes_at = base.get("upgrade_completes_at_tick")
    
    # FIX: Manejo robusto de target_tier para evitar TypeError
    target_tier = base.get("upgrade_target_tier")
    if target_tier is None:
        target_tier = base_tier + 1

    st.markdown(f"### :shield: {current_name} (Nv.{base_tier})")
    
    # --- Renombrado Rápido ---
    with st.expander("📝 Renombrar Base"):
        new_name = st.text_input("Nuevo nombre:", value=current_name, key=f"rename_in_{base_id}")
        if st.button("Guardar Nombre", key=f"btn_ren_{base_id}"):
            if update_base_name(base_id, new_name, player_id):
                st.success("Nombre actualizado.")
                st.rerun()
            else:
                st.error("Error al actualizar nombre.")

    # Estado de mejora
    if is_upgrading and completes_at:
        ticks_remaining = completes_at - current_tick
        
        # Validar consistencia de datos antes de calcular progreso
        if target_tier is not None and isinstance(target_tier, int):
            total_time = get_base_upgrade_time(target_tier)
        else:
            total_time = 1 # Fallback seguro para evitar división por cero
            
        if ticks_remaining > 0:
            st.warning(f"Mejorando a Nv.{target_tier}... Faltan {ticks_remaining} ciclo(s).")
            # Protección contra valores negativos o erróneos en progreso
            try:
                progress_val = max(0.0, min(1.0, 1 - (ticks_remaining / total_time)))
                st.progress(progress_val)
            except Exception:
                st.progress(0.5) # Visual fallback
        else:
            st.info("Mejora completandose en el proximo ciclo...")

    # Pestanas principales
    tab_modules, tab_upgrade = st.tabs(["Modulos", "Mejorar Base"])

    with tab_modules:
        _render_modules_tab(base, player_id)

    with tab_upgrade:
        _render_upgrade_tab(base, player_id)


def _render_modules_tab(base: dict, player_id: int):
    """Renderiza la pestana de gestion de modulos."""
    base_id = base.get("id")
    base_tier = base.get("tier", 1)
    is_upgrading = base.get("upgrade_in_progress", False)

    modules_status = get_base_module_status(base_id)

    if not modules_status:
        st.info("No hay modulos disponibles.")
        return

    max_level = get_max_module_level(base_tier)
    st.caption(f"Nivel maximo de modulos para Base Nv.{base_tier}: **{max_level}**")

    # Agrupar modulos por estado
    unlocked_modules = {k: v for k, v in modules_status.items() if v.get("is_unlocked")}
    locked_modules = {k: v for k, v in modules_status.items() if not v.get("is_unlocked")}

    # Modulos desbloqueados
    if unlocked_modules:
        st.markdown("#### Modulos Activos")

        for module_key, status in unlocked_modules.items():
            with st.container(border=True):
                col1, col2 = st.columns([0.7, 0.3])

                with col1:
                    current_lvl = status.get("current_level", 0)
                    max_lvl = status.get("max_level", max_level)

                    st.markdown(f"**{status.get('name')}** (Nv.{current_lvl}/{max_lvl})")
                    st.caption(status.get("description", ""))

                    # Barra de progreso
                    progress = current_lvl / max_lvl if max_lvl > 0 else 0
                    st.progress(progress)

                    # Efecto actual
                    effect = status.get("effect", {})
                    if effect:
                        effect_str = ", ".join([f"+{v * current_lvl} {k.replace('_', ' ')}" for k, v in effect.items()])
                        st.caption(f"Efecto actual: {effect_str}")

                with col2:
                    if status.get("is_maxed"):
                        st.success("MAX")
                    elif is_upgrading:
                        st.warning("Base en mejora")
                    else:
                        next_cost = status.get("next_upgrade_cost", {})
                        cost_str = f"{next_cost.get('creditos', 0)}C, {next_cost.get('materiales', 0)}Mat"
                        st.caption(f"Coste: {cost_str}")

                        if st.button("Mejorar", key=f"upg_mod_{module_key}", use_container_width=True):
                            result = upgrade_module(base_id, module_key, player_id)
                            if result.get("success"):
                                st.success(result.get("message"))
                                st.rerun()
                            else:
                                st.error(result.get("error"))

    # Modulos bloqueados
    if locked_modules:
        st.markdown("#### Modulos Bloqueados")
        st.caption("Mejora la base para desbloquear estos modulos.")

        for module_key, status in locked_modules.items():
            with st.container(border=True):
                unlock_tier = status.get("unlock_tier", 1)
                st.markdown(f":lock: **{status.get('name')}** (Requiere Base Nv.{unlock_tier})")
                st.caption(status.get("description", ""))


def _render_upgrade_tab(base: dict, player_id: int):
    """Renderiza la pestana de mejora de base."""
    base_id = base.get("id")
    base_tier = base.get("tier", 1)
    is_upgrading = base.get("upgrade_in_progress", False)

    if base_tier >= 4:
        st.success("La base esta al nivel maximo (Nv.4).")
        st.balloons()
        return

    if is_upgrading:
        st.warning("La base esta en proceso de mejora. Espera a que termine.")
        return

    target_tier = base_tier + 1
    costs = BASE_UPGRADE_COSTS.get(target_tier, {})
    upgrade_time = get_base_upgrade_time(target_tier)

    st.markdown(f"### Mejorar a Nv.{target_tier}")

    # Costes
    col1, col2, col3 = st.columns(3)
    col1.metric("Creditos", f"{costs.get('creditos', 0):,}")
    col2.metric("Materiales", f"{costs.get('materiales', 0):,}")
    col3.metric("Tiempo", f"{upgrade_time} ciclos")

    # Beneficios
    st.markdown("**Beneficios:**")

    # Nuevos modulos
    new_modules = BASE_MODULES_BY_TIER.get(target_tier, [])
    if new_modules:
        st.markdown("*Nuevos modulos desbloqueados:*")
        for module_key in new_modules:
            module_def = BASE_MODULES.get(module_key, {})
            st.markdown(f"- :unlock: **{module_def.get('name', module_key)}**: {module_def.get('desc', '')}")

    # Slots extra
    extra_slots = BASE_EXTRA_SLOTS.get(target_tier, 0)
    if extra_slots > 0:
        st.markdown(f"- :heavy_plus_sign: **+{extra_slots} Slot(s)** de construccion en el sector")

    # Nuevo nivel maximo de modulos
    new_max = get_max_module_level(target_tier)
    st.markdown(f"- :chart_with_upwards_trend: Nivel maximo de modulos aumenta a **{new_max}**")

    st.divider()

    # Verificar si puede mejorar
    can_upgrade, error_msg = can_upgrade_base(base_id, player_id)

    if not can_upgrade:
        st.error(error_msg)
    else:
        if st.button(f"Iniciar Mejora a Nv.{target_tier}", key=f"upgrade_base_{base_id}", use_container_width=True, type="primary"):
            result = upgrade_base(base_id, player_id)
            if result.get("success"):
                st.success(result.get("message"))
                st.rerun()
            else:
                st.error(result.get("error"))


def render_player_bases_overview():
    """
    Renderiza una vista general de todas las bases del jugador.
    Util para el panel principal o una pagina dedicada.
    """
    player_id = get_player_id()
    if not player_id:
        st.error("Sesion no detectada.")
        return

    bases = get_player_bases(player_id)

    if not bases:
        st.info("No tienes bases militares construidas.")
        st.caption("Construye bases en sectores urbanos bajo tu control para defender tus territorios.")
        return

    st.markdown(f"### :shield: Tus Bases Militares ({len(bases)})")

    world_state = get_world_state()
    current_tick = world_state.get("current_tick", 1)

    for base in bases:
        with st.container(border=True):
            base_tier = base.get("tier", 1)
            is_upgrading = base.get("upgrade_in_progress", False)
            sector_data = base.get("sectors", {})
            planet_data = base.get("planets", {})

            sector_name = sector_data.get("name", "Sector Desconocido") if sector_data else "Sector Desconocido"
            planet_name = planet_data.get("name", "Planeta Desconocido") if planet_data else "Planeta Desconocido"

            col1, col2 = st.columns([0.7, 0.3])

            with col1:
                st.markdown(f"**Base Nv.{base_tier}** en {sector_name}")
                st.caption(f"Planeta: {planet_name}")

                if is_upgrading:
                    completes_at = base.get("upgrade_completes_at_tick", 0)
                    ticks_remaining = max(0, completes_at - current_tick)
                    target = base.get("upgrade_target_tier", base_tier + 1)
                    st.warning(f"Mejorando a Nv.{target}... ({ticks_remaining} ciclos)")

            with col2:
                # Calcular estado de modulos
                modules_status = get_base_module_status(base.get("id"))
                unlocked = sum(1 for m in modules_status.values() if m.get("is_unlocked"))
                total = len(modules_status)
                st.metric("Modulos", f"{unlocked}/{total}")


def render_base_card_mini(sector_id: int):
    """
    Renderiza una tarjeta mini de base para mostrar en la vista de sector.
    Retorna True si hay base, False si no.
    """
    base = get_base_by_sector(sector_id)

    if not base:
        return False

    base_tier = base.get("tier", 1)
    is_upgrading = base.get("upgrade_in_progress", False)

    with st.container(border=True):
        col1, col2 = st.columns([0.7, 0.3])

        with col1:
            status_icon = ":shield:" if not is_upgrading else ":construction:"
            st.markdown(f"{status_icon} **Base Militar Nv.{base_tier}**")

            if is_upgrading:
                world_state = get_world_state()
                current_tick = world_state.get("current_tick", 1)
                completes_at = base.get("upgrade_completes_at_tick", 0)
                ticks_remaining = max(0, completes_at - current_tick)
                st.caption(f"En mejora... ({ticks_remaining} ciclos)")

        with col2:
            if st.button("Gestionar", key=f"manage_base_{sector_id}"):
                st.session_state.selected_base_sector = sector_id
                st.session_state.show_base_management = True
                st.rerun()

    return True