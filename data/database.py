# data/database.py
"""
Gestor de Conexiones y Contenedor de Servicios.
Implementa el patrón Singleton con inyección de dependencias.
Facilita testing mediante mocks y garantiza graceful degradation.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass

# Configurar logger nativo
logger = logging.getLogger(__name__)


# --- ESTADO DE CONEXIÓN ---

@dataclass
class ConnectionStatus:
    """Estado de las conexiones a servicios externos."""
    supabase_connected: bool = False
    ai_connected: bool = False
    supabase_error: Optional[str] = None
    ai_error: Optional[str] = None


# --- CONTENEDOR DE SERVICIOS (Singleton) ---

class ServiceContainer:
    """
    Contenedor central de servicios.
    Gestiona las instancias de Supabase y Gemini de forma thread-safe.
    Permite inyectar mocks para testing.
    """

    _instance: Optional['ServiceContainer'] = None
    _initialized: bool = False

    def __new__(cls) -> 'ServiceContainer':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Solo inicializar una vez
        if ServiceContainer._initialized:
            return

        self._supabase_client: Any = None
        self._ai_client: Any = None
        self._status = ConnectionStatus()

        # Inicializar conexiones
        self._init_supabase()
        self._init_gemini()

        ServiceContainer._initialized = True

    def _init_supabase(self) -> None:
        """Inicializa el cliente de Supabase con graceful degradation."""
        try:
            from supabase import create_client
            from config.settings import SUPABASE_URL, SUPABASE_KEY

            if not SUPABASE_URL or not SUPABASE_KEY:
                self._status.supabase_error = "Credenciales de Supabase no configuradas"
                logger.warning(self._status.supabase_error)
                return

            self._supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self._status.supabase_connected = True
            logger.info("Conexión a Supabase establecida correctamente")

        except ImportError as e:
            self._status.supabase_error = f"Librería supabase no instalada: {e}"
            logger.error(self._status.supabase_error)
        except Exception as e:
            self._status.supabase_error = f"Error conectando a Supabase: {e}"
            logger.critical(self._status.supabase_error)

    def _init_gemini(self) -> None:
        """Inicializa el cliente de Gemini AI con graceful degradation."""
        try:
            import google.genai as genai
            from config.settings import GEMINI_API_KEY

            if not GEMINI_API_KEY:
                self._status.ai_error = "GEMINI_API_KEY no configurada"
                logger.warning(self._status.ai_error)
                return

            self._ai_client = genai.Client(api_key=GEMINI_API_KEY)
            self._status.ai_connected = True
            logger.info("Conexión a Gemini AI establecida correctamente")

        except ImportError as e:
            self._status.ai_error = f"Librería google-genai no instalada: {e}"
            logger.error(self._status.ai_error)
        except Exception as e:
            self._status.ai_error = f"Error inicializando Gemini AI: {e}"
            logger.error(self._status.ai_error)

    # --- PROPIEDADES DE ACCESO ---

    @property
    def supabase(self) -> Any:
        """Retorna el cliente de Supabase o lanza excepción si no está disponible."""
        if self._supabase_client is None:
            raise ConnectionError(
                f"Base de datos no disponible: {self._status.supabase_error}"
            )
        return self._supabase_client

    @property
    def ai(self) -> Any:
        """Retorna el cliente de IA o lanza excepción si no está disponible."""
        if self._ai_client is None:
            raise ConnectionError(
                f"Servicio de IA no disponible: {self._status.ai_error}"
            )
        return self._ai_client

    @property
    def status(self) -> ConnectionStatus:
        """Retorna el estado de las conexiones."""
        return self._status

    def is_supabase_available(self) -> bool:
        """Verifica si Supabase está disponible."""
        return self._status.supabase_connected

    def is_ai_available(self) -> bool:
        """Verifica si el servicio de IA está disponible."""
        return self._status.ai_connected

    # --- MÉTODOS PARA TESTING ---

    def inject_supabase(self, client: Any) -> None:
        """Inyecta un cliente de Supabase (útil para mocks en tests)."""
        self._supabase_client = client
        self._status.supabase_connected = True
        self._status.supabase_error = None

    def inject_ai(self, client: Any) -> None:
        """Inyecta un cliente de IA (útil para mocks en tests)."""
        self._ai_client = client
        self._status.ai_connected = True
        self._status.ai_error = None

    @classmethod
    def reset(cls) -> None:
        """Resetea el singleton (solo para testing)."""
        cls._instance = None
        cls._initialized = False


# --- FUNCIONES DE ACCESO GLOBAL (Compatibilidad hacia atrás) ---

def get_service_container() -> ServiceContainer:
    """Obtiene la instancia del contenedor de servicios."""
    return ServiceContainer()


def get_supabase() -> Any:
    """Obtiene el cliente de Supabase (compatibilidad hacia atrás)."""
    return get_service_container().supabase


def get_ai_client() -> Any:
    """Obtiene el cliente de IA (compatibilidad hacia atrás)."""
    return get_service_container().ai


# --- VARIABLES GLOBALES (Solo para compatibilidad durante migración) ---
# DEPRECADO: Usar get_supabase() y get_ai_client() en su lugar

_container = get_service_container()

# Estas variables se mantienen para no romper imports existentes
# pero serán eliminadas en futuras versiones
supabase = _container._supabase_client if _container.is_supabase_available() else None
ai_client = _container._ai_client if _container.is_ai_available() else None

if supabase is None and not _container.is_supabase_available():
    logger.critical(f"ADVERTENCIA: Supabase no disponible - {_container.status.supabase_error}")
