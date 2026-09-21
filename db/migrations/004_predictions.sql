CREATE TABLE predictions (
    id bigserial PRIMARY KEY,
    device_key text NOT NULL,
    metric text NOT NULL,
    task text NOT NULL,
    made_at timestamptz NOT NULL,
    target_ts timestamptz NOT NULL,
    horizon_step integer NOT NULL,
    predicted double precision NOT NULL,
    lower double precision NOT NULL,
    upper double precision NOT NULL,
    model_version text NOT NULL
);

CREATE INDEX predictions_series_idx ON predictions (device_key, metric, made_at DESC);

CREATE TABLE risk_scores (
    device_key text NOT NULL,
    metric text NOT NULL,
    task text NOT NULL,
    computed_at timestamptz NOT NULL,
    risk double precision NOT NULL,
    severity text NOT NULL,
    p_warn double precision NOT NULL,
    p_crit double precision NOT NULL,
    rate_per_hour double precision NOT NULL,
    z_score double precision NOT NULL,
    breach_step integer,
    PRIMARY KEY (device_key, metric)
);

CREATE INDEX risk_scores_risk_idx ON risk_scores (risk DESC);
