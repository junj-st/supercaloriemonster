import json
from pathlib import Path

from app.sources.normalize import normalize_off, normalize_usda

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_normalize_usda_maps_per_100g():
    item = _load("usda_search.json")["foods"][0]
    f = normalize_usda(item)
    assert f.source == "usda"
    assert f.source_id == "171077"
    assert f.name.startswith("Chicken")
    assert f.calories_100g == 165.0
    assert f.protein_100g == 31.0
    assert f.carbs_100g == 0.0
    assert f.fat_100g == 3.57
    assert f.serving_desc == "100g"
    assert f.serving_grams == 100.0


def test_normalize_usda_returns_none_without_energy():
    item = _load("usda_search.json")["foods"][1]
    assert normalize_usda(item) is None


def test_normalize_off_maps_and_reads_serving():
    prod = _load("off_search.json")["products"][0]
    f = normalize_off(prod)
    assert f.source == "off"
    assert f.source_id == "3017620422003"
    assert f.name == "Nutella"
    assert f.brand == "Ferrero"
    assert f.calories_100g == 539
    assert f.protein_100g == 6.3
    assert f.serving_grams == 15
    assert f.serving_desc == "15 g"


def test_normalize_off_returns_none_without_energy():
    prod = _load("off_search.json")["products"][1]
    assert normalize_off(prod) is None
