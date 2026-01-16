# Guía de Implementación - Sistema Económico MMFR y POPs

## 📋 Resumen

Se ha implementado el sistema completo de **Macroeconomía (MMFR)** y **Población (POPs)** para SuperX Engine. Este documento describe la arquitectura, las decisiones de diseño y los pasos de integración.

---

## 🗂️ Archivos Entregados

### 1. **Base de Datos** - `data/db_update_mmfr_v2.sql`
Extensiones del esquema de la base de datos:

- **Recursos de Lujo (JSONB)**: Campo `recursos_lujo` en la tabla `players` para almacenar los 12 recursos estratégicos en 4 categorías.
- **Tabla `planet_buildings`**: Gestión de edificios planetarios con estado operativo, requisitos de POPs y consumo de energía.
- **Tabla `luxury_extraction_sites`**: Nodos de extracción de recursos de lujo en planetas especiales.
- **Actualizaciones a `planet_assets`**: Campos adicionales para población activa/desempleada, infraestructura defensiva y felicidad.
- **Tabla `economic_config`**: Constantes económicas configurables en runtime.

**Instrucciones de Ejecución**:
```bash
# Ejecutar en tu cliente de Supabase
psql -h <SUPABASE_HOST> -U <USER> -d <DB> -f data/db_update_mmfr_v2.sql
```

---

### 2. **Constantes del Mundo** - `core/world_constants.py`
Actualizado con:

- **`LUXURY_RESOURCES`**: Definición de los 12 recursos de lujo divididos en 4 categorías:
  - Materiales Avanzados: Superconductores, Aleaciones Exóticas, Nanotubos de Carbono
  - Componentes Avanzados: Reactores de Fusión, Chips Cuánticos, Sistemas de Armamento
  - Energía Avanzada: Antimateria, Cristales Energéticos, Helio-3
  - Influencia Avanzada: Data Encriptada, Artefactos de Precursores, Cultura Galáctica

- **`BROKER_PRICES`**: Precios fijos del mercado NPC para recursos base.
  - Materiales: 2 CI
  - Componentes: 5 CI
  - Células de Energía: 3 CI
  - Influencia: 10 CI

- **`ECONOMY_RATES`**: Tasas económicas configurables.
  - Ingreso por POP: 0.5 CI/turno
  - Seguridad Mínima: 0.3 (30%)
  - Seguridad Máxima: 1.2 (120%)
  - Bonus Felicidad Máximo: 0.5 (+50%)
  - Tasa Infraestructura->Seguridad: 0.01 (1% por punto)

- **`BUILDING_TYPES`**: Definición completa de 10 tipos de edificios:
  - **Extracción Base**: Extractor de Materiales, Fábrica de Componentes, Planta de Energía, Centro de Relaciones
  - **Industria Pesada**: Fundición Avanzada, Astillero Ligero
  - **Alta Tecnología**: Laboratorio de Investigación
  - **Defensa**: Búnker de Defensa, Escudo Planetario

- **`BUILDING_SHUTDOWN_PRIORITY`**: Orden de desactivación en cascada.

---

### 3. **Motor Económico** - `core/economy_engine.py`
Módulo principal con toda la lógica económica:

#### Funciones de Cálculo:
- `calculate_security_multiplier(infrastructure_defense)`: Calcula seguridad basada en infraestructura.
- `calculate_income(population, security, happiness)`: Fórmula de ingresos de créditos.
- `calculate_building_maintenance(buildings)`: Consumo total de energía.

#### Sistema de Desactivación en Cascada:
- `cascade_shutdown_buildings(planet_asset_id, available_pops, buildings)`: Desactiva edificios automáticamente si falta población.
  - **Orden**: Alta Tecnología → Industria Pesada → Defensa → Extracción (último)
- `reactivate_buildings_if_possible(planet_asset_id, available_pops, buildings)`: Reactiva edificios cuando hay POPs disponibles.

#### Procesamiento de Recursos:
- `process_planet_production(planet_asset, buildings)`: Suma la producción de todos los edificios activos.
- `apply_maintenance_costs(player_id, planet_asset, buildings)`: Deduce energía consumida.
- `process_luxury_resource_extraction(player_id)`: Extrae recursos de lujo de todos los sitios activos.

#### Orquestador Principal:
- `run_economy_tick_for_player(player_id)`: Ejecuta el ciclo económico completo para un jugador.
- `run_global_economy_tick()`: Procesa todos los jugadores en el tick global.

**Orden de Ejecución por Tick**:
1. Por cada planeta del jugador:
   - Calcular seguridad (infraestructura → multiplicador)
   - Calcular ingresos (POPs × seguridad × felicidad)
   - Obtener edificios del planeta
   - Ejecutar desactivación/reactivación en cascada
   - Calcular producción de edificios activos
   - Aplicar mantenimiento energético
