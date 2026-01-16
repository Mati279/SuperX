-- db_update_mmfr_v2.sql
-- Extensiones para el Sistema Económico Avanzado (MMFR) y Población (POPs)

-- 1. RECURSOS DE LUJO (Tier 2)
-- Usando JSONB para almacenar los 12 recursos estratégicos
-- Permite flexibilidad sin crear 12 columnas separadas
ALTER TABLE players
ADD COLUMN recursos_lujo JSONB DEFAULT '{
    "materiales_avanzados": {
        "superconductores": 0,
        "aleaciones_exoticas": 0,
        "nanotubos_carbono": 0
    },
    "componentes_avanzados": {
        "reactores_fusion": 0,
        "chips_cuanticos": 0,
        "sistemas_armamento": 0
    },
    "energia_avanzada": {
        "antimateria": 0,
        "cristales_energeticos": 0,
        "helio3": 0
    },
    "influencia_avanzada": {
        "data_encriptada": 0,
        "artefactos_antiguos": 0,
        "cultura_galáctica": 0
    }
}'::JSONB;

-- 2. TABLA DE EDIFICIOS PLANETARIOS
CREATE TABLE planet_buildings (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,

    -- Identificación del edificio
    building_type TEXT NOT NULL, -- Ej: "extractor_hierro", "fabrica_componentes"
    building_tier INTEGER DEFAULT 1, -- Nivel del edificio (1-3)

    -- Estado operativo
    is_active BOOLEAN DEFAULT TRUE, -- Si está operando o desactivado por falta de POPs
    pops_required INTEGER NOT NULL, -- Cantidad de población necesaria

    -- Producción y consumo
    energy_consumption INTEGER DEFAULT 0, -- Células de energía por turno

    -- Metadatos
    built_at_tick INTEGER DEFAULT 1, -- Turno en que se construyó
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Índice para optimizar consultas por planeta
    CONSTRAINT unique_building_per_planet UNIQUE(planet_asset_id, building_type)
);

-- Índices para mejorar performance en consultas frecuentes
CREATE INDEX idx_buildings_player ON planet_buildings(player_id);
CREATE INDEX idx_buildings_planet_asset ON planet_buildings(planet_asset_id);
CREATE INDEX idx_buildings_active ON planet_buildings(is_active);

-- 3. ACTUALIZAR TABLA planet_assets PARA INCLUIR DATOS DE POBLACIÓN
ALTER TABLE planet_assets
ADD COLUMN pops_activos INTEGER DEFAULT 1000, -- Población trabajando actualmente
ADD COLUMN pops_desempleados INTEGER DEFAULT 0, -- Población sin empleo
ADD COLUMN infraestructura_defensiva INTEGER DEFAULT 0, -- Puntos de defensa (0-100)
ADD COLUMN felicidad FLOAT DEFAULT 1.0; -- Multiplicador de felicidad (0.5 - 1.5)

-- Comentarios para documentación
COMMENT ON COLUMN planet_assets.seguridad IS 'Multiplicador de eficiencia económica (0.0 - 1.0+). Basado en infraestructura defensiva.';
COMMENT ON COLUMN planet_assets.infraestructura_defensiva IS 'Puntos de infraestructura defensiva (0-100). Cada 10 puntos = +10% seguridad.';
COMMENT ON COLUMN planet_assets.pops_activos IS 'Población actualmente empleada en edificios.';
COMMENT ON COLUMN planet_assets.pops_desempleados IS 'Población sin asignar a edificios.';

-- 4. TABLA DE EXTRACCIÓN DE RECURSOS DE LUJO
-- Representa nodos de extracción especiales en planetas
CREATE TABLE luxury_extraction_sites (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,

    -- Tipo de recurso extraído (debe coincidir con las claves en recursos_lujo JSONB)
    resource_key TEXT NOT NULL, -- Ej: "superconductores", "antimateria"
    resource_category TEXT NOT NULL, -- Ej: "materiales_avanzados", "energia_avanzada"

    -- Producción
    extraction_rate INTEGER DEFAULT 1, -- Unidades por turno
    is_active BOOLEAN DEFAULT TRUE,

    -- Requisitos
    pops_required INTEGER DEFAULT 500,
    building_id INTEGER REFERENCES planet_buildings(id) ON DELETE SET NULL, -- Edificio asociado

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_luxury_site UNIQUE(planet_asset_id, resource_key)
);

CREATE INDEX idx_luxury_sites_player ON luxury_extraction_sites(player_id);
CREATE INDEX idx_luxury_sites_planet ON luxury_extraction_sites(planet_asset_id);

-- 5. VALORES DE CONFIGURACIÓN GLOBAL (opcional)
-- Para almacenar constantes económicas que puedan cambiar sin recompilar
CREATE TABLE IF NOT EXISTS economic_config (
    key TEXT PRIMARY KEY,
    value_float FLOAT,
    value_int INTEGER,
    value_text TEXT,
    description TEXT
);

-- Valores iniciales
INSERT INTO economic_config (key, value_float, description) VALUES
('income_base_rate', 0.5, 'Créditos generados por POP por turno (base)'),
('security_min', 0.3, 'Multiplicador mínimo de seguridad'),
('security_max', 1.2, 'Multiplicador máximo de seguridad'),
('happiness_income_bonus', 0.5, 'Bonus máximo por felicidad al 150%')
ON CONFLICT (key) DO NOTHING;

-- Refrescar esquema de Supabase
NOTIFY pgrst, 'reload config';
