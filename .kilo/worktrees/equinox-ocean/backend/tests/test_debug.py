def test_debug_resume(client, org_admin, scenario_id):
    h = org_admin["headers"]
    r = client.post("/api/v1/simulations", headers=h, json={"scenario_id": scenario_id})
    sim = r.json()
    r = client.post(
        f"/api/v1/simulations/{sim['id']}/clarify",
        headers=h,
        json={"content": "question?"},
    )
    print("clarify", r.status_code, r.text[:200])
    r = client.post(f"/api/v1/simulations/{sim['id']}/resume", headers=h)
    print("resume", r.status_code, r.text[:400])
    assert True
