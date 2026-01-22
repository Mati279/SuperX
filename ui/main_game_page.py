# ui/main_game_page.py (Completo)
import streamlit as st
import time
from .state import logout_user, get_player, get_commander
from data.log_repository import get_recent_logs, log_event
from data.planet_repository import get_all_player_planets # Importación Nueva V5.8
from services.gemini_service import resolve_player_action
# Importación del servicio de generación para herramientas de Debug
from services.character_generation_service import generate_character_pool

# --- Imports para STRT (Sistema de Tiempo) ---
from core.time_engine import get_world_status_display, check_and_trigger_tick, debug_force_tick
from data.world_repository import get_commander_location_display
from data.player_repository import get_player_finances, delete_player_account, add_player_credits, reset_player_progress

# --- Imports para Economía ---
from core.economy_engine import get_player_projected_economy

# --- IMPORTS NUEVOS: MERCADO ---
from core.market_engine import calculate_market_prices, get_market_limits, place_market_order

# --- Importar las vistas del juego ---
from .faction_roster import render_faction_roster
from .recruitment_center import show_recruitment_center
from .galaxy_map_page import show_galaxy_map_page
from .ship_status_page import show_ship_status_page
from .planet_surface_view import render_planet_surface # Vista de Superficie conectada

# --- IMPORTACIÓN NUEVA: Widget de Resolución MRG ---
from .mrg_resolution_widget import render_full_mrg_resolution


def render_main_game_page(cookie_manager):
    """
    Página principal del juego con HUD superior FIXED y navegación lateral.
    """
    
    # --- STRT: Trigger de Tiempo ---
    try:
        check_and_trigger_tick()
    except Exception as e:
        print(f"Advertencia de tiempo: {e}")

    player = get_player()
    commander = get_commander()

    if not player or not commander:
        st.error("❌ ERROR CRÍTICO: No se pudieron cargar los datos del jugador. Reinicia sesión.")
        if st.button("Volver al Login", use_container_width=True):
            logout_user(cookie_manager)
        return

    # --- 1. RENDERIZAR HUD SUPERIOR (Siempre visible) ---
    _render_sticky_top_hud(player, commander)

    # --- 2. Renderizar Sidebar (Solo Navegación e Identidad) ---
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Puente de Mando"
        
    # --- LÓGICA DE LIMPIEZA MRG POR CAMBIO DE PÁGINA ---
    # Si cambiamos de página, limpiamos cualquier resultado MRG pendiente
    if 'previous_page' not in st.session_state:
        st.session_state.previous_page = st.session_state.current_page
    
    if st.session_state.current_page != st.session_state.previous_page:
        st.session_state.last_mrg_result = None
        st.session_state.previous_page = st.session_state.current_page

    _render_navigation_sidebar(player, commander, cookie_manager)

    # --- 3. Renderizar la página seleccionada ---
    PAGES = {
        "Puente de Mando": _render_war_room_page,
        "Cuadrilla": render_faction_roster,
        "Centro de Reclutamiento": show_recruitment_center,
        "Mapa de la Galaxia": show_galaxy_map_page,
        "Flota": show_ship_status_page,
        # Nueva Página de Superficie (Render condicional)
        "Superficie": lambda: render_planet_surface(st.session_state.selected_planet_id) if st.session_state.get("selected_planet_id") else st.warning("⚠️ Selecciona un planeta desde el Mapa o Accesos Directos.")
    }
    
    # Contenedor principal con margen superior para no quedar bajo el HUD
    with st.container():
        st.write("") # Espaciador
        st.write("") 
        render_func = PAGES.get(st.session_state.current_page, _render_war_room_page)
        render_func()


