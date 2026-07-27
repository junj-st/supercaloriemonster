import httpx

from app.schemas import NormalizedFood
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


def _food(name, brand=None, source="usda"):
    return NormalizedFood(source=source, source_id=name, name=name, brand=brand,
                          calories_100g=100, protein_100g=1, carbs_100g=1, fat_100g=1)


async def test_merge_dedupes_and_flags_partial():
    usda = _FakeSource("usda", [_food("Rice")])
    off = _FakeSource("off", boom=True)
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [usda, off], client)
    assert res.partial is True
    assert [f.name for f in res.results] == ["Rice"]


async def test_generic_ranks_before_branded():
    usda = _FakeSource("usda", [_food("Chicken breast")])
    off = _FakeSource("off", [_food("Chicken nuggets", brand="Acme", source="off")])
    async with httpx.AsyncClient() as client:
        res = await search_foods("chicken", [usda, off], client)
    assert res.partial is False
    assert res.results[0].name == "Chicken breast"  # generic first
    assert res.results[1].brand == "Acme"


async def test_dedupe_same_name_and_brand():
    a = _food("Milk")
    b = _food("milk")  # same name, different case, no brand
    src = _FakeSource("usda", [a, b])
    async with httpx.AsyncClient() as client:
        res = await search_foods("milk", [src], client)
    assert len(res.results) == 1
