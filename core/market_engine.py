# core/market_engine.py (Completo)
"""
Motor de Mercado y Logística - V5.3
Gestiona precios dinámicos, validación de órdenes y procesamiento diferido.
Spec 4.2: Influencia del Prestigio y Broker Dinámico.
Spec 5.3: Integración de Recursos de Lujo (Solo Venta) y Ajuste Logístico.
"""

from typing import Dict, List, Tuple, Any
import math

from core.models import MarketOrder, MarketOrderStatus, PlayerData
from core.time_engine import get_current_tick
from core.prestige_engine import get_player_prestige_level
from core.world_constants import ECONOMY_RATES, LUXURY_PRICES

from data.market_repository import (
    create_market_order, 
    get_orders_by_tick, 
    get_pending_orders_for_player,
    mark_orders_as_completed
)
from data.player_repository import get_player_resources, update_player_resources
from data.planet_repository import get_all_player_planets
from data.log_repository import log_event

# Precios Base V4.2 (Actualizados)
BASE_PRICES = {
    "materiales": 20,
    "componentes": 30,
    "celulas_energia": 30,
    "influencia": 50,
    "datos": 20
}

MARKET_FEE_PERCENT = 0.20 # Markup base del 20%
PRESTIGE_BASELINE = 14    # Nivel de prestigio neutral (14%)

