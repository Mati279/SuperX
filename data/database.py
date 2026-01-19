# data/database.py
import logging
import threading
from typing import Optional, Any
from dataclasses import dataclass

# Configurar logger
logger = logging.getLogger(__name__)

@dataclass
class ConnectionStatus:
    supabase_connected: bool = False
    ai_connected: bool = False
    supabase_error: Optional[str] = None
    ai_error: Optional[str] = None

class ServiceContainer:
    _instance: Optional['ServiceContainer'] = None
    _lock = threading.Lock() # Thread-safe Singleton

    def __new__(cls) -> 'ServiceContainer':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._supabase_client: Any = None
        self._ai_client: Any = None
        self._status = ConnectionStatus()

        self._init_supabase()
        self._init_gemini()
        self._initialized = True

    def _init_supabase(self) -> None:
        try:
            from supabase import create_client
            from config.settings import SUPABASE_URL, SUPABASE_KEY
            if not SUPABASE_URL or not SUPABASE_KEY:
                self._status.supabase_error = "Faltan credenciales Supabase"
                return
            self._supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            self._status.supabase_connected = True
            logger.info("Supabase OK")
        except Exception as e:
            self._status.supabase_error = str(e)
            logger.error(f"Supabase Fail: {e}")

    def _init_gemini(self) -> None:
        try:
            import google.genai as genai
            from config.settings import GEMINI_API_KEY
            if not GEMINI_API_KEY:
                self._status.ai_error = "Falta GEMINI_API_KEY"
                return
            self._ai_client = genai.Client(api_key=GEMINI_API_KEY)
            self._status.ai_connected = True
            logger.info("Gemini AI OK")
        except Exception as e:
            self._status.ai_error = str(e)
            logger.error(f"Gemini Fail: {e}")

    @property
    def supabase(self) -> Any:
        if not self._supabase_client:
            raise ConnectionError(f"DB No disponible: {self._status.supabase_error}")
        return self._supabase_client

    @property
    def ai(self) -> Any:
        if not self._ai_client:
            raise ConnectionError(f"IA No disponible: {self._status.ai_error}")
        return self._ai_client

    def is_ai_available(self) -> bool:
        return self._status.ai_connected

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

def get_service_container() -> ServiceContainer:
    return ServiceContainer()

def get_supabase() -> Any:
    return get_service_container().supabase