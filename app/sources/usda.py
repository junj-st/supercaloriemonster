import httpx

from app.schemas import NormalizedFood
from app.sources.normalize import normalize_usda


class USDAFoodSource:
    name = "usda"

    def __init__(self, base_url: str, api_key: str | None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        return self.api_key is not None

    async def search(
        self, query: str, client: httpx.AsyncClient
    ) -> list[NormalizedFood]:
        resp = await client.get(
            f"{self.base_url}/foods/search",
            params={"api_key": self.api_key, "query": query, "pageSize": 20},
        )
        resp.raise_for_status()
        foods = resp.json().get("foods", [])
        out = [normalize_usda(f) for f in foods]
        return [f for f in out if f is not None]

    async def get(
        self, source_id: str, client: httpx.AsyncClient
    ) -> NormalizedFood | None:
        resp = await client.get(
            f"{self.base_url}/food/{source_id}",
            params={"api_key": self.api_key},
        )
        resp.raise_for_status()
        return normalize_usda(resp.json())
