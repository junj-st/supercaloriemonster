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
