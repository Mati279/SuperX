# Guía de la Herramienta `scan_galaxy_data`

## 📡 Descripción

La herramienta `scan_galaxy_data` permite al Game Master IA consultar el **mapa galáctico procedural** que vive en memoria (RAM) usando el patrón Singleton. Esto le da a la IA "visión" de la geografía del universo, recursos naturales, biomas planetarios y características estelares.

## 🎯 Propósito

**ANTES**: La IA solo tenía acceso a datos SQL (jugadores, edificios, colonias) pero era "ciega" a la geografía del mapa.

**AHORA**: La IA puede responder preguntas como:
- "¿Qué sistemas estelares existen?"
- "¿Hay planetas con agua cerca?"
- "Busca el sistema Dantooine"
- "¿Qué recursos naturales tiene el planeta X?"

## 🔧 Arquitectura

### Componentes Clave

1. **`core/galaxy_generator.py`**: Genera la galaxia proceduralmente usando un seed fijo (42)
2. **`core/world_models.py`**: Define las dataclasses (`Galaxy`, `System`, `Star`, `Planet`, `AsteroidBelt`)
3. **`services/ai_tools.py`**: Implementa la herramienta de function calling

### Flujo de Datos

```
┌─────────────────────┐
│  Game Master IA     │
│  (Gemini 2.5)       │
└──────────┬──────────┘
           │
           │ Function Call: scan_galaxy_data()
           ▼
┌─────────────────────┐
│ ai_tools.py         │
│ scan_galaxy_data()  │
└──────────┬──────────┘
           │
           │ get_galaxy()
           ▼
┌─────────────────────┐
│ galaxy_generator.py │
│ GALAXY (Singleton)  │
└──────────┬──────────┘
           │
           │ Datos procedurales
           ▼
┌─────────────────────┐
│ JSON Response       │
│ (Systems, Planets,  │
│  Resources, Biomes) │
└─────────────────────┘
```

## 📋 Parámetros

### `system_name` (str, opcional)
- Nombre o parte del nombre del sistema a buscar
- Búsqueda parcial habilitada (case-insensitive)
- Ejemplos: `"Dantooine"`, `"Alpha"`, `"Centauri"`

### `scan_mode` (str, default: "SUMMARY")
- **SUMMARY**: Vista general ligera de todos los sistemas
- **DETAILED**: Información completa de un sistema específico

## 📖 Ejemplos de Uso

### Ejemplo 1: Exploración General de la Galaxia

**Pregunta del Jugador**: *"¿Qué sistemas estelares hay en la galaxia?"*

**Invocación de la IA**:
```python
scan_galaxy_data(scan_mode="SUMMARY")
```

**Respuesta JSON** (resumida):
```json
{
  "status": "success",
  "scan_mode": "SUMMARY",
  "total_systems": 30,
  "systems": [
    {
      "id": 0,
      "name": "Alpha-Centauri-42",
      "star_type": "Sol Amarillo",
      "star_class": "G",
      "position": [500, 400],
      "planet_count": 4,
      "asteroid_belt_count": 1
    },
    {
      "id": 1,
      "name": "Beta-Orionis-73",
      "star_type": "Gigante Azul",
      "star_class": "O",
      "position": [485, 415],
      "planet_count": 3,
      "asteroid_belt_count": 2
    }
    // ... 28 sistemas más
  ]
}
```

**Narrativa de la IA**:
> "Los sensores de largo alcance revelan 30 sistemas estelares en el sector. Alpha-Centauri-42, un sistema con estrella amarilla clase G, parece prometedor con 4 planetas orbitales..."

---

### Ejemplo 2: Buscar un Sistema Específico

**Pregunta del Jugador**: *"¿Existe el planeta Dantooine?"*

**Invocación de la IA**:
```python
scan_galaxy_data(system_name="Dantooine", scan_mode="DETAILED")
```

