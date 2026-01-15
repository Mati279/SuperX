-- ============================================================
-- SUPERX: DB EXPANSION - GESTION DE FACCION
-- ============================================================

-- 1. Alterar la tabla PLAYERS para añadir Créditos
ALTER TABLE players
ADD COLUMN creditos INTEGER DEFAULT 1000 NOT NULL;

-- Comentario: Añadimos un valor inicial de 1000 créditos a todos los jugadores existentes y futuros.

-- 2. Alterar la tabla CHARACTERS para añadir Costo de Reclutamiento
ALTER TABLE characters
ADD COLUMN costo INTEGER DEFAULT 100;

-- Comentario: Añadimos un costo base para los personajes.
-- El estado 'En Misión', 'Descansando' etc, se manejará con la columna 'estado' ya existente.
-- No es necesario alterar la estructura para eso.

-- Refrescar la API de Supabase para que reconozca los cambios
NOTIFY pgrst, 'reload config';

-- Opcional: Insertar un comentario en los logs del juego sobre la actualización
-- No es una acción de SQL estándar, pero conceptualmente es lo que haríamos.
-- INSERT INTO logs (evento_texto) VALUES ('[SYSTEM] Base de datos actualizada para incluir sistema económico y de reclutamiento.');
