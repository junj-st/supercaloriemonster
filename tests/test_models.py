from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

from app.db import Base
from app.models import Favorite, Food, Log


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_food_log_favorite_roundtrip():
    db = _session()
    food = Food(
        source="usda", source_id="123", name="Chicken breast",
        calories_100g=165.0, protein_100g=31.0, carbs_100g=0.0, fat_100g=3.6,
        serving_desc="100g", serving_grams=100.0, cached_at=datetime.now(timezone.utc),
    )
    db.add(food)
    db.commit()

    log = Log(food_id=food.id, date=date(2026, 7, 24),
              meal_type="lunch", amount_g=200.0, created_at=datetime.now(timezone.utc))
    fav = Favorite(food_id=food.id, label="my chicken")
    db.add_all([log, fav])
    db.commit()

    assert log.food.name == "Chicken breast"
    assert fav.food.calories_100g == 165.0


def test_duplicate_source_and_source_id_rejected():
    """Test that Food rows with duplicate (source, source_id) are rejected."""
    db = _session()
    food1 = Food(
        source="usda", source_id="123", name="Chicken breast",
        calories_100g=165.0, protein_100g=31.0, carbs_100g=0.0, fat_100g=3.6,
        cached_at=datetime.now(timezone.utc),
    )
    db.add(food1)
    db.commit()

    food2 = Food(
        source="usda", source_id="123", name="Different name",
        calories_100g=100.0, protein_100g=20.0, carbs_100g=5.0, fat_100g=2.0,
        cached_at=datetime.now(timezone.utc),
    )
    db.add(food2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_duplicate_favorite_food_id_rejected():
    """Test that Favorite rows with duplicate food_id are rejected."""
    db = _session()
    food = Food(
        source="usda", source_id="456", name="Salmon",
        calories_100g=208.0, protein_100g=20.0, carbs_100g=0.0, fat_100g=13.0,
        cached_at=datetime.now(timezone.utc),
    )
    db.add(food)
    db.commit()

    fav1 = Favorite(food_id=food.id, label="my salmon")
    db.add(fav1)
    db.commit()

    fav2 = Favorite(food_id=food.id, label="another salmon")
    db.add(fav2)
    with pytest.raises(IntegrityError):
        db.commit()


def test_get_db_yields_and_closes_session():
    """Test that get_db yields a usable Session and closes it properly."""
    from app.db import get_db

    gen = get_db()
    db = next(gen)
    assert isinstance(db, Session)
    # exhaust the generator so the finally-block closing runs
    with pytest.raises(StopIteration):
        next(gen)
