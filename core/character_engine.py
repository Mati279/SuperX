# core/character_engine.py
from typing import Dict, Any, Tuple, List, Optional
import random
from core.constants import SKILL_POINTS_PER_LEVEL, AVAILABLE_FEATS, XP_TABLE
# Importamos la nueva función y quitamos la constante vieja
from core.rules import calculate_passive_knowledge_progress
from core.models import KnowledgeLevel
from data.character_repository import (
    get_known_characters_by_player, 
    set_character_knowledge_level,
    get_character_knowledge_level,
    update_character
)
from data.log_repository import log_event

# ... (Mantener resto del archivo: generate_random_character, etc.) ...

def process_passive_knowledge_updates(player_id: int, current_tick: int) -> List[str]:
    """
    Se ejecuta cada Tick. Revisa todos los personajes de la facción.
    Aplica la fórmula dinámica basada en Presencia.
    """
    updates_log = []
    
    from data.character_repository import get_all_player_characters
    characters = get_all_player_characters(player_id)
    
    for char in characters:
        if char.get("es_comandante", False):
            continue
            
        char_id = char["id"]
        current_level_enum = get_character_knowledge_level(char_id, player_id)
        
        if current_level_enum == KnowledgeLevel.FRIEND:
            continue

        # Obtener Ticks
        recruited_tick = char.get("recruited_at_tick", current_tick)
        ticks_in_service = max(0, current_tick - recruited_tick)
        
        # Obtener Atributos para la fórmula (Stats V2)
        stats = char.get("stats_json", {})
        attributes = {}
        # Búsqueda defensiva de atributos en estructura V2 o legacy
        if "capacidades" in stats and "atributos" in stats["capacidades"]:
            attributes = stats["capacidades"]["atributos"]
        elif "atributos" in stats:
            attributes = stats["atributos"]
        
        # Verificar reglas con atributos
        new_level_enum, progress_pct = calculate_passive_knowledge_progress(
            ticks_in_service, 
            current_level_enum, 
            attributes
        )
        
        # Actualización
        if new_level_enum != current_level_enum:
            success = set_character_knowledge_level(char_id, player_id, new_level_enum)
            if success:
                char_name = char.get("nombre", "Unidad")
                msg = ""
                if new_level_enum == KnowledgeLevel.KNOWN:
                    msg = f"ℹ️ Conocimiento actualizado: Has pasado suficiente tiempo con **{char_name}** para conocer sus capacidades."
                elif new_level_enum == KnowledgeLevel.FRIEND:
                    msg = f"🤝 Vínculo fortalecido: **{char_name}** ahora confía plenamente en ti."
                
                updates_log.append(msg)
                log_event(msg, player_id)
    
    return updates_log