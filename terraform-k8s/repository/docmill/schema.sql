CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'queued',
    filename TEXT,
    bytes BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
