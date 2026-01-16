# services/ai_tools.py
"""
AI Tools - Herramientas para Native Function Calling de Gemini 2.5
Proporciona acceso controlado a la base de datos para el Game Master IA.

REFACTORIZACIÓN: Sincronizado con setup_ai_rpc_functions.sql y nuevo SDK de Google Gen AI
"""

from typing import Any, Dict, List
import json
from data.database import supabase
from data.log_repository import log_event


# =============================================================================
# HERRAMIENTA PRINCIPAL: EJECUCIÓN DE SQL
# =============================================================================

def execute_db_query(sql_query: str) -> str:
    """
    Ejecuta una consulta SQL en la base de datos PostgreSQL usando RPC de Supabase.

    Esta herramienta le da a la IA acceso controlado a la base de datos para:
    - Leer datos (SELECT)
    - Modificar datos (UPDATE, INSERT, DELETE)
    - Realizar JOINs complejos
    - Verificar recursos antes de acciones

    Args:
        sql_query: Consulta SQL válida para PostgreSQL.

    Returns:
        String JSON con el resultado o error para que la IA se autocorrija.

    Ejemplos:
        - SELECT: "SELECT * FROM players WHERE id = 1"
        - UPDATE: "UPDATE characters SET ubicacion = 'Puente' WHERE id = 5"
        - INSERT: "INSERT INTO planet_buildings (planet_asset_id, building_type) VALUES (1, 'extractor_materiales')"
    """
    try:
        # Sanitización básica
        sql_query = sql_query.strip()

        # Log de auditoría
        log_event(f"[AI SQL] {sql_query[:150]}{'...' if len(sql_query) > 150 else ''}")

        # Determinar tipo de consulta
        query_type = sql_query.split()[0].upper()

        # Bloquear comandos peligrosos
        dangerous_keywords = ["DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
        if query_type in dangerous_keywords:
            return json.dumps({
                "status": "error",
                "type": "FORBIDDEN_OPERATION",
                "message": f"Operación '{query_type}' no permitida por seguridad.",
                "hint": "Solo se permiten SELECT, INSERT, UPDATE, DELETE."
            }, indent=2)

        # Ejecutar según el tipo de consulta
        if query_type == "SELECT":
            # Consultas de lectura: usar execute_sql_query (devuelve JSON array)
            response = supabase.rpc('execute_sql_query', {'query': sql_query}).execute()

            # Verificar si hay error en la respuesta
            if isinstance(response.data, dict) and response.data.get('error'):
                return json.dumps({
                    "status": "error",
                    "type": "SQL_ERROR",
                    "sqlstate": response.data.get('sqlstate', 'UNKNOWN'),
                    "message": response.data.get('message', 'Error desconocido'),
                    "detail": response.data.get('detail', ''),
                    "hint": response.data.get('hint', 'Revisa la sintaxis SQL y nombres de columnas.')
                }, indent=2)

            # Respuesta exitosa
            # response.data ya es un JSONB que contiene un array
            data = response.data if response.data else []

            return json.dumps({
                "status": "success",
                "type": "SELECT",
                "rows": len(data) if isinstance(data, list) else 1,
                "data": data
            }, indent=2, default=str)

        elif query_type in ["UPDATE", "INSERT", "DELETE"]:
            # Consultas de escritura: usar execute_sql_mutation
            response = supabase.rpc('execute_sql_mutation', {'query': sql_query}).execute()

            # Verificar si hay error
            if isinstance(response.data, dict) and response.data.get('error'):
                return json.dumps({
                    "status": "error",
                    "type": "SQL_ERROR",
                    "sqlstate": response.data.get('sqlstate', 'UNKNOWN'),
                    "message": response.data.get('message', 'Error desconocido'),
                    "detail": response.data.get('detail', ''),
                    "hint": response.data.get('hint', 'Revisa la sintaxis SQL y restricciones de la BD.')
                }, indent=2)

            # Respuesta exitosa
            affected_rows = response.data.get('affected_rows', 0) if isinstance(response.data, dict) else 0

            return json.dumps({
                "status": "success",
                "type": query_type,
                "affected_rows": affected_rows,
                "message": f"{query_type} ejecutado correctamente. {affected_rows} fila(s) afectada(s)."
            }, indent=2)

        elif query_type in ["BEGIN", "COMMIT", "ROLLBACK"]:
            return json.dumps({
                "status": "error",
                "type": "TRANSACTION_NOT_ALLOWED",
                "message": "Las transacciones explícitas no están permitidas. Cada consulta es atómica."
            }, indent=2)

        else:
            return json.dumps({
                "status": "error",
                "type": "UNSUPPORTED_QUERY",
                "message": f"Tipo de consulta '{query_type}' no soportado.",
                "hint": "Solo se permiten SELECT, INSERT, UPDATE, DELETE."
            }, indent=2)

    except Exception as e:
        # Capturar errores de red, conexión, etc.
        error_message = str(e)
        log_event(f"[AI SQL ERROR] {error_message}", is_error=True)

        return json.dumps({
            "status": "error",
            "type": "EXECUTION_ERROR",
            "message": error_message,
            "hint": "Error al ejecutar la consulta. Verifica la conexión con Supabase y la sintaxis SQL."
        }, indent=2)


# =============================================================================
# HERRAMIENTAS AUXILIARES
# =============================================================================

def get_table_schema(table_name: str) -> str:
    """
    Retorna el esquema de una tabla específica.
    Útil si la IA necesita conocer las columnas disponibles.

    Args:
        table_name: Nombre de la tabla (ej: 'players', 'characters')

    Returns:
        String JSON con la información del esquema o error.
    """
    try:
        response = supabase.rpc('get_table_schema_info', {'table_name_param': table_name}).execute()

        # Verificar si hay error
        if isinstance(response.data, dict) and response.data.get('error'):
            return json.dumps({
                "status": "error",
                "message": response.data.get('message', f"Tabla '{table_name}' no encontrada")
            }, indent=2)

        # Respuesta exitosa
        return json.dumps({
            "status": "success",
            "table": table_name,
            "schema": response.data
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


def log_ai_action(action_description: str, player_id: int = None) -> str:
    """
    Registra una acción de la IA en los logs del sistema.

    Args:
        action_description: Descripción de la acción o evento
        player_id: ID del jugador asociado (opcional)

    Returns:
        String JSON confirmando el registro.
    """
    try:
        log_event(f"[GM IA] {action_description}", player_id)
        return json.dumps({
            "status": "success",
            "message": "Acción registrada en los logs del sistema"
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, indent=2)


# =============================================================================
# CONFIGURACIÓN PARA GEMINI 2.5
# =============================================================================

# Declaración de herramientas en formato Google Gen AI SDK
TOOL_DECLARATIONS = [
    {
        "function_declarations": [
            {
                "name": "execute_db_query",
                "description": """Ejecuta consultas SQL directamente en la base de datos PostgreSQL del juego.

USA ESTA HERRAMIENTA PARA:
- Leer el estado actual del juego (SELECT)
- Modificar datos del mundo (UPDATE, INSERT, DELETE)
- Verificar recursos del jugador antes de permitir acciones
- Actualizar estadísticas de personajes
- Crear o modificar edificios planetarios
- Registrar eventos

FLUJO CORRECTO:
1. Primero SIEMPRE verificar el estado actual con SELECT
2. Luego modificar con UPDATE/INSERT/DELETE
3. Narrar el resultado

ESQUEMA DE LA BASE DE DATOS:

players:
  - id (int) - Identificador único del jugador
  - nombre (text) - Nombre del jugador/facción
  - faccion_nombre (text) - Nombre de la facción
  - creditos (int) - Créditos Imperiales (CI), moneda universal
  - materiales (int) - Recursos base para construcción
  - componentes (int) - Componentes industriales avanzados
  - celulas_energia (int) - Energía para operar edificios
  - influencia (int) - Poder político/diplomático
  - recursos_lujo (jsonb) - Recursos Tier 2 organizados por categoría
    Estructura: {"materiales_avanzados": {"superconductores": 0, ...}, ...}

characters:
  - id (int) - Identificador único del personaje
  - player_id (int) - FK a players
  - nombre (text) - Nombre del personaje
  - stats_json (jsonb) - Estadísticas completas
    Estructura: {"atributos": {"fuerza": 10, "astucia": 15, ...}, "salud": {...}, ...}
  - ubicacion (text) - Ubicación actual del personaje
  - estado (text) - Estado actual: 'Disponible', 'En Misión', 'Herido', 'Descansando'
  - rango (text) - Rango militar/posición

planet_assets:
  - id (int) - Identificador único del asentamiento
  - player_id (int) - FK a players
  - system_id (int) - ID del sistema estelar
  - nombre_asentamiento (text) - Nombre de la colonia
  - poblacion (int) - Población total (POPS)
  - pops_activos (int) - POPS trabajando en edificios
  - pops_desempleados (int) - POPS sin asignar
  - infraestructura_defensiva (int) - Nivel de defensa
  - seguridad (float) - Nivel de seguridad (0.0-1.0)
  - felicidad (float) - Nivel de felicidad (0.0-1.0)

planet_buildings:
  - id (int) - Identificador único del edificio
  - planet_asset_id (int) - FK a planet_assets
  - player_id (int) - FK a players
  - building_type (text) - Tipo: 'extractor_materiales', 'generador_energia', etc.
  - building_tier (int) - Nivel del edificio (1, 2, 3...)
  - is_active (bool) - Si está operativo
  - pops_required (int) - POPS necesarios para operar
  - energy_consumption (int) - Energía consumida por turno

luxury_extraction_sites:
  - id (int) - Identificador único del sitio
  - planet_asset_id (int) - FK a planet_assets
  - player_id (int) - FK a players
  - resource_key (text) - Clave del recurso: 'superconductores', 'antimateria', etc.
  - resource_category (text) - Categoría: 'materiales_avanzados', 'energia_avanzada', etc.
  - extraction_rate (int) - Unidades extraídas por turno
  - is_active (bool) - Si está operativo

logs:
  - id (serial) - ID autoincrementable
  - player_id (int, nullable) - FK a players
  - evento_texto (text) - Descripción del evento
  - turno (int) - Turno en que ocurrió
  - created_at (timestamp) - Timestamp automático

EJEMPLOS DE CONSULTAS:

1. Verificar recursos del jugador:
   SELECT creditos, materiales, componentes, celulas_energia FROM players WHERE id = 1;

2. Ver comandante del jugador:
   SELECT nombre, ubicacion, estado, stats_json FROM characters WHERE player_id = 1 AND rango = 'Comandante';

3. Listar edificios en un planeta:
   SELECT building_type, is_active, pops_required FROM planet_buildings WHERE planet_asset_id = 1;

4. Construir edificio (PRIMERO verificar recursos, LUEGO construir):
   -- Paso 1: Verificar
   SELECT creditos, materiales FROM players WHERE id = 1;
   -- Paso 2: Descontar recursos
   UPDATE players SET creditos = creditos - 500, materiales = materiales - 50 WHERE id = 1;
   -- Paso 3: Crear edificio
   INSERT INTO planet_buildings (planet_asset_id, player_id, building_type, pops_required, energy_consumption)
   VALUES (1, 1, 'extractor_materiales', 100, 5);

5. Actualizar ubicación de personaje:
   UPDATE characters SET ubicacion = 'Sala de Máquinas', estado = 'Descansando' WHERE id = 5;

6. Consultas con JOIN:
   SELECT p.nombre, c.nombre as comandante, c.ubicacion
   FROM players p
   JOIN characters c ON c.player_id = p.id
   WHERE p.id = 1 AND c.rango = 'Comandante';

COSTOS DE EDIFICIOS (REFERENCIA):
- Extractor de Materiales: 500 CI, 10 Componentes
- Fábrica de Componentes: 800 CI, 50 Materiales
- Planta de Energía: 1000 CI, 30 Materiales, 20 Componentes
- Búnker de Defensa: 1500 CI, 80 Materiales, 30 Componentes

IMPORTANTE:
- Si es una PREGUNTA (¿cuántos créditos tengo?), usa SELECT y responde con el NÚMERO EXACTO
- Si es una ACCIÓN (construir edificio), verifica recursos primero, luego ejecuta
- Si la query falla, recibirás un error detallado para que te corrijas
""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "Consulta SQL válida en PostgreSQL. Debe ser sintácticamente correcta y usar los nombres exactos de tablas y columnas del esquema."
                        }
                    },
                    "required": ["sql_query"]
                }
            },
            {
                "name": "get_table_schema",
                "description": "Obtiene el esquema completo de una tabla específica, incluyendo nombres de columnas, tipos de datos y restricciones. Útil cuando la IA necesita recordar la estructura exacta de una tabla.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Nombre de la tabla (ej: 'players', 'characters', 'planet_assets', 'planet_buildings')"
                        }
                    },
                    "required": ["table_name"]
                }
            },
            {
                "name": "log_ai_action",
                "description": "Registra una acción narrativa o evento importante en los logs del sistema para auditoría y seguimiento.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_description": {
                            "type": "string",
                            "description": "Descripción clara de la acción o evento a registrar"
                        },
                        "player_id": {
                            "type": "integer",
                            "description": "ID del jugador asociado (opcional, omitir para eventos globales)"
                        }
                    },
                    "required": ["action_description"]
                }
            }
        ]
    }
]


# Mapeo de nombres de función a implementaciones Python
TOOL_FUNCTIONS = {
    "execute_db_query": execute_db_query,
    "get_table_schema": get_table_schema,
    "log_ai_action": log_ai_action
}
