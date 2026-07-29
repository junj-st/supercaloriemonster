import asyncio
import logging

import httpx

from app.schemas import NormalizedFood, SearchResult
from app.sources import ranking
from app.sources.base import FoodSource

logger = logging.getLogger("scm.search")


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
    query: str,
    sources: list[FoodSource],
    client: httpx.AsyncClient,
    history: dict | None = None,
) -> SearchResult:
    history = history or {}
    results = await asyncio.gather(
        *(s.search(query, client) for s in sources), return_exceptions=True
    )
    scored: list[tuple[float, NormalizedFood]] = []
    partial = False
    for source, res in zip(sources, results):
        if isinstance(res, Exception):
            partial = True
            logger.warning("source %s failed: %s", source.name, res)
            continue
        for position, food in enumerate(res):
            scored.append((ranking.score(food, query, position, history), food))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    merged = [food for _, food in scored]
    return SearchResult(results=_dedupe(merged), partial=partial)
