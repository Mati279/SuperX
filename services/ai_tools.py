# services/ai_tools.py
"""
Herramientas de IA para el Asistente Táctico.
Define las funciones que Gemini puede invocar mediante function calling.
"""

import json
from typing import Dict, Any, Callable
from google.genai import types

from data.database import get_supabase
from data.player_repository import get_player_finances
# IMPORTACIONES NUEVAS PARA UBICACIÓN
from data.world_repository import get_commander_location_display
from data.character_repository import get_commander_by_player_id


def _get_db():
    """Obtiene el cliente de Supabase de forma segura."""
    return get_supabase()


# --- DECLARACIÓN DE HERRAMIENTAS ---

TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_player_status",
                description="Obtiene el estado financiero, recursos y UBICACIÓN actual de la base principal.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del jugador."
                        )
                    },
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="scan_system_data",
                description="Busca información astronómica de un sistema estelar por su nombre o ID.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "system_identifier": types.Schema(
                            type=types.Type.STRING,
                            description="Nombre o ID del sistema."
                        )
                    },
                    required=["system_identifier"]
                )
            ),
            types.FunctionDeclaration(
                name="check_route_safety",
                description="Calcula la seguridad de una ruta entre dos sistemas basándose en starlanes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "origin_sys_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del sistema origen"
                        ),
                        "target_sys_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del sistema destino"
                        )
                    },
                    required=["origin_sys_id", "target_sys_id"]
                )
            ),
            types.FunctionDeclaration(
                name="recruit_character",
                description="Recluta un nuevo personaje aleatorio para el jugador. La IA genera nombre, apellido y biografía. El personaje aparece en la base tras 1 tick.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del jugador que recluta."
                        ),
                        "min_level": types.Schema(
                            type=types.Type.INTEGER,
                            description="Nivel mínimo del recluta (default: 1)."
                        ),
                        "max_level": types.Schema(
                            type=types.Type.INTEGER,
                            description="Nivel máximo del recluta (default: 1)."
                        )
                    },
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="get_recruitment_candidates",
                description="Genera un pool de candidatos para reclutamiento SIN guardarlos. El jugador puede elegir uno para reclutar.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del jugador."
                        ),
                        "pool_size": types.Schema(
                            type=types.Type.INTEGER,
                            description="Cantidad de candidatos a generar (default: 3)."
                        )
                    },
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="list_player_characters",
                description="Lista todos los personajes del jugador con su estado, ubicación y clase.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del jugador."
                        )
                    },
                    required=["player_id"]
                )
            )
        ]
    )
]


# --- IMPLEMENTACIÓN DE HERRAMIENTAS ---