2. Extraer recursos de lujo globales
3. Actualizar recursos del jugador en DB

---

### 4. **Integración en Time Engine** - `core/time_engine.py`
Se completaron las fases vacías:

```python
def _phase_macroeconomics():
    """Fase 4: Economía Macro (MMFR)"""
    from core.economy_engine import run_global_economy_tick
    run_global_economy_tick()

def _phase_social_logistics():
    """Fase 5: Logística Social y POPs"""
    # La desactivación en cascada ya se maneja en economy_engine
    # Esta fase queda reservada para:
    # - Crecimiento/declive de población
    # - Eventos de felicidad
    # - Migraciones entre planetas
    pass
```

---

### 5. **Repositorio de Datos** - `data/planet_repository.py`
Funciones helper para interactuar con la base de datos:

#### Gestión de Activos Planetarios:
- `get_planet_asset(planet_id, player_id)`: Obtiene un activo planetario.
- `get_all_player_planets(player_id)`: Lista todos los planetas del jugador.
- `create_planet_asset(...)`: Coloniza un nuevo planeta.
- `update_planet_asset(planet_asset_id, updates)`: Actualiza campos del activo.

#### Gestión de Edificios:
- `get_planet_buildings(planet_asset_id)`: Lista edificios de un planeta.
- `build_structure(planet_asset_id, player_id, building_type, tier)`: Construye un edificio.
- `demolish_building(building_id, player_id)`: Destruye un edificio.
- `toggle_building_status(building_id, is_active)`: Activa/desactiva manualmente.

#### Gestión de Recursos de Lujo:
- `create_luxury_extraction_site(...)`: Crea un sitio de extracción.
- `get_luxury_extraction_sites(planet_asset_id)`: Lista sitios del planeta.
- `decommission_luxury_site(site_id, player_id)`: Desactiva sitio.

---

## 🔧 Pasos de Integración

### 1. Ejecutar Script SQL
```bash
# Conectar a tu base de datos Supabase
psql -h db.abcdefg.supabase.co -U postgres -d postgres -f data/db_update_mmfr_v2.sql
```

O ejecutar directamente en el SQL Editor de Supabase.

### 2. Verificar Imports
Asegúrate de que todos los módulos se importan correctamente:

```python
# En cualquier módulo UI o servicio
from core.economy_engine import run_economy_tick_for_player
from data.planet_repository import build_structure, get_planet_buildings
from core.world_constants import BUILDING_TYPES, LUXURY_RESOURCES, BROKER_PRICES
```

### 3. Probar el Tick Económico
Puedes forzar un tick manualmente para verificar el funcionamiento:

```python
# En la consola de Streamlit o script de prueba
from core.time_engine import debug_force_tick

debug_force_tick()  # Ejecuta un tick completo incluyendo economía
```

### 4. Crear UI para Gestión de Edificios
Ejemplo básico para construir un edificio:

```python
import streamlit as st
from data.planet_repository import build_structure, get_planet_buildings
from core.world_constants import BUILDING_TYPES

# Suponiendo que tienes un planet_asset_id y player_id
planet_asset_id = st.session_state.get("current_planet_asset_id")
player_id = st.session_state.get("player_id")

# Mostrar edificios disponibles
st.subheader("Construir Edificio")
building_options = list(BUILDING_TYPES.keys())
selected_building = st.selectbox("Tipo de Edificio", building_options)

if st.button("Construir"):
    result = build_structure(planet_asset_id, player_id, selected_building)
    if result:
        st.success(f"Edificio {BUILDING_TYPES[selected_building]['name']} construido!")
    else:
        st.error("Error al construir el edificio.")

# Mostrar edificios existentes
st.subheader("Edificios del Planeta")
buildings = get_planet_buildings(planet_asset_id)
for building in buildings:
    building_type = building["building_type"]
    definition = BUILDING_TYPES.get(building_type, {})
    status = "✅ Activo" if building["is_active"] else "❌ Desactivado"
    st.write(f"{definition.get('name', 'Desconocido')} - {status}")
```

---

## 📊 Especificación Funcional

### Fórmula de Ingresos
```
Ingreso (CI) = (Población * 0.5) * Seguridad * (1 + Bonus_Felicidad)

Donde:
- Seguridad = 0.3 + (Infraestructura_Defensiva * 0.01), clamped entre 0.3 y 1.2
- Bonus_Felicidad = ((Felicidad - 1.0) / 0.5) * 0.5, solo si Felicidad > 1.0
```

### Sistema de Desactivación en Cascada
1. El motor económico calcula la población total disponible (activos + desempleados).
2. Suma los requisitos de POPs de todos los edificios activos.
3. Si la población es insuficiente:
   - Desactiva edificios en orden de prioridad: Alta Tecnología → Industria → Defensa → Extracción.
   - Los edificios desactivados NO producen pero SIGUEN consumiendo energía (mantenimiento reducido).
