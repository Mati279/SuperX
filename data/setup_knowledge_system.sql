-- ============================================================
-- MIGRATION: SYSTEMA DE CONOCIMIENTO (Relacional)
-- ============================================================

-- Crear tabla de relaciones de conocimiento
CREATE TABLE IF NOT EXISTS character_knowledge (
    id SERIAL PRIMARY KEY,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    observer_player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    knowledge_level TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Restricción única: Un jugador tiene un solo nivel de conocimiento sobre un personaje
    CONSTRAINT unique_observer_character UNIQUE (character_id, observer_player_id)
);

-- Índices para optimizar búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_knowledge_observer ON character_knowledge(observer_player_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_character ON character_knowledge(character_id);

-- Comentarios
COMMENT ON TABLE character_knowledge IS 'Almacena qué tanto sabe un jugador sobre un personaje específico.';