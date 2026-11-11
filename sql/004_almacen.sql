-- Datos privados que antes vivían solo en archivos de tu PC (CV base,
-- respuestas al Preguntón, historial y Word generados, plan de estudio,
-- actividad de los agentes, ofertas enviadas con el marcador).
-- Lo usa app/almacen.py con ALMACEN=supabase, y siempre en Cloud Run.
-- La clave es la ruta relativa del proyecto, p. ej. 'data/cv_base.yaml'.
-- Idempotente: se puede correr más de una vez.
CREATE TABLE IF NOT EXISTS almacen (
    clave       TEXT PRIMARY KEY,
    contenido   BYTEA NOT NULL,
    actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- La app se conecta como el usuario postgres y no usa la API de datos de
-- Supabase. Si esa API estuviera activada, esto impide leer la tabla con
-- la clave pública del proyecto.
ALTER TABLE almacen ENABLE ROW LEVEL SECURITY;
