import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.crud import to_normalized, upsert_food
from app.db import get_db
from app.schemas import ManualFoodIn, NormalizedFood, SearchResult
from app.sources.base import FoodSource
from app.sources.off import OFFFoodSource
from app.sources.search import search_foods
from app.sources.usda import USDAFoodSource

logger = logging.getLogger("scm.foods")
router = APIRouter(prefix="/foods", tags=["foods"])


def get_sources(settings: Settings = Depends(get_settings)) -> list[FoodSource]:
    sources: list[FoodSource] = []
    usda = USDAFoodSource(settings.usda_base_url, settings.usda_api_key)
    if usda.enabled:
        sources.append(usda)
    else:
        logger.warning("USDA_API_KEY not set — running Open Food Facts only")
    sources.append(OFFFoodSource(settings.off_base_url))
    return sources


@router.get("/search", response_model=SearchResult)
async def search(
    q: str = "",
    sources: list[FoodSource] = Depends(get_sources),
    settings: Settings = Depends(get_settings),
) -> SearchResult:
    if not q.strip():
        return SearchResult(results=[], partial=False)
    async with httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": "supercaloriemonster/1.0 (https://github.com/junj-st/supercaloriemonster)"},
    ) as client:
        return await search_foods(q.strip(), sources, client)


@router.post("/manual", response_model=NormalizedFood, status_code=201)
def manual(body: ManualFoodIn, db: Session = Depends(get_db)) -> NormalizedFood:
    food = NormalizedFood(source="manual", source_id=None, **body.model_dump())
    saved = upsert_food(db, food)
    return to_normalized(saved)
