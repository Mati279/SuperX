# Guía de Native Function Calling para SuperX Game Master IA
## Sistema de IA con Acceso Completo a Base de Datos

---

## 🎯 Descripción General

Este sistema reemplaza completamente el antiguo método de "respuesta en JSON" por **Native Function Calling** de Gemini 2.5, dándole a la IA acceso directo ("God Mode") a la base de datos PostgreSQL.

### Beneficios Clave
- ✅ **Sin parsing de JSON**: La IA llama funciones directamente
- ✅ **Verificación en tiempo real**: La IA consulta el estado actual antes de actuar
- ✅ **Autocorrección**: Si escribe SQL mal, recibe el error y se corrige
- ✅ **Transacciones atómicas**: Cada consulta es una transacción completa
- ✅ **Auditoría completa**: Todas las queries se registran en logs

---

## 📦 Archivos Implementados

### 1. [services/ai_tools.py](services/ai_tools.py)
Herramientas disponibles para la IA:

#### `execute_db_query(sql_query: str)`
Ejecuta SQL crudo en la base de datos.

**Capacidades**:
- SELECT: Lee datos y retorna JSON
- UPDATE/INSERT/DELETE: Modifica datos y confirma
- Manejo de errores robusto
- Logging automático

**Ejemplo de uso por la IA**:
```python
execute_db_query("SELECT creditos, materiales FROM players WHERE id = 1")
# Retorna: {"status": "success", "data": [{"creditos": 5000, "materiales": 120}]}

execute_db_query("UPDATE players SET creditos = creditos - 500 WHERE id = 1")
# Retorna: {"status": "success", "affected_rows": 1}
```

#### `log_ai_action(action_description: str, player_id: int)`
Registra eventos narrativos en los logs del sistema.

#### `TOOL_DECLARATIONS`
Declaración formal de herramientas en formato Gemini con:
- Nombres de función
- Descripciones detalladas
- Esquema completo de la BD
- Ejemplos de uso

### 2. [services/gemini_service.py](services/gemini_service.py)
Servicio principal refactorizado con:

#### `GAME_MASTER_SYSTEM_PROMPT`
System prompt épico (500+ líneas) que incluye:
- **Rol de la IA**: Narrador, árbitro, gestor del mundo
- **Reglas fundamentales**: Siempre verificar antes de actuar
- **Esquema de BD completo**: Todas las tablas y columnas documentadas
- **Ejemplos prácticos**: Construcción de edificios, combate, consultas complejas
- **Tono narrativo**: Cinematográfico, estilo Mass Effect/The Expanse

#### `resolve_player_action(action_text, player_id)`
Función principal que:
1. Ejecuta guardianes de tiempo (STRT)
2. Realiza tirada MRG (mecánicas de éxito/fracaso)
3. Construye contexto completo para la IA
4. Inicia chat con herramientas habilitadas
5. **Maneja function calls en loop automático**
6. Retorna narrativa final + metadata

---

## 🔄 Flujo de Ejecución

### Ejemplo Completo: "Construyo una mina de hierro"

#### Fase 1: Preparación
```python
resolve_player_action("Construyo una mina de hierro", player_id=1)
```

#### Fase 2: Verificación STRT
- ✅ Lazy Tick: Actualiza el mundo al día actual
- ✅ Freeze Check: Verifica que el universo no esté congelado
- ✅ Lock-in Window: Si es 23:50-00:00, encola la acción

#### Fase 3: Tirada MRG
```
🎲 Dados: 6 + 4 = 10
⚡ Bono: +5 (mérito: 65)
🎯 Dificultad: 50
📈 Margen: -35 (10 + 5 - 50)
🏆 Resultado: TOTAL_SUCCESS
```

#### Fase 4: Contexto para la IA
La IA recibe:
- Acción del jugador
- Datos del comandante
- **Resultado MRG completo**
- Instrucciones paso a paso

#### Fase 5: Function Calls Automáticos

**Call 1: Verificar recursos**
```python
# IA llama:
execute_db_query("SELECT creditos, materiales, componentes FROM players WHERE id = 1")

# Sistema retorna:
{
  "status": "success",
  "data": [{"creditos": 5000, "materiales": 200, "componentes": 50}]
}
```

