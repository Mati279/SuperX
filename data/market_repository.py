# data/market_repository.py
"""
Repositorio de Mercado.
Gestiona la persistencia de órdenes de compra/venta.
"""

from typing import List, Dict, Optional, Any
from .database import get_supabase
from .log_repository import log_event
from core.models import MarketOrder, MarketOrderStatus

def _get_db():
    return get_supabase()

def create_market_order(order: MarketOrder) -> Optional[MarketOrder]:
    """
    Crea una nueva orden de mercado en la base de datos.
    """
    try:
        # Preparamos el dict excluyendo campos que la DB genera (id, processed_at)
        data = {
            "player_id": order.player_id,
            "resource_type": order.resource_type,
            "amount": order.amount,
            "price_per_unit": order.price_per_unit,
            "status": order.status.value,
            "created_at_tick": order.created_at_tick
        }
        
        response = _get_db().table("market_orders").insert(data).execute()
        
        if response.data:
            # Retornamos el objeto con el ID generado
            return MarketOrder.from_dict(response.data[0])
        return None
    except Exception as e:
        log_event(f"Error creando orden de mercado: {e}", order.player_id, is_error=True)
        return None

def get_pending_orders_for_player(player_id: int) -> List[MarketOrder]:
    """
    Obtiene todas las órdenes pendientes de un jugador.
    """
    try:
        response = _get_db().table("market_orders")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("status", MarketOrderStatus.PENDING.value)\
            .execute()
            
        return [MarketOrder.from_dict(o) for o in response.data] if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo órdenes pendientes: {e}", player_id, is_error=True)
        return []

def get_orders_by_tick(player_id: int, tick: int) -> List[MarketOrder]:
    """
    Obtiene órdenes creadas en un tick específico (útil para validación de límites).
    """
    try:
        response = _get_db().table("market_orders")\
            .select("*")\
            .eq("player_id", player_id)\
            .eq("created_at_tick", tick)\
            .execute()
        return [MarketOrder.from_dict(o) for o in response.data] if response.data else []
    except Exception as e:
        log_event(f"Error checking tick orders: {e}", player_id, is_error=True)
        return []

def mark_orders_as_completed(order_ids: List[int], processed_tick: int) -> bool:
    """
    Actualiza el estado de múltiples órdenes a COMPLETED.
    """
    if not order_ids:
        return True
        
    try:
        _get_db().table("market_orders")\
            .update({
                "status": MarketOrderStatus.COMPLETED.value,
                "processed_at_tick": processed_tick
            })\
            .in_("id", order_ids)\
            .execute()
        return True
    except Exception as e:
        # Log genérico, no asociado a un player específico aquí fácilmente sin iterar
        print(f"Error marking orders completed: {e}") 
        return False