# services/gemini_service.py
"""
Gemini Service - Native Function Calling Implementation
Sistema de Game Master IA con acceso completo a la base de datos.
"""

import json
from typing import Dict, Any, Optional, List
from google.genai import types

from data.database import ai_client
from data.log_repository import log_event
from data.game_config_repository import get_game_config
from data.character_repository import get_commander_by_player_id
from data.world_repository import queue_player_action, get_world_state

# Importar el motor de tiempo
from core.time_engine import check_and_trigger_tick, is_lock_in_window

# Importar Motor de Resolución Galáctico (MRG)
from core.mrg_engine import resolve_action, ResultType
from core.mrg_constants import DIFFICULTY_NORMAL
from core.mrg_effects import apply_partial_success_complication

# Importar herramientas AI
from services.ai_tools import TOOL_DECLARATIONS, TOOL_FUNCTIONS

# Importar constantes
from config.app_constants import TEXT_MODEL_NAME, IMAGE_MODEL_NAME


# --- SYSTEM PROMPT (MODO BITÁCORA CORTA) ---

GAME_MASTER_SYSTEM_PROMPT = """
Eres el GAME MASTER de "SuperX".

## TU ROL
- Interfaz táctica del juego.
- Tu objetivo es informar resultados de forma RÁPIDA y CONCISA.

## REGLAS DE RESPUESTA (MODO TWEET)
1. **LONGITUD MÁXIMA:** Tus narraciones NO deben superar la longitud de un tweet (~280 caracteres) o 2 frases cortas.
2. **ESTILO:** Militar, directo, bitácora de vuelo. Sin florituras poéticas.
3. **DATOS:** Si preguntan un número, da solo el número y el concepto.

## LEY DE LA VERDAD DE DATOS
- Si preguntan créditos/recursos: "Saldo actual: [X] Créditos." (Usa `execute_db_query`).
- NUNCA inventes números.

## FLUJO
1. Entender.
2. Consultar DB (`execute_db_query`).
3. Ejecutar acción.
4. Responder CORTO.

Ejemplo Narrativa: "Escaneo completado. Se detectan trazas de iridio en el sector B4. Sin hostiles."
Ejemplo Combate: "Impacto crítico en el casco enemigo. Sus escudos han colapsado. Victoria inminente."
"""


# --- FUNCIÓN AUXILIAR: NARRATIVA MRG ---

def _get_narrative_guidance(result_type: ResultType) -> str:
    """Retorna guía narrativa según el resultado MRG."""
    guidance = {
        ResultType.CRITICAL_SUCCESS: "Éxito Crítico. Resultado perfecto.",
        ResultType.TOTAL_SUCCESS: "Éxito. Misión cumplida.",
        ResultType.PARTIAL_SUCCESS: "Éxito parcial. Complicaciones menores.",
        ResultType.PARTIAL_FAILURE: "Fallo. Objetivo no logrado.",
        ResultType.TOTAL_FAILURE: "Fallo total. Retroceso operativo.",
        ResultType.CRITICAL_FAILURE: "Catástrofe. Daños severos."
    }
    return guidance.get(result_type, "Resultado de acción.")


# --- FUNCIÓN PRINCIPAL: RESOLVER ACCIÓN ---

