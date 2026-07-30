from app.schemas import NormalizedFood


def _food(name="Rice", source="usda", sid="1"):
    return NormalizedFood(source=source, source_id=sid, name=name,
                          calories_100g=130, protein_100g=2.7, carbs_100g=28,
                          fat_100g=0.3, serving_desc="100g", serving_grams=100)


def test_search_returns_source_results(client, fake_sources):
    fake_sources[0].results = [_food("Brown rice")]
    resp = client.get("/foods/search", params={"q": "rice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["partial"] is False
    assert body["results"][0]["name"] == "Brown rice"


def test_search_blank_query_returns_empty(client):
    resp = client.get("/foods/search", params={"q": "  "})
    assert resp.json() == {"results": [], "partial": False}


def test_search_partial_when_source_fails(client, fake_sources):
    fake_sources[0].boom = True
    resp = client.get("/foods/search", params={"q": "rice"})
    assert resp.json() == {"results": [], "partial": True}


def test_search_boosts_logged_food(client, fake_sources):
    # Log "Brown rice" (usda/2) so it gains history weight.
    client.post("/logs", json={
        "food": {"source": "usda", "source_id": "2", "name": "Brown rice",
                 "calories_100g": 110, "protein_100g": 2, "carbs_100g": 23,
                 "fat_100g": 1, "serving_desc": "100g", "serving_grams": 100},
        "date": "2026-07-28", "meal_type": "lunch", "amount_g": 100,
    })
    # Search returns a non-logged generic and the logged food, same generic_score.
    fake_sources[0].results = [
        NormalizedFood(source="usda", source_id="1", name="White rice",
                       calories_100g=130, protein_100g=2.7, carbs_100g=28,
                       fat_100g=0.3, generic_score=0.5),
        NormalizedFood(source="usda", source_id="2", name="Brown rice",
                       calories_100g=110, protein_100g=2, carbs_100g=23,
                       fat_100g=1, generic_score=0.5),
    ]
    body = client.get("/foods/search", params={"q": "rice"}).json()
    assert body["results"][0]["name"] == "Brown rice"


def test_manual_food_persists_as_manual(client):
    resp = client.post("/foods/manual", json={
        "name": "Grandma stew", "calories_100g": 120, "protein_100g": 9,
        "carbs_100g": 6, "fat_100g": 5, "serving_desc": "1 bowl",
        "serving_grams": 350,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["source_id"] is None
    assert body["name"] == "Grandma stew"
