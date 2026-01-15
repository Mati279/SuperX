-- ============================================================
-- SUPERX: DB SETUP - REINICIO TOTAL (CON CASCADE)
-- ============================================================

-- 1. Limpieza inicial (El orden importa, usamos CASCADE para forzar borrado)
DROP TABLE IF EXISTS logs CASCADE;
DROP TABLE IF EXISTS characters CASCADE;
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS game_config CASCADE;

-- 2. Configuración del Juego
CREATE TABLE game_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO game_config (key, value) VALUES
('system_prompt', 'You act as a Game Master (GM) for a sci-fi RPG. Your task is to narrate events, resolve actions, and maintain universe coherence. Always respond with a JSON containing "narrative" and "updates".'),
('world_description', 'The known universe is in a fragile peace under the watchful eye of the Star Consortium. Megacorporations, criminal syndicates, and ancient alien factions compete for power in the shadows. Technology has advanced by leaps and bounds, but the galaxy remains a dangerous place full of mysteries.'),
('rules', '1. Actions are resolved based on character attributes (Strength, Agility, Intellect, Tech, Presence, Will) on a scale of 1 to 20. A higher score increases the probability of success.\n2. The GM (AI) has the final say on the outcome of an action, considering attributes and the situation.\n3. There is no health system (HP) or dice. Success is based on description and attribute logic.');

-- 3. Tabla PLAYERS (Tu Cuenta y Facción)
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,     -- Tu usuario de login
    pin TEXT NOT NULL,               -- Tu PIN de 4 dígitos (encriptado)
    faccion_nombre TEXT NOT NULL,    -- Nombre de tu facción
    banner_url TEXT,                 -- URL del estandarte
    fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Tabla CHARACTERS (Tus Personajes / Comandantes)
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE, -- Si borras el usuario, se borran sus pjs
    nombre TEXT NOT NULL,            -- Nombre del Comandante
    rango TEXT DEFAULT 'Comandante',
    es_comandante BOOLEAN DEFAULT FALSE,
    stats_json JSONB,                -- Ficha completa (Bio, Atributos, Habilidades)
    estado TEXT DEFAULT 'Activo',    
    ubicacion TEXT DEFAULT 'Base Principal',
    fecha_creacion TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- REGLA: Un jugador solo puede tener un Comandante activo a la vez.
CREATE UNIQUE INDEX idx_unico_comandante 
ON characters (player_id) 
WHERE es_comandante = TRUE;

-- 5. Tabla LOGS (Historial de Eventos)
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    turno INTEGER DEFAULT 1,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE, -- Vinculado al jugador
    evento_texto TEXT NOT NULL,
    prompt_imagen TEXT,
    fecha_evento TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Refrescar la API de Supabase
NOTIFY pgrst, 'reload config';