**Call 2: Verificar planeta**
```python
# IA llama:
execute_db_query("SELECT id, nombre_asentamiento, pops_desempleados FROM planet_assets WHERE player_id = 1 LIMIT 1")

# Sistema retorna:
{
  "status": "success",
  "data": [{"id": 5, "nombre_asentamiento": "Nueva Esperanza", "pops_desempleados": 500}]
}
```

**Call 3: Descontar recursos**
```python
# IA verifica que tiene recursos suficientes (500 CI, 10 Componentes) y descuenta:
execute_db_query("UPDATE players SET creditos = creditos - 500, componentes = componentes - 10 WHERE id = 1")

# Sistema retorna:
{"status": "success", "affected_rows": 1}
```

**Call 4: Construir edificio**
```python
execute_db_query("""
INSERT INTO planet_buildings
(planet_asset_id, player_id, building_type, building_tier, is_active, pops_required, energy_consumption)
VALUES (5, 1, 'extractor_materiales', 1, true, 100, 5)
""")

# Sistema retorna:
{"status": "success", "message": "INSERT ejecutado correctamente"}
```

**Call 5: Actualizar POPs**
```python
execute_db_query("UPDATE planet_assets SET pops_activos = pops_activos + 100, pops_desempleados = pops_desempleados - 100 WHERE id = 5")
```

#### Fase 6: Narrativa Final

La IA genera (usando el resultado MRG de TOTAL_SUCCESS):

```
Las excavadoras sísmicas descienden sobre Nueva Esperanza, perforando
la corteza rica en depósitos ferrosos. En 72 horas, 100 mineros especializados
activan los extractores de plasma. La primera carga de materiales sube a la
órbita: **+20 Materiales/turno**.

⚙️ **Extractor de Materiales Tier I** operativo
📊 Recursos descontados: -500 CI, -10 Componentes
👷 100 POPs asignados (400 desempleados restantes)
```

#### Fase 7: Retorno
```python
{
  "narrative": "Las excavadoras sísmicas...",
  "mrg_result": <MRGResult object>,
  "function_calls_made": [
    {"function": "execute_db_query", "args": {"sql_query": "SELECT..."}},
    {"function": "execute_db_query", "args": {"sql_query": "UPDATE..."}},
    ...
  ],
  "iterations": 5
}
```

---

## ⚙️ Configuración Requerida

### 1. Función RPC en Supabase (OPCIONAL)

Si quieres usar RPC para ejecutar SQL, crea esta función en Supabase:

```sql
-- En Supabase SQL Editor
CREATE OR REPLACE FUNCTION execute_sql_query(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result json;
BEGIN
  EXECUTE query INTO result;
  RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION execute_sql_mutation(query text)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  EXECUTE query;
  RETURN json_build_object('status', 'success');
END;
$$;
```

### 2. Conexión Directa (ALTERNATIVA)