def calculate_market_prices(player_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Calcula precios de compra y venta personalizados según el prestigio.
    Retorna: { "recurso": { "buy": int/None, "sell": int } }
    
    Lógica V4.2 + V5.3:
    - Base Markup: 20%
    - Ajuste: +/- 1% de markup por cada 1% de prestigio de diferencia con Baseline (14).
    - Lujo: Solo Venta disponible.
    """
    prestige = get_player_prestige_level(player_id)
    
    # Delta: Positivo (Prestigio > 14) mejora precios.
    # Negativo (Prestigio < 14) empeora precios.
    prestige_delta = prestige - PRESTIGE_BASELINE
    
    # Factor de ajuste: 1% (0.01) por punto de delta
    adjustment = prestige_delta / 100.0
    
    # Cálculo de tasas dinámicas
    # Compra: Base 20% - Ajuste. Si tienes mucho prestigio, el fee baja.
    # Si tienes poco prestigio (negativo delta), el fee sube.
    buy_fee = max(0.01, MARKET_FEE_PERCENT - adjustment)
    
    # Venta: Base 20% - Ajuste.
    # El markdown reduce el precio de venta. Queremos que sea PEQUEÑO si hay prestigio.
    # Si tienes mucho prestigio, el markdown baja (vendes más caro).
    sell_markdown = max(0.01, MARKET_FEE_PERCENT - adjustment)
    
    prices = {}
    
    # 1. Recursos Base (Compra y Venta)
    for resource, base_price in BASE_PRICES.items():
        # Precio Compra = Base * (1 + fee)
        buy_price = math.ceil(base_price * (1 + buy_fee))
        
        # Precio Venta = Base * (1 - markdown)
        sell_price = math.floor(base_price * (1 - sell_markdown))
        
        # Seguridad mínima
        if sell_price < 1: sell_price = 1
        
        prices[resource] = {
            "buy": buy_price,
            "sell": sell_price,
            "base": base_price,
            "fee_rate": buy_fee, # Debug info
            "type": "basic"
        }

    # 2. Recursos de Lujo (Solo Venta)
    for resource, base_price in LUXURY_PRICES.items():
        # Precio Venta = Base * (1 - markdown)
        sell_price = math.floor(base_price * (1 - sell_markdown))
        
        if sell_price < 1: sell_price = 1
        
        prices[resource] = {
            "buy": None, # No se pueden comprar
            "sell": sell_price,
            "base": base_price,
            "type": "luxury"
        }
        
    return prices

def get_market_limits(player_id: int) -> Tuple[int, int]:
    """
    Calcula límites de operación por tick.
    Returns: (operaciones_usadas, operaciones_totales)
    V5.3: Ajuste de capacidad a 2 por planeta.
    """
    current_tick = get_current_tick()
    
    # Capacidad: 2 por cada planeta activo
    planets = get_all_player_planets(player_id)
    # Consideramos 'activo' si tiene población > 0, o simplemente si existe el asset
    active_planets = len([p for p in planets if p.get("poblacion", 0) > 0])
    # Mínimo 1 planeta (el inicial siempre cuenta aunque esté en 0 pop temporalmente)
    active_planets = max(1, active_planets)
    
    total_capacity = active_planets * 2
    
    # Usados este tick
    orders_this_tick = get_orders_by_tick(player_id, current_tick)
    used_capacity = len(orders_this_tick)
    
    return used_capacity, total_capacity

def place_market_order(player_id: int, resource: str, amount: int, is_buy: bool) -> Tuple[bool, str]:
    """
    Coloca una orden en el mercado.
    Amount siempre positivo desde UI. Internamente:
    - Compra: amount > 0
    - Venta: amount < 0 (se guarda negativo en DB)
    """
    if amount <= 0:
        return False, "La cantidad debe ser mayor a 0."
        
    # Validación V5.3: El recurso debe existir en Base o Lujo
    if resource not in BASE_PRICES and resource not in LUXURY_PRICES:
        return False, "Recurso no válido."

    # Validación V5.3: No se permite comprar Lujo
    if is_buy and resource in LUXURY_PRICES:
        return False, "Los recursos de lujo no pueden ser comprados en el mercado."

    # 1. Validar Límites Logísticos
    used, total = get_market_limits(player_id)
    if used >= total:
        return False, f"Capacidad logística saturada ({used}/{total}). Espera al siguiente tick."

    # 2. Calcular Precio
    prices = calculate_market_prices(player_id)
    price_info = prices.get(resource)
    
    if is_buy:
        unit_price = price_info["buy"]
        total_cost = unit_price * amount
        db_amount = amount # Positivo
    else:
        unit_price = price_info["sell"]
        total_value = unit_price * amount
        db_amount = -amount # Negativo para venta
        
    # 3. Validar Recursos y Cobrar (Instantáneo)
    player_resources = get_player_resources(player_id)
    
    updates = {}
    
    if is_buy:
        # Compra: Necesita Créditos
        current_credits = player_resources.get("creditos", 0)
        if current_credits < total_cost:
            return False, f"Créditos insuficientes. Requieres {total_cost} Cr."
        updates["creditos"] = current_credits - total_cost
    else:
        # Venta: Diferenciar entre Base y Lujo
        if resource in LUXURY_PRICES:
            # Lógica para Recursos de Lujo (Nested JSON)
            luxe_storage = player_resources.get("recursos_lujo") or {}
            
            found_category = None
            current_stock = 0
            
            # Buscar en qué categoría está el recurso
            for category, items in luxe_storage.items():
                if resource in items:
                    current_stock = items[resource]
                    found_category = category
                    break
            
            if current_stock < amount:
                return False, f"Stock insuficiente de {resource} ({current_stock})."
            
            # Actualizar stock en el JSON
            if found_category:
                luxe_storage[found_category][resource] = current_stock - amount
                # Limpieza: si queda en 0, lo quitamos para limpiar el JSON
                if luxe_storage[found_category][resource] <= 0:
                    del luxe_storage[found_category][resource]
                
                updates["recursos_lujo"] = luxe_storage
            else:
                return False, f"Error: No se encuentra el recurso {resource} en inventario."

        else:
            # Lógica para Recursos Base (Columnas)
            current_res = player_resources.get(resource, 0)
            if current_res < amount:
                return False, f"Stock insuficiente de {resource}."
            updates[resource] = current_res - amount
    
    # 4. Persistir Orden
    try:
        current_tick = get_current_tick()
        
        # Cobrar primero (Atomicidad optimista)
        if not update_player_resources(player_id, updates):
            return False, "Error al actualizar recursos del jugador."
            
        order = MarketOrder(
            id=0, # DB Generado
            player_id=player_id,
            resource_type=resource,
            amount=db_amount,
            price_per_unit=unit_price,
            status=MarketOrderStatus.PENDING,
            created_at_tick=current_tick
        )
        
        created_order = create_market_order(order)
        
        if created_order:
            action_str = "Compra" if is_buy else "Venta"
            log_event(f"📈 Mercado: Orden {action_str} {amount} {resource} @ {unit_price} Cr/u (Entrega: Tick {current_tick + 1})", player_id)
            return True, "Orden registrada. Entrega programada para el próximo ciclo."
        else:
            return False, "Error de base de datos al crear orden."

    except Exception as e:
        return False, f"Error inesperado: {e}"

def process_pending_market_orders(player_id: int) -> int:
    """
    Procesa órdenes pendientes del tick anterior (Logística diferida).
    Se llama desde economy_engine.
    Returns: Cantidad de órdenes procesadas.
    """
    current_tick = get_current_tick()
    pending = get_pending_orders_for_player(player_id)
    
    processed_count = 0
    completed_ids = []
    
    # Recursos a acreditar (Inicializamos con base, pero agregamos dinámicos si es necesario)
    resource_delta = {k: 0 for k in BASE_PRICES.keys()}
    resource_delta["creditos"] = 0
    
    for order in pending:
        # Solo procesar si fue creada ANTES del tick actual (Entrega tick + 1)
        if order.created_at_tick < current_tick:
            
            if order.amount > 0:
                # Era COMPRA: Ya pagó créditos, recibe recurso
                # Asegurar que la key existe en el delta
                if order.resource_type not in resource_delta:
                    resource_delta[order.resource_type] = 0
                resource_delta[order.resource_type] += order.amount
            else:
                # Era VENTA: Ya entregó recurso, recibe créditos
                # amount es negativo, value es abs(amount) * price
                credit_gain = abs(order.amount) * order.price_per_unit
                resource_delta["creditos"] += credit_gain
                
            completed_ids.append(order.id)
            processed_count += 1
            
    if completed_ids:
        # 1. Actualizar Inventario Jugador
        current_res = get_player_resources(player_id)
        final_updates = {}
        
        for key, delta in resource_delta.items():
            if delta != 0:
                final_updates[key] = current_res.get(key, 0) + delta
        
        if final_updates:
            update_player_resources(player_id, final_updates)
            
        # 2. Marcar órdenes como completadas
        mark_orders_as_completed(completed_ids, current_tick)
        
        # Log resumen
        if processed_count > 0:
            log_event(f"🚚 Logística de Mercado: {processed_count} órdenes entregadas.", player_id)
            
    return processed_count