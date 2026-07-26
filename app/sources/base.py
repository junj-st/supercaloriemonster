from typing import Protocol

import httpx

from app.schemas import NormalizedFood


class FoodSource(Protocol):
    name: str

    async def search(
        self, query: str, client: httpx.AsyncClient
    ) -> list[NormalizedFood]: ...

    async def get(
        self, source_id: str, client: httpx.AsyncClient
    ) -> NormalizedFood | None: ...