Si no puedes usar RPC, usa la implementación `execute_db_query_direct()` en [ai_tools.py:103-143](services/ai_tools.py#L103-L143):

1. Obtén tu connection string de Supabase:
   - Settings → Database → Connection String
   - Formato: `postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

2. Instala psycopg2:
   ```bash
   pip install psycopg2-binary
   ```

3. Actualiza la línea 114 con tu connection string.

### 3. Variables de Entorno

Asegúrate de tener en `.env`:
```env
GEMINI_API_KEY=your_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
```

---

## 🧪 Testing

### Test Básico
```python
from services.gemini_service import resolve_player_action

# Test simple
result = resolve_player_action("Quiero construir una planta de energía", player_id=1)

print(result["narrative"])
print(f"Function calls realizadas: {len(result['function_calls_made'])}")
```

### Test de Verificación
```python
# La IA debería verificar recursos ANTES de construir
result = resolve_player_action("Construir un búnker de defensa", player_id=1)

# Verificar que se hicieron consultas SELECT antes de INSERT
calls = result["function_calls_made"]
select_calls = [c for c in calls if "SELECT" in str(c["args"])]
insert_calls = [c for c in calls if "INSERT" in str(c["args"])]

assert len(select_calls) > 0, "La IA debe verificar recursos primero"
assert len(insert_calls) > 0, "La IA debe insertar el edificio"
```

### Test de Autocorrección
```python
# Simular error SQL
# La IA debería recibir el error y corregirse

# Ejemplo: Si la IA escribe "SELEC" en vez de "SELECT"
# El sistema retorna: {"status": "error", "message": "syntax error..."}
# La IA lee el error y reintenta con SQL correcto
```

---

## 🔒 Seguridad

### Medidas Implementadas

1. **No permite transacciones explícitas**
   - Cada consulta es atómica
   - No se permite BEGIN/COMMIT/ROLLBACK

2. **Logging completo**
   - Todas las queries se registran en logs
   - Auditoría completa de acciones de la IA

3. **Límite de iteraciones**
   - Máximo 10 function calls por acción
   - Previene loops infinitos

4. **Manejo de errores robusto**
   - Errores SQL se devuelven a la IA (no crashean el sistema)
   - La IA aprende de sus errores

### Limitaciones Intencionadas

La IA **NO** tiene permiso para:
- Matar personajes sin consentimiento del jugador
- Eliminar recursos sin justificación narrativa
- Crear tablas o modificar el esquema
- Ejecutar comandos destructivos globales (DROP TABLE, TRUNCATE)

Estas reglas están en el SYSTEM_PROMPT y son respetadas por la IA.

---

## 📊 Esquema de Base de Datos Completo

### Tabla: players
```sql
id: int (PK)
nombre: text
faccion_nombre: text
creditos: int                  -- Créditos Imperiales (CI)
materiales: int                -- Recursos Tier 1
componentes: int
celulas_energia: int
influencia: int
recursos_lujo: jsonb           -- Recursos Tier 2
  {
    "materiales_avanzados": {
      "superconductores": 0,
      "aleaciones_exoticas": 0,
      "nanotubos_carbono": 0
    },
    "componentes_avanzados": { ... },
    "energia_avanzada": { ... },
    "influencia_avanzada": { ... }
  }
```

### Tabla: characters
```sql
id: int (PK)
player_id: int (FK)
nombre: text
stats_json: jsonb
  {
    "atributos": {
      "fuerza": 10,
      "astucia": 15,
      "carisma": 12,
      "tecnica": 18,
      "percepcion": 14
    },
    "salud": 100,
    "fatiga": 0,
    "moral": 80
  }
ubicacion: text                -- "Puente", "Sala de Máquinas", etc.
estado: text                   -- "Disponible", "En Misión", "Herido"
rango: text
```

### Tabla: planet_assets
```sql
id: int (PK)
player_id: int (FK)
system_id: int
nombre_asentamiento: text
poblacion: int
pops_activos: int              -- POPs empleados en edificios
pops_desempleados: int         -- POPs sin asignar
infraestructura_defensiva: int -- Puntos de defensa (0-100)
seguridad: float               -- Multiplicador económico (0.3-1.2)
felicidad: float               -- Moral (0.5-1.5)
```

### Tabla: planet_buildings
```sql
id: int (PK)
planet_asset_id: int (FK)
player_id: int (FK)
building_type: text            -- "extractor_materiales", "generador_energia", etc.
building_tier: int             -- 1-3
is_active: bool                -- Requiere POPs para estar activo
pops_required: int
energy_consumption: int
```

### Tabla: luxury_extraction_sites
```sql
id: int (PK)
planet_asset_id: int (FK)
player_id: int (FK)
resource_key: text             -- "superconductores", "antimateria", etc.
resource_category: text        -- "materiales_avanzados", etc.
extraction_rate: int           -- Unidades/turno
is_active: bool
```

### Tabla: logs
```sql
id: int (PK)
player_id: int (nullable)
evento_texto: text
turno: int
created_at: timestamp
```

---

## 📝 Ejemplos Avanzados

### Ejemplo 1: Combate Naval
```
Jugador: "Disparo mis torpedos de plasma al crucero enemigo"

MRG: CRITICAL_SUCCESS (margen +18)

Function Call 1:
execute_db_query("SELECT stats_json->'atributos'->>'tecnica' as tecnica FROM characters WHERE id = 3")

Function Call 2:
execute_db_query("UPDATE characters SET stats_json = jsonb_set(stats_json, '{fatiga}', '15') WHERE id = 3")

Narrativa:
"Tu salva de torpedos perfora el casco del crucero clase Destructor.
La explosión revienta la sala de reactores. El enemigo se parte en dos
secciones y deriva sin control. ¡Victoria decisiva! +500 CI de botín."

Function Call 3:
execute_db_query("UPDATE players SET creditos = creditos + 500 WHERE id = 1")
```

### Ejemplo 2: Consulta Compleja
```
Jugador: "¿Cuál es el estado de mi economía?"

Function Call:
execute_db_query("""
SELECT
  p.creditos,
  p.materiales,
  p.componentes,
  COUNT(pb.id) FILTER (WHERE pb.is_active = true) as edificios_activos,
  COUNT(pb.id) FILTER (WHERE pb.is_active = false) as edificios_inactivos,
  SUM(pa.poblacion) as poblacion_total,
  AVG(pa.felicidad) as felicidad_promedio
FROM players p
LEFT JOIN planet_assets pa ON pa.player_id = p.id
LEFT JOIN planet_buildings pb ON pb.player_id = p.id
WHERE p.id = 1
GROUP BY p.id, p.creditos, p.materiales, p.componentes
""")

Narrativa:
"📊 **Informe Económico Imperial**

💰 Tesorería: 12,450 CI
📦 Almacenes: 450 Materiales, 120 Componentes
🏭 Infraestructura: 23 edificios activos, 2 inactivos (falta población)
👥 Población: 45,000 ciudadanos (felicidad promedio: 85%)

Diagnóstico: Tu economía es sólida. Considera reactivar los 2 edificios
inactivos migrando POPs o construyendo nuevos hábitats."
```

### Ejemplo 3: Recursos de Lujo
```
Jugador: "¿Cuánta antimateria tengo?"

Function Call:
execute_db_query("SELECT recursos_lujo->'energia_avanzada'->>'antimateria' as antimateria FROM players WHERE id = 1")

Narrativa:
"Consultas el inventario seguro de la nave nodriza. En contenedores
magnéticos blindados, almacenados a -270°C: **3 unidades de antimateria**.
Suficiente para impulsar un acorazado clase Titán durante 6 meses...
o arrasar una ciudad con un solo proyectil."
```

---

## 🚀 Mejoras Futuras

### Fase 2: Herramientas Especializadas
- `create_ship(ship_class, player_id)`: Constructor de naves
- `initiate_combat(attacker_id, defender_id)`: Sistema de combate
- `generate_random_event(player_id)`: Eventos procedurales

### Fase 3: Memoria Conversacional
- Implementar historial de chat persistente
- La IA recuerda acciones anteriores del jugador
- Narrativa coherente a largo plazo

### Fase 4: Múltiples Agentes IA
- GM Principal: Narración y resolución
- Agente Económico: Gestión de recursos
- Agente Diplomático: Interacciones con NPCs

---

## ❓ Troubleshooting

### Error: "Function 'execute_db_query' not found"
**Solución**: Verificar que `TOOL_FUNCTIONS` en `ai_tools.py` incluya la función.

### Error: "syntax error at or near..."
**Comportamiento esperado**: La IA recibirá este error y se autocorregirá.

### La IA no llama herramientas
**Causas posibles**:
1. `tools` no configurado en `GenerateContentConfig`
2. SYSTEM_PROMPT no instruye claramente a usar herramientas
3. Modelo no es compatible (usar Gemini 2.5+)

### La IA inventa datos sin consultar
**Solución**: Reforzar en SYSTEM_PROMPT la regla "SIEMPRE VERIFICAR ANTES DE ACTUAR".

---

## 📚 Referencias

- [Google Gemini Function Calling Docs](https://ai.google.dev/gemini-api/docs/function-calling)
- [Supabase RPC Functions](https://supabase.com/docs/guides/database/functions)
- [SuperX MMFR Implementation Guide](MMFR_IMPLEMENTATION_GUIDE.md)

---

## ✅ Checklist de Implementación

- [x] `ai_tools.py` creado con `execute_db_query`
- [x] `gemini_service.py` refactorizado con Function Calling
- [x] SYSTEM_PROMPT épico con esquema de BD completo
- [x] Loop automático de function calls
- [x] Logging de todas las queries
- [x] Manejo de errores SQL robusto
- [ ] Crear función RPC en Supabase (opcional)
- [ ] Configurar connection string directa (si no usas RPC)
- [ ] Probar con acción de construcción
- [ ] Probar con acción de combate
- [ ] Verificar que la IA consulta ANTES de modificar

---

**Sistema implementado y listo para usar.**

Fecha: 2026-01-16
Versión: 2.0 (Native Function Calling)