def resolve_player_action(action_text: str, player_id: int, conversation_history: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, Any]]:
    """
    Resuelve la acción del jugador usando MRG + Native Function Calling de Gemini.

    Args:
        action_text: La acción o consulta del jugador
        player_id: ID del jugador
        conversation_history: Lista de mensajes previos (últimos 5 turnos) en formato:
            [{"role": "user", "text": "..."}, {"role": "assistant", "text": "..."}]

    Returns:
        Dict con narrative, mrg_result, function_calls_made y updated_history
    """

    # --- 0. GUARDIANES DE TIEMPO (STRT) ---
    check_and_trigger_tick()

    world_state = get_world_state()
    if world_state.get("is_frozen", False):
        return {"narrative": "❄️ Universo en Éxtasis.", "mrg_result": None}

    if is_lock_in_window():
        queue_player_action(player_id, action_text)
        return {"narrative": "⚠️ Ventana Bloqueo. Orden encolada.", "mrg_result": None}

    # --- 1. CONFIGURACIÓN ---
    if not ai_client:
        raise ConnectionError("IA no disponible.")

    game_config = get_game_config()
    commander = get_commander_by_player_id(player_id)
    if not commander:
        raise ValueError("Comandante no encontrado.")

    # --- 2. DETECTOR DE CONSULTAS VS ACCIONES ---
    query_keywords = ["cuantos", "cuántos", "que", "qué", "como", "cómo", "donde", "dónde", "quien", "quién", "estado", "listar", "ver", "info", "ayuda", "tengo"]
    is_informational_query = any(action_text.lstrip().lower().startswith(k) for k in query_keywords) or "?" in action_text

    mrg_result = None
    mrg_context = ""

    if is_informational_query:
        # Consulta: Sin tirada
        class DummyResult:
            result_type = ResultType.TOTAL_SUCCESS
            roll = None
        mrg_result = DummyResult()
        mrg_context = "\nℹ️ CONSULTA DE DATOS. Responde corto y exacto.\n"
    else:
        # Acción: Tirada MRG
        stats = commander.get('stats_json', {})
        attributes = stats.get('atributos', {})
        merit_points = sum(attributes.values()) if attributes else 0
        
        mrg_result = resolve_action(
            merit_points=merit_points,
            difficulty=DIFFICULTY_NORMAL,
            action_description=action_text,
            entity_id=commander['id'],
            entity_name=commander['nombre']
        )
        
        if mrg_result.result_type == ResultType.PARTIAL_SUCCESS:
            apply_partial_success_complication(mrg_result, player_id)

        mrg_context = f"\n🎲 Resultado: {mrg_result.result_type.value}\n"

    # --- 3. CONSTRUIR CONTEXTO DE CONVERSACIÓN ---
    context_messages = []

    # Añadir historial previo si existe (últimos 5 mensajes)
    if conversation_history:
        for msg in conversation_history[-10:]:  # Últimos 5 intercambios (10 mensajes total)
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if role == "user":
                context_messages.append(f"[JUGADOR DIJO]: {text}")
            else:
                context_messages.append(f"[TÚ RESPONDISTE]: {text}")

    history_context = "\n".join(context_messages) if context_messages else "[NUEVA CONVERSACIÓN]"

    # --- 4. MENSAJE USUARIO ---
    user_message = f"""
!!! MODO TWEET ACTIVO:
RESPONDE EN MENOS DE 280 CARACTERES. SÉ PRECISO.
SI ES DATO, USA `execute_db_query`.

**CONTEXTO CONVERSACIONAL**:
{history_context}

**ACCIÓN ACTUAL**: "{action_text}"
**Comandante**: {commander['nombre']}
{mrg_context}
"""

    try:
        # --- 5. INICIAR CHAT ---
        chat = ai_client.chats.create(
            model=TEXT_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=GAME_MASTER_SYSTEM_PROMPT,
                tools=TOOL_DECLARATIONS,
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO"
                    )
                ),
                temperature=0.7, # Equilibrado
                max_output_tokens=300, # Límite forzado para asegurar brevedad
                top_p=0.95
            )
        )

        response = chat.send_message(user_message)

        # --- 6. BUCLE DE HERRAMIENTAS ---
        max_iterations = 10
        iteration = 0
        function_calls_made = []

        while iteration < max_iterations:
            iteration += 1

            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                has_function_call = False

                for part in parts:
                    if part.function_call:
                        has_function_call = True
                        fc = part.function_call
                        fname = fc.name
                        fargs = fc.args

                        # No registrar las llamadas a herramientas en el log visible del jugador
                        function_calls_made.append({"function": fname, "args": fargs})

                        result_str = ""
                        if fname in TOOL_FUNCTIONS:
                            try:
                                args_dict = {k: v for k, v in fargs.items()}
                                result_str = TOOL_FUNCTIONS[fname](**args_dict)
                            except Exception as e:
                                result_str = json.dumps({"error": str(e)})
                        else:
                            result_str = json.dumps({"error": "Función no encontrada"})

                        response = chat.send_message(
                            [
                                types.Part.from_function_response(
                                    name=fname,
                                    response={"result": result_str}
                                )
                            ]
                        )
                        break

                if not has_function_call:
                    break
            else:
                break

        # --- 7. NARRATIVA FINAL ---
        narrative = "..."
        if response.candidates and response.candidates[0].content.parts:
            text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
            narrative = "".join(text_parts).strip()

        # Registrar la narrativa completa sin truncar
        log_event(f"[GM] {narrative}", player_id)

        # Actualizar historial de conversación
        updated_history = conversation_history[:] if conversation_history else []
        updated_history.append({"role": "user", "text": action_text})
        updated_history.append({"role": "assistant", "text": narrative})

        return {
            "narrative": narrative,
            "mrg_result": mrg_result,
            "function_calls_made": function_calls_made,
            "conversation_history": updated_history
        }

    except Exception as e:
        log_event(f"Error AI: {e}", player_id, is_error=True)
        return {"narrative": f"⚠️ Error: {str(e)}", "mrg_result": None}


# --- FUNCIÓN AUXILIAR: GENERACIÓN DE IMÁGENES ---

def generate_image(prompt: str, player_id: int) -> Optional[Any]:
    if not ai_client: return None
    try:
        return ai_client.models.generate_images(model=IMAGE_MODEL_NAME, prompt=prompt)
    except: return None