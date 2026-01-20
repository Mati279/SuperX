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

# --- NUEVO IMPORT ---
from services.image_service import generate_and_upload_tactical_image

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

        # Preparar acceso a estructura V2 (Capacidades)
        # Esto simplifica la lógica de fallback
        capacidades = stats.get("capacidades", {})

        # Regla 1: Atributos SIEMPRE visibles (UI Parity)
        if capacidades and "atributos" in capacidades:
            attributes = capacidades["atributos"]
        else:
            attributes = stats.get("atributos", {})

        # Regla 2: Habilidades
        # get_visible_skills manejará top_n=5 para UNKNOWN
        # FIX V2: Buscar primero en capacidades['habilidades']
        if capacidades and "habilidades" in capacidades:
            raw_skills = capacidades["habilidades"]
        else:
            # Fallback legacy V1
            raw_skills = stats.get("habilidades", {})
            
        visible_skills = get_visible_skills(raw_skills, knowledge_level, top_n=5)

        # Regla 3: Biografía
        visible_bio = get_visible_biography(stats, knowledge_level)

        # Regla 4: Feats
        # FIX V2: Buscar primero en capacidades['feats']
        if capacidades and "feats" in capacidades:
            raw_feats = capacidades["feats"]
        else:
            # Fallback legacy V1
            raw_feats = stats.get("feats", [])

        visible_feats = get_visible_feats(raw_feats, knowledge_level)

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

def execute_sql_query_tool(query: str, player_id: int) -> str:
    """
    Ejecuta una consulta SQL de solo lectura (SELECT).
    Wrapper para la función RPC 'execute_sql_query'.
    """
    try:
        # Validación simple de seguridad/intención
        if not query.strip().upper().startswith("SELECT") and not query.strip().upper().startswith("WITH"):
            return "Error: Esta herramienta es solo para consultas de análisis (SELECT). No intente modificar datos."

        log_event(f"🤖 AI SQL Query: {query}", player_id)
        
        # Llamada RPC
        response = get_supabase().rpc('execute_sql_query', {'query': query}).execute()
        
        # Retornar datos como string JSON formateado
        return json.dumps(response.data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error SQL: {str(e)} (Verifique la sintaxis y los nombres de tablas/columnas)"

def get_table_schema(table_name: str) -> str:
    """
    Obtiene la estructura de columnas de una tabla.
    Wrapper para la función RPC 'get_table_schema_info'.
    """
    try:
        response = get_supabase().rpc('get_table_schema_info', {'table_name_param': table_name}).execute()
        return json.dumps(response.data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error Schema: {str(e)}"

# --- NUEVA FUNCIÓN WRAPPER PARA IMÁGENES ---
def generate_tactical_visual(description: str, player_id: int) -> str:
    """
    Wrapper para generar una imagen táctica. Devuelve la URL formateada para que la UI la detecte.
    """
    try:
        log_event(f"🎨 Generando visual: {description[:50]}...", player_id)
        url = generate_and_upload_tactical_image(description, player_id)
        if url:
            # Este prefijo es clave para que main_game_page.py lo detecte
            return f"IMAGE_URL: {url}"
        return "Error: El sistema de visualización no pudo renderizar la imagen solicitada."
    except Exception as e:
        return f"Error Generación Imagen: {str(e)}"

# Mapa de funciones disponibles
TOOL_FUNCTIONS = {
    "investigate_character": investigate_character,
    "get_filtered_roster": get_filtered_roster,
    "execute_sql_query": execute_sql_query_tool,
    "get_table_schema": get_table_schema,
    "generate_tactical_visual": generate_tactical_visual # Registro de la nueva función
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
        description="""OBTIENE EXPEDIENTES COMPLETOS (PROCESADOS).
Usa esto SOLO para análisis cualitativo detallado de pocos individuos (< 5).
Devuelve 'habilidades_visibles' (Skills) y 'atributos' (Stats Base).
ADVERTENCIA: No usar para búsquedas masivas o comparaciones numéricas de toda la base de datos (Usar execute_sql_query).""",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador"),
                "source": types.Schema(type=types.Type.STRING, description="Fuente: 'faction', 'recruitment' o 'all'")
            },
            required=["player_id"]
        )
    ),
    types.FunctionDeclaration(
        name="execute_sql_query",
        description="""EJECUTA CONSULTAS SQL (Solo Lectura/SELECT).
CRÍTICO para comparaciones numéricas, búsquedas complejas o filtrado en grupos grandes.
Estructura JSONB: stats_json->'capacidades'->'habilidades' (diccionario key:value) o 'atributos'.
Ejemplo: SELECT nombre FROM characters WHERE (stats_json->'capacidades'->'atributos'->>'intelecto')::int > 10""",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="Consulta SQL SELECT válida (PostgreSQL)"),
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador para logging")
            },
            required=["query", "player_id"]
        )
    ),
    types.FunctionDeclaration(
        name="get_table_schema",
        description="Obtiene el nombre y tipo de columnas de una tabla específica de la base de datos.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "table_name": types.Schema(type=types.Type.STRING, description="Nombre de la tabla (ej: 'characters')")
            },
            required=["table_name"]
        )
    ),
    # --- NUEVA DECLARACIÓN ---
    types.FunctionDeclaration(
        name="generate_tactical_visual",
        description="""Genera una imagen visual táctica (planeta, nave, entidad, paisaje) basada en una descripción detallada.
Úsala cuando el usuario pida 'mostrar', 'visualizar' o 'generar una imagen' de algo en el juego.
NO la uses para interfaces, textos o datos abstractos.""",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "description": types.Schema(type=types.Type.STRING, description="Descripción visual rica y detallada (prompt) para la IA de imagen."),
                "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador")
            },
            required=["description", "player_id"]
        )
    )
]