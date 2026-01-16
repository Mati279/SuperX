# 🏛️ Sistema de Prestigio y Hegemonía v2.0

## ✅ IMPLEMENTACIÓN COMPLETA

El **Sistema de Prestigio y Hegemonía** ha sido implementado exitosamente en SuperX Engine. Este documento describe la arquitectura, uso y configuración del sistema.

---

## 📋 TABLA DE CONTENIDOS

1. [Visión General](#visión-general)
2. [Arquitectura](#arquitectura)
3. [Instalación](#instalación)
4. [Mecánicas del Sistema](#mecánicas-del-sistema)
5. [Uso en el Juego](#uso-en-el-juego)
6. [Casos de Prueba](#casos-de-prueba)
7. [Configuración Avanzada](#configuración-avanzada)
8. [API de Desarrollo](#api-de-desarrollo)

---

## 🎯 VISIÓN GENERAL

### ¿Qué es el Sistema de Prestigio?

El Sistema de Prestigio es un recurso competitivo de **suma cero** que representa el poder político de las 7 facciones galácticas. El prestigio total siempre es exactamente 100%, y cada facción compite por obtener más prestigio que las demás.

### Características Clave

- ✅ **Suma Cero Estricta**: El prestigio total siempre = 100%
- ✅ **Anti-Bullying**: Protección contra dominación descontrolada
- ✅ **Hegemonía Temporal**: Condición de victoria por mantener >25% durante 20 ticks
- ✅ **Fricción Galáctica**: Redistribución automática en cada tick
- ✅ **Riesgo Asimétrico**: Atacar "hacia arriba" da más recompensa

### 7 Facciones Iniciales

| Facción | Descripción | Color |
|---------|-------------|-------|
| Consorcio Estelar | Alianza comercial | 🟡 Dorado |
| Hegemonía Marciana | Poder militar | 🔴 Carmesí |
| Colectivo Selenita | Habitantes lunares | ⚪ Plata |
| Sindicato del Cinturón | Mineros y contrabandistas | 🟤 Marrón |
| Academia Científica | Guardianes del conocimiento | 🔵 Azul |
| Culto de la Máquina | Devotos de la IA | 🟣 Púrpura |
| Frente Independiente | Colonias rebeldes | 🟢 Verde |

Cada facción comienza con **14.29%** de prestigio (100/7).

---

## 🏗️ ARQUITECTURA

### Estructura de Archivos Creados

```
SuperX/
├── core/
│   ├── prestige_constants.py      # Constantes del sistema
│   └── prestige_engine.py          # Motor de cálculos
├── data/
│   └── faction_repository.py       # Acceso a BD de facciones
├── ui/
│   ├── prestige_widget.py          # Componentes visuales
│   └── diplomacy_page.py           # Página de diplomacia
├── db_update_factions.sql          # Schema de BD
└── SISTEMA_PRESTIGIO_README.md     # Esta documentación
```

### Modificaciones a Archivos Existentes

- ✅ `core/time_engine.py` - Fase 3 del tick ahora procesa prestigio
- ✅ `ui/main_game_page.py` - Agregada navegación a Diplomacia
- ✅ `ui/main_game_page.py` - Widget de prestigio en sidebar

### Base de Datos

**Nuevas Tablas:**
- `factions` - Datos de las 7 facciones
- `prestige_history` - Historial de transferencias

**Modificaciones:**
- `players.faction_id` - Foreign key a facciones

---

## 📦 INSTALACIÓN

### Paso 1: Ejecutar el Script SQL

Ejecuta el siguiente script en tu panel de Supabase (SQL Editor):

```bash
# En tu navegador, abre Supabase Dashboard
# Ve a: SQL Editor > New Query
# Copia y pega el contenido de: db_update_factions.sql
# Ejecuta el script
```

El script creará:
- Tabla `factions` con las 7 facciones iniciales
- Tabla `prestige_history` para auditoría
- Columna `faction_id` en `players`
- Índices optimizados
- Vistas útiles (`faction_ranking`, `faction_prestige_stats`)
- Funciones SQL auxiliares

### Paso 2: Verificar la Instalación

Ejecuta esta query en Supabase para verificar:

```sql
SELECT
    nombre,
    prestigio,
    es_hegemon
FROM factions
ORDER BY prestigio DESC;
```

Deberías ver las 7 facciones con 14.29% cada una.

### Paso 3: Sincronizar Jugadores Existentes

Si ya tienes jugadores en tu base de datos, ejecuta:

```sql
UPDATE players p
SET faction_id = f.id
FROM factions f
WHERE p.faccion_nombre = f.nombre
AND p.faction_id IS NULL;
```

Esto vinculará automáticamente a los jugadores con sus facciones.

### Paso 4: Reiniciar la Aplicación

```bash
# Detén la aplicación si está corriendo
# Ctrl+C

# Inicia nuevamente
streamlit run app.py
```

---

## ⚙️ MECÁNICAS DEL SISTEMA

### 1. Índice de Disparidad de Poder (IDP)

El IDP determina cuánto prestigio se transfiere en combates PVP:

```
IDP = max(0, 1 + (P_Defensor - P_Atacante) / 20)
Transferencia = Base_Evento × IDP
```

**Ejemplos:**

| Atacante | Defensor | IDP | Transferencia (base=1.0) |
|----------|----------|-----|--------------------------|
| 10% | 25% | 1.75 | 1.75% |
| 15% | 15% | 1.0 | 1.0% |
| 30% | 10% | 0.0 | 0% (anti-bullying) |

**Hard Cap Anti-Bullying:**
Si el atacante tiene ≥20% más prestigio que el defensor, IDP=0 y **no hay transferencia**.

### 2. Fricción Galáctica (Cada Tick)

**Impuesto Imperial:**
- Facciones con >20% de prestigio pierden 0.5% por tick

**Subsidio de Supervivencia:**
- Facciones con <5% de prestigio reciben subsidio
- El subsidio proviene del impuesto imperial
- Se distribuye equitativamente entre todas las facciones débiles

**Ejemplo:**
- Facción A: 30% → Pierde 0.5% = 29.5%
- Facción B: 25% → Pierde 0.5% = 24.5%
- Facción C: 3% → Recibe 1.0% = 4.0% (si solo ella está <5%)

### 3. Protocolo de Hegemonía (Buffer 25/20)

| Evento | Umbral | Efecto |
|--------|--------|--------|
| **Ascenso** | ≥25% | Inicia contador de victoria (20 ticks) |
| **Mantener** | 20-25% | Buffer: mantiene estatus de hegemón |
| **Caída** | <20% | Pierde estatus y resetea contador |
| **Victoria** | Contador=0 | ¡La facción GANA la partida! |

**Regla de Amortiguación:**
- Ascenso: >25%
- Caída: <20%
- Entre 20-25% el hegemón mantiene su estatus (zona de buffer)

Esto previene ping-pong de hegemonía por maniobras tácticas menores.

### 4. Estados de Poder

| Estado | Umbral | Efectos |
|--------|--------|---------|
| **Hegemónico** 👑 | ≥25% | Contador de victoria activo |
| **Normal** ⭐ | 5-25% | Sin efectos especiales |
| **Irrelevante** ⚠️ | 2-5% | Recibe subsidio |
| **Colapsado** 💀 | <2% | Recibe subsidio prioritario |

---

## 🎮 USO EN EL JUEGO

### Para Jugadores

#### Ver el Balance de Poder

1. Desde cualquier página, mira el **sidebar derecho**
2. Verás un widget compacto mostrando:
   - Hegemón actual (si existe)
   - Contador de victoria
   - O el líder actual si no hay hegemón

#### Página de Diplomacia Galáctica

1. Haz clic en **"Diplomacia Galáctica"** en el menú
2. Verás:
   - **Panel izquierdo**: Tu facción
     - Prestigio actual
     - Posición en el ranking
     - Estadísticas históricas
     - Alertas de estado
   - **Panel derecho**: Ranking completo
     - Todas las facciones ordenadas por prestigio
     - Indicadores visuales de estado
     - Contadores de victoria

#### Tabs Disponibles

**📊 Panorama General:**
- Estado del sistema (equilibrio o hegemonía)
- Gráfico de distribución
- Explicación de las mecánicas

**📜 Historial:**
- Transferencias recientes de prestigio
- Eventos PVP con detalles de IDP

**📈 Estadísticas:**
- Comparador de facciones
- Análisis de tu facción
- Tasa de victoria

### Para Game Masters

#### Forzar Tick Manualmente

```python
# En el sidebar hay un botón:
# 🚨 DEBUG: FORZAR TICK

# Esto ejecuta inmediatamente:
# - Fricción galáctica
# - Decremento de contadores
# - Verificación de hegemonía
```

#### Monitorear Logs

Todos los eventos de prestigio se registran en `logs`:

```sql
SELECT * FROM logs
WHERE evento_texto LIKE '%Prestigio%'
ORDER BY id DESC
LIMIT 20;
```

#### Ver Historial Completo

```sql
SELECT
    tick,
    a.nombre as atacante,
    d.nombre as defensor,
    amount,
    idp_multiplier,
    reason
FROM prestige_history ph
JOIN factions a ON a.id = ph.attacker_faction_id
JOIN factions d ON d.id = ph.defender_faction_id
ORDER BY ph.created_at DESC;
```

---

## 🧪 CASOS DE PRUEBA

### Caso 1: Fricción Básica

**Setup:**
- Facción A tiene 30% de prestigio

**Acción:**
- Ejecutar un tick

**Resultado Esperado:**
- Facción A pierde 0.5% → 29.5%
- El 0.5% se redistribuye a facciones <5%

**Verificar:**
```sql
SELECT nombre, prestigio FROM factions WHERE nombre = 'Facción A';
```

### Caso 2: Subsidio de Supervivencia

**Setup:**
- Facción B tiene 3% de prestigio
- Hay fricción de otras facciones

**Acción:**
- Ejecutar un tick

**Resultado Esperado:**
- Facción B recibe subsidio
- Su prestigio aumenta

### Caso 3: Ascenso a Hegemón

**Setup:**
- Facción C tiene 24.5% de prestigio

**Acción:**
- Transferir 1% a Facción C (llega a 25.5%)

**Resultado Esperado:**
- Facción C se convierte en hegemón
- Contador de victoria = 20 ticks
- Log: "👑 Facción C ASCIENDE A HEGEMÓN"

**Verificar:**
```sql
SELECT nombre, prestigio, es_hegemon, hegemonia_contador
FROM factions WHERE nombre = 'Facción C';
```

### Caso 4: Buffer de Hegemonía

**Setup:**
- Facción C es hegemón con 23% de prestigio

**Acción:**
- Ejecutar un tick

**Resultado Esperado:**
- Facción C **mantiene** estatus de hegemón (buffer 25/20)
- NO pierde el estatus porque está >20%

### Caso 5: Caída de Hegemonía

**Setup:**
- Facción C es hegemón con 20.5% de prestigio

**Acción:**
- Transferir -1% (cae a 19.5%)

**Resultado Esperado:**
- Facción C **pierde** estatus de hegemón
- Contador resetea a 0
- Log: "💔 Facción C PIERDE EL ESTATUS DE HEGEMÓN"

### Caso 6: Anti-Bullying

**Setup:**
- Facción D: 40% de prestigio
- Facción E: 5% de prestigio

**Acción:**
- Facción D ataca a Facción E (base=1.0)

**Resultado Esperado:**
- IDP = max(0, 1 + (5-40)/20) = max(0, -0.75) = **0**
- Transferencia = 1.0 × 0 = **0%**
- NO hay cambio de prestigio

### Caso 7: Victoria por Hegemonía

**Setup:**
- Facción F es hegemón con contador = 1

**Acción:**
- Ejecutar un tick

**Resultado Esperado:**
- Contador = 0
- Log: "🏆🏆🏆 ¡¡¡Facción F HA GANADO POR HEGEMONÍA TEMPORAL!!!"
- El tick se detiene (no procesa más fases)

### Caso 8: Suma Cero

**Acción:**
- Después de CUALQUIER operación

**Resultado Esperado:**
```sql
SELECT SUM(prestigio) as total FROM factions;
-- total debe ser 100.00 (±0.01 tolerancia)
```

**Verificar en logs:**
```
✅ Prestigio actualizado correctamente
```

Si aparece:
```
⚠️ ADVERTENCIA: Prestigio total = X% (debería ser 100%)
```

Hay un bug que debe reportarse.

---

## ⚙️ CONFIGURACIÓN AVANZADA

### Ajustar Constantes

Edita [core/prestige_constants.py](core/prestige_constants.py):

```python
# Cambiar umbral de hegemonía
HEGEMONY_THRESHOLD = 30.0  # Ahora se necesita 30% (más difícil)

# Cambiar velocidad de fricción
FRICTION_RATE = 1.0  # Ahora pierde 1% por tick (más rápido)

# Cambiar ticks para victoria
HEGEMONY_VICTORY_TICKS = 30  # Ahora se necesitan 30 ticks
```

### Personalizar Facciones

Edita los datos en `db_update_factions.sql` y re-ejecuta:

```sql
-- Cambiar color de facción
UPDATE factions
SET color_hex = '#FF0000'  -- Rojo
WHERE nombre = 'Tu Facción';

-- Cambiar descripción
UPDATE factions
SET descripcion = 'Nueva descripción épica'
WHERE nombre = 'Tu Facción';
```

### Balanceo de Juego

**Si las facciones se estancan:**
- ⬆️ Aumenta `FRICTION_RATE` (más redistribución)
- ⬇️ Disminuye `HEGEMONY_VICTORY_TICKS` (victorias más rápidas)

**Si hay demasiado caos:**
- ⬇️ Disminuye `FRICTION_RATE` (menos redistribución)
- ⬆️ Aumenta `HEGEMONY_VICTORY_TICKS` (victorias más lentas)

**Si el anti-bullying es muy fuerte:**
- ⬆️ Aumenta `IDP_DIVISOR` de 20 a 30
  - Esto hace que el IDP sea más "suave"
  - Atacar hacia abajo da más recompensa

---

## 🛠️ API DE DESARROLLO

### Registrar Transferencia de Prestigio

```python
from core.prestige_engine import calculate_transfer
from data.faction_repository import record_prestige_transfer
from data.world_repository import get_world_state

# Calcular transferencia
attacker_prestige = 15.0
defender_prestige = 25.0
base_event = 1.0

amount, idp = calculate_transfer(base_event, attacker_prestige, defender_prestige)

# Registrar en historial
world_state = get_world_state()
current_tick = world_state.get('current_tick', 1)

record_prestige_transfer(
    tick=current_tick,
    attacker_faction_id=1,
    defender_faction_id=2,
    amount=amount,
    idp_multiplier=idp,
    reason="Victoria en combate naval"
)

# Aplicar la transferencia
from data.faction_repository import get_prestige_map, batch_update_prestige
from core.prestige_engine import apply_prestige_changes

prestige_map = get_prestige_map()
adjustments = {
    1: +amount,  # Atacante gana
    2: -amount   # Defensor pierde
}

new_prestige_map = apply_prestige_changes(prestige_map, adjustments)
batch_update_prestige(new_prestige_map)
```

### Verificar Estado de Facción

```python
from core.prestige_engine import determine_faction_state, FactionState

prestige = 23.0
is_hegemon = False

state = determine_faction_state(prestige, is_hegemon)

if state == FactionState.HEGEMONIC:
    print("¡Esta facción es hegemónica!")
elif state == FactionState.COLLAPSED:
    print("Esta facción está en colapso")
```

### Obtener Estadísticas

```python
from data.faction_repository import get_faction_statistics

stats = get_faction_statistics(faction_id=1)

print(f"Ganado: {stats['total_gained']}%")
print(f"Perdido: {stats['total_lost']}%")
print(f"Neto: {stats['net_change']}%")
```

### Validar Suma Cero

```python
from core.prestige_engine import validate_zero_sum
from data.faction_repository import get_prestige_map

prestige_map = get_prestige_map()

if validate_zero_sum(prestige_map):
    print("✅ Suma válida: 100%")
else:
    total = sum(prestige_map.values())
    print(f"⚠️ Suma inválida: {total}%")
```

---

## 📚 RECURSOS ADICIONALES

### Archivos de Código

- [core/prestige_constants.py](core/prestige_constants.py) - Todas las constantes
- [core/prestige_engine.py](core/prestige_engine.py) - Lógica de cálculo
- [data/faction_repository.py](data/faction_repository.py) - Acceso a BD
- [ui/prestige_widget.py](ui/prestige_widget.py) - Componentes UI
- [ui/diplomacy_page.py](ui/diplomacy_page.py) - Página completa

### Base de Datos

- [db_update_factions.sql](db_update_factions.sql) - Schema completo

### Vistas SQL Útiles

```sql
-- Ver ranking actual
SELECT * FROM faction_ranking;

-- Ver estadísticas de prestigio
SELECT * FROM faction_prestige_stats;

-- Ver hegemón actual
SELECT * FROM get_current_hegemon();

-- Validar suma de prestigio
SELECT validate_prestige_sum();
```

---

## ❓ FAQ

**P: ¿Qué pasa si dos facciones superan el 25% al mismo tiempo?**
R: El código procesa en orden. La primera en ser evaluada se convierte en hegemón. La constraint `idx_single_hegemon` en BD previene múltiples hegemones.

**P: ¿Puedo cambiar el número de facciones?**
R: Técnicamente sí, pero requiere modificar `TOTAL_FACTIONS` y ajustar el SQL de inicialización. El sistema está optimizado para 7.

**P: ¿Los jugadores pueden cambiar de facción?**
R: Actualmente no está implementado, pero puedes agregar la lógica en `player_repository.py`.

**P: ¿Qué pasa si todos los jugadores están en la misma facción?**
R: El sistema sigue funcionando. La fricción galáctica equilibrará las otras facciones vacías.

**P: ¿Puedo deshabilitar la fricción?**
R: Sí, establece `FRICTION_RATE = 0` en `prestige_constants.py`.

---

## 🎉 ¡Listo para Jugar!

El sistema está completamente implementado y listo para usar. Disfruta de la competencia política galáctica!

**Próximos pasos sugeridos:**
1. Ejecutar el script SQL en Supabase
2. Reiniciar la aplicación
3. Visitar la página de Diplomacia Galáctica
4. Forzar un tick y observar la fricción en acción
5. ¡Que comience la batalla por la hegemonía!

---

*Documento generado el 2026-01-16*
*Sistema de Prestigio y Hegemonía v2.0*
