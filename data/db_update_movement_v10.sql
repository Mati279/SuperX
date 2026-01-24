-- =====================================================
-- MIGRACIÓN V10.0: Motor de Movimiento y Navegación
-- =====================================================
-- Ejecutar en Supabase SQL Editor
-- IMPORTANTE: Hacer backup antes de ejecutar

-- =====================================================
-- 1. NUEVAS COLUMNAS EN TABLA UNITS
-- =====================================================

-- Anillo de ubicación (0 = Sector Estelar, 1-6 = Anillos planetarios)
ALTER TABLE units ADD COLUMN IF NOT EXISTS ring integer DEFAULT 0;

-- ID de starlane (NULL si no está en tránsito interestelar)
ALTER TABLE units ADD COLUMN IF NOT EXISTS starlane_id integer;

-- Control de movimiento
ALTER TABLE units ADD COLUMN IF NOT EXISTS movement_locked boolean DEFAULT false;
ALTER TABLE units ADD COLUMN IF NOT EXISTS transit_end_tick integer;
ALTER TABLE units ADD COLUMN IF NOT EXISTS transit_ticks_remaining integer DEFAULT 0;

-- Datos de tránsito (origen y destino)
ALTER TABLE units ADD COLUMN IF NOT EXISTS transit_origin_system_id integer;
ALTER TABLE units ADD COLUMN IF NOT EXISTS transit_destination_system_id integer;

-- =====================================================
-- 2. ÍNDICES PARA QUERIES OPTIMIZADAS
-- =====================================================

-- Índice para unidades en tránsito que llegan en un tick específico
CREATE INDEX IF NOT EXISTS idx_units_transit_end_tick
ON units(transit_end_tick) WHERE status = 'TRANSIT';

-- Índice compuesto para detección por ubicación
CREATE INDEX IF NOT EXISTS idx_units_location_composite
ON units(location_system_id, ring, location_planet_id, location_sector_id)
WHERE status != 'TRANSIT';

-- Índice para unidades en una starlane específica
CREATE INDEX IF NOT EXISTS idx_units_starlane
ON units(starlane_id) WHERE starlane_id IS NOT NULL;

-- =====================================================
-- 3. TABLA DE HISTORIAL DE TRÁNSITOS (AUDITORÍA)
-- =====================================================

CREATE TABLE IF NOT EXISTS unit_transits (
    id SERIAL PRIMARY KEY,
    unit_id integer NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    player_id integer NOT NULL REFERENCES players(id),

    -- Origen
    origin_system_id integer,
    origin_planet_id integer,
    origin_sector_id bigint,
    origin_ring integer DEFAULT 0,

    -- Destino
    destination_system_id integer,
    destination_planet_id integer,
    destination_sector_id bigint,
    destination_ring integer DEFAULT 0,

    -- Ruta
    starlane_id integer,
    movement_type text NOT NULL,  -- 'sector_surface', 'surface_orbit', 'inter_ring', 'starlane', 'warp'

    -- Tiempos
    started_at_tick integer NOT NULL,
    completed_at_tick integer,
    ticks_required integer NOT NULL,

    -- Costos pagados
    energy_cost integer DEFAULT 0,
    credits_cost integer DEFAULT 0,

    -- Estado del tránsito
    status text DEFAULT 'IN_PROGRESS',  -- 'IN_PROGRESS', 'COMPLETED', 'INTERDICTED', 'CANCELLED'

    -- Metadata
    created_at timestamp with time zone DEFAULT now(),
    completed_at timestamp with time zone
);

-- Índice para tránsitos activos
CREATE INDEX IF NOT EXISTS idx_unit_transits_active
ON unit_transits(unit_id, status) WHERE status = 'IN_PROGRESS';

-- Índice para historial por jugador
CREATE INDEX IF NOT EXISTS idx_unit_transits_player
ON unit_transits(player_id, created_at DESC);

-- =====================================================
-- 4. MODIFICAR TABLA SHIPS PARA ASIGNACIÓN A UNIDADES
-- =====================================================

-- Nueva columna para asignar naves a unidades
ALTER TABLE ships ADD COLUMN IF NOT EXISTS unit_id integer REFERENCES units(id) ON DELETE SET NULL;
ALTER TABLE ships ADD COLUMN IF NOT EXISTS slot_in_unit integer;
ALTER TABLE ships ADD COLUMN IF NOT EXISTS is_transport_auto boolean DEFAULT false;

-- Índice para naves en una unidad
CREATE INDEX IF NOT EXISTS idx_ships_unit
ON ships(unit_id) WHERE unit_id IS NOT NULL;

-- =====================================================
-- 5. TABLA DE DETECCIONES (AUDITORÍA DE ENCUENTROS)
-- =====================================================

CREATE TABLE IF NOT EXISTS detection_events (
    id SERIAL PRIMARY KEY,
    tick integer NOT NULL,

    -- Unidad detectora
    detector_unit_id integer NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    detector_player_id integer NOT NULL REFERENCES players(id),

    -- Unidad detectada
    detected_unit_id integer NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    detected_player_id integer NOT NULL REFERENCES players(id),

    -- Ubicación del encuentro
    location_system_id integer,
    location_starlane_id integer,
    location_ring integer,

    -- Resultado de detección
    detection_type text NOT NULL,  -- 'passive', 'active', 'interdiction'
    mrg_roll integer,              -- Resultado del dado
    mrg_margin integer,            -- Margen de éxito/fallo
    detection_successful boolean NOT NULL,

    -- Interdicción (si aplica)
    interdiction_attempted boolean DEFAULT false,
    interdiction_successful boolean,

    created_at timestamp with time zone DEFAULT now()
);

-- Índice para detecciones por tick
CREATE INDEX IF NOT EXISTS idx_detection_events_tick
ON detection_events(tick);

-- Índice para detecciones de un jugador
CREATE INDEX IF NOT EXISTS idx_detection_events_player
ON detection_events(detector_player_id, created_at DESC);

-- =====================================================
-- 6. COMENTARIOS DE DOCUMENTACIÓN
-- =====================================================

COMMENT ON COLUMN units.ring IS 'V10.0: Anillo de ubicación. 0=Sector Estelar, 1-6=Anillos planetarios';
COMMENT ON COLUMN units.starlane_id IS 'V10.0: ID de starlane si la unidad está en tránsito interestelar';
COMMENT ON COLUMN units.movement_locked IS 'V10.0: True si la unidad acaba de moverse y no puede volver a moverse este tick';
COMMENT ON COLUMN units.transit_end_tick IS 'V10.0: Tick en que termina el tránsito actual';
COMMENT ON COLUMN units.transit_ticks_remaining IS 'V10.0: Ticks restantes de viaje';

COMMENT ON TABLE unit_transits IS 'V10.0: Historial de tránsitos de unidades para auditoría';
COMMENT ON TABLE detection_events IS 'V10.0: Registro de detecciones entre unidades';

-- =====================================================
-- FIN DE MIGRACIÓN V10.0
-- =====================================================
