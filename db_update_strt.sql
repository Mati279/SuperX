-- db_update_strt.sql

-- 1. Tabla Singleton para el Estado del Mundo
CREATE TABLE world_state (
    id SERIAL PRIMARY KEY,
    last_tick_processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() - INTERVAL '1 day'),
    is_frozen BOOLEAN DEFAULT FALSE,
    current_tick INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Asegurar que solo exista una fila (Singleton)
CREATE UNIQUE INDEX only_one_row ON world_state ((id IS NOT NULL));
INSERT INTO world_state (id, last_tick_processed_at, is_frozen, current_tick)
VALUES (1, (NOW() - INTERVAL '1 day'), FALSE, 1)
ON CONFLICT DO NOTHING;

-- 2. Cola de Acciones (Para Ventana de Bloqueo)
CREATE TABLE action_queue (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE,
    action_text TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING', -- PENDING, PROCESSED, REJECTED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE
);

-- 3. Tabla de Votos de Freeze
CREATE TABLE freeze_votes (
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE PRIMARY KEY,
    vote_type TEXT NOT NULL, -- 'FREEZE' o 'UNFREEZE'
    voted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. FUNCIÓN ATÓMICA PARA PROCESAR EL TICK
-- Esta es la pieza clave. Usa bloqueo optimista para asegurar que solo una llamada procese el turno.
CREATE OR REPLACE FUNCTION try_process_tick(target_date DATE) 
RETURNS BOOLEAN AS $$
DECLARE
    row_updated BOOLEAN;
BEGIN
    -- Intentamos actualizar la fecha SOLO SI la fecha guardada es menor a la fecha objetivo (hoy)
    -- y si el mundo no está congelado.
    UPDATE world_state
    SET 
        last_tick_processed_at = NOW(),
        current_tick = current_tick + 1
    WHERE id = 1 
      AND (last_tick_processed_at AT TIME ZONE '-03')::DATE < target_date
      AND is_frozen = FALSE
    RETURNING TRUE INTO row_updated;

    -- Si row_updated es NULL (no se actualizó nada), devolvemos FALSE
    RETURN COALESCE(row_updated, FALSE);
END;
$$ LANGUAGE plpgsql;

-- Notificar a la API
NOTIFY pgrst, 'reload config';