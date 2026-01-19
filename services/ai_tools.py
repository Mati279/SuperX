# services/ai_tools.py
from typing import Dict, Any, List, Optional
import json
from google.genai import types

from data.database import get_supabase
from data.world_repository import get_world_state, get_system_by_id, get_planets_by_system_id
from data.player_repository import get_player_by_id, get_player_finances
from data.character_repository import (
    get_all_player_characters, 
    get_character_knowledge_level, 
    set_character_knowledge_level
)
from data.recruitment_repository import get_recruitment_candidates
from data.log_repository import log_event

from core.galaxy_generator import get_galaxy
from core.models import KnowledgeLevel
from core.world_models import Planet, System
from core.mrg_engine import resolve_action, DIFFICULTY_NORMAL
from core.character_engine import get_visible_biography, get_visible_skills, get_visible_feats

# --- HERRAMIENTAS DE CONOCIMIENTO Y GESTIÓN ---

def investigate_character(character_name: str, player_id: int) -> str:
    """
    Intenta obtener información básica de un personaje (UNKNOWN -> KNOWN).
    Restricción: No funciona si el personaje ya es Conocido o Amigo.
    """
    # 1. Buscar personaje por nombre (aproximación para la IA)
    # Buscamos en facción
    chars = get_all_player_characters(player_id)
    target = next((c for c in chars if c["nombre"].lower() == character_name.lower()), None)
    
    # Si no está en facción, buscamos en reclutamiento
    if not target:
        candidates = get_recruitment_candidates(player_id)
        target = next((c for c in candidates if c["nombre"].lower() == character_name.lower()), None)
    
    if not target:
        return f"Error: No se encontró al personaje '{character_name}' en tu facción o lista de reclutamiento."

    # 2. Verificar estado actual (REGLA ESTRICTA)
    current_level = get_character_knowledge_level(target["id"], player_id)
    
    if current_level != KnowledgeLevel.UNKNOWN:
        # Aquí bloqueamos la investigación si ya es KNOWN o FRIEND
        return f"Investigación innecesaria. Ya posees el archivo completo de {target['nombre']} (Nivel: {current_level.value}). El nivel de confianza superior solo se gana con el tiempo."

    # 3. Resolver acción (MRG Engine)
    # Dificultad NORMAL para obtener antecedentes básicos
    result = resolve_action(merit_points=60, difficulty=DIFFICULTY_NORMAL)
    
    narrative = f"Investigación sobre {target['nombre']}: {result.result_type.name} (Margen: {result.margin})\n"
    
    # 4. Aplicar consecuencias
    if result.success:
        # Solo sube a KNOWN
        set_character_knowledge_level(target["id"], player_id, KnowledgeLevel.KNOWN)
        narrative += f"¡ÉXITO! Antecedentes recuperados. Nivel de conocimiento actualizado a CONOCIDO.\n"
        narrative += "Ahora puedes ver sus atributos ocultos y rasgos de personalidad."
        log_event(f"Investigación exitosa: {target['nombre']}", player_id)
    else:
        narrative += "Fallo. La encriptación de sus antecedentes es demasiado fuerte o no existen registros digitales."
    
    return narrative

def get_filtered_roster(player_id: int, source: str = "all") -> str:
    """
    Obtiene el expediente completo y visible de los personajes.
    Incluye atributos y habilidades (o las Top 5 si es desconocido).
    """
    sources = []
    
    # 1. Recopilar personajes según fuente
    if source in ["faction", "all"]:
        faction_chars = get_all_player_characters(player_id)
        for c in faction_chars:
            c["_source_type"] = "Facción"
        sources.extend(faction_chars)

    if source in ["recruitment", "all"]:
        recruit_chars = get_recruitment_candidates(player_id)
        for c in recruit_chars:
            c["_source_type"] = "Candidato"
        sources.extend(recruit_chars)

    if not sources:
        return json.dumps({"info": "No se encontraron personajes disponibles."})

    output_roster = []

    # 2. Procesar visibilidad (Fog of War)
    for char in sources:
        char_id = char.get("id")
        stats = char.get("stats_json", {}) or {}
        
        # Determinar Nivel de Conocimiento
        knowledge_level = get_character_knowledge_level(char_id, player_id)

        # Regla 1: Atributos SIEMPRE visibles (UI Parity)
        # Manejo de estructura v2 vs legacy
        if "capacidades" in stats and "atributos" in stats["capacidades"]:
            attributes = stats["capacidades"]["atributos"]
        else:
            attributes = stats.get("atributos", {})

        # Regla 2: Habilidades
        # get_visible_skills manejará top_n=5 para UNKNOWN
        raw_skills = stats.get("habilidades", {})
        visible_skills = get_visible_skills(raw_skills, knowledge_level, top_n=5)

        # Regla 3: Biografía
        visible_bio = get_visible_biography(stats, knowledge_level)

        # Regla 4: Feats
        visible_feats = get_visible_feats(stats.get("feats", []), knowledge_level)

        # Construir objeto JSON
        entry = {
            "id": char_id,
            "nombre": char.get("nombre", "Desconocido"),
            "rango": char.get("rango", "Sin Rango"),
            "clase": char.get("clase_social", "Desconocido"),
            "raza": char.get("raza", "Humano"),
            "nivel_personaje": stats.get("progresion", {}).get("nivel", 1),
            "estado": char.get("_source_type"),
            "nivel_conocimiento": knowledge_level.value,
            "atributos": attributes,
            "habilidades_visibles": visible_skills,
            "feats_visibles": visible_feats,
            "biografia_publica": visible_bio
        }
        output_roster.append(entry)

    return json.dumps(output_roster, ensure_ascii=False, indent=2)

# Mapa de funciones disponibles
TOOL_FUNCTIONS = {
    "investigate_character": investigate_character,
    "get_filtered_roster": get_filtered_roster
}

def execute_tool(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Ejecuta una herramienta por nombre con los argumentos dados."""
    if tool_name not in TOOL_FUNCTIONS:
        return f"Error: Herramienta '{tool_name}' no encontrada."
    try:
        return TOOL_FUNCTIONS[tool_name](**tool_args)
    except Exception as e:
        return f"Error ejecutando {tool_name}: {str(e)}"

# Declaraciones para Gemini (Function Calling)
TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="investigate_character",
        description="Investiga los antecedentes de un personaje para revelar sus stats ocultos. Solo funciona en personajes Desconocidos.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "character_name": types.Schema(type=types.Type.STRING, description="Nombre exacto del personaje a investigar"),
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador que realiza la acción")
            },
            required=["character_name", "player_id"]
        )
    ),
    types.FunctionDeclaration(
        name="get_filtered_roster",
        description="Obtiene el expediente completo y visible de los personajes. Incluye atributos y habilidades (o las Top 5 si es desconocido). Úsala para comparar competencias (ej: mejor piloto, médico) analizando las 'habilidades_visibles' y 'atributos' en conjunto.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador"),
                "source": types.Schema(type=types.Type.STRING, description="Fuente: 'faction', 'recruitment' o 'all'")
            },
            required=["player_id"]
        )
    )
]