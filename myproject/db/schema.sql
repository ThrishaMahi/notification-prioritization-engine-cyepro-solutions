CREATE TABLE IF NOT EXISTS notification_events (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    title         TEXT,
    message       TEXT,
    source        TEXT,
    priority_hint TEXT,
    channel       TEXT,
    dedupe_key    TEXT,
    expires_at    TIMESTAMP,
    metadata      JSONB DEFAULT '{}',
    timestamp     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_events_user   ON notification_events(user_id);
CREATE INDEX idx_events_dedupe ON notification_events(dedupe_key);

CREATE TABLE IF NOT EXISTS decision_logs (
    id           TEXT PRIMARY KEY,
    event_id     TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    decision     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    score        FLOAT DEFAULT 0,
    rule_matched TEXT,
    send_at      TIMESTAMP,
    ai_used      TEXT DEFAULT 'yes',
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_logs_event ON decision_logs(event_id);
CREATE INDEX idx_logs_user  ON decision_logs(user_id);

CREATE TABLE IF NOT EXISTS user_history (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channel    TEXT,
    sent_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_history_user ON user_history(user_id);

CREATE TABLE IF NOT EXISTS suppression_records (
    id               TEXT PRIMARY KEY,
    event_id         TEXT NOT NULL,
    user_id          TEXT NOT NULL,
    action           TEXT NOT NULL,
    reason           TEXT,
    original_payload JSONB,
    created_at       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_suppression_user ON suppression_records(user_id);
