import json
from pathlib import Path

import httpx
import pytest

from app.sources.off import OFFFoodSource
from app.sources.usda import USDAFoodSource

FIX = Path(__file__).parent / "fixtures"


def _mock_client(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_off_search_parses_results():
    payload = json.loads((FIX / "off_search.json").read_text())
    src = OFFFoodSource(base_url="https://off.test")
    async with _mock_client(payload) as client:
        results = await src.search("nutella", client)
    assert src.name == "off"
    assert results[0].name == "Nutella"
    # the no-energy product is dropped by normalization; the valid product
    # and the energy-only product both survive normalization.
    assert all(r.calories_100g is not None for r in results)
    assert len(results) == 2


async def test_usda_search_parses_results():
    payload = json.loads((FIX / "usda_search.json").read_text())
    src = USDAFoodSource(base_url="https://usda.test", api_key="KEY")
    async with _mock_client(payload) as client:
        results = await src.search("chicken", client)
    assert src.enabled is True
    assert results[0].source_id == "171077"
    # no-energy item dropped; valid item + energy-only item both survive
    assert len(results) == 2


def test_usda_disabled_without_key():
    src = USDAFoodSource(base_url="https://usda.test", api_key=None)
    assert src.enabled is False