def _render_sticky_top_hud(player, commander):
    """
    Renderiza la barra superior STICKY (siempre visible).
    Layout: Recursos CENTRADOS con DELTAS de proyección.
    """
    finances = get_player_finances(player.id)
    projection = get_player_projected_economy(player.id)

    # Helper para evitar crash por NoneType
    def safe_val(key):
        val = finances.get(key) if finances else None
        return val if val is not None else 0
    
    # Helper para formatear delta (proyección)
    def fmt_delta(key):
        val = projection.get(key, 0)
        if val == 0:
            return ""
        
        # Verde para positivo, Rojo para negativo
        color = "#4caf50" if val > 0 else "#ff5252"
        sign = "+" if val > 0 else "" # El negativo ya viene en el número
        
        return f'<span style="color: {color}; font-size: 0.7em; margin-left: 5px;">{sign}{val:,}</span>'

    # Preparar valores para el HTML (evita problemas de interpolación)
    creditos = f"{safe_val('creditos'):,}"
    delta_creditos = fmt_delta('creditos')

    materiales = f"{safe_val('materiales'):,}"
    delta_materiales = fmt_delta('materiales')

    componentes = f"{safe_val('componentes'):,}"
    delta_componentes = fmt_delta('componentes')

    celulas = f"{safe_val('celulas_energia'):,}"
    delta_celulas = fmt_delta('celulas_energia')

    influencia = f"{safe_val('influencia'):,}"
    delta_influencia = fmt_delta('influencia')

    # CSS separado para mayor claridad
    hud_css = """
    <style>
    .top-hud-sticky {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 50px;
        z-index: 999999;
        background-color: #262730;
        border-bottom: 1px solid #444;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    }

    .hud-resource-group {
        display: flex;
        gap: 40px;
        align-items: center;
        height: 100%;
    }

    .hud-metric {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: help;
        padding: 2px 8px;
        border-radius: 4px;
    }

    .hud-metric:hover {
        background-color: rgba(255,255,255,0.05);
    }

    .hud-icon {
        font-size: 1.1em;
        line-height: 1;
        opacity: 0.8;
    }

    .hud-value {
        font-family: 'Source Code Pro', monospace;
        font-weight: 600;
        color: #e0e0e0 !important;
        font-size: 0.95em;
        white-space: nowrap;
        display: flex;
        align-items: center; 
    }

    @media (max-width: 800px) {
        .hud-value { font-size: 0.8em; }
        .hud-icon { font-size: 1.0em; }
        .top-hud-sticky { padding-left: 60px; }
        .hud-resource-group { gap: 15px; }
    }
    </style>
    """

    # HTML con valores ya interpolados
    hud_html = f"""
    <div class="top-hud-sticky">
        <div class="hud-resource-group">
            <div class="hud-metric" title="Créditos Estándar">
                <span class="hud-icon">💳</span>
                <span class="hud-value">{creditos}{delta_creditos}</span>
            </div>
            <div class="hud-metric" title="Materiales de Construcción">
                <span class="hud-icon">📦</span>
                <span class="hud-value">{materiales}{delta_materiales}</span>
            </div>
            <div class="hud-metric" title="Componentes Tecnológicos">
                <span class="hud-icon">🧩</span>
                <span class="hud-value">{componentes}{delta_componentes}</span>
            </div>
            <div class="hud-metric" title="Células de Energía">
                <span class="hud-icon">⚡</span>
                <span class="hud-value">{celulas}{delta_celulas}</span>
            </div>
            <div class="hud-metric" title="Influencia Política">
                <span class="hud-icon">👑</span>
                <span class="hud-value">{influencia}{delta_influencia}</span>
            </div>
        </div>
    </div>

    <div style="height: 60px;"></div>
    """

    st.markdown(hud_css + hud_html, unsafe_allow_html=True)


