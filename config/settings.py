# config/settings.py
import os
import streamlit as st
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def get_secret(key: str) -> str | None:
    """
    Obtiene un secreto de forma segura, buscando primero en variables de entorno
    y luego en los secretos de Streamlit.

    Args:
        key: La clave del secreto a obtener.

    Returns:
        El valor del secreto o None si no se encuentra.
    """
    value = os.getenv(key)
    if value:
        return value
    if hasattr(st, 'secrets') and key in st.secrets:
        return st.secrets[key]
    return None

# --- Claves de APIs y Conexión ---
SUPABASE_URL: str | None = get_secret("SUPABASE_URL")
SUPABASE_KEY: str | None = get_secret("SUPABASE_KEY")
GEMINI_API_KEY: str | None = get_secret("GEMINI_API_KEY")

# Validar que las credenciales críticas existan
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Error Crítico: Las credenciales de Supabase (URL y KEY) no fueron encontradas.")
