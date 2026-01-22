-- ============================================================
-- SUPERX: DB SETUP - REINICIO TOTAL (ESQUEMA V5.0)
-- ============================================================

-- 1. LIMPIEZA TOTAL (Orden de dependencias invertido)
DROP TABLE IF EXISTS prestige_history CASCADE;
DROP TABLE IF EXISTS market_orders CASCADE;
DROP TABLE IF EXISTS luxury_extraction_sites CASCADE;
DROP TABLE IF EXISTS planet_buildings CASCADE;
DROP TABLE IF EXISTS sectors CASCADE;
DROP TABLE IF EXISTS planet_assets CASCADE;
DROP TABLE IF EXISTS player_exploration CASCADE;
DROP TABLE IF EXISTS planets CASCADE;
DROP TABLE IF EXISTS starlanes CASCADE;
DROP TABLE IF EXISTS system_knowledge CASCADE;
DROP TABLE IF EXISTS systems CASCADE;
DROP TABLE IF EXISTS freeze_votes CASCADE;
DROP TABLE IF EXISTS action_queue CASCADE;
DROP TABLE IF EXISTS active_missions CASCADE;
DROP TABLE IF EXISTS character_knowledge CASCADE;
DROP TABLE IF EXISTS characters CASCADE;
DROP TABLE IF EXISTS ships CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS factions CASCADE;
DROP TABLE IF EXISTS logs CASCADE;
DROP TABLE IF EXISTS generated_images CASCADE;
DROP TABLE IF EXISTS game_config CASCADE;
DROP TABLE IF EXISTS economic_config CASCADE;
DROP TABLE IF EXISTS world_state CASCADE;
DROP TABLE IF EXISTS game_state CASCADE;
DROP TABLE IF EXISTS entities CASCADE;
DROP TABLE IF EXISTS faction_assets CASCADE;

-- 2. CONFIGURACIÓN GLOBAL Y ESTADO DEL MUNDO
CREATE TABLE game_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE economic_config (
    key TEXT PRIMARY KEY,
    value_float DOUBLE PRECISION,
    value_int INTEGER,
    value_text TEXT,
    description TEXT
);

CREATE TABLE world_state (
    id SERIAL PRIMARY KEY,
    last_tick_processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() - INTERVAL '1 day'),
    is_frozen BOOLEAN DEFAULT FALSE,
    current_tick INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabla auxiliar de estado (redundancia para compatibilidad de motores legacy)
CREATE TABLE game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_tick BIGINT NOT NULL DEFAULT 1,
    last_tick_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 3. FACCIONES Y JUGADORES (Estructura central de identidad)
