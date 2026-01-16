# services/ai_tools.py
"""
AI Tools - Herramientas para Native Function Calling de Gemini
Proporciona acceso "God Mode" a la base de datos para el Game Master IA.
"""

from typing import Any, Dict, List
import json
from data.database import supabase
from data.log_repository import log_event


# --- HERRAMIENTA PRINCIPAL: EJECUCIÓN DE SQL ---

def execute_db_query(sql_query: str) -> str:
    """
    Ejecuta una consulta SQL cruda en la base de datos PostgreSQL.

    Esta herramienta le da a la IA acceso completo a la base de datos para:
    - Leer datos (SELECT)
    - Modificar datos (UPDATE, INSERT, DELETE)
    - Realizar JOINs complejos
    - Ejecutar transacciones

    Args:
        sql_query: Consulta SQL válida para PostgreSQL.
                   Ejemplos:
                   - "SELECT * FROM players WHERE id = 1"
                   - "UPDATE characters SET ubicacion = 'Puente' WHERE id = 5"
                   - "INSERT INTO planet_buildings (planet_asset_id, building_type, pops_required) VALUES (1, 'extractor_materiales', 100)"

    Returns:
        String con el resultado:
        - Para SELECT: JSON con los datos obtenidos
        - Para UPDATE/INSERT/DELETE: Mensaje de confirmación
        - Para errores: Descripción del error para que la IA se corrija

    Notas de Seguridad:
        - La IA debe ser cuidadosa con DELETE y UPDATE sin WHERE
        - Los errores de sintaxis se devuelven a la IA para autocorrección
    """
    try:
        # Sanitización básica (remover comentarios SQL que podrían causar problemas)
        sql_query = sql_query.strip()

        # Log de la consulta (para auditoría)
        log_event(f"[AI SQL] Ejecutando: {sql_query[:200]}...")

        # Determinar tipo de consulta
        query_type = sql_query.split()[0].upper()

        if query_type == "SELECT":
            # Consulta de lectura
            response = supabase.rpc('execute_sql_query', {'query': sql_query}).execute()

            # Si supabase no tiene RPC, usar postgrest directo
            # Fallback: usar .from_().select() parseando la query
            # Por simplicidad, asumimos que tienes un RPC function en Supabase
            # Si no, ver implementación alternativa abajo

            if response.data:
                # Convertir a JSON legible
                result = {
                    "status": "success",
                    "type": "SELECT",
                    "rows": len(response.data) if isinstance(response.data, list) else 1,
                    "data": response.data
                }
                return json.dumps(result, indent=2, default=str)
            else:
                return json.dumps({
                    "status": "success",
                    "type": "SELECT",
                    "rows": 0,
                    "data": []
                })

        elif query_type in ["UPDATE", "INSERT", "DELETE"]:
            # Consultas de escritura
            response = supabase.rpc('execute_sql_mutation', {'query': sql_query}).execute()

            return json.dumps({
                "status": "success",
                "type": query_type,
                "message": f"{query_type} ejecutado correctamente",
                "affected_rows": response.data if response.data else "unknown"
            }, indent=2)

        elif query_type == "BEGIN" or "COMMIT" in sql_query.upper() or "ROLLBACK" in sql_query.upper():
            return json.dumps({
                "status": "error",
                "message": "Las transacciones explícitas no están permitidas. Cada consulta es atómica."
            })

        else:
            # Otras consultas (CREATE TABLE, DROP, etc.)
            return json.dumps({
                "status": "error",
                "message": f"Tipo de consulta '{query_type}' no permitido. Solo se permiten SELECT, INSERT, UPDATE, DELETE."
            })

    except Exception as e:
        # Devolver el error a la IA para que se corrija
        error_message = str(e)

        # Log del error
        log_event(f"[AI SQL ERROR] {error_message}", is_error=True)

        return json.dumps({
            "status": "error",
            "type": "SQL_ERROR",
            "message": error_message,
            "hint": "Revisa la sintaxis SQL, nombres de tablas y columnas. Consulta el esquema de la base de datos."
        }, indent=2)


# --- IMPLEMENTACIÓN ALTERNATIVA SIN RPC ---
# Si Supabase no tiene la función RPC, usar este enfoque:

def execute_db_query_direct(sql_query: str) -> str:
    """
    Implementación directa sin RPC (usa psycopg2 o similar).
    SOLO usar si no tienes acceso a RPC en Supabase.
    """
    import psycopg2
    from config.settings import SUPABASE_URL, SUPABASE_KEY

    # Extraer credenciales de conexión directa
    # Necesitarás la connection string de Supabase (DB directo, no API)
    # Formato: postgresql://user:pass@host:port/database

    try:
        # IMPORTANTE: Reemplazar con tu connection string real
        # La obtienes en Supabase -> Settings -> Database -> Connection String
        conn = psycopg2.connect(
            "postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres"
        )

        cursor = conn.cursor()
        cursor.execute(sql_query)

        query_type = sql_query.split()[0].upper()

        if query_type == "SELECT":
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Convertir a lista de diccionarios
            data = [dict(zip(columns, row)) for row in rows]

            result = {
                "status": "success",
                "type": "SELECT",
                "rows": len(data),
                "data": data
            }
        else:
            conn.commit()
            result = {
                "status": "success",
                "type": query_type,
                "message": f"{query_type} ejecutado correctamente",
                "affected_rows": cursor.rowcount
            }

        cursor.close()
        conn.close()

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "type": "SQL_ERROR",
            "message": str(e)
        }, indent=2)


