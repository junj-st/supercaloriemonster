import asyncio
import logging

import httpx

from app.schemas import NormalizedFood, SearchResult
from app.sources.base import FoodSource

logger = logging.getLogger("scm.search")


def _rank_key(food: NormalizedFood) -> tuple[int, str]:
    # Generic (no brand) ranks before branded; stable by name within each group.
    return (1 if food.brand else 0, food.name.lower())


def _dedupe(foods: list[NormalizedFood]) -> list[NormalizedFood]:
    seen: set[tuple[str, str]] = set()
    out: list[NormalizedFood] = []
    for f in foods:
        key = (f.name.lower(), (f.brand or "").lower())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


async def search_foods(
    query: str, sources: list[FoodSource], client: httpx.AsyncClient
) -> SearchResult:
    results = await asyncio.gather(
        *(s.search(query, client) for s in sources), return_exceptions=True
    )
    merged: list[NormalizedFood] = []
    partial = False
    for source, res in zip(sources, results):
        if isinstance(res, Exception):
            partial = True
            logger.warning("source %s failed: %s", source.name, res)
            continue
        merged.extend(res)
    merged.sort(key=_rank_key)
    return SearchResult(results=_dedupe(merged), partial=partial)
