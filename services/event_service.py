# services/event_service.py
"""
Event Service - IA Omnisciente (Director del Universo)
Genera eventos narrativos globales y procesa eventos de personajes.
"""

from typing import List
from google.genai import types
from data.database import ai_client
from data.log_repository import log_event
from data.character_repository import get_all_player_characters, update_character_stats
from config.app_constants import TEXT_MODEL_NAME
from core.character_engine import update_character_access_level, BIO_ACCESS_DEEP

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

def process_character_development_tick(player_id: int) -> List[str]:
    """
    Avanza el tiempo interno de los personajes del jugador:
    - Incrementa ticks de servicio (antigüedad).
    - Desbloquea niveles de biografía (Conocido/Profundo).
    
    Returns:
        Lista de logs generados por desbloqueos.
    """
    chars = get_all_player_characters(player_id)
    logs_generated = []

    for char in chars:
        stats = char.get('stats_json', {})
        bio = stats.get('bio', {})
        
        # Incrementar Ticks
        if "ticks_reclutado" in bio:
            bio["ticks_reclutado"] += 1
        else:
            bio["ticks_reclutado"] = 1
            
        # Verificar desbloqueo
        updated, new_level = update_character_access_level(stats)
        
        if updated:
            # Guardar en BD
            update_character_stats(char['id'], stats)
            
            # Notificar
            char_name = char.get('nombre', 'Operativo')
            level_name = "PROFUNDO" if new_level == BIO_ACCESS_DEEP else "CONFIDENCIAL"
            msg = f"📂 INTELIGENCIA: Nuevos datos biográficos desbloqueados para {char_name}. Nivel de Acceso: {level_name}."
            log_event(msg, player_id)
            logs_generated.append(msg)
        else:
            # Guardar solo el incremento de ticks
            update_character_stats(char['id'], stats)
            
    return logs_generated