-- Portales de empleo de España como fuentes de ofertas (texto pegado o URL).
-- Idempotente: se puede correr más de una vez.
-- Mantener sincronizado con DOMINIO_A_SOURCE (app/source_resolver.py)
-- y con el Literal source_name de JobExtraction (app/schemas.py).
INSERT INTO source (nombre) VALUES ('InfoJobs'), ('Tecnoempleo')
ON CONFLICT (nombre) DO NOTHING;
