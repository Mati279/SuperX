# services/ai_tools.py
from typing import Dict, Any, List, Optional
import json
from google.genai import types
from data.database import get_supabase
from data.world_repository import get_world_state, get_system_by_id, get_planets_by_system_id
from data.player_repository import get_player_by_id, get_player_finances
from data.character_repository import get_all_player_characters, get_character_knowledge_level
from data.recruitment_repository import get_recruitment_candidates
from core.galaxy_generator import get_galaxy
from core.models import KnowledgeLevel
from core.world_models import Planet, System
from data.log_repository import log_event
from core.mrg_engine import resolve_action, DIFFICULTY_NORMAL
from core.character_engine import get_visible_biography, get_visible_skills, get_visible_feats

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

def get_filtered_roster(player_id: int, source: str = "all", name_filter: Optional[str] = None) -> str:
    """
    Obtiene una lista de personajes (facción o reclutas) filtrada por el Nivel de Conocimiento (Fog of War).
    Sanitiza biografías, habilidades y atributos antes de enviarlos a la IA.
    
    Args:
        player_id: ID del jugador.
        source: 'faction', 'recruitment' o 'all'.
        name_filter: Filtro opcional por nombre parcial.
    """
    raw_characters = []

    # 1. Obtener datos crudos según la fuente
    if source in ["faction", "all"]:
        faction_chars = get_all_player_characters(player_id)
        for c in faction_chars:
            c["_source_type"] = "Miembro de Facción"
        raw_characters.extend(faction_chars)

    if source in ["recruitment", "all"]:
        # Se asume que get_recruitment_candidates devuelve una lista similar de dicts
        recruit_chars = get_recruitment_candidates(player_id)
        for c in recruit_chars:
            c["_source_type"] = "Candidato a Reclutamiento"
        raw_characters.extend(recruit_chars)

    # 2. Filtrar por nombre si aplica
    if name_filter:
        name_filter = name_filter.lower()
        raw_characters = [c for c in raw_characters if name_filter in c.get("nombre", "").lower()]

    sanitized_roster = []

    # 3. Procesar y Sanitizar cada personaje
    for char in raw_characters:
        char_id = char.get("id")
        stats = char.get("stats_json", {})
        
        if not stats:
            stats = {} # Prevenir crash si es None

        # Obtener Nivel de Conocimiento
        # Incluso para reclutas, consultamos si ya existe un registro de conocimiento (ej. investigado previamente)
        # Si no existe registro en la DB, get_character_knowledge_level debería retornar UNKNOWN por defecto.
        knowledge_level = get_character_knowledge_level(char_id, player_id)

        # Sanitización usando core.character_engine
        visible_bio = get_visible_biography(stats, knowledge_level)
        
        # Extraer habilidades y feats del stats_json
        raw_skills = stats.get("habilidades", {})
        raw_feats = stats.get("feats", [])
        
        visible_skills = get_visible_skills(raw_skills, knowledge_level)
        visible_feats = get_visible_feats(raw_feats, knowledge_level)

        # Lógica de Atributos (Core stats)
        # Si es UNKNOWN, ocultamos los números exactos
        visible_attributes = " [DATOS CLASIFICADOS] Requiere nivel CONOCIDO."
        if knowledge_level in (KnowledgeLevel.KNOWN, KnowledgeLevel.FRIEND):
            visible_attributes = stats.get("capacidades", {}).get("atributos", stats.get("atributos", {}))

        # Construir objeto seguro para la IA
        safe_char = {
            "id": char_id,
            "nombre": char.get("nombre", "Desconocido"),
            "rol_clase": char.get("clase_social", "Desconocido"), # O campo 'rol' si existe
            "estado": char.get("_source_type"),
            "nivel_conocimiento": knowledge_level.value,
            "biografia_visible": visible_bio,
            "habilidades_visibles": visible_skills,
            "rasgos_visibles": visible_feats,
            "atributos": visible_attributes
        }
        
        sanitized_roster.append(safe_char)

    if not sanitized_roster:
        return json.dumps({"info": "No se encontraron personajes con los criterios dados."})

    return json.dumps(sanitized_roster, ensure_ascii=False, indent=2)

# Mapa de funciones disponibles
TOOL_FUNCTIONS = {
    # ... (existentes) ...
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
    # ... (existentes: scan_galaxy, get_system_info, etc. asumiendo que estaban antes) ...
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
        description="Consulta la base de datos de personal y reclutas. Úsala para responder preguntas sobre quién es quién, sus habilidades y biografías. Respeta automáticamente el nivel de conocimiento (Fog of War) ocultando datos sensibles si es necesario.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador."),
                "source": types.Schema(type=types.Type.STRING, description="Fuente de datos: 'faction' (actuales), 'recruitment' (candidatos) o 'all'."),
                "name_filter": types.Schema(type=types.Type.STRING, description="Opcional: Nombre parcial para filtrar la búsqueda.")
            },
            required=["player_id"]
        )
    )
]