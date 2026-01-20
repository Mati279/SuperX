# services/image_service.py
import time
import re
from typing import Optional
from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY
from config.app_constants import TEXT_MODEL_NAME
from data.database import get_supabase
from data.log_repository import log_event
from data.character_repository import get_character_by_id, update_character
from core.models import CommanderData

client = genai.Client(api_key=GEMINI_API_KEY)

def _generate_visual_dna(character: CommanderData) -> str:
    """
    Genera el ADN Visual (descripción física densa) usando Gemini Text Model.
    Se usa solo cuando el personaje no tiene uno predefinido.
    """
    try:
        # Construimos un contexto rico para que la IA deduzca la apariencia
        prompt = f"""
        ACTÚA COMO: Director de Arte de Ciencia Ficción.
        TAREA: Crear una "Ficha de Diseño de Personaje" (Visual DNA) ultra-detallada para generación de imágenes.
        
        DATOS DEL PERSONAJE:
        - Nombre: {character.nombre}
        - Raza: {character.sheet.taxonomia.raza}
        - Clase: {character.sheet.progresion.clase}
        - Bio Superficial: {character.sheet.bio.bio_superficial}
        
        INSTRUCCIONES DE SALIDA:
        Escribe un párrafo denso (80-100 palabras) describiendo SOLO su apariencia física inmutable.
        Usa un estilo descriptivo crudo, separado por comas o puntos. Enfócate en materiales, texturas, iluminación y rasgos anatómicos.
        NO incluyas personalidad. NO incluyas acciones. SOLO FÍSICO Y EQUIPAMIENTO BASE.
        
        EJEMPLO DE ESTILO REQUERIDO:
        "Male, 30s, hyper-defined gaunt face, razor-sharp cheekbones. Eyes: Deep-set heterochromia; left eye icy cerulean, right eye recessed 32mm cybernetic aperture with rotating red rings. Hair: Silver-white slicked-back undercut, wet-look pomade. Body: Tall, lanky build, visible external titanium vertebrae. Outfit: Distressed black buffalo leather duster, matte carbon-fiber chest plate with scorch marks."
        """

        response = client.models.generate_content(
            model=TEXT_MODEL_NAME,
            contents=prompt
        )
        
        if response.text:
            return response.text.strip()
        return f"{character.sheet.taxonomia.raza} con armadura táctica estándar, rostro oculto."
        
    except Exception as e:
        print(f"❌ Error generando ADN Visual: {e}")
        return f"{character.sheet.taxonomia.raza} {character.sheet.progresion.clase} con equipamiento de combate estándar."

def generate_and_upload_tactical_image(
    prompt_situation: str, 
    player_id: int, 
    character_id: int
) -> Optional[str]:
    """
    Flujo Inteligente:
    1. Carga Personaje.
    2. ¿Tiene ADN Visual? NO -> Genéralo y GUÁRDALO en DB.
    3. Genera Imagen combinando (ADN Visual + Situación).
    4. Sube con nombre semántico.
    """
    try:
        # 1. Obtener datos del personaje
        char_data_dict = get_character_by_id(character_id)
        if not char_data_dict:
            log_event(f"❌ Personaje {character_id} no encontrado para imagen.", player_id)
            return None
            
        # Convertimos a objeto CommanderData
        character = CommanderData.from_dict(char_data_dict)
        
        # --- FIX: Capturar la instancia del schema en una variable local ---
        # Esto evita que 'character.sheet' cree una nueva copia cada vez que se llama.
        char_sheet = character.sheet 
        
        # 2. Verificar / Generar ADN Visual (Lazy Load)
        visual_dna = char_sheet.bio.apariencia_visual
        
        # Si no existe o es muy corto, generamos uno nuevo
        if not visual_dna or len(visual_dna) < 10:
            log_event(f"🎨 Creando ADN Visual permanente para {character.nombre}...", player_id)
            
            # A) Generar texto con IA
            visual_dna = _generate_visual_dna(character)
            
            # B) Actualizar la variable LOCAL (char_sheet)
            char_sheet.bio.apariencia_visual = visual_dna
            
            # C) PERSISTENCIA: Serializar la variable local modificada
            updated_stats = char_sheet.model_dump() 
            
            # Guardar en SQL
            update_character(character.id, {"stats_json": updated_stats}) 
            
            log_event(f"💾 ADN Visual guardado para {character.nombre}.", player_id)

        # 3. Construcción del Prompt de Imagen
        final_prompt = f"""
        [SUBJECT VISUAL DNA]: {visual_dna}
        [CURRENT ACTION/CONTEXT]: {prompt_situation}
        [ART STYLE]: Cinematic sci-fi character portrait, hyper-realistic, 8k resolution, volumetric lighting, atmospheric, detailed textures.
        """
        
        print(f"🎨 Generando imagen para: {character.nombre}")

        # 4. Generación de Imagen
        # NOTA: Ajusta el modelo a 'imagen-3.0-generate-001' o 'imagen-4.0-fast-generate-001' según disponibilidad.
        response = client.models.generate_images(
            model='imagen-3.0-generate-001', 
            prompt=final_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                # IMPORTANTE: Relajamos un poco el filtro para permitir descripciones de "combate" o "cicatrices"
                safety_filter_level="block_medium_and_above", 
                person_generation="allow_adult"
            )
        )

        if not response.generated_images:
            log_event(f"⚠️ Imagen bloqueada por filtros o error de API para {character.nombre}", player_id)
            return None

        image_bytes = response.generated_images[0].image.image_bytes
        
        # 5. Nombre Semántico
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', character.nombre.replace(' ', '_'))
        safe_action = re.sub(r'[^a-zA-Z0-9]', '', prompt_situation[:15].replace(' ', '_'))
        timestamp = int(time.time())
        
        file_name = f"{safe_name}_{safe_action}_{timestamp}.png"
        bucket_name = "tactical-images"

        # 6. Subida a Supabase
        supabase = get_supabase()
        supabase.storage.from_(bucket_name).upload(
            path=file_name,
            file=image_bytes,
            file_options={"content-type": "image/png"}
        )

        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        return public_url

    except Exception as e:
        error_msg = f"❌ Error Critical Image Service: {str(e)}"
        print(error_msg)
        log_event(error_msg, player_id)
        return None