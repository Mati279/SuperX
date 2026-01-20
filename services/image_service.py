# services/image_service.py
import time
import io
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image

from config.settings import GEMINI_API_KEY
from data.database import get_supabase
# --- NUEVO IMPORT ---
from data.log_repository import log_event

# Inicializar cliente de GenAI
client = genai.Client(api_key=GEMINI_API_KEY)

def generate_and_upload_tactical_image(prompt: str, player_id: int) -> Optional[str]:
    """
    Genera una imagen táctica usando Google Imagen 3 y la sube a Supabase Storage.
    
    Args:
        prompt: Descripción detallada para la generación de la imagen.
        player_id: ID del jugador para nombrar el archivo.
        
    Returns:
        str: URL pública de la imagen generada, o None si hubo un error.
    """
    try:
        # 1. Generación de Imagen (Google GenAI)
        response = client.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_medium_and_above",
                person_generation="allow_adult"
            )
        )

        if not response.generated_images:
            msg = f"❌ Error GenAI: No se generaron imágenes para el prompt: {prompt}"
            print(msg)
            log_event(msg, player_id) # Log visible en DB
            return None

        # Obtener los bytes de la imagen
        image_bytes = response.generated_images[0].image.image_bytes
        
        # 2. Procesamiento
        timestamp = int(time.time())
        file_name = f"img_{player_id}_{timestamp}.png"
        bucket_name = "tactical-images"

        # 3. Subida a Supabase Storage
        supabase = get_supabase()
        
        # Subir el archivo
        res = supabase.storage.from_(bucket_name).upload(
            path=file_name,
            file=image_bytes,
            file_options={"content-type": "image/png"}
        )

        # 4. Obtener URL Pública
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        
        return public_url

    except Exception as e:
        # Capturamos el error completo y lo enviamos al log del juego
        error_msg = f"❌ ERROR CRÍTICO IMAGEN: {str(e)}"
        print(error_msg)
        # Esto hará que el error aparezca en tus logs (o chat si tienes modo debug)
        log_event(error_msg, player_id) 
        return None