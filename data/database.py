# data/database.py
from supabase import create_client, Client
from google import genai
import logging
import config.settings as settings

# Configuración de logging nativo para este módulo (evita ciclos con log_repository)
logger = logging.getLogger(__name__)

# Extraer variables del módulo importado
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
GEMINI_API_KEY = settings.GEMINI_API_KEY

# --- Inicialización de Clientes ---

# Cliente de Supabase
# Si esto falla, la app debe crashear porque es crítica.
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.critical(f"FATAL: No se pudo conectar a Supabase. {e}")
    raise e

# Cliente de Gemini AI
ai_client: genai.Client | None = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("✅ Cliente de Google Gemini conectado exitosamente.")
    except Exception as e:
        logger.warning(f"⚠️ Error al inicializar el cliente de Gemini: {e}")
else:
    logger.warning("📢 Advertencia: No se encontró la GEMINI_API_KEY. Las funciones de IA estarán desactivadas.")