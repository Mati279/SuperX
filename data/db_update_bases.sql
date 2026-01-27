-- db_update_bases.sql
-- Sistema de Bases Militares v1.0
-- Ejecutar en Supabase SQL Editor

-- ============================================
-- TABLA: bases
-- Bases militares construidas en sectores urbanos
-- ============================================

CREATE TABLE IF NOT EXISTS public.bases (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Relaciones
    player_id BIGINT NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    planet_id BIGINT NOT NULL REFERENCES public.planets(id) ON DELETE CASCADE,
    sector_id BIGINT NOT NULL REFERENCES public.sectors(id) ON DELETE CASCADE,

    -- Nivel de base (1-4)
    tier INTEGER NOT NULL DEFAULT 1 CHECK (tier >= 1 AND tier <= 4),

    -- Estado de mejora
    upgrade_in_progress BOOLEAN DEFAULT FALSE,
    upgrade_completes_at_tick INTEGER,
    upgrade_target_tier INTEGER,

    -- Módulos Nivel 1 (desbloqueados al crear la base)
    module_sensor_planetary INTEGER DEFAULT 0,
    module_sensor_orbital INTEGER DEFAULT 0,
    module_defense_ground INTEGER DEFAULT 0,
    module_bunker INTEGER DEFAULT 0,

    -- Módulos Nivel 2 (desbloqueados al mejorar a Nv.2)
    module_defense_aa INTEGER DEFAULT 0,

    -- Módulos Nivel 3 (desbloqueados al mejorar a Nv.3)
    module_defense_missile INTEGER DEFAULT 0,
    module_energy_shield INTEGER DEFAULT 0,

    -- Módulos Nivel 4 (desbloqueados al mejorar a Nv.4)
    module_planetary_shield INTEGER DEFAULT 0,

    -- Timestamps
    created_at_tick INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_bases_player_id ON public.bases(player_id);
CREATE INDEX IF NOT EXISTS idx_bases_planet_id ON public.bases(planet_id);
CREATE INDEX IF NOT EXISTS idx_bases_sector_id ON public.bases(sector_id);
CREATE INDEX IF NOT EXISTS idx_bases_upgrade_pending ON public.bases(upgrade_in_progress, upgrade_completes_at_tick)
    WHERE upgrade_in_progress = TRUE;

-- Restricción: Solo una base por sector
CREATE UNIQUE INDEX IF NOT EXISTS idx_bases_unique_sector ON public.bases(sector_id);

-- Trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_bases_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bases_updated_at ON public.bases;
CREATE TRIGGER trg_bases_updated_at
    BEFORE UPDATE ON public.bases
    FOR EACH ROW
    EXECUTE FUNCTION update_bases_updated_at();

-- ============================================
-- PERMISOS RLS (Row Level Security)
-- ============================================

ALTER TABLE public.bases ENABLE ROW LEVEL SECURITY;

-- Política: Los jugadores pueden ver sus propias bases
DROP POLICY IF EXISTS "Players can view own bases" ON public.bases;
CREATE POLICY "Players can view own bases" ON public.bases
    FOR SELECT
    USING (true);  -- Todas las bases son visibles (información pública de defensa)

-- Política: Los jugadores solo pueden modificar sus propias bases
DROP POLICY IF EXISTS "Players can modify own bases" ON public.bases;
CREATE POLICY "Players can modify own bases" ON public.bases
    FOR ALL
    USING (auth.uid()::text = player_id::text);

-- ============================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- ============================================

COMMENT ON TABLE public.bases IS 'Bases militares construidas en sectores urbanos. Niveles 1-4 con módulos desbloqueables.';

COMMENT ON COLUMN public.bases.tier IS 'Nivel de la base (1-4). Determina qué módulos están disponibles.';
COMMENT ON COLUMN public.bases.upgrade_in_progress IS 'True si la base está siendo mejorada.';
COMMENT ON COLUMN public.bases.upgrade_completes_at_tick IS 'Tick en el que se completará la mejora.';
COMMENT ON COLUMN public.bases.module_sensor_planetary IS 'Nivel del Sensor Planetario. Detecta incursiones terrestres.';
COMMENT ON COLUMN public.bases.module_sensor_orbital IS 'Nivel del Sensor Orbital. Detecta flotas en órbita.';
COMMENT ON COLUMN public.bases.module_defense_ground IS 'Nivel de Defensas Terrestres. Combate ejércitos invasores.';
COMMENT ON COLUMN public.bases.module_bunker IS 'Nivel del Búnker. Protege población civil.';
COMMENT ON COLUMN public.bases.module_defense_aa IS 'Nivel de Defensas Anti-Aéreas. Mitiga bombardeos. Requiere Nv.2.';
COMMENT ON COLUMN public.bases.module_defense_missile IS 'Nivel de Defensas Anti-Misiles. Intercepta misiles. Requiere Nv.3.';
COMMENT ON COLUMN public.bases.module_energy_shield IS 'Nivel del Escudo de Energía. Protege el sector. Requiere Nv.3.';
COMMENT ON COLUMN public.bases.module_planetary_shield IS 'Nivel del Escudo Planetario. Cubre todo el planeta. Requiere Nv.4.';
