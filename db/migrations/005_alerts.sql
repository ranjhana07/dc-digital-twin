CREATE TABLE alerts (
    id bigserial PRIMARY KEY,
    device_key text NOT NULL,
    rack_key text NOT NULL,
    metric text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('threshold', 'forecast')),
    severity text NOT NULL CHECK (severity IN ('warning', 'critical')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    message text NOT NULL,
    risk_score double precision,
    raised_at timestamptz NOT NULL DEFAULT now(),
    acknowledged_at timestamptz,
    resolved_at timestamptz,
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX alerts_open_unique_idx ON alerts (device_key, metric, kind) WHERE status <> 'resolved';
CREATE INDEX alerts_status_idx ON alerts (status, raised_at DESC);
CREATE INDEX alerts_rack_idx ON alerts (rack_key);
