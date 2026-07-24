import pytest
from pydantic import ValidationError

from app.schemas import LogCreate, NormalizedFood


def _food():
    return NormalizedFood(
        source="off", source_id="abc", name="Granola bar", brand="Acme",
        calories_100g=450.0, protein_100g=8.0, carbs_100g=60.0, fat_100g=18.0,
        serving_desc="1 bar", serving_grams=40.0,
    )


def test_normalized_food_defaults():
    f = NormalizedFood(source="manual", name="Water",
                       calories_100g=0, protein_100g=0, carbs_100g=0, fat_100g=0)
    assert f.brand is None and f.serving_grams is None


def test_logcreate_rejects_bad_meal_type():
    with pytest.raises(ValidationError):
        LogCreate(food=_food(), date="2026-07-24", meal_type="brunch", amount_g=40)
