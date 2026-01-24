-- db_update_stellar_sectors.sql
-- V8.0: Soporte para Sectores Estelares (Megaestructuras a nivel de sistema)

-- 1. Añadir columna system_id a la tabla sectors
-- Permite que un sector esté asociado a un sistema en lugar de a un planeta
ALTER TABLE sectors
ADD COLUMN IF NOT EXISTS system_id INTEGER REFERENCES systems(id) ON DELETE CASCADE;

-- 2. Hacer planet_id nullable para sectores estelares
-- Los sectores estelares tienen system_id pero NO planet_id
ALTER TABLE sectors
ALTER COLUMN planet_id DROP NOT NULL;

-- 3. Añadir constraint: un sector debe tener planet_id O system_id (pero no ambos vacíos)
-- Nota: Comentado porque puede requerir ajustes según tu esquema
-- ALTER TABLE sectors
-- ADD CONSTRAINT chk_sector_parent CHECK (planet_id IS NOT NULL OR system_id IS NOT NULL);

-- 4. Crear índice para consultas por system_id
CREATE INDEX IF NOT EXISTS idx_sectors_system ON sectors(system_id);

-- 5. Comentarios para documentación
COMMENT ON COLUMN sectors.system_id IS 'V8.0: ID del sistema para sectores estelares (NULL para sectores planetarios)';
COMMENT ON COLUMN sectors.planet_id IS 'ID del planeta para sectores planetarios (NULL para sectores estelares)';

-- Refrescar esquema de Supabase
NOTIFY pgrst, 'reload config';
