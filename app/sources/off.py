import httpx

from app.schemas import NormalizedFood
from app.sources.normalize import normalize_off


class OFFFoodSource:
    name = "off"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def search(
        self, query: str, client: httpx.AsyncClient
    ) -> list[NormalizedFood]:
        resp = await client.get(
            f"{self.base_url}/cgi/search.pl",
            params={"search_terms": query, "json": 1, "page_size": 20},
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
        out = [normalize_off(p) for p in products]
        return [f for f in out if f is not None]

    async def get(
        self, source_id: str, client: httpx.AsyncClient
    ) -> NormalizedFood | None:
        resp = await client.get(f"{self.base_url}/api/v2/product/{source_id}.json")
        resp.raise_for_status()
        product = resp.json().get("product")
        return normalize_off(product) if product else None
