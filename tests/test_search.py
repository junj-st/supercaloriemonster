import httpx

from app.schemas import NormalizedFood
from app.sources import staples
from app.sources.search import search_foods


class _FakeSource:
    def __init__(self, name, results=None, boom=False):
        self.name = name
        self._results = results or []
        self._boom = boom

    async def search(self, query, client):
        if self._boom:
            raise RuntimeError("source down")
        return self._results

    async def get(self, source_id, client):
        return None


def _food(name, brand=None, source="usda", sid=None, generic=0.5):
    return NormalizedFood(source=source, source_id=sid or name, name=name, brand=brand,
                          calories_100g=100, protein_100g=1, carbs_100g=1, fat_100g=1,
                          generic_score=generic)


async def test_partial_flag_when_source_fails():
    usda = _FakeSource("usda", [_food("Rice", generic=1.0)])
    off = _FakeSource("off", boom=True)
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice bowl", [usda, off], client)
    assert res.partial is True
    assert [f.name for f in res.results] == ["Rice"]


async def test_broad_query_ranks_generic_first():
    usda = _FakeSource("usda", [_food("Rice snack bar", generic=0.1)])
    off = _FakeSource("off", [_food("Rice, white, cooked", source="off", generic=1.0)])
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice bowl", [usda, off], client)
    assert res.partial is False
    assert res.results[0].name == "Rice, white, cooked"


async def test_specific_query_ranks_relevance_first():
    generic = _FakeSource("usda", [_food("Rice, white, cooked", generic=1.0)])
    specific = _FakeSource("off", [_food("Basmati rice pilaf", source="off", generic=0.2)])
    async with httpx.AsyncClient() as client:
        res = await search_foods("basmati rice pilaf", [generic, specific], client)
    assert res.results[0].name == "Basmati rice pilaf"


async def test_history_boost_reorders():
    a = _food("White rice", sid="1", generic=0.5)
    b = _food("Brown rice", sid="2", generic=0.5)
    src = _FakeSource("usda", [a, b])
    history = {("id", "usda", "2"): 4}
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice bowl", [src], client, history)
    assert res.results[0].name == "Brown rice"


async def test_dedupe_keeps_highest_scored():
    low = _food("Milk", sid="1", generic=0.1)
    high = _food("milk", sid="2", generic=1.0)   # same name/brand key, higher generic
    src = _FakeSource("usda", [low, high])
    async with httpx.AsyncClient() as client:
        res = await search_foods("milk shake", [src], client)
    assert len(res.results) == 1
    assert res.results[0].generic_score == 1.0


async def test_staple_injected_first_for_trigger_query():
    branded = _food("Rice snack bar", source="off", sid="b1", generic=0.1)
    src = _FakeSource("off", [branded])
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [src], client)
    assert res.results[0].name == staples.staple_for("rice").name


async def test_no_staple_for_non_trigger_query():
    branded = _food("Rice snack bar", source="off", sid="b1", generic=0.1)
    src = _FakeSource("off", [branded])
    async with httpx.AsyncClient() as client:
        res = await search_foods("wild rice blend", [src], client)
    assert res.results[0].name == "Rice snack bar"   # composite only, no staple


async def test_staple_dedupes_same_named_source_result():
    staple = staples.staple_for("rice")
    dup = _food(staple.name, source="off", sid="dup", generic=0.1)   # same name as staple
    src = _FakeSource("off", [dup])
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [src], client)
    assert sum(1 for r in res.results if r.name == staple.name) == 1  # no duplicate
    assert res.results[0].source_id == staple.source_id              # staple won the slot
