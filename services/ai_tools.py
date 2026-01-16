# services/ai_tools.py
"""
AI Tools - Herramientas para que Gemini interactúe con el Universo Persistente (DB).
Refactorizado para leer directamente de Supabase (Tablas: systems, planets, starlanes).
"""

import json
from google.genai import types
from data.database import supabase
from data.player_repository import get_player_finances

# --- DEFINICIÓN DE HERRAMIENTAS (DECLARATIONS) ---

TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_player_status",
                description="Obtiene el estado financiero y recursos actuales del jugador.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador.")
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
                        "system_identifier": types.Schema(type=types.Type.STRING, description="Nombre o ID del sistema a escanear.")
                    },
                    required=["system_identifier"]
                )
            ),
            types.FunctionDeclaration(
                name="list_available_missions",
                description="Lista las misiones disponibles en el sistema actual del jugador.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                         "player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador.")
                    },
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="check_route_safety",
                description="Calcula la seguridad de una ruta entre dos sistemas basándose en starlanes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "origin_sys_id": types.Schema(type=types.Type.INTEGER, description="ID del sistema origen"),
                        "target_sys_id": types.Schema(type=types.Type.INTEGER, description="ID del sistema destino")
                    },
                    required=["origin_sys_id", "target_sys_id"]
                )
            )
        ]
    )
]

# --- IMPLEMENTACIÓN DE FUNCIONES (LOGIC) ---

def get_player_status(player_id: int) -> str:
    """Consulta la DB para obtener finanzas."""
    finances = get_player_finances(player_id)
    return json.dumps(finances)

def scan_system_data(system_identifier: str) -> str:
    """
    Consulta la DB (tablas 'systems' y 'planets') para obtener datos reales.
    """
    try:
        # 1. Buscar el Sistema
        query = supabase.table("systems").select("*")
        
        # Detectar si es ID numérico o Nombre
        if str(system_identifier).isdigit():
            query = query.eq("id", int(system_identifier))
        else:
            # Búsqueda insensible a mayúsculas si es posible, o exacta
            query = query.ilike("name", f"%{system_identifier}%")
            
        sys_res = query.execute()
        
        if not sys_res.data:
            return json.dumps({"error": f"Sistema '{system_identifier}' no encontrado en los cartas de navegación."})
        
        system = sys_res.data[0]
        sys_id = system['id']
        
        # 2. Buscar Planetas asociados
        planets_res = supabase.table("planets").select("*").eq("system_id", sys_id).execute()
        planets = planets_res.data if planets_res.data else []
        
        # 3. Formatear respuesta táctica
        scan_report = {
            "sistema": {
                "id": system['id'],
                "nombre": system['name'],
                "clase_estelar": system.get('star_class', 'Desconocida'),
                "posicion_galactica": f"{system['x']:.1f}, {system['y']:.1f}",
                "estado_politico": "Ocupado" if system.get('ocupado_por_faction_id') else "Neutral"
            },
            "cuerpos_celestes": [
                {
                    "nombre": p['name'],
                    "tipo": p.get('biome', 'Desconocido'),
                    "tamaño": p.get('planet_size', 'Estándar'),
                    "orbita": p.get('orbital_ring', 0),
                    "recursos_detectados": p.get('resources', [])
                }
                for p in planets
            ]
        }
        return json.dumps(scan_report, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Fallo en sensores de largo alcance: {str(e)}"})

def list_available_missions(player_id: int) -> str:
    """
    (Placeholder) En el futuro consultará la tabla 'missions'.
    Por ahora genera misiones procedurales básicas basadas en la ubicación.
    """
    # Aquí podríamos consultar la ubicación del jugador en la DB y generar misiones locales.
    return json.dumps([
        {"id": 101, "tipo": "Patrulla", "objetivo": "Sector Local", "recompensa": 150},
        {"id": 102, "tipo": "Transporte", "objetivo": "Entrega de Suministros", "recompensa": 300}
    ])

def check_route_safety(origin_sys_id: int, target_sys_id: int) -> str:
    """
    Verifica si existe una ruta directa en 'starlanes' y su estado.
    """
    try:
        # Buscar conexión A->B o B->A
        res = supabase.table("starlanes").select("*")\
            .or_(f"and(system_a_id.eq.{origin_sys_id},system_b_id.eq.{target_sys_id}),and(system_a_id.eq.{target_sys_id},system_b_id.eq.{origin_sys_id})")\
            .execute()
            
        if res.data:
            lane = res.data[0]
            return json.dumps({
                "ruta_existente": True,
                "distancia": lane['distance'],
                "estado_hiperespacio": lane.get('estado', 'Estable'),
                "peligro": "Bajo" if lane.get('estado') == 'Estable' else "Alto"
            })
        else:
            return json.dumps({"ruta_existente": False, "mensaje": "No hay conexión directa por Starlane."})
            
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- MAPEO DE FUNCIONES ---
TOOL_FUNCTIONS = {
    "get_player_status": get_player_status,
    "scan_system_data": scan_system_data,
    "list_available_missions": list_available_missions,
    "check_route_safety": check_route_safety
}