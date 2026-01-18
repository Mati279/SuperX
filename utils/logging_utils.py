# utils/logging_utils.py
"""
Centralized logging utilities for SuperX.
Provides consistent error logging and decorators for safe operations.
"""
import logging
import traceback
from typing import Optional, Any, Callable
from functools import wraps

# Configure logger
logger = logging.getLogger("superx")


def log_exception(
    error: Exception,
    context: str,
    player_id: Optional[int] = None,
    extra_data: Optional[dict] = None
) -> None:
    """
    Log an exception with full context.

    Args:
        error: The caught exception
        context: Description of what operation failed
        player_id: Optional player ID for correlation
        extra_data: Additional debugging information
    """
    error_details = {
        "context": context,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "player_id": player_id,
        **(extra_data or {})
    }

    logger.error(f"[{context}] {type(error).__name__}: {error}", extra=error_details)

    # Also log to game logs if player_id provided
    if player_id:
        try:
            from data.log_repository import log_event
            log_event(f"Error en {context}: {str(error)[:100]}", player_id, is_error=True)
        except Exception:
            # Don't let logging failures cascade
            pass


def safe_db_operation(operation_name: str, default_return: Any = None):
    """
    Decorator for safe database operations with proper error handling.

    Usage:
        @safe_db_operation("get_player")
        def get_player_by_id(player_id: int) -> Optional[Dict]:
            ...

    Args:
        operation_name: Name of the operation for logging
        default_return: Value to return on error (default: None)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Try to extract player_id from args/kwargs
                player_id = kwargs.get('player_id')
                if player_id is None and args:
                    first_arg = args[0]
                    if isinstance(first_arg, int):
                        player_id = first_arg

                log_exception(e, operation_name, player_id)
                return default_return
        return wrapper
    return decorator


def safe_operation(operation_name: str, default_return: Any = None, reraise: bool = False):
    """
    General purpose decorator for safe operations.

    Args:
        operation_name: Name of the operation for logging
        default_return: Value to return on error
        reraise: If True, re-raises the exception after logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_exception(e, operation_name)
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator


def setup_logging(level: int = logging.INFO) -> None:
    """
    Setup logging configuration for the application.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger.setLevel(level)
