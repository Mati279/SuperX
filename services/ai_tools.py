# services/ai_tools.py
"""
Herramientas de IA para el Asistente Táctico.
Define las funciones que Gemini puede invocar mediante function calling.
"""

import json
import re
from typing import Dict, Any, Callable
from google.genai import types

from data.database import get_supabase
from data.player_repository import get_player_finances
from data.log_repository import log_event
# IMPORTACIONES NUEVAS PARA UBICACIÓN Y ACCIONES
from data.world_repository import get_commander_location_display, queue_player_action
from data.character_repository import get_commander_by_player_id

# IMPORTACIONES PARA RESOLUCIÓN MRG
from core.mrg_engine import resolve_action, ResultType
from core.mrg_constants import DIFFICULTY_NORMAL


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
                description="Busca información astronómica de un sistema estelar (planetas, recursos, facciones).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "system_name": types.Schema(
                            type=types.Type.STRING,
                            description="Nombre del sistema estelar a escanear (ej: 'Sol', 'Alpha Centauri')."
                        )
                    },
                    required=["system_name"]
                )
            ),
             types.FunctionDeclaration(
                name="check_route_safety",
                description="Calcula la seguridad de una ruta hiperespacial entre dos sistemas.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "origin_system": types.Schema(type=types.Type.STRING),
                        "destination_system": types.Schema(type=types.Type.STRING)
                    },
                    required=["origin_system", "destination_system"]
                )
            ),
             types.FunctionDeclaration(
                name="investigar",
                description="Inicia una operación de inteligencia para obtener datos ocultos de un objetivo. IMPORTANTE: Extrae siempre el 'player_id' del contexto. Puede recibir flag 'force_success' en el prompt.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "target_name": types.Schema(
                            type=types.Type.STRING,
                            description="Nombre de la entidad, facción o sistema a investigar."
                        ),
                         "focus": types.Schema(
                            type=types.Type.STRING,
                            description="Enfoque de la investigación (militar, económico, político)."
                        ),
                        "player_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID del jugador que ordena la investigación."
                        ),
                        "execution_mode": types.Schema(
                            type=types.Type.STRING,
                            description="USO INTERNO: 'SCHEDULE' (Default) para programar, 'EXECUTE' para resolver.",
                            enum=["SCHEDULE", "EXECUTE"]
                        ),
                        "force_success": types.Schema(
                            type=types.Type.BOOLEAN,
                            description="Debug: Si es true, garantiza el éxito de la investigación."
                        )
                    },
                    required=["target_name", "player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="recruit_character",
                description="Intenta reclutar un personaje específico de la lista de candidatos.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(type=types.Type.INTEGER),
                        "candidate_name": types.Schema(type=types.Type.STRING)
                    },
                    required=["player_id", "candidate_name"]
                )
            ),
            types.FunctionDeclaration(
                name="get_recruitment_candidates",
                description="Obtiene la lista actual de candidatos disponibles para reclutamiento.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(type=types.Type.INTEGER)
                    },
                    required=["player_id"]
                )
            ),
            types.FunctionDeclaration(
                name="list_player_characters",
                description="Lista todos los personajes/operativos bajo el mando del jugador.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "player_id": types.Schema(type=types.Type.INTEGER)
                    },
                    required=["player_id"]
                )
            )
        ]
    )
]


# --- IMPLEMENTACIÓN DE FUNCIONES ---

