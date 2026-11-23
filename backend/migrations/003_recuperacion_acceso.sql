BEGIN;
CREATE TABLE IF NOT EXISTS regova.recuperaciones_acceso (
 token_hash varchar(64) PRIMARY KEY CHECK(token_hash ~ '^[0-9a-f]{64}$'),
 usuario_id bigint NOT NULL REFERENCES regova.usuarios(id) ON DELETE RESTRICT,
 email varchar(254) NOT NULL,
 creada_en timestamptz NOT NULL DEFAULT current_timestamp,
 expira_en timestamptz NOT NULL,
 CHECK(expira_en > creada_en)
);
CREATE INDEX IF NOT EXISTS recuperaciones_usuario_idx ON regova.recuperaciones_acceso(usuario_id);
COMMIT;
