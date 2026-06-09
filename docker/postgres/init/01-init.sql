CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS face_embeddings (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    embedding vector(512) NOT NULL,
    source TEXT NOT NULL DEFAULT 'enrollment',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_face_embeddings_user_id
    ON face_embeddings (user_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id TEXT NULL,
    authenticated BOOLEAN NOT NULL,
    deepfake_detected BOOLEAN NOT NULL,
    confidence DOUBLE PRECISION NULL,
    latency_ms BIGINT NOT NULL,
    source_ip TEXT NULL,
    notes TEXT NULL
);
