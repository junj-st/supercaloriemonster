from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import compute_macros, to_normalized, upsert_food
from app.db import Base
from app.schemas import NormalizedFood


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _food():
    return NormalizedFood(source="usda", source_id="1", name="Rice",
                          calories_100g=130, protein_100g=2.7, carbs_100g=28,
                          fat_100g=0.3, serving_desc="100g", serving_grams=100)


def test_upsert_inserts_then_updates_same_row():
    db = _session()
    f1 = upsert_food(db, _food())
    updated = _food()
    updated.calories_100g = 150
    f2 = upsert_food(db, updated)
    assert f1.id == f2.id  # same row
    assert f2.calories_100g == 150


def test_compute_macros_scales_by_grams():
    db = _session()
    food = upsert_food(db, _food())
    m = compute_macros(food, 200.0)
    assert m.calories == 260.0
    assert m.protein_g == 5.4


def test_to_normalized_roundtrip():
    db = _session()
    food = upsert_food(db, _food())
    n = to_normalized(food)
    assert n.source == "usda" and n.source_id == "1" and n.name == "Rice"


def test_upsert_manual_food_matches_same_row_by_name_and_brand():
    db = _session()
    # Create a manual food with name and brand
    manual_food_1 = NormalizedFood(
        source="manual", source_id=None, name="Grandma stew", brand=None,
        calories_100g=120, protein_100g=9, carbs_100g=6, fat_100g=5,
        serving_desc="1 bowl", serving_grams=300
    )
    f1 = upsert_food(db, manual_food_1)

    # Upsert same manual food with changed calories (should update same row)
    manual_food_2 = NormalizedFood(
        source="manual", source_id=None, name="Grandma stew", brand=None,
        calories_100g=200, protein_100g=9, carbs_100g=6, fat_100g=5,
        serving_desc="1 bowl", serving_grams=300
    )
    f2 = upsert_food(db, manual_food_2)

    # Same row (matched by name+brand with brand IS NULL)
    assert f1.id == f2.id
    assert f2.calories_100g == 200

    # Different manual food with different name should get different id
    manual_food_3 = NormalizedFood(
        source="manual", source_id=None, name="Other dish", brand=None,
        calories_100g=150, protein_100g=10, carbs_100g=8, fat_100g=4,
        serving_desc="1 plate", serving_grams=250
    )
    f3 = upsert_food(db, manual_food_3)

    # Different row (name is different)
    assert f3.id != f1.id


def test_to_normalized_maps_all_fields():
    db = _session()
    # Create a food with distinct values in every field
    food_input = NormalizedFood(
        source="custom", source_id="42", name="Pasta Primavera",
        brand="BrandName",
        calories_100g=180, protein_100g=7.5, carbs_100g=35.2, fat_100g=4.1,
        serving_desc="1 cup", serving_grams=250
    )
    food = upsert_food(db, food_input)

    # Map back to normalized and verify all fields
    normalized = to_normalized(food)
    assert normalized.source == "custom"
    assert normalized.source_id == "42"
    assert normalized.name == "Pasta Primavera"
    assert normalized.brand == "BrandName"
    assert normalized.calories_100g == 180
    assert normalized.protein_100g == 7.5
    assert normalized.carbs_100g == 35.2
    assert normalized.fat_100g == 4.1
    assert normalized.serving_desc == "1 cup"
    assert normalized.serving_grams == 250
