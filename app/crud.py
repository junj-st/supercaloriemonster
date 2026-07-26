from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Food
from app.schemas import NormalizedFood, Totals


def _find_existing(db: Session, food: NormalizedFood) -> Food | None:
    if food.source == "manual" or food.source_id is None:
        stmt = select(Food).where(
            Food.source == "manual",
            Food.name == food.name,
            Food.brand == food.brand,
        )
    else:
        stmt = select(Food).where(
            Food.source == food.source, Food.source_id == food.source_id
        )
    return db.execute(stmt).scalars().first()


def upsert_food(db: Session, food: NormalizedFood) -> Food:
    existing = _find_existing(db, food)
    if existing is None:
        existing = Food(source=food.source, source_id=food.source_id)
        db.add(existing)
    existing.name = food.name
    existing.brand = food.brand
    existing.calories_100g = food.calories_100g
    existing.protein_100g = food.protein_100g
    existing.carbs_100g = food.carbs_100g
    existing.fat_100g = food.fat_100g
    existing.serving_desc = food.serving_desc
    existing.serving_grams = food.serving_grams
    existing.cached_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    return existing


def compute_macros(food: Food, amount_g: float) -> Totals:
    factor = amount_g / 100.0
    return Totals(
        calories=round(food.calories_100g * factor, 1),
        protein_g=round(food.protein_100g * factor, 1),
        carbs_g=round(food.carbs_100g * factor, 1),
        fat_g=round(food.fat_100g * factor, 1),
    )


def to_normalized(food: Food) -> NormalizedFood:
    return NormalizedFood(
        source=food.source,
        source_id=food.source_id,
        name=food.name,
        brand=food.brand,
        calories_100g=food.calories_100g,
        protein_100g=food.protein_100g,
        carbs_100g=food.carbs_100g,
        fat_100g=food.fat_100g,
        serving_desc=food.serving_desc,
        serving_grams=food.serving_grams,
    )
