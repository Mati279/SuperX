-- Esquema SQL para Supabase

-- 1. Tabla de Configuración del Juego
-- Almacena las reglas y la ambientación del universo.
DROP TABLE IF EXISTS game_config;
CREATE TABLE game_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Insertar valores iniciales para un entorno de ciencia ficción galáctica.
INSERT INTO game_config (key, value) VALUES
('system_prompt', 'Actúas como un Game Master (GM) de un juego de rol de ciencia ficción. Tu tarea es narrar eventos, resolver acciones y mantener la coherencia del universo. Responde siempre con un JSON que contenga "narrative" y "updates".'),
('world_description', 'El universo conocido está en un estado de frágil paz bajo el ojo vigilante del Consorcio Estelar. Megacorporaciones, sindicatos criminales y antiguas facciones alienígenas compiten por el poder en las sombras. La tecnología ha avanzado a pasos agigantados, pero la galaxia sigue siendo un lugar peligroso y lleno de misterios.'),
('rules', '1. Las acciones se resuelven según los atributos del personaje (Fuerza, Agilidad, Intelecto, Técnica, Presencia, Voluntad) en una escala de 1 a 20. Una puntuación más alta aumenta la probabilidad de éxito.\n2. El GM (IA) tiene la última palabra sobre el resultado de una acción, considerando los atributos y la situación.\n3. No hay sistema de salud (HP) ni dados. El éxito se basa en la descripción y la lógica de los atributos.');

-- 2. Tabla de Entidades del Juego
-- Contiene a todos los personajes (jugadores, NPCs, etc.)
-- La columna stats_json almacenará la biografía y los atributos.
DROP TABLE IF EXISTS entities;
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'Operativo', -- Ej: 'Operativo', 'Aliado', 'Enemigo'
    stats_json JSONB,
    -- Ejemplo de stats_json:
    -- {
    --   "biografia": {
    --     "nombre": "Zane Krios",
    --     "raza": "Humano modificado",
    --     "edad": 35,
    --     "sexo": "Masculino"
    --   },
    --   "atributos": {
    --     "fuerza": 12,
    --     "agilidad": 16,
    --     "intelecto": 14,
    --     "tecnica": 18,
    --     "presencia": 10,
    --     "voluntad": 15
    --   }
    -- }
    estado TEXT DEFAULT 'Activo',
    ubicacion TEXT
);

-- 3. Tabla de Logs de Eventos
-- Registra la narrativa generada por el GM.
DROP TABLE IF EXISTS logs;
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    turno INTEGER,
    evento_texto TEXT NOT NULL,
    prompt_imagen TEXT
);

-- 4. Tabla de Jugadores (simplificada)
-- Se usará para vincular un usuario a una entidad.
DROP TABLE IF EXISTS players;
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE,
    id_entidad_asignada INTEGER REFERENCES entities(id)
);