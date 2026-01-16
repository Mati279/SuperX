-- ============================================================================
-- SuperX AI RPC Functions Setup
-- Script SQL para Supabase: Habilita Native Function Calling robusto
-- ============================================================================

-- ============================================================================
-- PASO 0: Limpiar funciones existentes (si existen)
-- Esto permite recrear las funciones con nuevos tipos de retorno
-- ============================================================================

DROP FUNCTION IF EXISTS execute_sql_query(TEXT) CASCADE;
DROP FUNCTION IF EXISTS execute_sql_mutation(TEXT) CASCADE;
DROP FUNCTION IF EXISTS get_table_schema_info(TEXT) CASCADE;


-- ============================================================================
-- PASO 1: Función RPC para consultas SELECT (Lectura)
-- Envuelve resultados en JSON array para evitar error de "múltiples filas"
-- ============================================================================

CREATE FUNCTION execute_sql_query(query TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER -- Ejecuta con permisos del owner de la función
AS $$
DECLARE
    result JSONB;
BEGIN
    -- Ejecutar la query y envolver en json_agg
    -- Esto convierte cualquier resultado de múltiples filas en un array JSON
    EXECUTE format('SELECT COALESCE(json_agg(t), ''[]''::json) FROM (%s) t', query)
    INTO result;

    RETURN result;
EXCEPTION
    WHEN OTHERS THEN
        -- Capturar el error real de Postgres y devolverlo
        -- Esto permite que la IA vea el error exacto y se corrija
        RETURN jsonb_build_object(
            'error', true,
            'sqlstate', SQLSTATE,
            'message', SQLERRM,
            'detail', COALESCE(PG_EXCEPTION_DETAIL, 'No hay detalles disponibles'),
            'hint', COALESCE(PG_EXCEPTION_HINT, 'Verifica la sintaxis SQL y nombres de tablas/columnas'),
            'context', COALESCE(PG_EXCEPTION_CONTEXT, 'Sin contexto')
        );
END;
$$;

-- Otorgar permisos de ejecución
GRANT EXECUTE ON FUNCTION execute_sql_query(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION execute_sql_query(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION execute_sql_query(TEXT) TO service_role;


-- ============================================================================
-- PASO 2: Función RPC para consultas de ESCRITURA (UPDATE, INSERT, DELETE)
-- Retorna el número de filas afectadas
-- ============================================================================

CREATE FUNCTION execute_sql_mutation(query TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    affected_rows INTEGER;
    result JSONB;
BEGIN
    -- Ejecutar la consulta de modificación
    EXECUTE query;

    -- Obtener el número de filas afectadas
    GET DIAGNOSTICS affected_rows = ROW_COUNT;

    -- Devolver resultado exitoso
    RETURN jsonb_build_object(
        'success', true,
        'affected_rows', affected_rows,
        'message', format('Operación completada: %s filas afectadas', affected_rows)
    );
EXCEPTION
    WHEN OTHERS THEN
        -- Capturar y devolver el error
        RETURN jsonb_build_object(
            'error', true,
            'success', false,
            'sqlstate', SQLSTATE,
            'message', SQLERRM,
            'detail', COALESCE(PG_EXCEPTION_DETAIL, 'No hay detalles disponibles'),
            'hint', COALESCE(PG_EXCEPTION_HINT, 'Verifica la sintaxis SQL y restricciones de la base de datos'),
            'context', COALESCE(PG_EXCEPTION_CONTEXT, 'Sin contexto')
        );
END;
$$;

-- Otorgar permisos de ejecución
GRANT EXECUTE ON FUNCTION execute_sql_mutation(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION execute_sql_mutation(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION execute_sql_mutation(TEXT) TO service_role;


-- ============================================================================
-- PASO 3: Función auxiliar para obtener esquema de tablas
-- Útil para que la IA pueda explorar la estructura de la base de datos
-- ============================================================================

CREATE FUNCTION get_table_schema_info(table_name_param TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT json_agg(
        json_build_object(
            'column_name', column_name,
            'data_type', data_type,
            'is_nullable', is_nullable,
            'column_default', column_default,
            'character_maximum_length', character_maximum_length
        )
        ORDER BY ordinal_position
    )
    INTO result
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = table_name_param;

    IF result IS NULL THEN
        RETURN jsonb_build_object(
            'error', true,
            'message', format('Tabla "%s" no encontrada en el esquema público', table_name_param)
        );
    END IF;

    RETURN jsonb_build_object(
        'table_name', table_name_param,
        'columns', result
    );
EXCEPTION
    WHEN OTHERS THEN
        RETURN jsonb_build_object(
            'error', true,
            'message', SQLERRM
        );
END;
$$;

-- Otorgar permisos de ejecución
GRANT EXECUTE ON FUNCTION get_table_schema_info(TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION get_table_schema_info(TEXT) TO anon;
GRANT EXECUTE ON FUNCTION get_table_schema_info(TEXT) TO service_role;


-- ============================================================================
-- VERIFICACIÓN: Probar las funciones
-- ============================================================================

-- Comentado por seguridad, descomentar para probar:

-- Test 1: SELECT simple
-- SELECT execute_sql_query('SELECT * FROM players LIMIT 1');

-- Test 2: SELECT que devuelve múltiples filas (esto antes fallaba)
-- SELECT execute_sql_query('SELECT id, nombre FROM players');

-- Test 3: Query con error de sintaxis (debe devolver el error)
-- SELECT execute_sql_query('SELEC * FROM jugadores'); -- Typo intencional

-- Test 4: INSERT (descomentar si quieres probarlo)
-- SELECT execute_sql_mutation('INSERT INTO logs (evento_texto, player_id, turno) VALUES (''Test SQL RPC'', 1, 0)');

-- Test 5: Obtener esquema de tabla
-- SELECT get_table_schema_info('players');

-- ============================================================================
-- NOTAS DE IMPLEMENTACIÓN
-- ============================================================================

/*
 * SEGURIDAD:
 * - SECURITY DEFINER permite que estas funciones se ejecuten con los permisos del owner
 * - Esto es necesario porque la API de Supabase normalmente tiene restricciones RLS
 * - IMPORTANTE: En producción, considera añadir validaciones adicionales:
 *   1. Limitar qué tablas pueden ser accedidas
 *   2. Bloquear comandos peligrosos (DROP, TRUNCATE, etc.)
 *   3. Implementar rate limiting
 *   4. Auditar todas las llamadas en una tabla de logs
 *
 * USO DESDE PYTHON:
 *
 * # Para SELECT:
 * result = supabase.rpc('execute_sql_query', {'query': 'SELECT * FROM players WHERE id = 1'}).execute()
 *
 * # Para INSERT/UPDATE/DELETE:
 * result = supabase.rpc('execute_sql_mutation', {'query': 'UPDATE players SET creditos = 5000 WHERE id = 1'}).execute()
 *
 * # Para obtener esquema:
 * result = supabase.rpc('get_table_schema_info', {'table_name_param': 'players'}).execute()
 *
 * MANEJO DE ERRORES:
 * - Si la query tiene un error, el resultado contendrá 'error': true
 * - La IA puede leer el mensaje de error y autocorregirse
 * - Ejemplo de error:
 *   {
 *     "error": true,
 *     "sqlstate": "42P01",
 *     "message": "relation \"jugadores\" does not exist",
 *     "hint": "Perhaps you meant to reference the table \"players\"."
 *   }
 */
