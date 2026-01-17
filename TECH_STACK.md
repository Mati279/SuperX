# SuperX Engine - Stack Tecnológico

> **Versión:** 2.0
> **Última Actualización:** Enero 2026
> **Estado:** Producción

---

## Resumen Ejecutivo

SuperX es un juego de estrategia espacial persistente que utiliza IA generativa para narrativa dinámica. Este documento congela las decisiones técnicas del proyecto para garantizar estabilidad y evitar cambios arbitrarios.

---

## Stack Principal

### Lenguaje de Programación

| Componente | Tecnología | Versión | Justificación |
|------------|------------|---------|---------------|
| **Backend/Frontend** | Python | 3.10+ | Ecosistema maduro para ML/AI, integración nativa con Streamlit y librerías de IA |

**Requisitos:**
- Python 3.10 mínimo (por uso de `match`, union types `X | Y`, etc.)
- Recomendado: Python 3.11+ para mejor rendimiento

---

### Frontend

| Componente | Tecnología | Versión | Justificación |
|------------|------------|---------|---------------|
| **Framework UI** | Streamlit | 1.30+ | Prototipado rápido, ideal para juegos basados en texto, reactividad automática |
| **Componentes Extra** | extra-streamlit-components | 0.1+ | Manejo de cookies para persistencia de sesión |

**Decisiones de Diseño:**
- **Layout Wide:** Optimizado para dashboards de juego
- **Sidebar Navigation:** Menú persistente para navegación entre secciones
- **Session State:** Gestión de estado tipada con Pydantic models

**Limitaciones Aceptadas:**
- Sin soporte nativo para WebSockets (workaround: polling con `st.rerun()`)
- Renderizado síncrono (aceptable para juegos por turnos)

---

### Backend / Base de Datos

| Componente | Tecnología | Versión | Justificación |
|------------|------------|---------|---------------|
| **BaaS** | Supabase | Cloud | PostgreSQL gestionado, Auth integrado, API REST automática |
| **Base de Datos** | PostgreSQL | 15+ | JSONB para datos flexibles, extensiones geoespaciales disponibles |
| **Cliente Python** | supabase-py | 2.0+ | SDK oficial con soporte para Realtime (futuro) |

**Arquitectura de Datos:**
- **Patrón Repositorio:** Capa `data/*_repository.py` abstrae todas las queries
- **JSONB:** Usado para `stats_json`, `recursos_lujo` (datos semi-estructurados)
- **Foreign Keys:** Cascade delete habilitado para integridad referencial

**Tablas Principales:**
```
players          - Datos de jugadores y recursos
characters       - Personajes y comandantes
planet_assets    - Colonias y asentamientos
planet_buildings - Edificios construidos
systems          - Sistemas estelares (procedural)
planets          - Planetas del universo
starlanes        - Rutas entre sistemas
world_state      - Estado global del juego (singleton)
logs             - Historial de eventos
```

---

### Motor de IA

| Componente | Tecnología | Modelo | Justificación |
|------------|------------|--------|---------------|
| **SDK** | google-genai | 1.0+ | SDK oficial de Google para Gemini |
| **Modelo Texto** | Gemini 2.5 Flash | `gemini-2.5-flash` | Balance costo/rendimiento, function calling nativo |
| **Modelo Imagen** | Imagen 3.0 | `imagen-3.0-generate-001` | Generación de arte (futuro) |

**Configuración del Modelo:**
```python
temperature = 0.7      # Creatividad moderada
max_output_tokens = 1024
top_p = 0.95
function_calling = AUTO
```

**Decisiones de Diseño IA:**
- **System Prompt Desacoplado:** Templates en constantes, no hardcodeados
- **Function Calling:** Herramientas declarativas para consultas a DB
- **Fog of War:** IA con conocimiento limitado (solo datos del jugador)

---

## Patrones Arquitectónicos

### Separación de Responsabilidades

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py                               │
│                   (Entry Point)                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      ui/ Layer                              │
│  - state.py (Session State tipado)                         │
│  - auth_page.py, main_game_page.py, etc.                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   services/ Layer                           │
│  - gemini_service.py (Asistente Táctico)                   │
│  - ai_tools.py (Function Calling)                          │
│  - event_service.py (Eventos Narrativos)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     core/ Layer                             │
│  - economy_engine.py (MMFR System)                         │
│  - time_engine.py (STRT Ticks)                             │
│  - mrg_engine.py (Resolución de Acciones)                  │
│  - models.py (Pydantic Models)                             │
│  ⚠️ NUNCA importa supabase directamente                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                     data/ Layer                             │
│  - database.py (ServiceContainer Singleton)                │
│  - player_repository.py                                    │
│  - planet_repository.py                                    │
│  - character_repository.py                                 │
│  - world_repository.py                                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │      Supabase         │
              │     (PostgreSQL)      │
              └───────────────────────┘