4. Si sobra población, reactiva edificios en orden inverso.

### Recursos de Lujo
- **No se compran en el mercado**. Se extraen de planetas con nodos especiales.
- Cada sitio de extracción produce `extraction_rate` unidades por turno.
- Requieren POPs para operar (por defecto 500).
- Se almacenan en el campo JSONB `recursos_lujo` del jugador.

---

## 🎯 Próximos Pasos (Opcionales)

1. **UI de Gestión Planetaria**: Crear páginas de Streamlit para construir/demoler edificios.
2. **Sistema de Construcción con Costos**: Validar recursos antes de construir (actualmente no se verifica).
3. **Mercado de Recursos de Lujo**: Implementar comercio entre jugadores de recursos estratégicos.
4. **Eventos de Población**: Crecimiento demográfico, migraciones, eventos de felicidad.
5. **Mejora de Edificios (Tier 2-3)**: Sistema de upgrade de edificios existentes.
6. **Dashboard Económico**: Panel de visualización de flujos de recursos y producción.

---

## 🐛 Debugging y Logs

El motor económico registra todos los eventos en la tabla `logs`:

```sql
-- Ver logs económicos recientes
SELECT * FROM logs
WHERE evento_texto LIKE '%Economía%' OR evento_texto LIKE '%Edificio%'
ORDER BY id DESC
LIMIT 20;
```

Para ver el detalle de un jugador:

```sql
SELECT * FROM logs
WHERE player_id = 1 AND turno >= 10
ORDER BY id DESC;
```

---

## 📚 Estructura de Datos

### Tabla `planet_buildings`
```sql
CREATE TABLE planet_buildings (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id),
    player_id INTEGER REFERENCES players(id),
    building_type TEXT NOT NULL,
    building_tier INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    pops_required INTEGER NOT NULL,
    energy_consumption INTEGER DEFAULT 0,
    built_at_tick INTEGER DEFAULT 1
);
```

### Tabla `luxury_extraction_sites`
```sql
CREATE TABLE luxury_extraction_sites (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id),
    player_id INTEGER REFERENCES players(id),
    resource_key TEXT NOT NULL,
    resource_category TEXT NOT NULL,
    extraction_rate INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    pops_required INTEGER DEFAULT 500
);
```

### Campo JSONB `recursos_lujo` en `players`
```json
{
    "materiales_avanzados": {
        "superconductores": 0,
        "aleaciones_exoticas": 0,
        "nanotubos_carbono": 0
    },
    "componentes_avanzados": {
        "reactores_fusion": 0,
        "chips_cuanticos": 0,
        "sistemas_armamento": 0
    },
    "energia_avanzada": {
        "antimateria": 0,
        "cristales_energeticos": 0,
        "helio3": 0
    },
    "influencia_avanzada": {
        "data_encriptada": 0,
        "artefactos_antiguos": 0,
        "cultura_galactica": 0
    }
}
```

---

## ✅ Checklist de Validación

- [ ] Script SQL ejecutado sin errores
- [ ] Tabla `planet_buildings` creada correctamente
- [ ] Tabla `luxury_extraction_sites` creada correctamente
- [ ] Campo `recursos_lujo` añadido a `players`
- [ ] Imports de `economy_engine` funcionan sin errores circulares
- [ ] Time engine ejecuta `_phase_macroeconomics()` correctamente
- [ ] Logs muestran "running fase económica global (MMFR)..." en cada tick
- [ ] Se puede construir un edificio desde el repositorio
- [ ] Los edificios se desactivan automáticamente cuando falta población
- [ ] Los recursos de lujo se extraen y actualizan en JSONB

---

## 🎓 Notas Técnicas

### Decisiones de Diseño

1. **JSONB para Recursos de Lujo**: Se eligió JSONB en lugar de 12 columnas separadas por flexibilidad. Permite agregar/modificar recursos sin alterar el esquema.

2. **Desactivación en Cascada**: Se implementa en el propio motor económico, no como job separado. Esto garantiza consistencia en cada tick.

3. **Mantenimiento de Edificios Desactivados**: Los edificios desactivados siguen consumiendo energía (mantenimiento) para representar costos de infraestructura pasiva.

4. **Seguridad Basada en Infraestructura**: Cada 10 puntos de infraestructura defensiva = +10% de seguridad. Máximo 120% (requiere 90+ puntos).

5. **Logging Estructurado**: Todos los eventos económicos se registran con `log_event()` para trazabilidad completa.

---

**Autor**: Claude Sonnet 4.5
**Fecha**: 2026-01-16
**Versión**: 1.0
