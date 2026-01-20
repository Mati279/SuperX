# services/image_service.py
import time
import io
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image

from config.settings import GEMINI_API_KEY
from data.database import get_supabase

# Inicializar cliente de GenAI
# Se asume que GEMINI_API_KEY tiene permisos para usar modelos de Imagen
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
        # Usamos el modelo 'imagen-3.0-generate-001' según especificación
        response = client.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9", # Formato cinemático para la UI
                safety_filter_level="block_medium_and_above",
                person_generation="allow_adult"
            )
        )

        if not response.generated_images:
            print(f"❌ Error GenAI: No se generaron imágenes para el prompt: {prompt}")
            return None

        # Obtener los bytes de la imagen
        image_bytes = response.generated_images[0].image.image_bytes
        
        # 2. Procesamiento (Validación opcional con PIL)
        # Convertimos a objeto Image para asegurar formato, aunque Imagen suele devolver PNG/JPEG
        # En este caso, pasamos los bytes directamente a Supabase para eficiencia, 
        # pero usamos el timestamp para unicidad.
        timestamp = int(time.time())
        file_name = f"img_{player_id}_{timestamp}.png"
        bucket_name = "tactical-images"

        # 3. Subida a Supabase Storage
        supabase = get_supabase()
        
        # Subir el archivo (file_options content-type es importante)
        res = supabase.storage.from_(bucket_name).upload(
            path=file_name,
            file=image_bytes,
            file_options={"content-type": "image/png"}
        )

        # 4. Obtener URL Pública
        # El método get_public_url devuelve la URL completa
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        
        return public_url

    except Exception as e:
        print(f"❌ Error en generate_and_upload_tactical_image: {str(e)}")
        # Aquí podrías agregar un log_event si importaras log_repository, 
        # pero mantenemos las dependencias limpias para este servicio base.
        return None