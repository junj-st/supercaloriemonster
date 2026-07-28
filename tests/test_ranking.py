from app.schemas import NormalizedFood
from app.sources import ranking


def _food(name, source="usda", sid="1", generic=0.5):
    return NormalizedFood(source=source, source_id=sid, name=name,
                          calories_100g=1, protein_100g=1, carbs_100g=1, fat_100g=1,
                          generic_score=generic)


def test_query_weights_broad_vs_specific():
    wg1, wr1 = ranking.query_weights("rice")
    wg2, wr2 = ranking.query_weights("basmati rice pilaf")
    assert wg1 > wr1        # broad: genericness dominates
    assert wr2 > wg2        # specific: relevance dominates


def test_relevance_tiers():
    assert ranking.relevance("rice", "rice", 0) > ranking.relevance("rice", "rice pilaf", 0)
    assert ranking.relevance("rice", "rice pilaf", 0) > ranking.relevance("rice", "wild rice blend", 0)
    # earlier position ranks at least as high as a later one, all else equal
    assert ranking.relevance("rice", "rice", 0) >= ranking.relevance("rice", "rice", 5)


def test_broad_query_prefers_generic():
    generic = _food("Rice, white, cooked", sid="1", generic=1.0)
    branded = _food("Rice snack bar", source="off", sid="2", generic=0.1)
    sg = ranking.score(generic, "rice", 0, {})
    sb = ranking.score(branded, "rice", 0, {})
    assert sg > sb


def test_specific_query_prefers_relevance():
    exact = _food("Basmati rice pilaf", sid="1", generic=0.2)
    generic = _food("Rice, white, cooked", sid="2", generic=1.0)
    se = ranking.score(exact, "basmati rice pilaf", 0, {})
    sgen = ranking.score(generic, "basmati rice pilaf", 1, {})
    assert se > sgen


def test_history_boost_raises_score():
    food = _food("Brown rice", source="usda", sid="9", generic=0.5)
    history = {("id", "usda", "9"): 3}
    assert ranking.score(food, "rice", 0, history) > ranking.score(food, "rice", 0, {})
