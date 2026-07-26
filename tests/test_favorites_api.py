def _food(sid="1", name="Rice"):
    return {"source": "usda", "source_id": sid, "name": name,
            "calories_100g": 130, "protein_100g": 2.7, "carbs_100g": 28,
            "fat_100g": 0.3, "serving_desc": "100g", "serving_grams": 100}


def _log_body(sid="1", name="Rice", meal="lunch"):
    return {"food": _food(sid, name), "date": "2026-07-24",
            "meal_type": meal, "amount_g": 100}


def test_add_list_delete_favorite(client):
    add = client.post("/favorites", json={"food": _food(), "label": "staple"})
    assert add.status_code == 201
    fid = add.json()["id"]
    listed = client.get("/favorites").json()
    assert len(listed) == 1
    assert listed[0]["label"] == "staple"
    assert listed[0]["food"]["name"] == "Rice"
    assert client.delete(f"/favorites/{fid}").status_code == 204
    assert client.get("/favorites").json() == []


def test_favorite_same_food_updates_label(client):
    client.post("/favorites", json={"food": _food(), "label": "a"})
    client.post("/favorites", json={"food": _food(), "label": "b"})
    listed = client.get("/favorites").json()
    assert len(listed) == 1
    assert listed[0]["label"] == "b"


def test_recents_returns_distinct_recent_foods(client):
    client.post("/logs", json=_log_body(sid="1", name="Rice"))
    client.post("/logs", json=_log_body(sid="2", name="Eggs"))
    client.post("/logs", json=_log_body(sid="1", name="Rice"))  # repeat
    recents = client.get("/recents", params={"limit": 10}).json()
    names = [r["name"] for r in recents]
    assert names[0] == "Rice"  # most recent first
    assert names.count("Rice") == 1  # distinct
    assert "Eggs" in names


def test_recents_respects_limit(client):
    client.post("/logs", json=_log_body(sid="1", name="Rice"))
    client.post("/logs", json=_log_body(sid="2", name="Eggs"))
    client.post("/logs", json=_log_body(sid="3", name="Oats"))
    recents = client.get("/recents", params={"limit": 2}).json()
    names = [r["name"] for r in recents]
    assert len(recents) == 2
    assert names == ["Oats", "Eggs"]  # two most recent distinct foods, newest first


def test_delete_missing_favorite_returns_404(client):
    resp = client.delete("/favorites/99999")
    assert resp.status_code == 404
