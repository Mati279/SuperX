-- db_update_mmfr.sql

-- 1. Añadir Recursos Base a la tabla PLAYERS
ALTER TABLE players 
ADD COLUMN materiales INTEGER DEFAULT 500,
ADD COLUMN componentes INTEGER DEFAULT 200,
ADD COLUMN celulas_energia INTEGER DEFAULT 100,
ADD COLUMN influencia INTEGER DEFAULT 10;

-- 2. Crear tabla de ACTIVOS PLANETARIOS (Para gestionar Seguridad y Población)
-- Esta tabla vincula los planetas generados proceduralmente con datos persistentes de la facción.
CREATE TABLE planet_assets (
    id SERIAL PRIMARY KEY,
    planet_id INTEGER NOT NULL, -- ID del planeta generado por el sistema procedural
    system_id INTEGER NOT NULL, -- ID del sistema solar
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    
    -- Economía Local
    poblacion INTEGER DEFAULT 1000,   -- Base para generación de Créditos
    seguridad FLOAT DEFAULT 1.0,      -- Multiplicador (1.0 = 100%). S
    
    -- Estado
    nombre_asentamiento TEXT DEFAULT 'Colonia Principal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Restricción: Un jugador solo puede tener un asentamiento principal por planeta (por ahora)
    UNIQUE(planet_id, player_id)
);

-- Refrescar la API de Supabase
NOTIFY pgrst, 'reload config';