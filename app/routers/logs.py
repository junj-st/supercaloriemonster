from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import compute_macros, upsert_food
from app.db import get_db
from app.models import Food, Log
from app.schemas import (
    MEAL_ORDER,
    DayOut,
    LogCreate,
    LogEntryOut,
    LogUpdate,
    Totals,
)

router = APIRouter(prefix="/logs", tags=["logs"])


def _entry_out(log: Log, food: Food) -> LogEntryOut:
    m = compute_macros(food, log.amount_g)
    return LogEntryOut(
        id=log.id, food_id=food.id, name=food.name, brand=food.brand,
        meal_type=log.meal_type, amount_g=log.amount_g,
        calories=m.calories, protein_g=m.protein_g,
        carbs_g=m.carbs_g, fat_g=m.fat_g,
    )


@router.post("", response_model=LogEntryOut, status_code=201)
def create_log(body: LogCreate, db: Session = Depends(get_db)) -> LogEntryOut:
    food = upsert_food(db, body.food)
    log = Log(food_id=food.id, date=body.date, meal_type=body.meal_type,
              amount_g=body.amount_g, created_at=datetime.now(timezone.utc))
    db.add(log)
    db.commit()
    db.refresh(log)
    return _entry_out(log, food)


@router.put("/{log_id}", response_model=LogEntryOut)
def update_log(log_id: int, body: LogUpdate, db: Session = Depends(get_db)) -> LogEntryOut:
    log = db.get(Log, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="log not found")
    if body.date is not None:
        log.date = body.date
    if body.meal_type is not None:
        log.meal_type = body.meal_type
    if body.amount_g is not None:
        log.amount_g = body.amount_g
    db.commit()
    db.refresh(log)
    return _entry_out(log, db.get(Food, log.food_id))


@router.delete("/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)) -> Response:
    log = db.get(Log, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="log not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)


@router.get("/day/{day}", response_model=DayOut)
def day_summary(day: date, db: Session = Depends(get_db)) -> DayOut:
    rows = db.execute(
        select(Log, Food).join(Food, Log.food_id == Food.id).where(Log.date == day)
    ).all()
    meals: dict[str, list[LogEntryOut]] = {m: [] for m in MEAL_ORDER}
    totals = Totals()
    for log, food in rows:
        entry = _entry_out(log, food)
        meals.setdefault(entry.meal_type, []).append(entry)
        totals.calories = round(totals.calories + entry.calories, 1)
        totals.protein_g = round(totals.protein_g + entry.protein_g, 1)
        totals.carbs_g = round(totals.carbs_g + entry.carbs_g, 1)
        totals.fat_g = round(totals.fat_g + entry.fat_g, 1)
    return DayOut(date=day, meals=meals, totals=totals)