# --- HERRAMIENTAS AUXILIARES (OPCIONALES) ---

def get_table_schema(table_name: str) -> str:
    """
    Retorna el esquema de una tabla específica.
    Útil si la IA necesita recordar las columnas disponibles.
    """
    try:
        # Consultar información del esquema
        query = f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position;
        """

        response = supabase.rpc('execute_sql_query', {'query': query}).execute()

        if response.data:
            schema_info = {
                "table": table_name,
                "columns": response.data
            }
            return json.dumps(schema_info, indent=2)
        else:
            return json.dumps({"error": f"Tabla '{table_name}' no encontrada"})

    except Exception as e:
        return json.dumps({"error": str(e)})


def log_ai_action(action_description: str, player_id: int = None) -> str:
    """
    Registra una acción de la IA en los logs del sistema.
    """
    try:
        log_event(f"[GM IA] {action_description}", player_id)
        return json.dumps({"status": "logged"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- CONFIGURACIÓN PARA GEMINI ---

# Declaración de herramientas en formato de Gemini 2.5
TOOL_DECLARATIONS = [
    {
        "function_declarations": [
            {
                "name": "execute_db_query",
                "description": """
                Ejecuta consultas SQL directamente en la base de datos PostgreSQL del juego.

                Usa esta herramienta para:
                - Leer el estado actual del juego (SELECT)
                - Modificar datos del mundo (UPDATE, INSERT)
                - Verificar recursos del jugador antes de permitir acciones
                - Actualizar estadísticas de personajes
                - Crear o modificar edificios planetarios
                - Registrar eventos en logs

                IMPORTANTE: Siempre verifica el estado actual ANTES de modificar datos.
                Ejemplo: Antes de construir un edificio, verifica que el jugador tenga recursos suficientes.

                Esquema de la Base de Datos:

                players:
                  - id (int)
                  - nombre (text)
                  - faccion_nombre (text)
                  - creditos (int)
                  - materiales (int)
                  - componentes (int)
                  - celulas_energia (int)
                  - influencia (int)
                  - recursos_lujo (jsonb) → {"materiales_avanzados": {"superconductores": 0, ...}, ...}

                characters:
                  - id (int)
                  - player_id (int)
                  - nombre (text)
                  - stats_json (jsonb) → {"atributos": {"fuerza": 10, "astucia": 15, ...}, ...}
                  - ubicacion (text)
                  - estado (text) → 'Disponible', 'En Misión', 'Herido', etc.
                  - rango (text)

                planet_assets:
                  - id (int)
                  - player_id (int)
                  - system_id (int)
                  - nombre_asentamiento (text)
                  - poblacion (int)
                  - pops_activos (int)
                  - pops_desempleados (int)
                  - infraestructura_defensiva (int)
                  - seguridad (float)
                  - felicidad (float)

                planet_buildings:
                  - id (int)
                  - planet_asset_id (int)
                  - player_id (int)
                  - building_type (text) → 'extractor_materiales', 'generador_energia', etc.
                  - building_tier (int)
                  - is_active (bool)
                  - pops_required (int)
                  - energy_consumption (int)

                luxury_extraction_sites:
                  - id (int)
                  - planet_asset_id (int)
                  - player_id (int)
                  - resource_key (text) → 'superconductores', 'antimateria', etc.
                  - resource_category (text) → 'materiales_avanzados', 'energia_avanzada', etc.
                  - extraction_rate (int)
                  - is_active (bool)

                logs:
                  - id (int)
                  - player_id (int, nullable)
                  - evento_texto (text)
                  - turno (int)
                  - created_at (timestamp)

                Ejemplos de Consultas:

                1. Verificar recursos del jugador:
                   SELECT creditos, materiales, componentes FROM players WHERE id = 1;

                2. Actualizar ubicación de personaje:
                   UPDATE characters SET ubicacion = 'Sala de Máquinas' WHERE id = 5;

                3. Construir edificio (después de verificar recursos):
                   INSERT INTO planet_buildings (planet_asset_id, player_id, building_type, pops_required, energy_consumption)
                   VALUES (1, 1, 'extractor_materiales', 100, 5);

                4. Descontar recursos:
                   UPDATE players SET creditos = creditos - 500, materiales = materiales - 50 WHERE id = 1;

                5. Consultas complejas con JOIN:
                   SELECT p.nombre, c.nombre as comandante, c.ubicacion
                   FROM players p
                   JOIN characters c ON c.player_id = p.id
                   WHERE p.id = 1;
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "Consulta SQL válida en PostgreSQL. Debe ser sintácticamente correcta."
                        }
                    },
                    "required": ["sql_query"]
                }
            },
            {
                "name": "log_ai_action",
                "description": "Registra una acción narrativa o evento importante en los logs del sistema.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_description": {
                            "type": "string",
                            "description": "Descripción de la acción o evento a registrar"
                        },
                        "player_id": {
                            "type": "integer",
                            "description": "ID del jugador asociado (opcional)"
                        }
                    },
                    "required": ["action_description"]
                }
            }
        ]
    }
]


# Mapeo de nombres de función a implementaciones
TOOL_FUNCTIONS = {
    "execute_db_query": execute_db_query,
    "log_ai_action": log_ai_action,
    "get_table_schema": get_table_schema
}
