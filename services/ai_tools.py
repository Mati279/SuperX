# services/ai_tools.py
from typing import Dict, Any, List, Optional
import json
from google.genai import types
from data.database import get_supabase
from data.world_repository import get_world_state, get_system_by_id, get_planets_by_system_id
from data.player_repository import get_player_by_id, get_player_finances
from core.galaxy_generator import get_galaxy
from core.models import KnowledgeLevel
from core.world_models import Planet, System
from data.log_repository import log_event
from core.mrg_engine import resolve_action, DIFFICULTY_NORMAL

# ... (Mantener imports y definiciones previas: TOOL_DECLARATIONS, etc.)

# --- NUEVAS HERRAMIENTAS DE CONOCIMIENTO ---

def investigate_character(character_name: str, player_id: int) -> str:
    """
    Intenta obtener información básica de un personaje (UNKNOWN -> KNOWN).
    Restricción: No funciona si el personaje ya es Conocido o Amigo.
    """
    from data.character_repository import get_all_player_characters, set_character_knowledge_level, get_character_knowledge_level
    
    # 1. Buscar personaje por nombre (aproximación para la IA)
    chars = get_all_player_characters(player_id)
    target = next((c for c in chars if c["nombre"].lower() == character_name.lower()), None)
    
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

# ... (Asegúrate de registrar investigate_character en TOOL_FUNCTIONS y TOOL_DECLARATIONS abajo) ...

# Mapa de funciones disponibles
TOOL_FUNCTIONS = {
    # ... (existentes) ...
    "investigate_character": investigate_character 
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
    # ... (existentes) ...
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
    )
]