def get_player_status(player_id: int) -> str:
    """Retorna estado financiero y ubicación."""
    try:
        finances = get_player_finances(player_id)
        
        # Obtener ubicación del comandante
        commander = get_commander_by_player_id(player_id)
        location_str = "Desconocida"
        base_name = "Nave Capital"
        
        if commander:
             # Usar la función robusta de world_repository
            loc_details = get_commander_location_display(commander['id'])
            location_str = f"{loc_details['system']} - {loc_details['planet']}"
            base_name = loc_details['base']

        return json.dumps({
            "creditos": finances.get("creditos", 0),
            "ubicacion_actual": location_str,
            "base_operativa": base_name,
            "estado_alerta": "Normal"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def scan_system_data(system_name: str) -> str:
    """Busca datos de un sistema en la DB."""
    try:
        db = _get_db()
        response = db.table("planets").select("*").ilike("sistema", f"%{system_name}%").execute()
        
        if not response.data:
            return json.dumps({"resultado": f"No se encontraron datos astronómicos para el sistema '{system_name}'. Posiblemente inexplorado."})
            
        planets = response.data
        summary = []
        for p in planets:
            summary.append({
                "nombre": p["nombre"],
                "tipo": p.get("tipo", "Desconocido"),
                "recursos": p.get("recursos_json", {}),
                "habitado": p.get("es_asentamiento", False)
            })
            
        return json.dumps({
            "sistema": system_name,
            "cuerpos_celestes": summary,
            "analisis": "Sistema estable. Rutas de comercio viables detectadas."
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Error de escaneo: {e}"})


def check_route_safety(origin_system: str, destination_system: str) -> str:
    """Simula un cálculo de seguridad de ruta."""
    # Lógica simplificada
    return json.dumps({
        "origen": origin_system,
        "destino": destination_system,
        "nivel_riesgo": "Moderado",
        "amenazas": ["Piratería en sector intermedio", "Tormenta de iones"],
        "tiempo_estimado": "2 saltos"
    }, ensure_ascii=False)


def investigar(target_name: str, player_id: int, focus: str = "general", execution_mode: str = "SCHEDULE", force_success: bool = False) -> str:
    """
    Realiza una investigación sobre un objetivo.
    Maneja la lógica de resultados:
    - Crítico: Descuento 30%.
    - Éxito (Parcial/Total): Revela Bio.
    - Fallo: Reintentar.
    - Pifia: Eliminar candidato.
    """
    print(f"🕵️ DEBUG: llamada a investigar() - Target: {target_name}, Mode: {execution_mode}, PID: {player_id}, Force: {force_success}")
    try:
        # MODO 1: PROGRAMACIÓN (Default)
        if execution_mode == "SCHEDULE":
            force_flag = " force_success=True" if force_success else ""
            internal_command = f"[INTERNAL_EXECUTE_INVESTIGATION] target='{target_name}' focus='{focus}' player_id={player_id}{force_flag}"
            
            queue_ok = queue_player_action(player_id, internal_command)
            
            if queue_ok:
                return json.dumps({
                    "status": "SCHEDULED",
                    "mensaje": f"Protocolo de investigación sobre '{target_name}' iniciado. Recibirá un informe en el próximo Tick.",
                    "tiempo_estimado": "1 Tick"
                }, ensure_ascii=False)
            else:
                return json.dumps({"error": "No se pudo programar la investigación. Error en cola de operaciones."})

        # MODO 2: EJECUCIÓN (Internal)
        elif execution_mode == "EXECUTE":
            commander = get_commander_by_player_id(player_id)
            if not commander:
                return json.dumps({"error": "Comandante no encontrado."})

            # Obtener stats
            stats = commander.get('stats_json', {})
            attributes = stats.get('atributos', {})
            skills = stats.get('habilidades', {})
            
            base_merit = attributes.get('intelecto', 0)
            skill_bonus = skills.get('Recopilación de Información', 0)
            total_merit = base_merit + skill_bonus

            print(f"🎲 DEBUG: Tirada MRG. Mérito total: {total_merit}. Force: {force_success}")

            if force_success:
                # Mock para debug
                class MockResult:
                    result_type = ResultType.CRITICAL_SUCCESS
                    roll = type('obj', (object,), {'total': 100})
                    margin = 50
                result = MockResult()
            else:
                result = resolve_action(
                    merit_points=total_merit,
                    difficulty=DIFFICULTY_NORMAL, 
                    action_description=f"Investigación de {target_name}"
                )
            
            print(f"🎲 DEBUG: Resultado MRG: {result.result_type}")

            # --- LÓGICA DE RESULTADOS ---
            
            # 1. ÉXITO CRÍTICO: Descuento + Bio
            if result.result_type == ResultType.CRITICAL_SUCCESS:
                outcome_code = "CRITICAL_SUCCESS"
                log_event(f"SYSTEM_EVENT: INVESTIGATION_RESULT | target={target_name} | outcome={outcome_code}", player_id)
                
                lore = f"¡ÉXITO ROTUNDO! Se han encontrado puntos de presión psicológica en {target_name}. "
                lore += "Sabemos exactamente qué ofrecerle para que se una por menos créditos. (Descuento 30% aplicado)."
                
                return json.dumps({
                    "status": "SUCCESS",
                    "resultado": lore,
                    "analisis": "Operación perfecta. Activo comprometido favorablemente."
                }, ensure_ascii=False)

            # 2. ÉXITO (TOTAL O PARCIAL): Solo Bio
            elif result.result_type in [ResultType.TOTAL_SUCCESS, ResultType.PARTIAL_SUCCESS]:
                outcome_code = "SUCCESS"
                log_event(f"SYSTEM_EVENT: INVESTIGATION_RESULT | target={target_name} | outcome={outcome_code}", player_id)
                
                lore = f"Investigación completada. Se han verificado los antecedentes de {target_name}. "
                lore += "Información biográfica añadida al expediente."
                
                return json.dumps({
                    "status": "SUCCESS",
                    "resultado": lore,
                    "analisis": "Información recuperada correctamente."
                }, ensure_ascii=False)

            # 3. FALLO CRÍTICO: Eliminación
            elif result.result_type == ResultType.CRITICAL_FAILURE:
                outcome_code = "CRITICAL_FAILURE"
                log_event(f"SYSTEM_EVENT: INVESTIGATION_RESULT | target={target_name} | outcome={outcome_code}", player_id)
                
                lore = f"¡ALERTA! La operación contra {target_name} ha sido descubierta. "
                lore += "El objetivo se ha ofendido por la intrusión y ha retirado su solicitud de reclutamiento."
                
                return json.dumps({
                    "status": "FAILURE",
                    "resultado": lore,
                    "analisis": "Operación comprometida. Objetivo perdido."
                }, ensure_ascii=False)

            # 4. FALLO NORMAL: Reintentar
            else:
                outcome_code = "FAILURE"
                log_event(f"SYSTEM_EVENT: INVESTIGATION_RESULT | target={target_name} | outcome={outcome_code}", player_id)
                
                lore = f"No se han encontrado datos relevantes sobre {target_name} en esta pasada. "
                lore += "Los archivos parecen estar encriptados o fuera de alcance por ahora."
                
                return json.dumps({
                    "status": "FAILURE",
                    "resultado": lore,
                    "analisis": "Sin resultados concluyentes. Se puede volver a intentar."
                }, ensure_ascii=False)
                
        else:
            return json.dumps({"error": f"Modo desconocido: {execution_mode}"})

    except Exception as e:
        print(f"❌ DEBUG: Exception en investigar: {e}")
        return json.dumps({"error": f"Error crítico: {str(e)}"})


def recruit_character(player_id: int, candidate_name: str) -> str:
    return json.dumps({
        "status": "REQUIERE_CONFIRMACION_UI",
        "mensaje": f"El reclutamiento de {candidate_name} debe ser autorizado en el Centro."
    })


def get_recruitment_candidates(player_id: int) -> str:
    return json.dumps({
        "candidatos": [],
        "nota": "Datos simulados."
    })

def list_player_characters(player_id: int) -> str:
    try:
        db = _get_db()
        response = db.table("characters").select("*").eq("player_id", player_id).execute()
        char_list = []
        if response.data:
            for c in response.data:
                stats = c.get("stats_json", {})
                estado = c.get("estado", "Activo")
                char_list.append({
                    "nombre": c["nombre"],
                    "clase": c.get("clase"),
                    "nivel": c.get("nivel"),
                    "rango": c.get("rango"),
                    "estado": c.get("estado"),
                    "ubicacion": c.get("ubicacion"),
                    "rol": estado.get("rol_asignado", "Sin Asignar"),
                    "accion": estado.get("accion_actual", "Esperando"),
                    "es_comandante": c.get("es_comandante", False)
                })
        return json.dumps({"personajes": char_list, "total": len(char_list)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error listando personajes: {e}"})


TOOL_FUNCTIONS: Dict[str, Callable[..., str]] = {
    "get_player_status": get_player_status,
    "scan_system_data": scan_system_data,
    "check_route_safety": check_route_safety,
    "investigar": investigar,
    "recruit_character": recruit_character,
    "get_recruitment_candidates": get_recruitment_candidates,
    "list_player_characters": list_player_characters
}


def execute_tool(function_name: str, arguments: Dict[str, Any]) -> str:
    if function_name not in TOOL_FUNCTIONS:
        return json.dumps({"error": f"Función desconocida: {function_name}"})
    try:
        func = TOOL_FUNCTIONS[function_name]
        if "player_id" in arguments:
            arguments["player_id"] = int(arguments["player_id"])
        return func(**arguments)
    except Exception as e:
        return json.dumps({"error": f"Error ejecutando {function_name}: {e}"})