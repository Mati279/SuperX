# data/faction_repository.py (Completo)
"""
Repositorio de datos para facciones y prestigio.

Este módulo maneja todas las operaciones de base de datos relacionadas con:
- CRUD de facciones
- Actualización de prestigio
- Gestión de hegemonía
- Historial de transferencias
- Procesamiento de hitos PvE
"""

from typing import Dict, Any, List, Optional
from data.database import get_supabase
from data.log_repository import log_event
# Modificación: Importación eliminada para evitar ciclo. Se mueve a process_pve_prestige_hit.
# from core.prestige_engine import calculate_pve_reward
from core.prestige_constants import LOG_PREFIX_PVE
import logging

logger = logging.getLogger(__name__)


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# ============================================================
# CONSULTAS DE FACCIONES
# ============================================================

def get_all_factions() -> List[Dict[str, Any]]:
    """
    Obtiene todas las facciones ordenadas por prestigio descendente.

    Returns:
        Lista de diccionarios con datos de facciones
    """
    try:
        response = _get_db().table("factions").select("*").order("prestigio", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo facciones: {e}", is_error=True)
        return []


def get_faction_by_id(faction_id: int) -> Optional[Dict[str, Any]]:
    """
    Obtiene una facción por su ID.

    Args:
        faction_id: ID de la facción

    Returns:
        Diccionario con datos de la facción o None si no existe
    """
    try:
        response = _get_db().table("factions").select("*").eq("id", faction_id).single().execute()
        return response.data
    except Exception:
        return None


def get_faction_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene una facción por su nombre.

    Args:
        name: Nombre de la facción

    Returns:
        Diccionario con datos de la facción o None si no existe
    """
    try:
        response = _get_db().table("factions").select("*").eq("nombre", name).single().execute()
        return response.data
    except Exception:
        return None


def get_prestige_map() -> Dict[int, float]:
    """
    Retorna un mapa de {faction_id: prestigio} para cálculos.

    Este formato es más eficiente para operaciones de cálculo masivo.

    Returns:
        Dict con el prestigio de cada facción por ID
    """
    factions = get_all_factions()
    return {f["id"]: float(f["prestigio"]) for f in factions}


# ============================================================
# ACTUALIZACIÓN DE PRESTIGIO
# ============================================================

def update_faction_prestige(faction_id: int, new_prestige: float) -> bool:
    """
    Actualiza el prestigio de una facción individual.

    Args:
        faction_id: ID de la facción
        new_prestige: Nuevo valor de prestigio (0-100)

    Returns:
        bool: True si la actualización fue exitosa
    """
    try:
        _get_db().table("factions").update({
            "prestigio": round(new_prestige, 2)
        }).eq("id", faction_id).execute()
        return True
    except Exception as e:
        log_event(f"Error actualizando prestigio facción {faction_id}: {e}", is_error=True)
        return False


def batch_update_prestige(prestige_map: Dict[int, float]) -> bool:
    """
    Actualiza el prestigio de múltiples facciones de forma atómica.

    Este método es más eficiente que actualizar una por una.

    Args:
        prestige_map: Dict de {faction_id: nuevo_prestigio}

    Returns:
        bool: True si todas las actualizaciones fueron exitosas

    Note:
        En caso de error parcial, se registra pero no se hace rollback.
        Supabase maneja transacciones por operación individual.
    """
    try:
        for faction_id, new_prestige in prestige_map.items():
            _get_db().table("factions").update({
                "prestigio": round(new_prestige, 2)
            }).eq("id", faction_id).execute()
        return True
    except Exception as e:
        log_event(f"Error en actualización batch de prestigio: {e}", is_error=True)
        return False


# ============================================================
# GESTIÓN DE HEGEMONÍA
# ============================================================

def set_hegemony_status(faction_id: int, is_hegemon: bool, victory_counter: int = 0) -> bool:
    """
    Establece el estado de hegemonía de una facción.

    Args:
        faction_id: ID de la facción
        is_hegemon: True si debe ser hegemón
        victory_counter: Número de ticks para victoria (default: 0)

    Returns:
        bool: True si la actualización fue exitosa

    Side Effects:
        - Registra evento en logs
        - Si is_hegemon=True, inicia contador de victoria
        - Si is_hegemon=False, resetea contador a 0
    """
    try:
        faction = get_faction_by_id(faction_id)
        if not faction:
            log_event(f"Error: Facción {faction_id} no encontrada", is_error=True)
            return False

        _get_db().table("factions").update({
            "es_hegemon": is_hegemon,
            "hegemonia_contador": victory_counter
        }).eq("id", faction_id).execute()

        # Logging según el cambio
        faction_name = faction.get("nombre", f"ID{faction_id}")
        if is_hegemon:
            log_event(f"👑 {faction_name} ASCIENDE A HEGEMÓN. Contador de victoria: {victory_counter} ticks")
        else:
            log_event(f"💔 {faction_name} PIERDE EL ESTATUS DE HEGEMÓN")

        return True
    except Exception as e:
        log_event(f"Error actualizando hegemonía: {e}", is_error=True)
        return False


def decrement_hegemony_counters() -> List[Dict[str, Any]]:
    """
    Decrementa contadores de victoria de todos los hegemones activos.

    Este método debe ejecutarse en cada tick.

    Returns:
        Lista de facciones que llegaron a 0 (¡victoria!)

    Process:
        1. Obtiene todos los hegemones activos
        2. Decrementa su contador
        3. Si llegan a 0, los marca como ganadores
        4. Registra eventos en logs

    Note:
        Los ganadores NO pierden su estatus de hegemón automáticamente.
        El game master debe decidir qué hacer (reiniciar partida, etc.)
    """
    winners = []
    try:
        # Obtener hegemones activos
        response = _get_db().table("factions").select("*").eq("es_hegemon", True).execute()

        for faction in response.data or []:
            current_counter = faction.get("hegemonia_contador", 0)
            new_counter = current_counter - 1

            if new_counter <= 0:
                # ¡VICTORIA!
                winners.append(faction)
                log_event(f"🏆🏆🏆 ¡¡¡{faction['nombre']} HA GANADO POR HEGEMONÍA TEMPORAL!!!")

                # Marcar en BD (mantener es_hegemon=True pero contador=0)
                _get_db().table("factions").update({
                    "hegemonia_contador": 0
                }).eq("id", faction["id"]).execute()

            else:
                # Decrementar normalmente
                _get_db().table("factions").update({
                    "hegemonia_contador": new_counter
                }).eq("id", faction["id"]).execute()

                # Log de progreso
                log_event(f"⏳ Hegemón {faction['nombre']}: {new_counter} ticks restantes para victoria.")

        return winners
    except Exception as e:
        log_event(f"Error decrementando contadores de hegemonía: {e}", is_error=True)
        return []


def get_current_hegemon() -> Optional[Dict[str, Any]]:
    """
    Obtiene el hegemón actual (si existe).

    Returns:
        Diccionario con datos del hegemón o None si no hay ninguno

    Note:
        Solo puede haber un hegemón a la vez.
        Si hay múltiples (error de BD), retorna el primero.
    """
    try:
        response = _get_db().table("factions").select("*").eq("es_hegemon", True).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None


# ============================================================
# HISTORIAL DE TRANSFERENCIAS
# ============================================================

def record_prestige_transfer(
    tick: int,
    attacker_faction_id: int,
    defender_faction_id: Optional[int],
    amount: float,
    idp_multiplier: float,
    reason: str
) -> bool:
    """
    Registra una transferencia de prestigio en el historial.

    Este registro permite auditoría, replay de partidas y análisis estadístico.

    Args:
        tick: Número de tick en el que ocurrió
        attacker_faction_id: ID de la facción atacante (o ganadora en PvE)
        defender_faction_id: ID de la facción defensora (o None para PvE/System)
        amount: Cantidad de prestigio transferida
        idp_multiplier: Multiplicador IDP aplicado
        reason: Descripción del evento (ej: "Victoria en combate naval")

    Returns:
        bool: True si el registro fue exitoso
    """
    try:
        data = {
            "tick": tick,
            "attacker_faction_id": attacker_faction_id,
            "defender_faction_id": defender_faction_id,
            "amount": round(amount, 2),
            "idp_multiplier": round(idp_multiplier, 2),
            "reason": reason
        }
        _get_db().table("prestige_history").insert(data).execute()
        return True
    except Exception as e:
        log_event(f"Error registrando transferencia de prestigio: {e}", is_error=True)
        return False


def get_prestige_history(
    limit: int = 50,
    faction_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Obtiene el historial de transferencias de prestigio.

    Args:
        limit: Número máximo de registros a retornar
        faction_id: Si se especifica, filtra por facción (como atacante o defensor)

    Returns:
        Lista de transferencias ordenadas por fecha (más recientes primero)
    """
    try:
        query = _get_db().table("prestige_history").select("*")

        if faction_id:
            # Filtrar por facción (como atacante O defensor)
            query = query.or_(f"attacker_faction_id.eq.{faction_id},defender_faction_id.eq.{faction_id}")

        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data if response.data else []
    except Exception as e:
        log_event(f"Error obteniendo historial de prestigio: {e}", is_error=True)
        return []


# ============================================================
# PROCESAMIENTO PVE
# ============================================================

def process_pve_prestige_hit(faction_id: int, tier_amount: float, reason: str) -> bool:
    """
    Procesa un hito de prestigio PvE (suma cero).

    Flujo:
    1. Obtiene el mapa actual de prestigio.
    2. Calcula el nuevo estado usando calculate_pve_reward (core).
    3. Aplica la actualización en batch a DB.
    4. Registra el evento en historial y logs.

    Args:
        faction_id: ID de la facción que logró el hito.
        tier_amount: Cantidad a ganar (PVE_TIER_I, etc.)
        reason: Motivo del hito (ej: "Descubrimiento de Ruinas").

    Returns:
        bool: True si el proceso fue exitoso.
    """
    try:
        # IMPORTACIÓN LOCAL PARA ROMPER CICLO
        from core.prestige_engine import calculate_pve_reward

        # 1. Obtener estado actual
        current_map = get_prestige_map()
        if not current_map:
            log_event(f"Error procesando PvE: No se pudo obtener mapa de prestigio", is_error=True)
            return False
            
        # 2. Calcular nuevo estado (redistribución y normalización)
        new_map = calculate_pve_reward(faction_id, tier_amount, current_map)
        
        # 3. Aplicar cambios
        if batch_update_prestige(new_map):
            # 4. Registrar evento
            # Nota: Usamos 0 como tick placeholder si no tenemos contexto de tick global aquí.
            # En una implementación completa, se debería inyectar el tick actual.
            record_prestige_transfer(
                tick=0,
                attacker_faction_id=faction_id,
                defender_faction_id=None,  # PvE: El "defensor" es el entorno/sistema
                amount=tier_amount,
                idp_multiplier=1.0,  # No aplica IDP en PvE
                reason=f"[PvE] {reason}"
            )
            
            log_event(f"{LOG_PREFIX_PVE} Hito PvE: Facción {faction_id} gana {tier_amount}% por '{reason}'")
            return True
            
        return False
        
    except Exception as e:
        log_event(f"Error crítico procesando hito PvE para facción {faction_id}: {e}", is_error=True)
        return False


# ============================================================
# ESTADÍSTICAS Y ANÁLISIS
# ============================================================

def get_faction_statistics(faction_id: int) -> Dict[str, Any]:
    """
    Obtiene estadísticas agregadas de una facción.

    Args:
        faction_id: ID de la facción

    Returns:
        Dict con estadísticas (total ganado, perdido, neto, etc.)
    """
    try:
        # Obtener transferencias donde fue atacante (ganancias)
        gains_response = _get_db().table("prestige_history").select("amount")\
            .eq("attacker_faction_id", faction_id).execute()
        total_gained = sum(float(t["amount"]) for t in (gains_response.data or []))

        # Obtener transferencias donde fue defensor (pérdidas)
        losses_response = _get_db().table("prestige_history").select("amount")\
            .eq("defender_faction_id", faction_id).execute()
        total_lost = sum(float(t["amount"]) for t in (losses_response.data or []))

        return {
            "total_gained": round(total_gained, 2),
            "total_lost": round(total_lost, 2),
            "net_change": round(total_gained - total_lost, 2),
            "transfers_as_attacker": len(gains_response.data or []),
            "transfers_as_defender": len(losses_response.data or [])
        }
    except Exception as e:
        log_event(f"Error calculando estadísticas facción {faction_id}: {e}", is_error=True)
        return {
            "total_gained": 0.0,
            "total_lost": 0.0,
            "net_change": 0.0,
            "transfers_as_attacker": 0,
            "transfers_as_defender": 0
        }