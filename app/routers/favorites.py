from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.crud import to_normalized, upsert_food
from app.db import get_db
from app.models import Favorite, Food, Log
from app.schemas import FavoriteIn, FavoriteOut, NormalizedFood

router = APIRouter(tags=["favorites"])


def _favorite_out(fav: Favorite, food: Food) -> FavoriteOut:
    return FavoriteOut(id=fav.id, food_id=food.id, label=fav.label,
                       food=to_normalized(food))


@router.get("/favorites", response_model=list[FavoriteOut])
def list_favorites(db: Session = Depends(get_db)) -> list[FavoriteOut]:
    rows = db.execute(
        select(Favorite, Food).join(Food, Favorite.food_id == Food.id)
    ).all()
    return [_favorite_out(fav, food) for fav, food in rows]


@router.post("/favorites", response_model=FavoriteOut, status_code=201)
def add_favorite(body: FavoriteIn, db: Session = Depends(get_db)) -> FavoriteOut:
    food = upsert_food(db, body.food)
    fav = db.execute(
        select(Favorite).where(Favorite.food_id == food.id)
    ).scalars().first()
    if fav is None:
        fav = Favorite(food_id=food.id, label=body.label)
        db.add(fav)
    else:
        fav.label = body.label
    db.commit()
    db.refresh(fav)
    return _favorite_out(fav, food)


@router.delete("/favorites/{fav_id}", status_code=204)
def delete_favorite(fav_id: int, db: Session = Depends(get_db)) -> Response:
    fav = db.get(Favorite, fav_id)
    if fav is None:
        raise HTTPException(status_code=404, detail="favorite not found")
    db.delete(fav)
    db.commit()
    return Response(status_code=204)


@router.get("/recents", response_model=list[NormalizedFood])
def recents(limit: int = 10, db: Session = Depends(get_db)) -> list[NormalizedFood]:
    if limit <= 0:
        return []
    last_log = (
        select(
            Log.food_id.label("food_id"),
            func.max(Log.created_at).label("last_created"),
            func.max(Log.id).label("last_id"),
        )
        .group_by(Log.food_id)
        .subquery()
    )
    rows = (
        db.execute(
            select(Food)
            .join(last_log, Food.id == last_log.c.food_id)
            .order_by(desc(last_log.c.last_created), desc(last_log.c.last_id))
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [to_normalized(food) for food in rows]
