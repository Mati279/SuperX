# data/database.py
import os
import logging
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY

# Configurar logger nativo para evitar dependencias circulares con data.log_repository
logger = logging.getLogger(__name__)

ai_client = None

# Intentar configurar Google Generative AI (Gemini)
try:
    import google.genai as genai
    from config.settings import GEMINI_API_KEY
    
    if GEMINI_API_KEY:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY no encontrada en la configuración.")
except ImportError:
    logger.error("Librería google-genai no instalada.")
except Exception as e:
    logger.error(f"Error inicializando Gemini AI: {e}")

# Inicializar Supabase
supabase: Client = None

try:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Faltan credenciales de Supabase (URL o KEY).")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Prueba de conexión silenciosa
    # supabase.table("app_config").select("count", count="exact").execute()

except Exception as e:
    logger.critical(f"❌ ERROR CRÍTICO DE CONEXIÓN A BASE DE DATOS: {e}")
    # NO llamamos a log_event aquí porque causaría ImportError circular
    raise e