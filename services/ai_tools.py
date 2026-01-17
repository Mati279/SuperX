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


# --- REGISTRO DE FUNCIONES ---

TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "get_player_status": get_player_status,
    "scan_system_data": scan_system_data,
    "check_route_safety": check_route_safety
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