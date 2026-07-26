from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc, select
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
    rows = db.execute(
        select(Log.food_id).order_by(desc(Log.created_at), desc(Log.id))
    ).scalars().all()
    seen: set[int] = set()
    out: list[NormalizedFood] = []
    for food_id in rows:
        if food_id in seen:
            continue
        seen.add(food_id)
        food = db.get(Food, food_id)
        if food is not None:
            out.append(to_normalized(food))
        if len(out) >= limit:
            break
    return out
