CREATE TABLE rca_results (
    id bigserial PRIMARY KEY,
    run_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    rank integer NOT NULL,
    root_cause_key text NOT NULL,
    fault_kind text,
    score double precision NOT NULL,
    alert_ids bigint[] NOT NULL DEFAULT '{}',
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX rca_results_run_idx ON rca_results (run_id, rank);
CREATE INDEX rca_results_created_idx ON rca_results (created_at DESC);
