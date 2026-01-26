-- =====================================================
-- MIGRACION V17.0: Habilidades Colectivas de Unidad
-- Ejecutar en Supabase SQL Editor
-- =====================================================

-- 1. Nuevas columnas de habilidades en tabla units
-- Cada columna representa el promedio ponderado de las habilidades
-- de los personajes miembros de la unidad.

ALTER TABLE units ADD COLUMN IF NOT EXISTS skill_deteccion INTEGER DEFAULT 0;
ALTER TABLE units ADD COLUMN IF NOT EXISTS skill_radares INTEGER DEFAULT 0;
ALTER TABLE units ADD COLUMN IF NOT EXISTS skill_exploracion INTEGER DEFAULT 0;
ALTER TABLE units ADD COLUMN IF NOT EXISTS skill_sigilo INTEGER DEFAULT 0;
ALTER TABLE units ADD COLUMN IF NOT EXISTS skill_evasion_sensores INTEGER DEFAULT 0;

-- 2. Comentarios de documentacion
COMMENT ON COLUMN units.skill_deteccion IS 'V17.0: Habilidad colectiva de Deteccion. Base: INT + VOL de personajes.';
COMMENT ON COLUMN units.skill_radares IS 'V17.0: Habilidad colectiva de Radares. Base: INT + VOL de personajes.';
COMMENT ON COLUMN units.skill_exploracion IS 'V17.0: Habilidad colectiva de Exploracion. Base: INT + AGI de personajes.';
COMMENT ON COLUMN units.skill_sigilo IS 'V17.0: Habilidad colectiva de Sigilo. Base: AGI + VOL de personajes.';
COMMENT ON COLUMN units.skill_evasion_sensores IS 'V17.0: Habilidad colectiva de Evasion de Sensores. Base: TEC + INT de personajes.';

-- 3. Indice parcial para unidades con habilidades calculadas (optimizacion de queries)
CREATE INDEX IF NOT EXISTS idx_units_skills_calculated
ON units(id) WHERE skill_deteccion > 0;

-- =====================================================
-- FIN MIGRACION V17.0
-- =====================================================
