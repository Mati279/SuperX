-- Migracion: Sistema de Reclutamiento con Candidatos Persistentes
-- Fecha: 2026-01-18

-- Tabla para almacenar candidatos de reclutamiento
CREATE TABLE IF NOT EXISTS recruitment_candidates (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    stats_json JSONB NOT NULL,
    costo INTEGER NOT NULL DEFAULT 100,
    tick_created INTEGER NOT NULL DEFAULT 1,
    is_tracked BOOLEAN DEFAULT FALSE,
    is_being_investigated BOOLEAN DEFAULT FALSE,
    investigation_outcome TEXT DEFAULT NULL,
    discount_applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_candidates_player ON recruitment_candidates(player_id);
CREATE INDEX IF NOT EXISTS idx_candidates_tracked ON recruitment_candidates(player_id, is_tracked);

-- Constraint: Solo un candidato puede estar marcado como seguido por jugador
-- Nota: Esto se maneja en la logica de aplicacion para mayor flexibilidad

COMMENT ON TABLE recruitment_candidates IS 'Candidatos disponibles para reclutamiento en el Centro de Reclutamiento';
COMMENT ON COLUMN recruitment_candidates.is_tracked IS 'Si el jugador marco este candidato para seguimiento (no expira)';
COMMENT ON COLUMN recruitment_candidates.is_being_investigated IS 'Si hay una investigacion en curso sobre este candidato';
COMMENT ON COLUMN recruitment_candidates.investigation_outcome IS 'Resultado de la investigacion: SUCCESS, CRIT_SUCCESS, FAIL, CRIT_FAIL';
COMMENT ON COLUMN recruitment_candidates.discount_applied IS 'Si se aplico descuento por exito critico en investigacion';
