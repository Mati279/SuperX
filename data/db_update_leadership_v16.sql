-- =====================================================
-- MIGRACION V16.0: Sistema de Liderazgo Dinamico
-- Ejecutar en Supabase SQL Editor
-- =====================================================

-- 1. Nueva columna is_leader en unit_members
-- Indica cual miembro es el lider de la unidad (solo puede haber 1 por unidad)
ALTER TABLE unit_members ADD COLUMN IF NOT EXISTS is_leader BOOLEAN DEFAULT FALSE;

-- 2. Indice para busqueda rapida del lider de una unidad
CREATE INDEX IF NOT EXISTS idx_unit_members_leader
ON unit_members(unit_id) WHERE is_leader = true;

-- 3. Comentario de documentacion
COMMENT ON COLUMN unit_members.is_leader IS 'V16.0: True si este miembro es el lider de la unidad. Solo puede haber un lider por unidad.';

-- 4. Migrar datos existentes: marcar el primer character de cada unidad como lider
-- Esto asegura compatibilidad con unidades existentes
WITH first_characters AS (
    SELECT DISTINCT ON (unit_id)
        unit_id,
        entity_id,
        slot_index
    FROM unit_members
    WHERE entity_type = 'character'
    ORDER BY unit_id, slot_index ASC
)
UPDATE unit_members um
SET is_leader = true
FROM first_characters fc
WHERE um.unit_id = fc.unit_id
  AND um.entity_id = fc.entity_id
  AND um.entity_type = 'character';

-- =====================================================
-- FIN MIGRACION V16.0
-- =====================================================
