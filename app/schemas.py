from datetime import date as _date

from pydantic import BaseModel, field_validator

MEAL_TYPES: set[str] = {"breakfast", "lunch", "dinner", "snack"}


class NormalizedFood(BaseModel):
    source: str
    source_id: str | None = None
    name: str
    brand: str | None = None
    calories_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    serving_desc: str | None = None
    serving_grams: float | None = None


class SearchResult(BaseModel):
    results: list[NormalizedFood]
    partial: bool = False


class ManualFoodIn(BaseModel):
    name: str
    brand: str | None = None
    calories_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    serving_desc: str | None = None
    serving_grams: float | None = None


def _validate_meal(value: str) -> str:
    if value not in MEAL_TYPES:
        raise ValueError(f"meal_type must be one of {sorted(MEAL_TYPES)}")
    return value


class LogCreate(BaseModel):
    food: NormalizedFood
    date: _date
    meal_type: str
    amount_g: float

    @field_validator("meal_type")
    @classmethod
    def _meal(cls, v: str) -> str:
        return _validate_meal(v)


class LogUpdate(BaseModel):
    date: _date | None = None
    meal_type: str | None = None
    amount_g: float | None = None

    @field_validator("meal_type")
    @classmethod
    def _meal(cls, v: str | None) -> str | None:
        return _validate_meal(v) if v is not None else v


class LogEntryOut(BaseModel):
    id: int
    food_id: int
    name: str
    brand: str | None
    meal_type: str
    amount_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class Totals(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


class DayOut(BaseModel):
    date: _date
    meals: dict[str, list[LogEntryOut]]
    totals: Totals


class FavoriteIn(BaseModel):
    food: NormalizedFood
    label: str | None = None


class FavoriteOut(BaseModel):
    id: int
    food_id: int
    label: str | None
    food: NormalizedFood
