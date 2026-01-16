# services/ai_tools.py
import json
from google.genai import types
from data.database import supabase
from data.player_repository import get_player_finances

TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_player_status",
                description="Obtiene el estado financiero y recursos actuales del jugador.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={"player_id": types.Schema(type=types.Type.INTEGER, description="ID del jugador.")},
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="scan_system_data",
                description="Busca información astronómica de un sistema estelar por su nombre o ID en la base de datos.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={"system_identifier": types.Schema(type=types.Type.STRING, description="Nombre o ID del sistema.")},
                    required=["system_identifier"]
                )
            ),
            types.FunctionDeclaration(
                name="check_route_safety",
                description="Calcula la seguridad de una ruta entre dos sistemas basándose en starlanes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "origin_sys_id": types.Schema(type=types.Type.INTEGER, description="ID origen"),
                        "target_sys_id": types.Schema(type=types.Type.INTEGER, description="ID destino")
                    },
                    required=["origin_sys_id", "target_sys_id"]
                )
            )
        ]
    )
]

def get_player_status(player_id: int) -> str:
    finances = get_player_finances(player_id)
    return json.dumps(finances)

def scan_system_data(system_identifier: str) -> str:
    try:
        query = supabase.table("systems").select("*")
        if str(system_identifier).isdigit():
            query = query.eq("id", int(system_identifier))
        else:
            query = query.ilike("name", f"%{system_identifier}%")
            
        sys_res = query.execute()
        if not sys_res.data:
            return json.dumps({"error": f"Sistema '{system_identifier}' no encontrado."})
        
        system = sys_res.data[0]
        planets_res = supabase.table("planets").select("*").eq("system_id", system['id']).execute()
        planets = planets_res.data if planets_res.data else []
        
        scan_report = {
            "sistema": {
                "id": system['id'],
                "nombre": system['name'],
                "clase_estelar": system.get('star_class', 'Desconocida'),
                "posicion": f"{system['x']:.1f}, {system['y']:.1f}",
            },
            "cuerpos_celestes": [
                {"nombre": p['name'], "tipo": p.get('biome'), "recursos": p.get('resources')} for p in planets
            ]
        }
        return json.dumps(scan_report, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

def check_route_safety(origin_sys_id: int, target_sys_id: int) -> str:
    try:
        res = supabase.table("starlanes").select("*")\
            .or_(f"and(system_a_id.eq.{origin_sys_id},system_b_id.eq.{target_sys_id}),and(system_a_id.eq.{target_sys_id},system_b_id.eq.{origin_sys_id})")\
            .execute()
        if res.data:
            return json.dumps({"ruta_existente": True, "estado": res.data[0].get('estado', 'Estable')})
        return json.dumps({"ruta_existente": False})
    except Exception as e:
        return json.dumps({"error": str(e)})

TOOL_FUNCTIONS = {
    "get_player_status": get_player_status,
    "scan_system_data": scan_system_data,
    "check_route_safety": check_route_safety
}