CREATE TABLE sites (
    id serial PRIMARY KEY,
    code text NOT NULL UNIQUE,
    name text NOT NULL
);

CREATE TABLE halls (
    id serial PRIMARY KEY,
    site_id integer NOT NULL REFERENCES sites (id) ON DELETE CASCADE,
    code text NOT NULL,
    UNIQUE (site_id, code)
);

CREATE TABLE racks (
    id serial PRIMARY KEY,
    hall_id integer NOT NULL REFERENCES halls (id) ON DELETE CASCADE,
    code text NOT NULL,
    rack_key text NOT NULL UNIQUE,
    grid_row integer NOT NULL DEFAULT 0,
    grid_col integer NOT NULL DEFAULT 0,
    power_capacity_w integer NOT NULL DEFAULT 2400,
    UNIQUE (hall_id, code)
);

CREATE TABLE devices (
    id serial PRIMARY KEY,
    hall_id integer NOT NULL REFERENCES halls (id) ON DELETE CASCADE,
    rack_id integer REFERENCES racks (id) ON DELETE CASCADE,
    code text NOT NULL,
    device_key text NOT NULL UNIQUE,
    device_type text NOT NULL CHECK (device_type IN ('server', 'switch', 'transceiver', 'pdu', 'crac'))
);

CREATE INDEX devices_rack_idx ON devices (rack_id);
CREATE INDEX devices_type_idx ON devices (device_type);

CREATE TABLE asset_edges (
    src_key text NOT NULL,
    dst_key text NOT NULL,
    relation text NOT NULL,
    PRIMARY KEY (src_key, dst_key, relation)
);

CREATE INDEX asset_edges_dst_idx ON asset_edges (dst_key);
