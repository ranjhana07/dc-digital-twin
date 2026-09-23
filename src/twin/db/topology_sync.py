from psycopg2.extras import execute_values

from twin.common.topology import HALL_LEVEL_RACK, Topology


def site_rows(topology: Topology) -> list[tuple[str, str]]:
    codes = sorted({rack.site for rack in topology.racks.values()} | {d.site for d in topology.devices.values()})
    return [(code, code.upper()) for code in codes]


def hall_rows(topology: Topology) -> list[tuple[str, str]]:
    halls = {(device.site, device.hall) for device in topology.devices.values()}
    return sorted(halls)


def upsert_topology(conn, topology: Topology, rack_capacity_w: int = 2400) -> None:
    with conn.cursor() as cur:
        execute_values(
            cur, "INSERT INTO sites (code, name) VALUES %s ON CONFLICT (code) DO NOTHING", site_rows(topology)
        )
        execute_values(
            cur,
            "INSERT INTO halls (site_id, code) SELECT s.id, v.hall FROM (VALUES %s) AS v (site, hall) "
            "JOIN sites s ON s.code = v.site WHERE true ON CONFLICT (site_id, code) DO NOTHING",
            hall_rows(topology),
        )
        rack_rows = [
            (rack.site, rack.hall, rack.code, rack.key, rack.grid_row, rack.grid_col, rack_capacity_w)
            for rack in topology.racks.values()
        ]
        execute_values(
            cur,
            "INSERT INTO racks (hall_id, code, rack_key, grid_row, grid_col, power_capacity_w) "
            "SELECT h.id, v.code, v.rack_key, v.grid_row::int, v.grid_col::int, v.capacity::int "
            "FROM (VALUES %s) AS v (site, hall, code, rack_key, grid_row, grid_col, capacity) "
            "JOIN sites s ON s.code = v.site JOIN halls h ON h.site_id = s.id AND h.code = v.hall "
            "WHERE true ON CONFLICT (rack_key) DO NOTHING",
            rack_rows,
        )
        device_rows = [
            (d.site, d.hall, d.rack, d.code, d.key, d.type.value) for d in topology.devices.values()
        ]
        execute_values(
            cur,
            "INSERT INTO devices (hall_id, rack_id, code, device_key, device_type) "
            "SELECT h.id, r.id, v.code, v.device_key, v.device_type "
            "FROM (VALUES %s) AS v (site, hall, rack, code, device_key, device_type) "
            "JOIN sites s ON s.code = v.site JOIN halls h ON h.site_id = s.id AND h.code = v.hall "
            f"LEFT JOIN racks r ON r.hall_id = h.id AND r.code = v.rack AND v.rack <> '{HALL_LEVEL_RACK}' "
            "WHERE true ON CONFLICT (device_key) DO NOTHING",
            device_rows,
        )
        execute_values(
            cur,
            "INSERT INTO asset_edges (src_key, dst_key, relation) VALUES %s ON CONFLICT DO NOTHING",
            [(edge.src, edge.dst, edge.relation) for edge in topology.edges],
        )
    conn.commit()
