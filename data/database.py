# data/database.py
from supabase import create_client, Client
from google import genai
import logging
# CORRECCIÓN: Importamos el módulo como objeto para evitar KeyError en la búsqueda de símbolos
import config.settings as settings

# Extraer variables del módulo importado
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
GEMINI_API_KEY = settings.GEMINI_API_KEY

# --- Inicialización de Clientes ---

# Cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente de Gemini AI
ai_client: genai.Client | None = None
if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
        print("✅ Cliente de Google Gemini conectado exitosamente.")
    except Exception as e:
        print(f"⚠️ Error al inicializar el cliente de Gemini: {e}")
else:
    print("📢 Advertencia: No se encontró la GEMINI_API_KEY. Las funciones de IA estarán desactivadas.")