```

### Patrón Repositorio

**Regla:** La capa `core/` NUNCA debe importar `supabase` directamente.

```python
# ❌ INCORRECTO (en core/)
from data.database import supabase
response = supabase.table("players").select("*").execute()

# ✅ CORRECTO (en core/)
from data.player_repository import get_all_players
players = get_all_players()
```

### Inyección de Dependencias

```python
# ServiceContainer (Singleton)
from data.database import get_service_container

container = get_service_container()
db = container.supabase  # Cliente de Supabase
ai = container.ai        # Cliente de Gemini

# Para testing
container.inject_supabase(mock_client)
```

---

## Modelos de Datos Tipados

### Pydantic Models (core/models.py)

```python
class PlayerData(BaseModel):
    id: int
    nombre: str
    creditos: int = 0
    materiales: int = 0
    # ...

class CommanderData(BaseModel):
    id: int
    player_id: int
    nombre: str
    stats_json: Dict[str, Any]
    # ...

class ProductionSummary(BaseModel):
    materiales: int = 0
    componentes: int = 0
    celulas_energia: int = 0
    influencia: int = 0
```

---

## Configuración

### Variables de Entorno (.env)

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR...
GEMINI_API_KEY=AIza...
```

### Constantes (config/app_constants.py)

```python
# Modelos de IA
TEXT_MODEL_NAME = "gemini-2.5-flash"
IMAGE_MODEL_NAME = "imagen-3.0-generate-001"

# Sesión
SESSION_COOKIE_NAME = 'superx_session_token'

# Tiempo (STRT)
LOCK_IN_WINDOW_START_HOUR = 23
LOCK_IN_WINDOW_START_MINUTE = 50
TIMEZONE_NAME = 'America/Argentina/Buenos_Aires'
```

---

## Dependencias (requirements.txt)

```
# Core
streamlit>=1.30.0
supabase>=2.0.0
google-genai>=1.0.0
pydantic>=2.0.0

# Utilidades
python-dotenv>=1.0.0
extra-streamlit-components>=0.1.60
bcrypt>=4.0.0
Pillow>=10.0.0
pandas>=2.0.0

# Testing
pytest>=7.0.0
pytest-mock>=3.0.0
```

---

## Decisiones Congeladas

Las siguientes decisiones están **congeladas** y requieren justificación formal para cambiar:

| Decisión | Status | Razón |
|----------|--------|-------|
| Streamlit como frontend | 🔒 Congelado | Prototipo funcional, cambio requiere reescritura total |
| Supabase como BaaS | 🔒 Congelado | Datos de producción existentes |
| Gemini como motor IA | 🔒 Congelado | Function calling integrado, costo optimizado |
| Python 3.10+ | 🔒 Congelado | Compatibilidad con todas las dependencias |
| Patrón Repositorio | 🔒 Congelado | Testabilidad y separación de capas |
| Pydantic para modelos | 🔒 Congelado | Validación y serialización robusta |

---

## Roadmap Técnico

### Fase Actual (v2.0)
- [x] ServiceContainer con inyección de dependencias
- [x] Modelos tipados con Pydantic
- [x] Patrón Repositorio completo
- [x] Batch updates en economy_engine

### Fase Futura (v2.1+)
- [ ] Supabase Realtime para eventos multi-jugador
- [ ] Cache con Redis para queries frecuentes
- [ ] Background jobs con Celery para ticks
- [ ] WebSocket opcional para notificaciones

---

## Testing

### Estrategia

1. **Unit Tests:** Funciones puras en `core/` (cálculos económicos, MRG)
2. **Integration Tests:** Repositorios con DB de test
3. **Mocks:** ServiceContainer permite inyectar clientes mock

### Ejemplo de Test

```python
def test_calculate_income():
    income = calculate_income(
        population=1000,
        security=1.0,
        happiness=1.0
    )
    assert income > 0

def test_economy_with_mock_repository(mocker):
    mock_repo = mocker.patch('data.player_repository.get_player_finances')
    mock_repo.return_value = {"creditos": 1000}
    # ...
```

---

## Contacto y Contribuciones

Para propuestas de cambios en el stack tecnológico, abrir un Issue con:
1. Justificación técnica
2. Análisis de impacto
3. Plan de migración
4. Timeline propuesto

---

*Documento generado como parte del refactor arquitectónico v2.0*