**Respuesta JSON**:
```json
{
  "status": "success",
  "scan_mode": "DETAILED",
  "query": "Dantooine",
  "matches_found": 1,
  "systems": [
    {
      "id": 8,
      "name": "Dantooine-Prime",
      "position": [620, 380],
      "star": {
        "name": "Sol Amarillo",
        "type": "Sol Amarillo",
        "rarity": "Común",
        "class_type": "G",
        "energy_modifier": 1.0,
        "special_rule": "N/A"
      },
      "orbital_rings": {
        "1": {"type": "EMPTY"},
        "2": {
          "type": "PLANET",
          "id": 42,
          "name": "Dantooine-Prime-2",
          "ring": 2,
          "biome": "Pradera Templada",
          "size": "Grande",
          "bonuses": "+Alimentos, +Felicidad",
          "construction_slots": 16,
          "maintenance_mod": 1.0,
          "explored_pct": 18.5,
          "resources": ["Hierro", "Titanio"],
          "moons": [
            {"id": 101, "name": "Luna 1"}
          ]
        },
        "3": {
          "type": "PLANET",
          "id": 43,
          "name": "Dantooine-Prime-3",
          "ring": 3,
          "biome": "Oceánico",
          "size": "Mediano",
          "bonuses": "+Felicidad, +Ciencia",
          "construction_slots": 12,
          "maintenance_mod": 0.9,
          "explored_pct": 22.1,
          "resources": ["Aetherion", "Agua"],
          "moons": []
        }
      }
    }
  ]
}
```

**Narrativa de la IA**:
> "Afirmativo, Comandante. El sistema Dantooine-Prime ha sido localizado en las coordenadas (620, 380). Orbita una estrella clase G y contiene dos planetas colonizables:
> - **Dantooine-Prime-2** (Anillo 2): Un mundo de praderas templadas rico en Hierro y Titanio. Tiene 16 slots de construcción.
> - **Dantooine-Prime-3** (Anillo 3): Un planeta oceánico con depósitos de Aetherion, ideal para investigación científica."

---

### Ejemplo 3: Búsqueda por Patrón

**Pregunta del Jugador**: *"¿Hay sistemas con 'Alpha' en el nombre?"*

**Invocación de la IA**:
```python
scan_galaxy_data(system_name="Alpha", scan_mode="DETAILED")
```

**Resultado**: Devuelve TODOS los sistemas que contengan "Alpha" (ej: Alpha-Centauri-42, Alpha-Draconis-17, etc.)

---

### Ejemplo 4: Encontrar Recursos Específicos

**Pregunta del Jugador**: *"¿Dónde puedo encontrar Antimateria?"*

**Flujo de la IA**:
1. Primero obtiene lista de sistemas con `SUMMARY`
2. Luego itera consultando cada sistema con `DETAILED`
3. Filtra planetas que tengan `"Antimateria"` en su array `resources`
4. Presenta al jugador los resultados

**Código Conceptual** (la IA lo ejecuta internamente):
```python
# Paso 1: Obtener todos los sistemas
all_systems = scan_galaxy_data(scan_mode="SUMMARY")

# Paso 2: Por cada sistema, buscar en detalle
planets_with_antimateria = []
for system in all_systems['systems']:
    details = scan_galaxy_data(system_name=system['name'], scan_mode="DETAILED")
    for ring, body in details['systems'][0]['orbital_rings'].items():
        if body['type'] == 'PLANET' and 'Antimateria' in body['resources']:
            planets_with_antimateria.append({
                'system': system['name'],
                'planet': body['name'],
                'ring': ring
            })

# Paso 3: Narrar resultados
```

**Narrativa de la IA**:
> "Los escaneos de largo alcance han identificado 3 planetas con depósitos de Antimateria:
> 1. **Beta-Orionis-73-4** (Anillo 4) - Estrella Gigante Azul
> 2. **Omega-Pegasi-12-5** (Anillo 5) - Enana Roja
> 3. **Gamma-Cygnus-88-6** (Anillo 6) - Estrella Singular
>
> ¿Deseas establecer una colonia minera en alguno de estos sistemas?"

---

## 🔍 Diferencias con `execute_db_query`

| Aspecto | `scan_galaxy_data` | `execute_db_query` |
|---------|-------------------|-------------------|
| **Fuente de Datos** | Memoria RAM (Singleton) | Base de datos SQL (Supabase) |
| **Tipo de Datos** | Geografía inmutable, recursos naturales | Estado de jugadores, edificios, colonias |
| **Operaciones** | Solo lectura (read-only) | SELECT, INSERT, UPDATE, DELETE |
| **Mutabilidad** | Datos INMUTABLES (generados al inicio) | Datos MUTABLES (cambian durante el juego) |
| **Ejemplos** | "¿Qué planetas hay?", "¿Dónde está Dantooine?" | "¿Cuántos créditos tengo?", "Construir mina" |

### Flujo Correcto para Construcción de Edificios

**Incorrecto** ❌:
```python
# La IA NO puede hacer esto:
scan_galaxy_data(system_name="Alpha-Centauri", action="BUILD_MINE")
```

