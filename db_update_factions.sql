-- ============================================================
-- SUPERX: SISTEMA DE FACCIONES Y PRESTIGIO
-- ============================================================
-- Este script crea las tablas necesarias para el sistema de
-- prestigio y hegemonía, incluyendo las 7 facciones iniciales
-- y el historial de transferencias.
--
-- Ejecutar en Supabase SQL Editor
-- ============================================================

-- ============================================================
-- TABLA PRINCIPAL DE FACCIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS factions (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,

    -- Sistema de Prestigio
    prestigio DECIMAL(5,2) DEFAULT 14.29 NOT NULL CHECK (prestigio >= 0 AND prestigio <= 100),

    -- Estado de Hegemonía
    es_hegemon BOOLEAN DEFAULT FALSE,
    hegemonia_contador INTEGER DEFAULT 0 CHECK (hegemonia_contador >= 0),

    -- Personalización Visual
    color_hex TEXT DEFAULT '#888888',
    banner_url TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- DATOS INICIALES: 7 FACCIONES
-- ============================================================

INSERT INTO factions (nombre, descripcion, prestigio, color_hex) VALUES
(
    'Consorcio Estelar',
    'La alianza comercial que domina las rutas de comercio galácticas. Riqueza es poder.',
    14.29,
    '#FFD700'
),
(
    'Hegemonía Marciana',
    'El poder militar forjado en las arenas rojas de Marte. La fuerza lo es todo.',
    14.29,
    '#DC143C'
),
(
    'Colectivo Selenita',
    'Los enigmáticos habitantes del lado oscuro de la Luna. Conocimiento es supervivencia.',
    14.29,
    '#C0C0C0'
),
(
    'Sindicato del Cinturón',
    'Mineros, contrabandistas y supervivientes del vacío. Libertad a cualquier costo.',
    14.29,
    '#8B4513'
),
(
    'Academia Científica',
    'Guardianes del conocimiento y la investigación. La ciencia iluminará el camino.',
    14.29,
    '#4169E1'
),
(
    'Culto de la Máquina',
    'Devotos de la singularidad y la inteligencia artificial. El futuro es sintético.',
    14.29,
    '#9932CC'
),
(
    'Frente Independiente',
    'Colonias rebeldes unidas contra la tiranía. Unidos jamás serán vencidos.',
    14.29,
    '#228B22'
)
ON CONFLICT (nombre) DO NOTHING;

-- ============================================================
-- ÍNDICES PARA CONSULTAS FRECUENTES
-- ============================================================

-- Índice para ordenar por prestigio (leaderboard)
CREATE INDEX IF NOT EXISTS idx_faction_prestigio
ON factions(prestigio DESC);

-- Índice para consultas de hegemón
CREATE INDEX IF NOT EXISTS idx_faction_hegemon
ON factions(es_hegemon) WHERE es_hegemon = TRUE;

-- Índice para búsquedas por nombre
CREATE INDEX IF NOT EXISTS idx_faction_nombre
ON factions(nombre);

-- ============================================================
-- VINCULAR JUGADORES A FACCIONES
-- ============================================================

-- Agregar columna faction_id a players si no existe
ALTER TABLE players
ADD COLUMN IF NOT EXISTS faction_id INTEGER REFERENCES factions(id);

-- Crear índice para consultas de jugadores por facción
CREATE INDEX IF NOT EXISTS idx_players_faction_id
ON players(faction_id);

-- Actualizar faction_id basado en faccion_nombre existente
-- (Esto sincroniza el sistema legacy con el nuevo sistema)
UPDATE players p
SET faction_id = f.id
FROM factions f
WHERE p.faccion_nombre = f.nombre
AND p.faction_id IS NULL;

-- ============================================================
-- TABLA DE HISTORIAL DE TRANSFERENCIAS DE PRESTIGIO
-- ============================================================

CREATE TABLE IF NOT EXISTS prestige_history (
    id SERIAL PRIMARY KEY,

    -- Contexto temporal
    tick INTEGER NOT NULL,

    -- Facciones involucradas
    attacker_faction_id INTEGER REFERENCES factions(id) ON DELETE CASCADE,
    defender_faction_id INTEGER REFERENCES factions(id) ON DELETE CASCADE,

    -- Detalles de la transferencia
    amount DECIMAL(5,2) NOT NULL,
    idp_multiplier DECIMAL(4,2),
    reason TEXT,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para consultas de historial
CREATE INDEX IF NOT EXISTS idx_prestige_history_tick
ON prestige_history(tick DESC);

CREATE INDEX IF NOT EXISTS idx_prestige_history_attacker
ON prestige_history(attacker_faction_id);

CREATE INDEX IF NOT EXISTS idx_prestige_history_defender
ON prestige_history(defender_faction_id);

CREATE INDEX IF NOT EXISTS idx_prestige_history_created
ON prestige_history(created_at DESC);

-- ============================================================
-- TRIGGER PARA AUTO-ACTUALIZAR updated_at
-- ============================================================

-- Función para actualizar timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger en factions
DROP TRIGGER IF EXISTS update_factions_updated_at ON factions;
CREATE TRIGGER update_factions_updated_at
    BEFORE UPDATE ON factions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- CONSTRAINT PARA GARANTIZAR UN SOLO HEGEMÓN
-- ============================================================

-- Esta constraint previene que haya múltiples hegemones simultáneos
-- Solo puede haber una fila con es_hegemon=TRUE
CREATE UNIQUE INDEX IF NOT EXISTS idx_single_hegemon
ON factions (es_hegemon) WHERE es_hegemon = TRUE;

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

-- Vista de ranking de facciones
CREATE OR REPLACE VIEW faction_ranking AS
SELECT
    f.id,
    f.nombre,
    f.prestigio,
    f.es_hegemon,
    f.hegemonia_contador,
    f.color_hex,
    COUNT(DISTINCT p.id) as jugadores_activos,
    CASE
        WHEN f.es_hegemon THEN 'Hegemónico'
        WHEN f.prestigio < 2 THEN 'Colapsado'
        WHEN f.prestigio < 5 THEN 'Irrelevante'
        ELSE 'Normal'
    END as estado_poder
FROM factions f
LEFT JOIN players p ON p.faction_id = f.id
GROUP BY f.id, f.nombre, f.prestigio, f.es_hegemon, f.hegemonia_contador, f.color_hex
ORDER BY f.prestigio DESC;

-- Vista de estadísticas de prestigio por facción
CREATE OR REPLACE VIEW faction_prestige_stats AS
SELECT
    f.id,
    f.nombre,
    f.prestigio as prestigio_actual,
    COALESCE(SUM(CASE WHEN ph.attacker_faction_id = f.id THEN ph.amount ELSE 0 END), 0) as total_ganado,
    COALESCE(SUM(CASE WHEN ph.defender_faction_id = f.id THEN ph.amount ELSE 0 END), 0) as total_perdido,
    COUNT(CASE WHEN ph.attacker_faction_id = f.id THEN 1 END) as veces_atacante,
    COUNT(CASE WHEN ph.defender_faction_id = f.id THEN 1 END) as veces_defensor
FROM factions f
LEFT JOIN prestige_history ph ON ph.attacker_faction_id = f.id OR ph.defender_faction_id = f.id
GROUP BY f.id, f.nombre, f.prestigio
ORDER BY f.prestigio DESC;

-- ============================================================
-- POLÍTICAS DE SEGURIDAD (ROW LEVEL SECURITY)
-- ============================================================

-- Habilitar RLS en las tablas
ALTER TABLE factions ENABLE ROW LEVEL SECURITY;
ALTER TABLE prestige_history ENABLE ROW LEVEL SECURITY;

-- Política: Todos pueden leer facciones
CREATE POLICY "Factions are viewable by everyone"
ON factions FOR SELECT
USING (true);

-- Política: Solo el sistema puede modificar prestigio
CREATE POLICY "Only system can modify prestige"
ON factions FOR UPDATE
USING (auth.role() = 'service_role');

-- Política: Todos pueden leer historial
CREATE POLICY "Prestige history is viewable by everyone"
ON prestige_history FOR SELECT
USING (true);

-- Política: Solo el sistema puede insertar historial
CREATE POLICY "Only system can insert prestige history"
ON prestige_history FOR INSERT
WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- FUNCIONES ÚTILES
-- ============================================================

-- Función para obtener el hegemón actual
CREATE OR REPLACE FUNCTION get_current_hegemon()
RETURNS TABLE (
    faction_id INTEGER,
    faction_name TEXT,
    prestigio DECIMAL(5,2),
    ticks_to_victory INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT id, nombre, prestigio, hegemonia_contador
    FROM factions
    WHERE es_hegemon = TRUE
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Función para validar suma de prestigio = 100
CREATE OR REPLACE FUNCTION validate_prestige_sum()
RETURNS BOOLEAN AS $$
DECLARE
    total_prestige DECIMAL(5,2);
BEGIN
    SELECT SUM(prestigio) INTO total_prestige FROM factions;
    RETURN ABS(total_prestige - 100.0) < 0.1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- NOTIFICAR A POSTGREST PARA RECARGAR SCHEMA
-- ============================================================

NOTIFY pgrst, 'reload schema cache';

-- ============================================================
-- VERIFICACIÓN FINAL
-- ============================================================

-- Mostrar facciones creadas
SELECT
    nombre,
    prestigio,
    es_hegemon,
    color_hex
FROM factions
ORDER BY prestigio DESC;

-- Verificar suma de prestigio
SELECT
    SUM(prestigio) as total_prestigio,
    validate_prestige_sum() as suma_valida
FROM factions;

-- ============================================================
-- FIN DEL SCRIPT
-- ============================================================