def get_player_status(player_id: int) -> str:
    """
    Obtiene el estado financiero Y LA UBICACIÓN del jugador.
    """
    try:
        # 1. Finanzas
        finances = get_player_finances(player_id)
        
        # 2. Ubicación (Requiere buscar al comandante primero)
        commander = get_commander_by_player_id(player_id)
        location_info = {"system": "Desconocido", "planet": "---", "base": "Sin Base"}
        
        if commander:
             # Usamos la nueva lógica centralizada en world_repository
             location_info = get_commander_location_display(commander['id'])
        
        status_report = {
            "recursos": finances,
            "ubicacion_base_principal": location_info
        }
        
        return json.dumps(status_report, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error obteniendo estado: {e}"})


def scan_system_data(system_identifier: str) -> str:
    """Escanea datos de un sistema estelar."""
    try:
        db = _get_db()
        query = db.table("systems").select("*")

        if str(system_identifier).isdigit():
            query = query.eq("id", int(system_identifier))
        else:
            query = query.ilike("name", f"%{system_identifier}%")

        sys_res = query.execute()

        if not sys_res.data:
            return json.dumps({
                "error": f"Sistema '{system_identifier}' no encontrado en la base de datos."
            })

        system = sys_res.data[0]
        planets_res = db.table("planets")\
            .select("*")\
            .eq("system_id", system['id'])\
            .execute()

        planets = planets_res.data if planets_res.data else []

        scan_report = {
            "sistema": {
                "id": system['id'],
                "nombre": system['name'],
                "clase_estelar": system.get('star_class', 'Desconocida'),
                "posicion": f"{system['x']:.1f}, {system['y']:.1f}",
            },
            "cuerpos_celestes": [
                {
                    "nombre": p['name'],
                    "tipo": p.get('biome'),
                    "recursos": p.get('resources')
                }
                for p in planets
            ]
        }

        return json.dumps(scan_report, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Error en escaneo: {e}"})


def check_route_safety(origin_sys_id: int, target_sys_id: int) -> str:
    """Verifica la seguridad de una ruta."""
    try:
        db = _get_db()
        res = db.table("starlanes")\
            .select("*")\
            .or_(
                f"and(system_a_id.eq.{origin_sys_id},system_b_id.eq.{target_sys_id}),"
                f"and(system_a_id.eq.{target_sys_id},system_b_id.eq.{origin_sys_id})"
            )\
            .execute()

        if res.data:
            return json.dumps({
                "ruta_existente": True,
                "estado": res.data[0].get('estado', 'Estable'),
                "distancia": res.data[0].get('distancia', 'Desconocida')
            })

        return json.dumps({
            "ruta_existente": False,
            "mensaje": "No existe ruta directa entre los sistemas especificados."
        })

    except Exception as e:
        return json.dumps({"error": f"Error verificando ruta: {e}"})


# --- FUNCIONES DE RECLUTAMIENTO ---

def recruit_character(player_id: int, min_level: int = 1, max_level: int = 1) -> str:
    """
    Recluta un nuevo personaje aleatorio usando IA.
    """
    try:
        from data.character_repository import recruit_random_character_with_ai

        result = recruit_random_character_with_ai(
            player_id=player_id,
            min_level=min_level,
            max_level=max_level
        )

        if result:
            stats = result.get("stats_json", {})
            bio = stats.get("bio", {})
            taxonomia = stats.get("taxonomia", {})
            progresion = stats.get("progresion", {})

            return json.dumps({
                "exito": True,
                "personaje": {
                    "id": result.get("id"),
                    "nombre_completo": result.get("nombre"),
                    "raza": taxonomia.get("raza"),
                    "clase": progresion.get("clase"),
                    "nivel": progresion.get("nivel"),
                    "edad": bio.get("edad"),
                    "sexo": bio.get("sexo"),
                    "biografia": bio.get("biografia_corta"),
                    "ubicacion": result.get("ubicacion")
                },
                "mensaje": f"Reclutado exitosamente: {result.get('nombre')}"
            }, ensure_ascii=False)

        return json.dumps({
            "exito": False,
            "error": "No se pudo completar el reclutamiento."
        })

    except Exception as e:
        return json.dumps({"exito": False, "error": f"Error en reclutamiento: {e}"})


def get_recruitment_candidates(player_id: int, pool_size: int = 3) -> str:
    """
    Genera candidatos para reclutamiento sin guardarlos.
    """
    try:
        from data.character_repository import get_recruitment_candidates as get_candidates

        candidates = get_candidates(
            player_id=player_id,
            pool_size=pool_size
        )

        if candidates:
            candidates_summary = []
            for i, c in enumerate(candidates, 1):
                stats = c.get("stats_json", {})
                bio = stats.get("bio", {})
                taxonomia = stats.get("taxonomia", {})
                progresion = stats.get("progresion", {})
                capacidades = stats.get("capacidades", {})
                atributos = capacidades.get("atributos", {})

                # Obtener atributos más altos
                top_attrs = sorted(atributos.items(), key=lambda x: x[1], reverse=True)[:2]
                destaca_en = ", ".join([f"{a[0].capitalize()}: {a[1]}" for a in top_attrs])

                candidates_summary.append({
                    "numero": i,
                    "nombre": c.get("nombre"),
                    "raza": taxonomia.get("raza"),
                    "clase": progresion.get("clase"),
                    "nivel": progresion.get("nivel"),
                    "edad": bio.get("edad"),
                    "sexo": bio.get("sexo"),
                    "destaca_en": destaca_en,
                    "biografia": bio.get("biografia_corta")
                })

            return json.dumps({
                "candidatos": candidates_summary,
                "instruccion": "El jugador debe elegir uno de estos candidatos para reclutar."
            }, ensure_ascii=False)

        return json.dumps({
            "error": "No se pudieron generar candidatos."
        })

    except Exception as e:
        return json.dumps({"error": f"Error generando candidatos: {e}"})


def list_player_characters(player_id: int) -> str:
    """
    Lista todos los personajes del jugador.
    """
    try:
        from data.character_repository import get_all_characters_by_player_id

        characters = get_all_characters_by_player_id(player_id)

        if not characters:
            return json.dumps({
                "personajes": [],
                "mensaje": "No tienes personajes reclutados aún."
            })

        char_list = []
        for c in characters:
            stats = c.get("stats_json", {})
            bio = stats.get("bio", {})
            taxonomia = stats.get("taxonomia", {})
            progresion = stats.get("progresion", {})
            estado = stats.get("estado", {})

            char_list.append({
                "id": c.get("id"),
                "nombre": c.get("nombre"),
                "raza": taxonomia.get("raza"),
                "clase": progresion.get("clase"),
                "nivel": progresion.get("nivel"),
                "rango": c.get("rango"),
                "estado": c.get("estado"),
                "ubicacion": c.get("ubicacion"),
                "rol": estado.get("rol_asignado", "Sin Asignar"),
                "accion": estado.get("accion_actual", "Esperando"),
                "es_comandante": c.get("es_comandante", False)
            })

        return json.dumps({
            "personajes": char_list,
            "total": len(char_list)
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Error listando personajes: {e}"})


# --- REGISTRO DE FUNCIONES ---

TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "get_player_status": get_player_status,
    "scan_system_data": scan_system_data,
    "check_route_safety": check_route_safety,
    "recruit_character": recruit_character,
    "get_recruitment_candidates": get_recruitment_candidates,
    "list_player_characters": list_player_characters
}


def execute_tool(function_name: str, arguments: Dict[str, Any]) -> str:
    if function_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Función desconocida: {function_name}"})

    try:
        func = TOOL_FUNCTIONS[function_name]
        return func(**arguments)
    except TypeError as e:
        return json.dumps({"error": f"Argumentos inválidos para {function_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Error ejecutando {function_name}: {e}"})