def _render_navigation_sidebar(player, commander, cookie_manager):
    """Sidebar con reloj galáctico, identidad y menú de navegación."""
    status = get_world_status_display()
    
    # Obtener ubicación real (Base Principal)
    loc_data = get_commander_location_display(commander.id)
    loc_system = loc_data.get("system", "Desconocido")
    loc_planet = loc_data.get("planet", "---")
    loc_base_name = loc_data.get("base", "Base Principal")

    with st.sidebar:
        
        # --- PANEL DE UBICACIÓN ---
        location_css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700&display=swap');
        .sidebar-loc-panel {
            background: rgba(30, 33, 40, 0.6);
            border-left: 3px solid #8ab4f8;
            padding: 10px;
            margin-bottom: 15px;
            font-family: 'Orbitron', sans-serif;
            color: #e0e0e0;
        }
        .loc-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
            font-size: 0.85em;
        }
        .loc-row:last-child { margin-bottom: 0; }
        .loc-icon { color: #8ab4f8; width: 20px; text-align: center; }
        .loc-label { color: #888; font-size: 0.7em; text-transform: uppercase; margin-right: 5px; font-weight: 600; }
        </style>
        """
        
        location_html = f"""
        <div class="sidebar-loc-panel">
            <div class="loc-row" title="Sistema Estelar">
                <span class="loc-icon">☀</span>
                <div>
                    <div class="loc-label">SISTEMA</div>
                    {loc_system}
                </div>
            </div>
            <div class="loc-row" title="Cuerpo Celeste">
                <span class="loc-icon">🪐</span>
                 <div>
                    <div class="loc-label">PLANETA</div>
                    {loc_planet}
                </div>
            </div>
            <div class="loc-row" title="Asentamiento">
                <span class="loc-icon">🏛</span>
                 <div>
                    <div class="loc-label">BASE</div>
                    {loc_base_name}
                </div>
            </div>
        </div>
        """
        st.markdown(location_css + location_html, unsafe_allow_html=True)

        # --- RELOJ GALÁCTICO ---
        clock_time = str(status.get('time', '00:00'))
        clock_tick = str(status.get('tick', 0))

        if status.get("is_frozen"):
            time_color = "#ff6b6b"
            status_icon = "❄️"
            status_text = "CONGELADO"
        elif status.get("is_lock_in"):
            time_color = "#f9ca24"
            status_icon = "⚠️"
            status_text = "BLOQUEO"
        else:
            time_color = "#56d59f"
            status_icon = "🟢"
            status_text = "NOMINAL"

        clock_css = f"""
        <style>
        .sidebar-clock-panel {{
            background: linear-gradient(135deg, rgba(20,25,35,0.9) 0%, rgba(30,40,55,0.9) 100%);
            border: 1px solid rgba(86, 213, 159, 0.3);
            border-radius: 10px;
            padding: 12px 15px;
            margin-bottom: 10px;
        }}
        .clock-time {{
            font-family: 'Orbitron', monospace;
            font-size: 1.8em;
            font-weight: 700;
            color: {time_color};
            text-align: center;
            letter-spacing: 3px;
        }}
        </style>
        <div class="sidebar-clock-panel">
            <div style="display: flex; justify-content: space-between; font-size: 0.7em; color: #888;">
                <span>Ciclo Galáctico</span>
                <span style="color: {time_color};">{status_icon} {status_text}</span>
            </div>
            <div class="clock-time">{clock_time}</div>
            <div style="text-align: center; font-size: 0.7em; color: #666;">TICK #{clock_tick}</div>
        </div>
        """
        st.markdown(clock_css, unsafe_allow_html=True)

        col_tick1, col_tick10 = st.columns(2)
        with col_tick1:
            if st.button("🔄 +1 Tick", use_container_width=True):
                debug_force_tick()
                st.rerun()
        
        with col_tick10:
            if st.button("⏩ +10 Ticks", use_container_width=True):
                with st.spinner("Avanzando tiempo..."):
                    for _ in range(10):
                        debug_force_tick()
                        time.sleep(0.1) # Pequeña pausa para evitar lock de DB
                st.rerun()

        st.divider()

        # --- SECCIÓN: IDENTIDAD ---
        st.header(f"{player.faccion_nombre}")
        if player.banner_url:
            st.image(player.banner_url, width="stretch")

        st.caption(f"Comandante {commander.nombre}")

        # --- SECCIÓN: NAVEGACIÓN ---
        st.divider()
        
        pages = ["Puente de Mando", "Mapa de la Galaxia", 
                 "Cuadrilla", "Centro de Reclutamiento", "Flota"]
        
        for p in pages:
            # Los botones siguen usando use_container_width (correcto para widgets)
            if st.button(p, use_container_width=True, type="primary" if st.session_state.current_page == p else "secondary"):
                st.session_state.current_page = p
                st.rerun()

        # --- NUEVA SECCIÓN: ACCESOS DIRECTOS COLONIAS ---
        st.divider()
        st.caption("📍 Accesos Directos: Colonias")
        
        my_planets = get_all_player_planets(player.id)
        if my_planets:
            for p_asset in my_planets:
                # Nombre del asentamiento o planeta
                p_name = p_asset.get("nombre_asentamiento") or "Colonia Sin Nombre"
                sys_name = p_asset.get("planets", {}).get("name", "Sistema Desc.")
                
                label = f"🏠 {p_name}"
                
                # Al hacer click, configuramos el estado y cambiamos la página
                if st.button(label, key=f"nav_col_{p_asset['id']}", use_container_width=True, help=f"Ir a {sys_name}"):
                    st.session_state.selected_planet_id = p_asset["planet_id"]
                    st.session_state.selected_system_id = p_asset["system_id"]
                    st.session_state.current_page = "Superficie"
                    st.rerun()
        else:
            st.info("Sin colonias establecidas.")

        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            logout_user(cookie_manager)
            st.rerun()

        # --- DEBUG ZONE ---
        st.write("")
        st.write("")
        st.markdown("---")
        st.caption("🛠️ DEBUG TOOLS")

        # 1. Toggle de Omnisciencia
        st.toggle("🔭 Omnisciencia (Debug)", key="debug_omniscience", help="Permite ver todos los sistemas y superficies sin exploración ni colonias.")

        if st.button("💰 +5000 Créditos", use_container_width=True):
            if add_player_credits(player.id, 5000):
                st.toast("✅ 5000 Créditos añadidos")
                st.rerun()
            else:
                st.error("Error al añadir créditos.")

        if st.button("🧪 Generar Candidato Elite (Lvl 10, Skills 99)", use_container_width=True, help="Genera un candidato de nivel 10 con todas las habilidades al 99."):
            try:
                generate_character_pool(
                    player_id=player.id, 
                    pool_size=1,
                    min_level=10,
                    max_level=10,
                    force_max_skills=True
                )
                st.toast("✅ Candidato Elite (Lvl 10, Skills 99) enviado al Centro de Reclutamiento.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error generando candidato de elite: {e}")

        if st.button("🗑️ ELIMINAR CUENTA", type="secondary", use_container_width=True, help="Elimina permanentemente el jugador y todos sus datos."):
            if delete_player_account(player.id):
                st.success("Cuenta eliminada.")
                logout_user(cookie_manager)
                st.rerun()
            else:
                st.error("Error al eliminar cuenta.")

        if st.button("🔄 REINICIAR CUENTA (Debug)", type="secondary", use_container_width=True, help="Reinicia el progreso del jugador manteniendo la cuenta (Soft Reset)."):
            if reset_player_progress(player.id):
                st.success("✅ Cuenta reiniciada exitosamente.")
                st.rerun()
            else:
                st.error("❌ Falló el reinicio de cuenta.")


def _render_war_room_page():
    """Página del Puente de Mando con CHAT y MERCADO."""
    player = get_player()
    if not player: return

    # --- Layout Principal: Operaciones (70%) | Monitor (30%) ---
    col_left, col_right = st.columns([0.7, 0.3], gap="medium")

    # --- COLUMNA IZQUIERDA: ÁREA OPERATIVA ---
    with col_left:
        # 1. Cabecera (Título)
        st.markdown("### 📟 Enlace Neuronal de Mando")
        
        # 2. Botonera de Acción (Toolbar arriba del chat)
        # Separamos en columnas para que no ocupen todo el ancho innecesariamente
        col_btn_market, col_btn_stock, col_spacer = st.columns([0.25, 0.25, 0.5])
        
        with col_btn_market:
            label_market = "📈 Mercado"
            if hasattr(st, "popover"):
                market_pop = st.popover(label_market, use_container_width=True, help="Mercado Galáctico")
                with market_pop:
                    _render_market_ui(player)
            else:
                with st.expander(label_market):
                    _render_market_ui(player)
        
        with col_btn_stock:
            label_stock = "💎 Stock"
            if hasattr(st, "popover"):
                stock_pop = st.popover(label_stock, use_container_width=True, help="Recursos de Lujo")
                is_popover = True
            else:
                stock_pop = st.expander(label_stock)
                is_popover = False
                
            with stock_pop:
                if is_popover: st.markdown("##### 💎 Recursos de Lujo")
                recursos_lujo = getattr(player, "recursos_lujo", {}) or {}
                has_items = False
                for cat, items in recursos_lujo.items():
                    if isinstance(items, dict):
                        active_items = {k: v for k, v in items.items() if v > 0}
                        if active_items:
                            has_items = True
                            st.caption(f"**{cat}**")
                            for nombre, cant in active_items.items():
                                st.write(f"• {nombre}: `{cant:,}`")
                            st.divider()
                if not has_items: st.info("No hay stock disponible.")

        # 3. Chat Principal (Debajo de la botonera)
        chat_box = st.container(height=500, border=True)
        logs = get_recent_logs(player.id, limit=30) 

        with chat_box:
            for log in reversed(logs):
                mensaje = log.get('evento_texto', '')
                if "[PLAYER]" in mensaje:
                    with st.chat_message("user"): st.write(mensaje.replace("[PLAYER] ", ""))
                else:
                    with st.chat_message("assistant"): 
                        clean_msg = mensaje.replace("🤖 [ASISTENTE] ", "").strip()
                        if "IMAGE_URL:" in clean_msg:
                            try:
                                parts = clean_msg.split("IMAGE_URL:", 1)
                                pre_text = parts[0].strip()
                                remainder = parts[1].strip()
                                if " " in remainder:
                                    url_part, post_text = remainder.split(" ", 1)
                                else:
                                    url_part = remainder
                                    post_text = ""
                                
                                if pre_text: st.markdown(pre_text)
                                if url_part: st.image(url_part.strip(), width="stretch")
                                if post_text: st.markdown(post_text)
                            except Exception:
                                st.write(clean_msg)
                        else:
                            st.markdown(clean_msg)

        # 4. Input de Chat con Status (UX MEJORADA)
        action = st.chat_input("Escriba sus órdenes...")
        if action:
            log_event(f"[PLAYER] {action}", player.id)
            
            # --- FEEDBACK VISUAL MEJORADO ---
            with st.status("🛰️ Enlace Neuronal Activo...", expanded=True) as status:
                st.write("Analizando telemetría y protocolos...")
                # Llamada principal al servicio
                response_data = resolve_player_action(action, player.id)
                status.update(label="✅ Órdenes procesadas", state="complete", expanded=False)
            
            # Actualizar estado MRG
            if response_data and "mrg_result" in response_data:
                st.session_state.last_mrg_result = response_data["mrg_result"]
            else:
                st.session_state.last_mrg_result = None
            
            # Pequeña pausa para permitir que el usuario vea el check verde antes de recargar
            time.sleep(0.5)
            st.rerun()

    # --- COLUMNA DERECHA: MONITOR MRG ---
    with col_right:
        st.caption("🎯 Monitor de Operaciones")
        if "last_mrg_result" in st.session_state and st.session_state.last_mrg_result:
            mrg_res = st.session_state.last_mrg_result
            if hasattr(mrg_res, 'roll') and mrg_res.roll is not None:
                render_full_mrg_resolution(mrg_res)
        else:
            # Espacio vacío o placeholder cuando no hay acción activa
            st.empty()


def _render_market_ui(player):
    """
    Renderiza la UI interna del popover de Mercado.
    """
    st.markdown("### Mercado Galáctico")
    
    # 1. Info de Capacidad
    used, total = get_market_limits(player.id)
    perc = used / total if total > 0 else 1.0
    st.progress(perc, text=f"Capacidad Logística: {used}/{total} envíos hoy")
    
    if used >= total:
        st.warning("⚠️ Capacidad saturada. Espera al próximo tick.")
    
    # 2. Obtener Precios actuales
    prices = calculate_market_prices(player.id)
    
    # 3. Tabs de Operación
    tab_buy, tab_sell = st.tabs(["Comprar", "Vender"])
    
    resources = ["materiales", "componentes", "celulas_energia", "datos", "influencia"]
    
    with tab_buy:
        res_buy = st.selectbox("Recurso a Comprar", resources, key="mkt_buy_res")
        price_info = prices.get(res_buy, {})
        unit_price = price_info.get("buy", 0)
        
        st.info(f"Precio Actual: **{unit_price} Cr** / unidad")
        
        amount_buy = st.number_input("Cantidad", min_value=1, value=100, step=10, key="mkt_buy_amount")
        total_cost = amount_buy * unit_price
        
        st.caption(f"Costo Total: `{total_cost:,} Cr`")
        
        if st.button("Confirmar Compra", type="primary", use_container_width=True, key="btn_buy", disabled=(used >= total)):
            success, msg = place_market_order(player.id, res_buy, amount_buy, is_buy=True)
            if success:
                st.success(msg)
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(msg)
                
    with tab_sell:
        res_sell = st.selectbox("Recurso a Vender", resources, key="mkt_sell_res")
        price_info = prices.get(res_sell, {})
        unit_price = price_info.get("sell", 0)
        
        st.info(f"Oferta de Compra: **{unit_price} Cr** / unidad")
        
        # Mostrar stock actual para referencia
        current_stock = getattr(player, res_sell, 0)
        st.caption(f"Tu Stock: {current_stock:,}")
        
        amount_sell = st.number_input("Cantidad", min_value=1, max_value=max(1, current_stock), value=min(100, max(1, current_stock)), step=10, key="mkt_sell_amount")
        total_gain = amount_sell * unit_price
        
        st.caption(f"Ganancia Estimada: `{total_gain:,} Cr`")
        
        if st.button("Confirmar Venta", type="primary", use_container_width=True, key="btn_sell", disabled=(used >= total)):
            success, msg = place_market_order(player.id, res_sell, amount_sell, is_buy=False)
            if success:
                st.success(msg)
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(msg)