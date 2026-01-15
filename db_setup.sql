-- Esquema SQL para Supabase

-- Tabla de configuración del juego
CREATE TABLE game_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Insertar valores iniciales para la configuración del juego
INSERT INTO game_config (key, value) VALUES
('system_prompt', 'Actúas como un Game Master de un juego de rol. Tu objetivo es describir el mundo, los eventos y las consecuencias de las acciones de los jugadores. Debes ser imparcial y seguir las reglas del juego. El formato de respuesta para las acciones debe ser un JSON con "narrative" y "updates".'),
('world_description', 'Un mundo de fantasía medieval llamado Eldoria, lleno de magia, criaturas peligrosas y reinos en conflicto.'),
('rules', '1. Los jugadores pueden realizar cualquier acción que se les ocurra.\n2. El éxito de una acción se determina lanzando un dado de 20 caras (d20). Una tirada de 1 es un fallo crítico, una de 20 es un éxito crítico.\n3. El combate se resuelve por turnos. Cada personaje tiene puntos de vida (HP) y puntos de acción (AP).');

-- Tabla de jugadores
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    faccion_nombre TEXT,
    recursos_json JSONB
);

-- Tabla de entidades del juego (NPCs, monstruos, objetos)
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    stats_json JSONB,
    estado TEXT,
    ubicacion TEXT
);

-- Tabla de logs de eventos del juego
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    turno INTEGER,
    evento_texto TEXT NOT NULL,
    prompt_imagen TEXT
);