**Correcto** ✅:
```python
# 1. Primero: Consultar geografía
galaxy_data = scan_galaxy_data(system_name="Alpha-Centauri", scan_mode="DETAILED")

# 2. Validar que el planeta tiene el recurso deseado
if "Hierro" in planet['resources']:
    # 3. Luego: Modificar la BD con execute_db_query
    execute_db_query(
        "INSERT INTO planet_buildings (planet_asset_id, building_type) VALUES (5, 'mina_hierro')"
    )
```

---

## 🚀 Ventajas de esta Implementación

### 1. **Separación de Responsabilidades**
- Datos procedurales (geografía) → RAM (rápido, inmutable)
- Datos de jugadores (progreso) → SQL (persistente, mutable)

### 2. **Escalabilidad**
- La galaxia puede tener 1000+ sistemas sin sobrecargar la BD
- Solo se guarda en SQL lo que el jugador construye/modifica

### 3. **Performance**
- Consultas de geografía son instantáneas (sin latencia de red)
- No hay queries SQL innecesarias para datos que nunca cambian

### 4. **Flexibilidad**
- Modo SUMMARY evita saturar el contexto del LLM
- Búsqueda parcial permite exploración natural ("busca algo con Alpha")

---

## 🛠️ Mantenimiento Futuro

### Posibles Extensiones

1. **Filtros Avanzados**:
   ```python
   scan_galaxy_data(filter_by_resource="Aetherion", scan_mode="SUMMARY")
   # Devuelve solo sistemas con planetas que tengan Aetherion
   ```

2. **Búsqueda por Bioma**:
   ```python
   scan_galaxy_data(filter_by_biome="Oceánico", scan_mode="SUMMARY")
   # Encuentra todos los planetas oceánicos
   ```

3. **Rango de Coordenadas**:
   ```python
   scan_galaxy_data(near_coordinates=(500, 400), radius=100, scan_mode="SUMMARY")
   # Sistemas dentro de 100 unidades del centro galáctico
   ```

4. **Caché Inteligente**:
   - Cachear resultados DETAILED para evitar re-procesar sistemas ya consultados
   - Invalidar caché solo si la galaxia se regenera

---

## 🧪 Testing

### Test Manual desde Python

```python
from services.ai_tools import scan_galaxy_data
import json

# Test 1: Vista general
result = scan_galaxy_data(scan_mode="SUMMARY")
data = json.loads(result)
print(f"Total sistemas: {data['total_systems']}")

# Test 2: Buscar Dantooine
result = scan_galaxy_data(system_name="Dantooine", scan_mode="DETAILED")
data = json.loads(result)
print(f"Encontrados: {data['matches_found']}")

# Test 3: Sistema inexistente
result = scan_galaxy_data(system_name="Tatooine-Fake", scan_mode="DETAILED")
data = json.loads(result)
assert data['status'] == 'error'
```

### Test de Integración con la IA

**Prompt de prueba**:
> "Comandante, ¿puedes escanear la galaxia y decirme qué sistema tiene más planetas?"

**Comportamiento esperado de la IA**:
1. Invoca `scan_galaxy_data(scan_mode="SUMMARY")`
2. Parsea el JSON y cuenta `planet_count` de cada sistema
3. Identifica el sistema con mayor cantidad
4. Invoca `scan_galaxy_data(system_name=<nombre>, scan_mode="DETAILED")` para obtener detalles
5. Narra una respuesta cinematográfica con la información

---

## 📚 Referencias

- **Archivo de implementación**: `services/ai_tools.py` (líneas 185-330)
- **Generador de galaxia**: `core/galaxy_generator.py`
- **Modelos de datos**: `core/world_models.py`
- **Constantes del mundo**: `core/world_constants.py`

---

## ✅ Checklist de Implementación Completado

- [x] Función Python `scan_galaxy_data()` con lógica de serialización de dataclasses
- [x] Modo SUMMARY para vista general ligera
- [x] Modo DETAILED con búsqueda parcial por nombre
- [x] Manejo robusto de errores
- [x] Integración con `TOOL_DECLARATIONS` para Gemini
- [x] Registro en `TOOL_FUNCTIONS` para el dispatcher
- [x] Documentación exhaustiva con ejemplos
- [x] Diferenciación clara con `execute_db_query`

---

**Autor**: Claude Sonnet 4.5
**Fecha**: 2026-01-16
**Versión**: 1.0
