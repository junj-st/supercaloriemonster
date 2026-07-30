from app.schemas import NormalizedFood
from app.sources.staples import _STAPLES, staple_for


def test_staple_for_trigger_terms():
    r = staple_for("rice")
    assert r is not None
    assert "rice" in r.name.lower()
    assert staple_for("Rice") is not None            # case-insensitive
    assert staple_for("chicken") is not None


def test_staple_for_non_triggers():
    assert staple_for("wild rice blend") is None      # specific, not a trigger
    assert staple_for("nonexistent food xyz") is None
    assert staple_for("") is None


def test_every_staple_is_valid():
    assert len(_STAPLES) >= 20
    for triggers, food in _STAPLES:
        assert triggers and all(t == t.lower() for t in triggers)
        assert isinstance(food, NormalizedFood)
        assert food.source == "usda"
        assert food.source_id                          # real fdcId, non-empty
        assert food.calories_100g > 0
        assert food.generic_score == 1.0