CREATE TABLE factions (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    prestigio NUMERIC NOT NULL DEFAULT 14.29 CHECK (prestigio >= 0 AND prestigio <= 100),
    es_hegemon BOOLEAN DEFAULT FALSE,
    hegemonia_contador INTEGER DEFAULT 0 CHECK (hegemonia_contador >= 0),
    color_hex TEXT DEFAULT '#888888',
    banner_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    pin TEXT NOT NULL,
    faccion_nombre TEXT NOT NULL,
    banner_url TEXT,
    session_token TEXT,
    creditos INTEGER DEFAULT 5000, -- Valores iniciales de balance
    materiales INTEGER DEFAULT 1000,
    componentes INTEGER DEFAULT 200,
    celulas_energia INTEGER DEFAULT 500,
    influencia INTEGER DEFAULT 10,
    datos INTEGER DEFAULT 0,
    prestige INTEGER DEFAULT 0,
    recursos_lujo JSONB DEFAULT '{}'::jsonb,
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. GEOGRAFÍA GALÁCTICA
CREATE TABLE systems (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    x DOUBLE PRECISION NOT NULL,
    y DOUBLE PRECISION NOT NULL,
    star_type TEXT,
    description TEXT DEFAULT '',
    controlling_faction_id BIGINT REFERENCES factions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE planets (
    id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES systems(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    orbital_ring INTEGER NOT NULL,
    biome TEXT,
    size_class TEXT,
    construction_slots INTEGER DEFAULT 3,
    poblacion BIGINT DEFAULT 0,
    resources JSONB,
    bonuses TEXT,
    maintenance_mod DOUBLE PRECISION DEFAULT 1.0,
    explored_pct DOUBLE PRECISION DEFAULT 0.0,
    max_sectors INTEGER DEFAULT 4,
    orbital_owner_id BIGINT REFERENCES players(id),
    surface_owner_id BIGINT REFERENCES players(id),
    is_disputed BOOLEAN DEFAULT FALSE,
    is_known BOOLEAN DEFAULT FALSE,
    mass_class TEXT DEFAULT 'Estándar',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE sectors (
    id BIGSERIAL PRIMARY KEY,
    planet_id BIGINT REFERENCES planets(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('Urbano', 'Llanura', 'Montañoso', 'Inhospito')),
    resource_type TEXT,
    slots INTEGER NOT NULL CHECK (slots >= 0 AND slots <= 3),
    buildings_count INTEGER DEFAULT 0,
    owner_id BIGINT REFERENCES players(id),
    has_outpost BOOLEAN DEFAULT FALSE,
    is_known BOOLEAN DEFAULT FALSE,
    explored_by JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE starlanes (
    id SERIAL PRIMARY KEY,
    system_a_id INTEGER REFERENCES systems(id) ON DELETE CASCADE,
    system_b_id INTEGER REFERENCES systems(id) ON DELETE CASCADE,
    distancia DOUBLE PRECISION DEFAULT 1.0,
    tipo TEXT DEFAULT 'Ruta Comercial Estable',
    nivel_riesgo DOUBLE PRECISION DEFAULT 0.0,
    estado_activo BOOLEAN DEFAULT TRUE,
    CONSTRAINT unique_starlane UNIQUE (system_a_id, system_b_id)
);

-- 5. PERSONAJES Y CONOCIMIENTO
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    apellido TEXT DEFAULT '',
    rango TEXT DEFAULT 'Comandante',
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    es_comandante BOOLEAN DEFAULT FALSE,
    stats_json JSONB,
    loyalty INTEGER DEFAULT 100 CHECK (loyalty >= 0 AND loyalty <= 100),
    location_system_id INTEGER REFERENCES systems(id),
    location_planet_id INTEGER REFERENCES planets(id),
    location_sector_id BIGINT REFERENCES sectors(id),
    portrait_url TEXT,
    is_npc BOOLEAN DEFAULT FALSE,
    estado_id INTEGER DEFAULT 1,
    recruited_at_tick INTEGER DEFAULT 0,
    last_processed_tick INTEGER DEFAULT 0,
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE character_knowledge (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    knowledge_level TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. ACTIVOS, CONSTRUCCIONES Y ECONOMÍA
CREATE TABLE planet_assets (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    system_id INTEGER REFERENCES systems(id),
    planet_id INTEGER REFERENCES planets(id),
    nombre_asentamiento TEXT DEFAULT 'Colonia',
    tipo TEXT DEFAULT 'Base',
    nivel INTEGER DEFAULT 1,
    poblacion DOUBLE PRECISION DEFAULT 0.0,
    pops_activos DOUBLE PRECISION DEFAULT 0.0,
    pops_desempleados DOUBLE PRECISION DEFAULT 0.0,
    seguridad DOUBLE PRECISION DEFAULT 50.0,
    infraestructura_defensiva INTEGER DEFAULT 0,
    recursos_almacenados JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE planet_buildings (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    sector_id BIGINT REFERENCES sectors(id) ON DELETE CASCADE,
    building_type TEXT NOT NULL,
    building_tier INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    pops_required INTEGER NOT NULL,
    energy_consumption INTEGER DEFAULT 0,
    built_at_tick INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE luxury_extraction_sites (
    id SERIAL PRIMARY KEY,
    planet_asset_id INTEGER REFERENCES planet_assets(id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    building_id INTEGER REFERENCES planet_buildings(id) ON DELETE CASCADE,
    resource_key TEXT NOT NULL,
    resource_category TEXT NOT NULL,
    extraction_rate INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    pops_required INTEGER DEFAULT 500,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE market_orders (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    amount INTEGER NOT NULL,
    price_per_unit INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at_tick INTEGER NOT NULL,
    processed_at_tick INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- 7. LOGS, IMÁGENES Y AUDITORÍA
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    turno INTEGER DEFAULT 1,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    evento_texto TEXT NOT NULL,
    prompt_imagen TEXT,
    fecha_evento TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE generated_images (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    image_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE prestige_history (
    id SERIAL PRIMARY KEY,
    tick INTEGER NOT NULL,
    attacker_faction_id INTEGER REFERENCES factions(id),
    defender_faction_id INTEGER REFERENCES factions(id),
    amount NUMERIC NOT NULL,
    idp_multiplier NUMERIC,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. VALORES INICIALES OBLIGATORIOS
INSERT INTO world_state (current_tick) VALUES (1);
INSERT INTO game_state (id, current_tick) VALUES (1, 1);

INSERT INTO game_config (key, value) VALUES
('system_prompt', 'Actúas como Game Master (GM) para un RPG de ciencia ficción...'),
('world_description', 'El universo conocido se encuentra en una paz frágil...'),
('rules', '1. Las acciones se resuelven mediante el sistema MRG (Margen de Éxito) 2d50...');

-- Refrescar Supabase/PostgREST
NOTIFY pgrst, 'reload config';