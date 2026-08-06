def _log_body(meal="lunch", amount=200, sid="1", name="Rice"):
    return {
        "food": {"source": "usda", "source_id": sid, "name": name,
                 "calories_100g": 130, "protein_100g": 2.7, "carbs_100g": 28,
                 "fat_100g": 0.3, "serving_desc": "100g", "serving_grams": 100},
        "date": "2026-07-24", "meal_type": meal, "amount_g": amount,
    }


def test_create_log_computes_macros(client):
    resp = client.post("/logs", json=_log_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["calories"] == 260.0
    assert body["meal_type"] == "lunch"


def test_day_summary_groups_and_totals(client):
    client.post("/logs", json=_log_body(meal="breakfast", amount=100))
    client.post("/logs", json=_log_body(meal="lunch", amount=200))
    resp = client.get("/logs/day/2026-07-24")
    body = resp.json()
    assert set(body["meals"].keys()) == {"breakfast", "lunch", "dinner", "snack"}
    assert list(body["meals"].keys()) == ["breakfast", "lunch", "dinner", "snack"]
    assert len(body["meals"]["breakfast"]) == 1
    assert len(body["meals"]["dinner"]) == 0
    assert body["totals"]["calories"] == 130.0 + 260.0


def test_edit_and_delete_log(client):
    created = client.post("/logs", json=_log_body()).json()
    lid = created["id"]
    edited = client.put(f"/logs/{lid}", json={"amount_g": 100})
    assert edited.json()["calories"] == 130.0
    assert client.delete(f"/logs/{lid}").status_code == 204
    assert client.put(f"/logs/{lid}", json={"amount_g": 50}).status_code == 404


def test_reused_food_is_not_duplicated(client):
    client.post("/logs", json=_log_body(sid="1"))
    client.post("/logs", json=_log_body(sid="1", amount=50))
    # both logs point at the same upserted food row; day has 2 entries
    body = client.get("/logs/day/2026-07-24").json()
    assert len(body["meals"]["lunch"]) == 2


def test_history_frozen_after_food_edit(client):
    # Log a manual food at 120 cal/100g, 100 g -> 120 cal.
    client.post("/logs", json={
        "food": {"source": "manual", "source_id": None, "name": "Stew",
                 "calories_100g": 120, "protein_100g": 9, "carbs_100g": 6,
                 "fat_100g": 5, "serving_desc": "1 bowl", "serving_grams": 350},
        "date": "2026-07-28", "meal_type": "lunch", "amount_g": 100,
    })
    # Edit the same manual food's macros via re-POST (upsert by name+brand).
    client.post("/foods/manual", json={
        "name": "Stew", "calories_100g": 999, "protein_100g": 1,
        "carbs_100g": 1, "fat_100g": 1,
    })
    # Past History must still reflect the snapshot (120), not 999.
    day = client.get("/logs/day/2026-07-28").json()
    assert day["totals"]["calories"] == 120.0
