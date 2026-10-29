CRAC = "dc1/hall-a/hall/crac-1"


def seed_cooling_incident(repo):
    repo.add_alert(1, CRAC, "supply_temp", "critical", minutes=0)
    for index, rack in enumerate(("r01", "r03")):
        repo.add_alert(10 + index, f"dc1/hall-a/{rack}/srv-01", "inlet_temp", "warning", minutes=4 + index)


def test_analyze_ranks_shared_crac_first_and_persists(client, repo):
    seed_cooling_incident(repo)
    response = client.post("/api/rca/analyze")
    assert response.status_code == 200
    results = response.json()
    assert results[0]["rank"] == 1
    assert results[0]["root_cause_key"] == CRAC
    assert results[0]["fault_kind"] == "cooling_failure"
    assert results[0]["alert_ids"] == [1, 10, 11]
    assert "cooling failure" in results[0]["summary"]
    stored = client.get("/api/rca").json()
    assert stored[0]["root_cause_key"] == CRAC


def test_analyze_ignores_resolved_alerts(client, repo):
    repo.add_alert(1, CRAC, "supply_temp", "critical", status="resolved")
    assert client.post("/api/rca/analyze").json() == []
    assert client.get("/api/rca").json() == []


def test_analyze_parameters_are_validated(client):
    assert client.post("/api/rca/analyze", params={"top_n": 0}).status_code == 422
    assert client.post("/api/rca/analyze", params={"window_minutes": -5}).status_code == 422
