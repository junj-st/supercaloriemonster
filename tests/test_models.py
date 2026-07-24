from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
        serving_desc="100g", serving_grams=100.0, cached_at=datetime.utcnow(),
    )
    db.add(food)
    db.commit()

    log = Log(food_id=food.id, date=date(2026, 7, 24),
              meal_type="lunch", amount_g=200.0, created_at=datetime.utcnow())
    fav = Favorite(food_id=food.id, label="my chicken")
    db.add_all([log, fav])
    db.commit()

    assert log.food.name == "Chicken breast"
    assert fav.food.calories_100g == 165.0
