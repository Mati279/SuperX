# services/event_service.py
"""
Event Service - IA Omnisciente (Director del Universo)
Genera eventos narrativos globales que dan vida al universo en cada Tick.
"""

from google.genai import types
from data.database import ai_client
from data.log_repository import log_event
from config.app_constants import TEXT_MODEL_NAME

# --- PROMPT DEL DIRECTOR DEL UNIVERSO ---

EVENT_MASTER_PROMPT = """
Eres el DIRECTOR NARRATIVO de un universo de ciencia ficción (Space Opera).
Tu trabajo es generar un "Evento de Transmisión Galáctica" breve y atmosférico para el inicio de un nuevo ciclo temporal.

## OBJETIVO
Generar un texto corto (máximo 2 frases) que sirva como "Flavor Text" o noticia global.
No tiene impacto mecánico directo, pero da vida al universo.

## TEMAS POSIBLES
- Fenómenos estelares (tormentas de iones, erupciones solares).
- Rumores políticos o comerciales (rutas bloqueadas, huelgas, tratados).
- Avistamientos misteriosos en el vacío.
- Propaganda de facciones (sin especificar nombres de jugadores reales).

## FORMATO DE SALIDA
Solo el texto del evento. Tono periodístico, militar o científico según el evento.
"""

def generate_tick_event(tick_number: int) -> str:
    """
    Genera un evento narrativo aleatorio para el Tick actual usando la IA.
    Registra el evento en los logs globales.
    """
    if not ai_client:
        return "Sistemas de comunicación estática. Sin noticias."

    try:
        user_message = f"Genera un evento narrativo para el Ciclo Galáctico {tick_number}."

        response = ai_client.models.generate_content(
            model=TEXT_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=EVENT_MASTER_PROMPT,
                temperature=0.9, # Alta creatividad
                max_output_tokens=100,
                top_p=0.95
            ),
            contents=[user_message]
        )

        event_text = response.text.strip() if response.text else "Calma tensa en los sectores centrales."
        
        # Formatear para que destaque en el log
        formatted_event = f"📡 [TRANSMISIÓN GALÁCTICA] {event_text}"
        
        # Guardar en logs (sin player_id para que sea global/sistema)
        log_event(formatted_event)
        
        return event_text

    except Exception as e:
        error_msg = f"Error generando evento narrativo: {str(e)}"
        log_event(error_msg, is_error=True)
        return "Interferencias en la red de noticias."