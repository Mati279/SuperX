# services/image_service.py
import time
from typing import Optional, Dict, Any
from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY
from data.database import get_supabase
from data.log_repository import log_event
from data.character_repository import get_character_by_id, update_character_stats

# Inicializar cliente de GenAI
client = genai.Client(api_key=GEMINI_API_KEY)

# CONSTANTE FORZADA SEGÚN REQUERIMIENTO
VISUAL_DNA_MODEL = 'gemini-2.0-flash-exp' 

def _generate_visual_dna(character_data: Dict[str, Any]) -> str:
    """
    Genera una descripción visual densa (ADN Visual) usando Gemini 2.0 Flash.
    Sigue estrictamente el formato de alta densidad con materiales y cibernética.
    """
    try:
        stats = character_data.get("stats_json", {})
        bio = stats.get("bio", {})
        taxonomia = stats.get("taxonomia", {})
        progresion = stats.get("progresion", {})
        
        # Construcción del Prompt de ADN Visual con el EJEMPLO DE ORO
        dna_prompt = f"""
        ACT AS: Senior Sci-Fi Concept Artist & Character Designer.
        TASK: Generate a "Visual DNA" profile for a character with EXTREME DETAIL.
        
        INPUT DATA:
        - Race: {taxonomia.get('raza', 'Human')}
        - Class: {progresion.get('clase', 'Operative')}
        - Gender: {bio.get('sexo', 'Unknown')}
        - Age: {bio.get('edad', 'Unknown')}
        - Base Bio: {bio.get('biografia_corta', 'N/A')}
        
        MANDATORY OUTPUT FORMAT & STYLE:
        You must match the information density of the example below. 
        - Specify materials (e.g., "distressed buffalo leather", "matte carbon-fiber", "brushed titanium").
        - Specify exact eye details (e.g., "recessed 32mm aperture", "icy cerulean blue").
        - Specify hair texture/products (e.g., "wet-look pomade", "razor-cut lines").
        - Specify cybernetics clearly (e.g., "external glowing vertebrae").
        
        *** GOLD STANDARD EXAMPLE (FOLLOW THIS STRUCTURE EXACTLY) ***
        Character DNA: Male, 30s, hyper-defined gaunt face, razor-sharp cheekbones, paper-thin lips with a cynical smirk. Eyes: Deep-set heterochromia; left eye icy cerulean blue, right eye is a recessed 32mm cybernetic aperture with rotating red titanium rings and a glowing crimson pupil. Hair: Silver-white slicked-back undercut, wet-look pomade, shaved sides with three horizontal razor-cut lines on the left temple. Body: Tall, lanky build, visible external titanium cybernetic spine vertebrae glowing through the back of the neck.
        Outfit: Distressed black buffalo leather tactical duster with an oversized Kevlar collar. Matte carbon-fiber chest plate with diagonal plasma burn scorch marks and "SXR-01" stenciled in faded white on the shoulder. Fingerless combat gloves.
        *************************************************************

        OUTPUT INSTRUCTION:
        Generate ONLY the text block following the format "Character DNA: ... Outfit: ...". Do not add introductions.
        """

        response = client.models.generate_content(
            model=VISUAL_DNA_MODEL, # Forzado a Gemini 2.0 Flash
            contents=dna_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500 # Aumentado para permitir la densidad requerida
            )
        )
        
        if response.text:
            return response.text.strip()
        return ""

    except Exception as e:
        print(f"⚠️ Error generando ADN Visual con {VISUAL_DNA_MODEL}: {e}")
        return ""

def generate_and_upload_tactical_image(
    prompt: str, 
    player_id: int, 
    character_id: Optional[int] = None
) -> Optional[str]:
    """
    Genera una imagen táctica. 
    Si se provee character_id, utiliza/genera el 'ADN Visual' para consistencia.
    """
    try:
        final_image_prompt = prompt
        
        # --- FASE 1: GESTIÓN DE ADN VISUAL (LAZY LOAD) ---
        if character_id:
            try:
                char_data = get_character_by_id(character_id)
                if char_data:
                    stats = char_data.get("stats_json", {})
                    bio = stats.get("bio", {})
                    
                    # Verificar si ya tiene ADN Visual
                    visual_dna = bio.get("apariencia_visual")
                    
                    # Si no tiene, o si es muy corto (versión vieja), regeneramos
                    if not visual_dna or len(visual_dna) < 50:
                        print(f"🧬 ADN Visual no encontrado/obsoleto para Char {character_id}. Generando con Gemini 2.5 Flash...")
                        log_event(f"Generando matriz visual de alta densidad para {char_data.get('nombre')}...", player_id)
                        
                        # Generar ADN
                        visual_dna = _generate_visual_dna(char_data)
                        
                        if visual_dna:
                            # Persistencia Inmediata
                            if "bio" not in stats: stats["bio"] = {}
                            stats["bio"]["apariencia_visual"] = visual_dna
                            
                            # Guardar en DB para futuras llamadas
                            update_character_stats(character_id, stats, player_id)
                            print(f"💾 ADN Visual guardado para Char {character_id}")

                    # Construcción del Prompt Compuesto para Imagen 3
                    if visual_dna:
                        final_image_prompt = (
                            f"{visual_dna}\n"
                            f"ACTION/CONTEXT: {prompt}\n"
                            f"STYLE: 8k resolution, cinematic lighting, photorealistic, volumetric fog, highly detailed textures."
                        )
            except Exception as e:
                print(f"⚠️ Warning: Fallo en lógica de personaje, usando prompt crudo. Error: {e}")
                final_image_prompt = prompt

        # --- FASE 2: GENERACIÓN DE IMAGEN ---
        
        # Debug Log: Inicio del proceso
        print(f"🎨 Iniciando generación de imagen (Imagen 3.0 Fast) para Player {player_id}...")
        
        response = client.models.generate_images(
            model='imagen-3.0-fast-generate-001',
            prompt=final_image_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="block_low_and_above",
                person_generation="allow_adult"
            )
        )

        if not response.generated_images:
            msg = f"❌ Error GenAI: No se generaron imágenes."
            print(msg)
            log_event(msg, player_id)
            return None

        # Obtener los bytes de la imagen
        image_bytes = response.generated_images[0].image.image_bytes
        
        # --- FASE 3: SUBIDA A STORAGE ---
        
        timestamp = int(time.time())
        char_suffix = f"_char{character_id}" if character_id else ""
        file_name = f"img_{player_id}{char_suffix}_{timestamp}.png"
        bucket_name = "tactical-images"

        supabase = get_supabase()
        
        # Subir el archivo
        res = supabase.storage.from_(bucket_name).upload(
            path=file_name,
            file=image_bytes,
            file_options={"content-type": "image/png"}
        )

        # Obtener URL Pública
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        
        print(f"✅ Imagen generada y subida exitosamente: {public_url}")
        
        return public_url

    except Exception as e:
        error_msg = f"❌ ERROR CRÍTICO IMAGEN: {str(e)}"
        print(error_msg)
        log_event(error_msg, player_id, is_error=True) 
        return None