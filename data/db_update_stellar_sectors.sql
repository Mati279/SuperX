-- db_update_stellar_sectors.sql
-- V8.0: Soporte para Sectores Estelares (Megaestructuras a nivel de sistema)
--
-- NOTA: El "dueño" de un sector estelar se infiere de systems.controlling_faction_id
-- Los edificios individuales rastrean su propietario via stellar_buildings.player_id

-- 1. Añadir columna system_id a la tabla sectors
-- Permite que un sector esté asociado a un sistema en lugar de a un planeta
ALTER TABLE sectors
ADD COLUMN IF NOT EXISTS system_id INTEGER REFERENCES systems(id) ON DELETE CASCADE;

-- 2. Hacer planet_id nullable para sectores estelares
-- Los sectores estelares tienen system_id pero NO planet_id
ALTER TABLE sectors
ALTER COLUMN planet_id DROP NOT NULL;

-- 3. Crear índice para consultas por system_id
CREATE INDEX IF NOT EXISTS idx_sectors_system ON sectors(system_id);

-- 4. Comentarios para documentación
COMMENT ON COLUMN sectors.system_id IS 'V8.0: ID del sistema para sectores estelares (NULL para sectores planetarios)';
COMMENT ON COLUMN sectors.planet_id IS 'ID del planeta para sectores planetarios (NULL para sectores estelares)';

-- Refrescar esquema de Supabase
NOTIFY pgrst, 'reload config';
