# supercaloriemonster (scm) Phase 1 MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, self-hosted calorie/macro tracker: search foods across USDA + Open Food Facts, log them by day and meal, see daily totals, and re-log from favorites/recents — served as a phone-first PWA and packaged with Docker.

**Architecture:** A FastAPI backend with SQLAlchemy over a single SQLite file. Two external food APIs sit behind one `FoodSource` interface and are normalized to a per-100g canonical shape; search queries both concurrently, merges, and returns ephemeral results. A food is persisted only when logged or favorited (upsert on `(source, source_id)`). A vanilla-JS static frontend (no build step) served by the same app provides Today / Search / History views and installs as a PWA. Docker Compose runs it locally with a bind-mounted data volume.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.x, Pydantic v2 + pydantic-settings, httpx (async external calls), pytest + pytest-asyncio, vanilla JS/HTML/CSS, Docker + Docker Compose.

## Global Constraints

- **Canonical nutrition unit:** every food stores nutrition **per 100g** in fields `calories_100g`, `protein_100g`, `carbs_100g`, `fat_100g`. Source serving info is stored separately in `serving_desc` (text) and `serving_grams` (float, nullable).
- **Log source of truth:** a log entry stores `amount_g` (actual grams). Totals are always `amount_g / 100 × <nutrient>_100g`.
- **Meal types:** exactly one of `breakfast | lunch | dinner | snack`.
- **Food source values:** `source` is exactly one of `usda | off | manual`.
- **Food identity / upsert key:** `UNIQUE(source, source_id)`. Manual foods have `source='manual'` and `source_id=NULL`.
- **Persist-on-use:** search results are never written to the DB; a food row is created only via a log or favorite create, or `POST /foods/manual`.
- **Config:** all settings from env via pydantic-settings. `USDA_API_KEY` is optional; when unset, USDA is skipped (OFF-only) with a logged warning — never a hard error.
- **Secrets/data hygiene:** `.env` and `data/*.db` are gitignored from commit #1. `.env.example` is committed.
- **DB file location:** `data/scm.db` (bind-mounted in Docker so it survives restarts).
- **Auth, rate limiting, public hosting, barcode, recipes, trends, CSV, multi-user, offline-write queue:** OUT OF SCOPE for this plan.

---

## File Structure

```
supercaloriemonster/
  app/
    __init__.py
    main.py            # FastAPI app, static mount, router include, startup
    config.py          # pydantic-settings Settings
    db.py              # SQLAlchemy engine/session, Base, get_db, init_db
    models.py          # ORM: Food, Log, Favorite
    schemas.py         # Pydantic: NormalizedFood, requests, responses
    crud.py            # upsert_food, macro math, day summary helpers
    sources/
      __init__.py
      base.py          # FoodSource Protocol + NormalizedFood re-export
      normalize.py     # normalize_usda, normalize_off
      off.py           # OFFFoodSource
      usda.py          # USDAFoodSource
      search.py        # search_foods(query, sources) -> SearchResult
    routers/
      __init__.py
      foods.py         # GET /foods/search, POST /foods/manual
      logs.py          # POST/PUT/DELETE /logs, GET /logs/day/{date}
      favorites.py     # GET/POST/DELETE /favorites, GET /recents
  static/
    index.html
    app.js
    style.css
    manifest.json
    sw.js
  tests/
    __init__.py
    conftest.py
    fixtures/
      usda_search.json
      off_search.json
    test_models.py
    test_normalize.py
    test_sources.py
    test_search.py
    test_foods_api.py
    test_logs_api.py
    test_favorites_api.py
    test_static.py
  data/                # scm.db (gitignored)
  .env.example
  .gitignore
  requirements.txt
  Dockerfile
  docker-compose.yml
  README.md
  LICENSE
```

**Note on existing state:** the repo already exists with `main` pushed and a committed spec at `docs/superpowers/specs/2026-07-24-supercaloriemonster-design.md`. This plan adds application code; it does not restructure existing files.

---

### Task 1: Project scaffold, config, and app skeleton

**Files:**
- Create: `.gitignore`, `LICENSE`, `requirements.txt`, `.env.example`
- Create: `app/__init__.py` (empty), `app/config.py`, `app/main.py`
- Create: `tests/__init__.py` (empty), `tests/conftest.py`, `tests/test_static.py` (health only for now)

**Interfaces:**
- Consumes: nothing.
- Produces: `app.config.Settings` (attributes: `usda_api_key: str | None`, `usda_base_url: str`, `off_base_url: str`, `db_path: str`, `http_timeout: float`); `app.config.get_settings() -> Settings` (cached). `app.main.app` (FastAPI instance) exposing `GET /health -> {"status": "ok"}`.

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.env
data/*.db
.pytest_cache/
.DS_Store
```

- [ ] **Step 2: Create `LICENSE` (MIT)**

```text
MIT License

Copyright (c) 2026 junj-st

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `requirements.txt`**

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
pydantic==2.10.4
pydantic-settings==2.7.1
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.25.2
```

- [ ] **Step 4: Create `.env.example`**

```text
# USDA FoodData Central API key (free: https://fdc.nal.usda.gov/api-key-signup.html)
# Leave unset to run Open Food Facts only.
USDA_API_KEY=
```

- [ ] **Step 5: Install dependencies**

Run: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
Expected: installs without error. (On later steps assume the venv is active.)

- [ ] **Step 6: Write `app/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    usda_api_key: str | None = None
    usda_base_url: str = "https://api.nal.usda.gov/fdc/v1"
    off_base_url: str = "https://world.openfoodfacts.org"
    db_path: str = "data/scm.db"
    http_timeout: float = 8.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 7: Write the failing test `tests/test_static.py`**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 8: Write `tests/conftest.py` (pytest-asyncio mode)**

```python
import pytest

pytest_plugins = []


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: async test")
```

Also create `pytest.ini` at repo root:

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 9: Write `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="supercaloriemonster")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 10: Run the test**

Run: `pytest tests/test_static.py -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add .gitignore LICENSE requirements.txt .env.example pytest.ini app/ tests/
git commit -m "chore: scaffold FastAPI app, config, and health endpoint"
```

---

### Task 2: Database layer and ORM models

**Files:**
- Create: `app/db.py`, `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.get_settings`.
- Produces:
  - `app.db.Base` (declarative base), `app.db.engine`, `app.db.SessionLocal`, `app.db.get_db()` (FastAPI dependency yielding a `Session`), `app.db.init_db()` (creates tables + `data/` dir).
  - `app.models.Food` columns: `id:int pk`, `source:str`, `source_id:str|None`, `name:str`, `brand:str|None`, `calories_100g:float`, `protein_100g:float`, `carbs_100g:float`, `fat_100g:float`, `serving_desc:str|None`, `serving_grams:float|None`, `cached_at:datetime`. Unique constraint on `(source, source_id)`.
  - `app.models.Log` columns: `id:int pk`, `food_id:int fk`, `date:date`, `meal_type:str`, `amount_g:float`, `created_at:datetime`; relationship `food`.
  - `app.models.Favorite` columns: `id:int pk`, `food_id:int fk unique`, `label:str|None`; relationship `food`.

- [ ] **Step 1: Write `app/db.py`**

```python
import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    import app.models  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Write the failing test `tests/test_models.py`**

```python
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Favorite, Food, Log


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_food_log_favorite_roundtrip():
    db = _session()
    food = Food(
        source="usda", source_id="123", name="Chicken breast",
        calories_100g=165.0, protein_100g=31.0, carbs_100g=0.0, fat_100g=3.6,
        serving_desc="100g", serving_grams=100.0, cached_at=datetime.utcnow(),
    )
    db.add(food)
    db.commit()

    log = Log(food_id=food.id, date=date(2026, 7, 24),
              meal_type="lunch", amount_g=200.0, created_at=datetime.utcnow())
    fav = Favorite(food_id=food.id, label="my chicken")
    db.add_all([log, fav])
    db.commit()

    assert log.food.name == "Chicken breast"
    assert fav.food.calories_100g == 165.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 4: Write `app/models.py`**

```python
from datetime import date, datetime

from sqlalchemy import DateTime, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Food(Base):
    __tablename__ = "foods"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_food_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    calories_100g: Mapped[float] = mapped_column(Float)
    protein_100g: Mapped[float] = mapped_column(Float)
    carbs_100g: Mapped[float] = mapped_column(Float)
    fat_100g: Mapped[float] = mapped_column(Float)
    serving_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    serving_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime)


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"))
    date: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String)
    amount_g: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    food: Mapped[Food] = relationship()


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), unique=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)

    food: Mapped[Food] = relationship()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db.py app/models.py tests/test_models.py
git commit -m "feat: add SQLAlchemy models and database layer"
```

---

### Task 3: Pydantic schemas and NormalizedFood

**Files:**
- Create: `app/schemas.py`
- Modify: none
- Test: folded into later API tasks (schemas are validated through use); add one direct validation test here.

**Interfaces:**
- Consumes: nothing (pure Pydantic).
- Produces:
  - `NormalizedFood(BaseModel)`: `source:str`, `source_id:str|None=None`, `name:str`, `brand:str|None=None`, `calories_100g:float`, `protein_100g:float`, `carbs_100g:float`, `fat_100g:float`, `serving_desc:str|None=None`, `serving_grams:float|None=None`.
  - `SearchResult(BaseModel)`: `results:list[NormalizedFood]`, `partial:bool=False`.
  - `ManualFoodIn`: same fields as `NormalizedFood` minus `source`/`source_id` (server sets `source='manual'`).
  - `LogCreate`: `food:NormalizedFood`, `date:datetime.date`, `meal_type:str`, `amount_g:float`.
  - `LogUpdate`: `date:date|None=None`, `meal_type:str|None=None`, `amount_g:float|None=None`.
  - `LogEntryOut`: `id:int`, `food_id:int`, `name:str`, `brand:str|None`, `meal_type:str`, `amount_g:float`, `calories:float`, `protein_g:float`, `carbs_g:float`, `fat_g:float`.
  - `Totals`: `calories:float`, `protein_g:float`, `carbs_g:float`, `fat_g:float`.
  - `DayOut`: `date:date`, `meals:dict[str,list[LogEntryOut]]`, `totals:Totals`.
  - `FavoriteIn`: `food:NormalizedFood`, `label:str|None=None`.
  - `FavoriteOut`: `id:int`, `food_id:int`, `label:str|None`, `food:NormalizedFood`.
  - `MEAL_TYPES: set[str] = {"breakfast","lunch","dinner","snack"}` and a validator that rejects other meal types.

- [ ] **Step 1: Write the failing test `tests/test_schemas.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas import LogCreate, NormalizedFood


def _food():
    return NormalizedFood(
        source="off", source_id="abc", name="Granola bar", brand="Acme",
        calories_100g=450.0, protein_100g=8.0, carbs_100g=60.0, fat_100g=18.0,
        serving_desc="1 bar", serving_grams=40.0,
    )


def test_normalized_food_defaults():
    f = NormalizedFood(source="manual", name="Water",
                       calories_100g=0, protein_100g=0, carbs_100g=0, fat_100g=0)
    assert f.brand is None and f.serving_grams is None


def test_logcreate_rejects_bad_meal_type():
    with pytest.raises(ValidationError):
        LogCreate(food=_food(), date="2026-07-24", meal_type="brunch", amount_g=40)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas'`.

- [ ] **Step 3: Write `app/schemas.py`**

```python
from datetime import date

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
    date: date
    meal_type: str
    amount_g: float

    @field_validator("meal_type")
    @classmethod
    def _meal(cls, v: str) -> str:
        return _validate_meal(v)


class LogUpdate(BaseModel):
    date: date | None = None
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
    date: date
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py tests/test_schemas.py
git commit -m "feat: add Pydantic schemas and NormalizedFood shape"
```

---

### Task 4: Normalization (highest-value tests)

**Files:**
- Create: `app/sources/__init__.py` (empty), `app/sources/normalize.py`
- Create fixtures: `tests/fixtures/usda_search.json`, `tests/fixtures/off_search.json`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: `app.schemas.NormalizedFood`.
- Produces:
  - `normalize_usda(item: dict) -> NormalizedFood | None` — maps one USDA FDC `foods[]` entry. USDA `foodNutrients` are already per-100g; nutrient numbers: Energy `1008` (kcal), Protein `1003`, Carbohydrate `1005`, Total lipid/fat `1004`. Returns `None` if energy is missing.
  - `normalize_off(product: dict) -> NormalizedFood | None` — maps one OFF `products[]` entry; nutrients live under `nutriments` as `energy-kcal_100g`, `proteins_100g`, `carbohydrates_100g`, `fat_100g`; serving from `serving_quantity` (grams) + `serving_size` (text). Returns `None` if energy is missing.

- [ ] **Step 1: Create `tests/fixtures/usda_search.json`** (trimmed real-shape sample)

```json
{
  "foods": [
    {
      "fdcId": 171077,
      "description": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
      "brandOwner": null,
      "foodNutrients": [
        {"nutrientNumber": "1008", "value": 165.0},
        {"nutrientNumber": "1003", "value": 31.0},
        {"nutrientNumber": "1005", "value": 0.0},
        {"nutrientNumber": "1004", "value": 3.57}
      ]
    },
    {
      "fdcId": 999999,
      "description": "Mystery food with no energy",
      "foodNutrients": [
        {"nutrientNumber": "1003", "value": 5.0}
      ]
    }
  ]
}
```

- [ ] **Step 2: Create `tests/fixtures/off_search.json`** (trimmed real-shape sample)

```json
{
  "products": [
    {
      "code": "3017620422003",
      "product_name": "Nutella",
      "brands": "Ferrero",
      "serving_quantity": 15,
      "serving_size": "15 g",
      "nutriments": {
        "energy-kcal_100g": 539,
        "proteins_100g": 6.3,
        "carbohydrates_100g": 57.5,
        "fat_100g": 30.9
      }
    },
    {
      "code": "0000000000000",
      "product_name": "No energy product",
      "brands": "",
      "nutriments": {"proteins_100g": 1}
    }
  ]
}
```

- [ ] **Step 3: Write the failing test `tests/test_normalize.py`**

```python
import json
from pathlib import Path

from app.sources.normalize import normalize_off, normalize_usda

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_normalize_usda_maps_per_100g():
    item = _load("usda_search.json")["foods"][0]
    f = normalize_usda(item)
    assert f.source == "usda"
    assert f.source_id == "171077"
    assert f.name.startswith("Chicken")
    assert f.calories_100g == 165.0
    assert f.protein_100g == 31.0
    assert f.carbs_100g == 0.0
    assert f.fat_100g == 3.57
    assert f.serving_desc == "100g"
    assert f.serving_grams == 100.0


def test_normalize_usda_returns_none_without_energy():
    item = _load("usda_search.json")["foods"][1]
    assert normalize_usda(item) is None


def test_normalize_off_maps_and_reads_serving():
    prod = _load("off_search.json")["products"][0]
    f = normalize_off(prod)
    assert f.source == "off"
    assert f.source_id == "3017620422003"
    assert f.name == "Nutella"
    assert f.brand == "Ferrero"
    assert f.calories_100g == 539
    assert f.protein_100g == 6.3
    assert f.serving_grams == 15
    assert f.serving_desc == "15 g"


def test_normalize_off_returns_none_without_energy():
    prod = _load("off_search.json")["products"][1]
    assert normalize_off(prod) is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sources.normalize'`.

- [ ] **Step 5: Write `app/sources/normalize.py`**

```python
from app.schemas import NormalizedFood

# USDA FoodData Central nutrient numbers (values are per 100g)
_USDA_ENERGY = "1008"
_USDA_PROTEIN = "1003"
_USDA_CARBS = "1005"
_USDA_FAT = "1004"


def _usda_nutrients(item: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for n in item.get("foodNutrients", []):
        num = str(n.get("nutrientNumber", ""))
        val = n.get("value")
        if num and val is not None:
            out[num] = float(val)
    return out


def normalize_usda(item: dict) -> NormalizedFood | None:
    nut = _usda_nutrients(item)
    if _USDA_ENERGY not in nut:
        return None
    brand = item.get("brandOwner") or item.get("brandName")
    return NormalizedFood(
        source="usda",
        source_id=str(item["fdcId"]),
        name=item.get("description", "").strip(),
        brand=brand or None,
        calories_100g=nut[_USDA_ENERGY],
        protein_100g=nut.get(_USDA_PROTEIN, 0.0),
        carbs_100g=nut.get(_USDA_CARBS, 0.0),
        fat_100g=nut.get(_USDA_FAT, 0.0),
        serving_desc="100g",
        serving_grams=100.0,
    )


def normalize_off(product: dict) -> NormalizedFood | None:
    nut = product.get("nutriments", {})
    energy = nut.get("energy-kcal_100g")
    if energy is None:
        return None
    brand = (product.get("brands") or "").split(",")[0].strip() or None
    serving_grams = product.get("serving_quantity")
    return NormalizedFood(
        source="off",
        source_id=str(product.get("code", "")),
        name=(product.get("product_name") or "").strip(),
        brand=brand,
        calories_100g=float(energy),
        protein_100g=float(nut.get("proteins_100g", 0.0)),
        carbs_100g=float(nut.get("carbohydrates_100g", 0.0)),
        fat_100g=float(nut.get("fat_100g", 0.0)),
        serving_desc=(product.get("serving_size") or None),
        serving_grams=float(serving_grams) if serving_grams is not None else None,
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS (4 passed).

- [ ] **Step 7: Commit**

```bash
git add app/sources/__init__.py app/sources/normalize.py tests/fixtures/ tests/test_normalize.py
git commit -m "feat: normalize USDA and OFF responses to per-100g shape"
```

---

### Task 5: FoodSource protocol, OFF and USDA sources

**Files:**
- Create: `app/sources/base.py`, `app/sources/off.py`, `app/sources/usda.py`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `normalize_off`, `normalize_usda`, `NormalizedFood`, `get_settings`.
- Produces:
  - `app.sources.base.FoodSource(Protocol)`: attribute `name: str`; `async search(self, query: str, client: httpx.AsyncClient) -> list[NormalizedFood]`; `async get(self, source_id: str, client: httpx.AsyncClient) -> NormalizedFood | None`.
  - `OFFFoodSource(name="off")` — hits `{off_base_url}/cgi/search.pl?search_terms=..&json=1&page_size=20` for search; `{off_base_url}/api/v2/product/{barcode}.json` for get.
  - `USDAFoodSource(name="usda")` — hits `{usda_base_url}/foods/search?api_key=..&query=..&pageSize=20`; `{usda_base_url}/food/{fdcId}?api_key=..` for get. Class exposes `enabled` (bool) = `api_key is not None`.

- [ ] **Step 1: Write the failing test `tests/test_sources.py`**

```python
import json
from pathlib import Path

import httpx
import pytest

from app.sources.off import OFFFoodSource
from app.sources.usda import USDAFoodSource

FIX = Path(__file__).parent / "fixtures"


def _mock_client(payload: dict) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_off_search_parses_results():
    payload = json.loads((FIX / "off_search.json").read_text())
    src = OFFFoodSource(base_url="https://off.test")
    async with _mock_client(payload) as client:
        results = await src.search("nutella", client)
    assert src.name == "off"
    assert results[0].name == "Nutella"
    # the no-energy product is dropped by normalization
    assert all(r.calories_100g is not None for r in results)
    assert len(results) == 1


async def test_usda_search_parses_results():
    payload = json.loads((FIX / "usda_search.json").read_text())
    src = USDAFoodSource(base_url="https://usda.test", api_key="KEY")
    async with _mock_client(payload) as client:
        results = await src.search("chicken", client)
    assert src.enabled is True
    assert results[0].source_id == "171077"
    assert len(results) == 1  # no-energy item dropped


def test_usda_disabled_without_key():
    src = USDAFoodSource(base_url="https://usda.test", api_key=None)
    assert src.enabled is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_sources.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sources.off'`.

- [ ] **Step 3: Write `app/sources/base.py`**

```python
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
```

- [ ] **Step 4: Write `app/sources/off.py`**

```python
import httpx

from app.schemas import NormalizedFood
from app.sources.normalize import normalize_off


class OFFFoodSource:
    name = "off"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def search(
        self, query: str, client: httpx.AsyncClient
    ) -> list[NormalizedFood]:
        resp = await client.get(
            f"{self.base_url}/cgi/search.pl",
            params={"search_terms": query, "json": 1, "page_size": 20},
        )
        resp.raise_for_status()
        products = resp.json().get("products", [])
        out = [normalize_off(p) for p in products]
        return [f for f in out if f is not None]

    async def get(
        self, source_id: str, client: httpx.AsyncClient
    ) -> NormalizedFood | None:
        resp = await client.get(f"{self.base_url}/api/v2/product/{source_id}.json")
        resp.raise_for_status()
        product = resp.json().get("product")
        return normalize_off(product) if product else None
```

- [ ] **Step 5: Write `app/sources/usda.py`**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_sources.py -v`
Expected: PASS (3 passed).

- [ ] **Step 7: Commit**

```bash
git add app/sources/base.py app/sources/off.py app/sources/usda.py tests/test_sources.py
git commit -m "feat: add FoodSource protocol with OFF and USDA implementations"
```

---

### Task 6: Concurrent search, merge, and ranking

**Files:**
- Create: `app/sources/search.py`
- Test: `tests/test_search.py`

**Interfaces:**
- Consumes: `FoodSource`, `NormalizedFood`, `SearchResult`.
- Produces: `async search_foods(query: str, sources: list[FoodSource], client: httpx.AsyncClient) -> SearchResult`. Behavior: runs every source's `search` concurrently (`asyncio.gather(return_exceptions=True)`); if any source raises, sets `partial=True` and uses the others' results; merges with ranking — branded results are interleaved so USDA generic matches rank first for un-branded queries; de-dupes by `(name.lower(), (brand or "").lower())`.

- [ ] **Step 1: Write the failing test `tests/test_search.py`**

```python
import httpx

from app.schemas import NormalizedFood
from app.sources.search import search_foods


class _FakeSource:
    def __init__(self, name, results=None, boom=False):
        self.name = name
        self._results = results or []
        self._boom = boom

    async def search(self, query, client):
        if self._boom:
            raise RuntimeError("source down")
        return self._results

    async def get(self, source_id, client):
        return None


def _food(name, brand=None, source="usda"):
    return NormalizedFood(source=source, source_id=name, name=name, brand=brand,
                          calories_100g=100, protein_100g=1, carbs_100g=1, fat_100g=1)


async def test_merge_dedupes_and_flags_partial():
    usda = _FakeSource("usda", [_food("Rice")])
    off = _FakeSource("off", boom=True)
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [usda, off], client)
    assert res.partial is True
    assert [f.name for f in res.results] == ["Rice"]


async def test_generic_ranks_before_branded():
    usda = _FakeSource("usda", [_food("Chicken breast")])
    off = _FakeSource("off", [_food("Chicken nuggets", brand="Acme", source="off")])
    async with httpx.AsyncClient() as client:
        res = await search_foods("chicken", [usda, off], client)
    assert res.partial is False
    assert res.results[0].name == "Chicken breast"  # generic first
    assert res.results[1].brand == "Acme"


async def test_dedupe_same_name_and_brand():
    a = _food("Milk")
    b = _food("milk")  # same name, different case, no brand
    src = _FakeSource("usda", [a, b])
    async with httpx.AsyncClient() as client:
        res = await search_foods("milk", [src], client)
    assert len(res.results) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sources.search'`.

- [ ] **Step 3: Write `app/sources/search.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/sources/search.py tests/test_search.py
git commit -m "feat: concurrent multi-source search with merge, rank, and partial flag"
```

---

### Task 7: CRUD helpers — upsert and macro math

**Files:**
- Create: `app/crud.py`
- Test: `tests/test_crud.py`

**Interfaces:**
- Consumes: `app.models` (Food, Log), `app.schemas.NormalizedFood`.
- Produces:
  - `upsert_food(db: Session, food: NormalizedFood) -> Food` — finds existing by `(source, source_id)` (or, for manual foods where `source_id is None`, by `(source='manual', name, brand)`); updates nutrition + `cached_at` on hit, inserts on miss; returns the persisted `Food`.
  - `compute_macros(food: Food, amount_g: float) -> Totals` — `amount_g/100 × <nutrient>_100g`, each rounded to 1 decimal.
  - `to_normalized(food: Food) -> NormalizedFood`.

- [ ] **Step 1: Write the failing test `tests/test_crud.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import compute_macros, to_normalized, upsert_food
from app.db import Base
from app.schemas import NormalizedFood


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _food():
    return NormalizedFood(source="usda", source_id="1", name="Rice",
                          calories_100g=130, protein_100g=2.7, carbs_100g=28,
                          fat_100g=0.3, serving_desc="100g", serving_grams=100)


def test_upsert_inserts_then_updates_same_row():
    db = _session()
    f1 = upsert_food(db, _food())
    updated = _food()
    updated.calories_100g = 150
    f2 = upsert_food(db, updated)
    assert f1.id == f2.id  # same row
    assert f2.calories_100g == 150


def test_compute_macros_scales_by_grams():
    db = _session()
    food = upsert_food(db, _food())
    m = compute_macros(food, 200.0)
    assert m.calories == 260.0
    assert m.protein_g == 5.4


def test_to_normalized_roundtrip():
    db = _session()
    food = upsert_food(db, _food())
    n = to_normalized(food)
    assert n.source == "usda" and n.source_id == "1" and n.name == "Rice"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crud.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.crud'`.

- [ ] **Step 3: Write `app/crud.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crud.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add app/crud.py tests/test_crud.py
git commit -m "feat: add upsert, macro math, and normalization CRUD helpers"
```

---

### Task 8: Shared test fixtures for the API layer

**Files:**
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: `app.main.app`, `app.db` (Base, get_db), `app.routers.foods.get_sources` (defined in Task 9; this fixture overrides it, so Task 9 must expose it).
- Produces: pytest fixtures `client` (TestClient with an isolated in-memory-file SQLite DB and dependency overrides) and `fake_sources` (a list with one controllable fake source). This centralizes DB isolation so every API test task reuses it.

- [ ] **Step 1: Replace `tests/conftest.py` with the shared harness**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.schemas import NormalizedFood


class FakeSource:
    """A controllable in-test food source. Set .results / .boom per test."""

    def __init__(self, name="usda"):
        self.name = name
        self.results: list[NormalizedFood] = []
        self.boom = False

    async def search(self, query, client):
        if self.boom:
            raise RuntimeError("boom")
        return self.results

    async def get(self, source_id, client):
        for r in self.results:
            if r.source_id == source_id:
                return r
        return None


@pytest.fixture
def fake_sources():
    return [FakeSource()]


@pytest.fixture
def client(fake_sources):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def _get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # get_sources is defined in app/routers/foods.py (Task 9)
    from app.routers.foods import get_sources

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_sources] = lambda: fake_sources
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Note**

This task has no standalone test; it is validated by Tasks 9–11 passing. Do NOT commit yet — commit it together with Task 9 (the fixture imports `get_sources`, which Task 9 creates, so it cannot pass in isolation).

---

### Task 9: Foods router — search and manual entry

**Files:**
- Create: `app/routers/__init__.py` (empty), `app/routers/foods.py`
- Modify: `app/main.py` (mount router, init DB on startup)
- Test: `tests/test_foods_api.py`

**Interfaces:**
- Consumes: `search_foods`, `upsert_food`, `to_normalized`, `get_db`, `get_settings`, schemas.
- Produces:
  - `app.routers.foods.get_sources() -> list[FoodSource]` — dependency building `[USDAFoodSource(...)]` (only if `enabled`) + `[OFFFoodSource(...)]` from settings. Logs a warning and omits USDA when the key is missing.
  - `GET /foods/search?q=...` → `SearchResult` JSON (`{results, partial}`); empty/blank `q` → `{results: [], partial: false}`.
  - `POST /foods/manual` (body `ManualFoodIn`) → persisted food as `NormalizedFood` (`source='manual'`).
  - `router` object included by `main.py`.

- [ ] **Step 1: Write the failing test `tests/test_foods_api.py`**

```python
from app.schemas import NormalizedFood


def _food(name="Rice", source="usda", sid="1"):
    return NormalizedFood(source=source, source_id=sid, name=name,
                          calories_100g=130, protein_100g=2.7, carbs_100g=28,
                          fat_100g=0.3, serving_desc="100g", serving_grams=100)


def test_search_returns_source_results(client, fake_sources):
    fake_sources[0].results = [_food("Brown rice")]
    resp = client.get("/foods/search", params={"q": "rice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["partial"] is False
    assert body["results"][0]["name"] == "Brown rice"


def test_search_blank_query_returns_empty(client):
    resp = client.get("/foods/search", params={"q": "  "})
    assert resp.json() == {"results": [], "partial": False}


def test_search_partial_when_source_fails(client, fake_sources):
    fake_sources[0].boom = True
    resp = client.get("/foods/search", params={"q": "rice"})
    assert resp.json() == {"results": [], "partial": True}


def test_manual_food_persists_as_manual(client):
    resp = client.post("/foods/manual", json={
        "name": "Grandma stew", "calories_100g": 120, "protein_100g": 9,
        "carbs_100g": 6, "fat_100g": 5, "serving_desc": "1 bowl",
        "serving_grams": 350,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["source"] == "manual"
    assert body["source_id"] is None
    assert body["name"] == "Grandma stew"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foods_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routers.foods'`.

- [ ] **Step 3: Write `app/routers/foods.py`**

```python
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
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        return await search_foods(q.strip(), sources, client)


@router.post("/manual", response_model=NormalizedFood, status_code=201)
def manual(body: ManualFoodIn, db: Session = Depends(get_db)) -> NormalizedFood:
    food = NormalizedFood(source="manual", source_id=None, **body.model_dump())
    saved = upsert_food(db, food)
    return to_normalized(saved)
```

- [ ] **Step 4: Update `app/main.py` to mount the router and init DB**

```python
import logging

from fastapi import FastAPI

from app.db import init_db
from app.routers import foods

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="supercaloriemonster")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(foods.router)
```

- [ ] **Step 5: Run tests (foods API + the conftest harness from Task 8)**

Run: `pytest tests/test_foods_api.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit (includes Task 8 conftest)**

```bash
git add app/routers/__init__.py app/routers/foods.py app/main.py tests/conftest.py tests/test_foods_api.py
git commit -m "feat: add foods router (search + manual) and shared test harness"
```

---

### Task 10: Logs router — CRUD and day summary

**Files:**
- Create: `app/routers/logs.py`
- Modify: `app/main.py` (include logs router)
- Test: `tests/test_logs_api.py`

**Interfaces:**
- Consumes: `upsert_food`, `compute_macros`, `get_db`, models, schemas.
- Produces:
  - `POST /logs` (body `LogCreate`) → `LogEntryOut`, 201. Upserts the food, then creates the log.
  - `PUT /logs/{id}` (body `LogUpdate`) → `LogEntryOut`; 404 if missing.
  - `DELETE /logs/{id}` → 204; 404 if missing.
  - `GET /logs/day/{date}` → `DayOut` with entries grouped into all four meal buckets (empty lists present) and summed totals.
  - `router` included by `main.py`.

- [ ] **Step 1: Write the failing test `tests/test_logs_api.py`**

```python
def _log_body(meal="lunch", amount=200, sid="1", name="Rice"):
    return {
        "food": {"source": "usda", "source_id": sid, "name": name,
                 "calories_100g": 130, "protein_100g": 2.7, "carbs_100g": 28,
                 "fat_100g": 0.3, "serving_desc": "100g", "serving_grams": 100},
        "date": "2026-07-24", "meal_type": meal, "amount_g": amount,
    }


def test_create_log_computes_macros(client):
    resp = client.post("/logs", json=_log_body())
    assert resp.status_code == 201
    body = resp.json()
    assert body["calories"] == 260.0
    assert body["meal_type"] == "lunch"


def test_day_summary_groups_and_totals(client):
    client.post("/logs", json=_log_body(meal="breakfast", amount=100))
    client.post("/logs", json=_log_body(meal="lunch", amount=200))
    resp = client.get("/logs/day/2026-07-24")
    body = resp.json()
    assert set(body["meals"].keys()) == {"breakfast", "lunch", "dinner", "snack"}
    assert len(body["meals"]["breakfast"]) == 1
    assert len(body["meals"]["dinner"]) == 0
    assert body["totals"]["calories"] == 130.0 + 260.0


def test_edit_and_delete_log(client):
    created = client.post("/logs", json=_log_body()).json()
    lid = created["id"]
    edited = client.put(f"/logs/{lid}", json={"amount_g": 100})
    assert edited.json()["calories"] == 130.0
    assert client.delete(f"/logs/{lid}").status_code == 204
    assert client.put(f"/logs/{lid}", json={"amount_g": 50}).status_code == 404


def test_reused_food_is_not_duplicated(client):
    client.post("/logs", json=_log_body(sid="1"))
    client.post("/logs", json=_log_body(sid="1", amount=50))
    # both logs point at the same upserted food row; day has 2 entries
    body = client.get("/logs/day/2026-07-24").json()
    assert len(body["meals"]["lunch"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logs_api.py -v`
Expected: FAIL with `404` / router not found (`/logs` unmounted).

- [ ] **Step 3: Write `app/routers/logs.py`**

```python
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import compute_macros, upsert_food
from app.db import get_db
from app.models import Food, Log
from app.schemas import (
    MEAL_TYPES,
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
              amount_g=body.amount_g, created_at=datetime.utcnow())
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
    meals: dict[str, list[LogEntryOut]] = {m: [] for m in sorted(MEAL_TYPES)}
    totals = Totals()
    for log, food in rows:
        entry = _entry_out(log, food)
        meals.setdefault(entry.meal_type, []).append(entry)
        totals.calories = round(totals.calories + entry.calories, 1)
        totals.protein_g = round(totals.protein_g + entry.protein_g, 1)
        totals.carbs_g = round(totals.carbs_g + entry.carbs_g, 1)
        totals.fat_g = round(totals.fat_g + entry.fat_g, 1)
    return DayOut(date=day, meals=meals, totals=totals)
```

- [ ] **Step 4: Include the router in `app/main.py`**

Modify the imports and the include section of `app/main.py`:

```python
from app.routers import foods, logs
```

and after `app.include_router(foods.router)` add:

```python
app.include_router(logs.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_logs_api.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add app/routers/logs.py app/main.py tests/test_logs_api.py
git commit -m "feat: add logs router with CRUD and day summary totals"
```

---

### Task 11: Favorites and recents router

**Files:**
- Create: `app/routers/favorites.py`
- Modify: `app/main.py` (include favorites router)
- Test: `tests/test_favorites_api.py`

**Interfaces:**
- Consumes: `upsert_food`, `to_normalized`, `get_db`, models, schemas.
- Produces:
  - `GET /favorites` → `list[FavoriteOut]`.
  - `POST /favorites` (body `FavoriteIn`) → `FavoriteOut`, 201; upserts food; if the food already has a favorite, updates its label instead of duplicating.
  - `DELETE /favorites/{id}` → 204; 404 if missing.
  - `GET /recents?limit=10` → `list[NormalizedFood]` — distinct foods from the most recent logs, newest first.
  - `router` included by `main.py`.

- [ ] **Step 1: Write the failing test `tests/test_favorites_api.py`**

```python
def _food(sid="1", name="Rice"):
    return {"source": "usda", "source_id": sid, "name": name,
            "calories_100g": 130, "protein_100g": 2.7, "carbs_100g": 28,
            "fat_100g": 0.3, "serving_desc": "100g", "serving_grams": 100}


def _log_body(sid="1", name="Rice", meal="lunch"):
    return {"food": _food(sid, name), "date": "2026-07-24",
            "meal_type": meal, "amount_g": 100}


def test_add_list_delete_favorite(client):
    add = client.post("/favorites", json={"food": _food(), "label": "staple"})
    assert add.status_code == 201
    fid = add.json()["id"]
    listed = client.get("/favorites").json()
    assert len(listed) == 1
    assert listed[0]["label"] == "staple"
    assert listed[0]["food"]["name"] == "Rice"
    assert client.delete(f"/favorites/{fid}").status_code == 204
    assert client.get("/favorites").json() == []


def test_favorite_same_food_updates_label(client):
    client.post("/favorites", json={"food": _food(), "label": "a"})
    client.post("/favorites", json={"food": _food(), "label": "b"})
    listed = client.get("/favorites").json()
    assert len(listed) == 1
    assert listed[0]["label"] == "b"


def test_recents_returns_distinct_recent_foods(client):
    client.post("/logs", json=_log_body(sid="1", name="Rice"))
    client.post("/logs", json=_log_body(sid="2", name="Eggs"))
    client.post("/logs", json=_log_body(sid="1", name="Rice"))  # repeat
    recents = client.get("/recents", params={"limit": 10}).json()
    names = [r["name"] for r in recents]
    assert names[0] == "Rice"  # most recent first
    assert names.count("Rice") == 1  # distinct
    assert "Eggs" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_favorites_api.py -v`
Expected: FAIL (routes unmounted → 404).

- [ ] **Step 3: Write `app/routers/favorites.py`**

```python
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
```

- [ ] **Step 4: Include the router in `app/main.py`**

Change the import line to:

```python
from app.routers import favorites, foods, logs
```

and after the logs include add:

```python
app.include_router(favorites.router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_favorites_api.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/routers/favorites.py app/main.py tests/test_favorites_api.py
git commit -m "feat: add favorites and recents endpoints"
```

---

### Task 12: Static frontend — Today, Search/Add, History

**Files:**
- Create: `static/index.html`, `static/style.css`, `static/app.js`
- Modify: `app/main.py` (mount static dir, serve `index.html` at `/`)
- Test: `tests/test_static.py` (extend to assert `/` serves the app shell)

**Interfaces:**
- Consumes: the JSON API from Tasks 9–11.
- Produces: a single-page app served at `/`. `app.js` uses `fetch` against `/foods/search`, `/logs`, `/logs/day/{date}`, `/favorites`, `/recents`. No build step.

- [ ] **Step 1: Extend `tests/test_static.py`**

```python
def test_root_serves_app_shell():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "supercaloriemonster" in resp.text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static.py::test_root_serves_app_shell -v`
Expected: FAIL (404, `/` not mounted yet).

- [ ] **Step 3: Write `static/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#111827" />
  <link rel="manifest" href="/static/manifest.json" />
  <link rel="stylesheet" href="/static/style.css" />
  <title>supercaloriemonster</title>
</head>
<body>
  <header>
    <h1>scm</h1>
    <nav>
      <button data-view="today" class="active">Today</button>
      <button data-view="search">Add</button>
      <button data-view="history">History</button>
    </nav>
  </header>

  <main>
    <section id="view-today" class="view">
      <div class="totals" id="totals"></div>
      <div id="day-meals"></div>
    </section>

    <section id="view-search" class="view hidden">
      <input id="search-box" type="search" placeholder="Search foods…" autocomplete="off" />
      <div id="search-results"></div>
      <div id="quick-lists"></div>
    </section>

    <section id="view-history" class="view hidden">
      <input id="history-date" type="date" />
      <div class="totals" id="history-totals"></div>
      <div id="history-meals"></div>
    </section>
  </main>

  <div id="log-dialog" class="hidden">
    <div class="dialog-card">
      <h3 id="log-food-name"></h3>
      <label>Meal
        <select id="log-meal">
          <option value="breakfast">Breakfast</option>
          <option value="lunch">Lunch</option>
          <option value="dinner">Dinner</option>
          <option value="snack">Snack</option>
        </select>
      </label>
      <label>Amount (g) <input id="log-grams" type="number" min="0" step="1" value="100" /></label>
      <div id="serving-hint" class="hint"></div>
      <div class="dialog-actions">
        <button id="log-cancel">Cancel</button>
        <button id="log-save">Save</button>
      </div>
    </div>
  </div>

  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write `static/style.css`**

```css
:root { --bg:#0b1220; --card:#111827; --fg:#e5e7eb; --muted:#9ca3af; --accent:#22c55e; }
* { box-sizing: border-box; }
body { margin:0; font-family: system-ui, sans-serif; background:var(--bg); color:var(--fg); }
header { position:sticky; top:0; background:var(--card); padding:12px 16px; }
header h1 { margin:0 0 8px; font-size:20px; }
nav { display:flex; gap:8px; }
nav button { flex:1; padding:10px; border:0; border-radius:8px; background:#1f2937; color:var(--fg); }
nav button.active { background:var(--accent); color:#04210f; font-weight:600; }
main { padding:16px; max-width:640px; margin:0 auto; }
.view.hidden, .hidden { display:none; }
.totals { display:flex; gap:8px; margin-bottom:16px; }
.totals .cell { flex:1; background:var(--card); border-radius:10px; padding:10px; text-align:center; }
.totals .cell b { display:block; font-size:18px; }
.totals .cell span { color:var(--muted); font-size:12px; }
.meal-block h4 { margin:16px 0 6px; color:var(--muted); text-transform:capitalize; }
.entry, .result, .quick { display:flex; justify-content:space-between; align-items:center;
  background:var(--card); padding:10px 12px; border-radius:8px; margin-bottom:6px; }
.entry small, .result small { color:var(--muted); }
.entry button { background:transparent; border:0; color:#ef4444; font-size:18px; }
input, select { background:#0b1220; color:var(--fg); border:1px solid #374151; border-radius:8px; padding:10px; width:100%; }
#search-box { margin-bottom:12px; }
#log-dialog { position:fixed; inset:0; background:rgba(0,0,0,.6); display:flex; align-items:flex-end; }
#log-dialog.hidden { display:none; }
.dialog-card { background:var(--card); width:100%; max-width:640px; margin:0 auto; padding:16px; border-radius:16px 16px 0 0; }
.dialog-card label { display:block; margin:12px 0; }
.dialog-actions { display:flex; gap:8px; margin-top:16px; }
.dialog-actions button { flex:1; padding:12px; border:0; border-radius:8px; }
#log-save { background:var(--accent); color:#04210f; font-weight:600; }
#log-cancel { background:#374151; color:var(--fg); }
.hint { color:var(--muted); font-size:12px; }
```

- [ ] **Step 5: Write `static/app.js`**

```javascript
const $ = (sel) => document.querySelector(sel);
const api = (path, opts) => fetch(path, opts).then((r) => (r.status === 204 ? null : r.json()));
const today = () => new Date().toISOString().slice(0, 10);

let pendingFood = null; // NormalizedFood awaiting log confirmation

// ---- view switching ----
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $("#view-" + btn.dataset.view).classList.remove("hidden");
    if (btn.dataset.view === "today") loadDay(today(), "#totals", "#day-meals");
    if (btn.dataset.view === "search") loadQuickLists();
  });
});

// ---- totals + meals rendering ----
function renderTotals(el, t) {
  $(el).innerHTML = [["cal", t.calories], ["P", t.protein_g], ["C", t.carbs_g], ["F", t.fat_g]]
    .map(([k, v]) => `<div class="cell"><b>${v}</b><span>${k}</span></div>`).join("");
}

function renderMeals(el, meals) {
  $(el).innerHTML = Object.entries(meals).map(([meal, entries]) => {
    if (!entries.length) return "";
    const rows = entries.map((e) => `
      <div class="entry">
        <div><div>${e.name}</div><small>${e.amount_g} g · ${e.calories} cal</small></div>
        <button data-del="${e.id}">✕</button>
      </div>`).join("");
    return `<div class="meal-block"><h4>${meal}</h4>${rows}</div>`;
  }).join("");
  $(el).querySelectorAll("[data-del]").forEach((b) =>
    b.addEventListener("click", async () => {
      await fetch("/logs/" + b.dataset.del, { method: "DELETE" });
      loadDay(today(), "#totals", "#day-meals");
    }));
}

async function loadDay(date, totalsEl, mealsEl) {
  const day = await api("/logs/day/" + date);
  renderTotals(totalsEl, day.totals);
  renderMeals(mealsEl, day.meals);
}

// ---- search ----
let searchTimer = null;
$("#search-box").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  const q = e.target.value.trim();
  if (!q) return loadQuickLists();
  searchTimer = setTimeout(async () => {
    const res = await api("/foods/search?q=" + encodeURIComponent(q));
    renderResults("#search-results", res.results);
    $("#quick-lists").innerHTML = res.partial ? "<small>Some sources were unavailable.</small>" : "";
  }, 300);
});

function renderResults(el, foods) {
  $(el).innerHTML = foods.map((f, i) => `
    <div class="result" data-i="${i}">
      <div><div>${f.name}</div><small>${f.brand || "generic"} · ${f.calories_100g} cal/100g</small></div>
      <button>＋</button>
    </div>`).join("");
  $(el).querySelectorAll(".result").forEach((row) =>
    row.addEventListener("click", () => openLogDialog(foods[row.dataset.i])));
}

async function loadQuickLists() {
  $("#search-results").innerHTML = "";
  const [recents, favorites] = await Promise.all([api("/recents?limit=10"), api("/favorites")]);
  const favFoods = favorites.map((f) => f.food);
  const section = (title, foods) => foods.length
    ? `<h4>${title}</h4>` + foods.map((f, i) =>
        `<div class="quick" data-list="${title}" data-i="${i}"><span>${f.name}</span><button>＋</button></div>`).join("")
    : "";
  $("#quick-lists").innerHTML = section("Recents", recents) + section("Favorites", favFoods);
  $("#quick-lists").querySelectorAll(".quick").forEach((row) => {
    const list = row.dataset.list === "Recents" ? recents : favFoods;
    row.addEventListener("click", () => openLogDialog(list[row.dataset.i]));
  });
}

// ---- log dialog ----
function openLogDialog(food) {
  pendingFood = food;
  $("#log-food-name").textContent = food.name;
  $("#log-grams").value = food.serving_grams || 100;
  $("#serving-hint").textContent = food.serving_grams
    ? `1 serving ≈ ${food.serving_grams} g${food.serving_desc ? " (" + food.serving_desc + ")" : ""}` : "";
  $("#log-dialog").classList.remove("hidden");
}
$("#log-cancel").addEventListener("click", () => $("#log-dialog").classList.add("hidden"));
$("#log-save").addEventListener("click", async () => {
  await api("/logs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      food: pendingFood, date: today(),
      meal_type: $("#log-meal").value, amount_g: parseFloat($("#log-grams").value),
    }),
  });
  $("#log-dialog").classList.add("hidden");
  document.querySelector('nav button[data-view="today"]').click();
});

// ---- history ----
$("#history-date").value = today();
$("#history-date").addEventListener("change", (e) =>
  loadDay(e.target.value, "#history-totals", "#history-meals"));

// ---- boot ----
loadDay(today(), "#totals", "#day-meals");
```

- [ ] **Step 6: Mount static files and serve the shell in `app/main.py`**

Add imports:

```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
```

After the routers are included, add:

```python
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")
```

- [ ] **Step 7: Run static tests**

Run: `pytest tests/test_static.py -v`
Expected: PASS (health + app shell).

- [ ] **Step 8: Manual smoke test**

Run: `uvicorn app.main:app --reload` then open `http://localhost:8000`.
Expected: Today view loads (empty totals); Add tab searches (OFF works without a key); tapping a result opens the log dialog; saving returns to Today with the entry and totals.

- [ ] **Step 9: Commit**

```bash
git add static/index.html static/style.css static/app.js app/main.py tests/test_static.py
git commit -m "feat: add vanilla-JS frontend (today, search, history)"
```

---

### Task 13: PWA — manifest and service worker

**Files:**
- Create: `static/manifest.json`, `static/sw.js`
- Modify: `static/app.js` (register the service worker)
- Test: `tests/test_static.py` (assert manifest is served with correct content-type/keys)

**Interfaces:**
- Consumes: static mount from Task 12.
- Produces: installable PWA. `sw.js` caches the app shell (`/`, `/static/*`) for offline viewing; network-first for `/logs/day/*` GETs with cache fallback so recently-viewed days show offline. Writes (POST/PUT/DELETE) are never intercepted (online-only, per scope).

- [ ] **Step 1: Extend `tests/test_static.py`**

```python
def test_manifest_served():
    resp = client.get("/static/manifest.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "supercaloriemonster"
    assert body["display"] == "standalone"
    assert body["start_url"] == "/"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static.py::test_manifest_served -v`
Expected: FAIL (manifest.json does not exist → 404).

- [ ] **Step 3: Write `static/manifest.json`**

```json
{
  "name": "supercaloriemonster",
  "short_name": "scm",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0b1220",
  "theme_color": "#111827",
  "icons": [
    {
      "src": "/static/icon.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 4: Create `static/icon.svg`** (simple inline icon so the manifest reference resolves)

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="36" fill="#22c55e"/>
  <text x="96" y="128" font-size="96" text-anchor="middle" font-family="system-ui" fill="#04210f">scm</text>
</svg>
```

- [ ] **Step 5: Write `static/sw.js`**

```javascript
const CACHE = "scm-shell-v1";
const SHELL = ["/", "/static/index.html", "/static/style.css", "/static/app.js", "/static/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return; // never intercept writes

  const url = new URL(request.url);
  // network-first for day summaries so recently-viewed days work offline
  if (url.pathname.startsWith("/logs/day/")) {
    e.respondWith(
      fetch(request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }
  // cache-first for the app shell / static assets
  if (url.origin === location.origin && (url.pathname === "/" || url.pathname.startsWith("/static/"))) {
    e.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
```

- [ ] **Step 6: Register the service worker — append to `static/app.js`**

```javascript
// ---- PWA registration ----
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/static/sw.js"));
}
```

- [ ] **Step 7: Run static tests**

Run: `pytest tests/test_static.py -v`
Expected: PASS (health, app shell, manifest).

- [ ] **Step 8: Manual PWA check**

Run: `uvicorn app.main:app --reload`, open `http://localhost:8000` in Chrome → DevTools → Application → Manifest shows "supercaloriemonster"; Service Workers shows `sw.js` activated. On a phone on the same network, "Add to Home Screen" installs it.

- [ ] **Step 9: Commit**

```bash
git add static/manifest.json static/icon.svg static/sw.js static/app.js tests/test_static.py
git commit -m "feat: add PWA manifest and offline service worker"
```

---

### Task 14: Dockerize and finalize README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `README.md`
- Modify: none
- Test: manual (container build + run); the pytest suite already covers the app.

**Interfaces:**
- Consumes: the full app.
- Produces: `docker compose up` serving the app at `http://localhost:8000` with `data/` bind-mounted so `scm.db` survives restarts. Same image redeploys to Fly.io/Railway unchanged (Phase 2).

- [ ] **Step 1: Create `.dockerignore`**

```text
.venv/
venv/
__pycache__/
.pytest_cache/
data/*.db
.git/
docs/
tests/
.env
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY static/ ./static/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  scm:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - USDA_API_KEY=${USDA_API_KEY:-}
    restart: unless-stopped
```

- [ ] **Step 4: Create `README.md`**

```markdown
# supercaloriemonster (scm)

A free, self-hosted calorie and macro tracker. Search foods across USDA
FoodData Central and Open Food Facts, log them by day and meal, and see daily
calorie/protein/carb/fat totals. Phone-first PWA, single SQLite file, no
subscriptions.

## Tech stack

FastAPI · SQLAlchemy · SQLite · vanilla-JS PWA · Docker.

## Run locally (Docker)

```bash
cp .env.example .env   # optionally add your free USDA_API_KEY
docker compose up --build
```

Open http://localhost:8000. Without a USDA key it runs Open Food Facts only.

## Run locally (without Docker)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Configuration

| Env var        | Default | Purpose |
|----------------|---------|---------|
| `USDA_API_KEY` | (unset) | Free key from https://fdc.nal.usda.gov/api-key-signup.html. Unset → OFF-only. |

Your data lives in `data/scm.db` (gitignored). Back it up by copying that file.

## Tests

```bash
pytest -v
```

## API

Interactive docs at http://localhost:8000/docs.

## License

MIT — see [LICENSE](LICENSE).
```

- [ ] **Step 5: Build and run the container**

Run: `docker compose up --build`
Expected: image builds; server logs "Uvicorn running on http://0.0.0.0:8000".

- [ ] **Step 6: Verify persistence**

Log a food at `http://localhost:8000`, then `docker compose down && docker compose up`. Reopen Today — the entry is still there (proves the `data/` volume persists `scm.db`).

- [ ] **Step 7: Run the full test suite one final time**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 8: Commit and push**

```bash
git add Dockerfile docker-compose.yml .dockerignore README.md
git commit -m "feat: dockerize app and add README"
git push
```

---

## Self-Review

**Spec coverage:**
- Data model (per-100g + serving, grams-based logs) → Tasks 2, 3, 7. ✓
- USDA + OFF behind a FoodSource interface, normalization → Tasks 4, 5. ✓
- Concurrent search, merge/rank, `partial` flag → Task 6. ✓
- Persist-on-use upsert on `(source, source_id)` → Task 7 (`upsert_food`), used by Tasks 10, 11. ✓
- API surface (search, manual, logs CRUD, day summary, favorites, recents) → Tasks 9, 10, 11. ✓
- Missing-USDA-key → OFF-only with warning → Task 9 (`get_sources`), config in Task 1. ✓
- Vanilla-JS Today/Search/History frontend → Task 12. ✓
- PWA manifest + service worker (offline day viewing, online-only writes) → Task 13. ✓
- Docker Compose with persistent `data/` volume → Task 14. ✓
- Git/secrets hygiene (`.env`, `data/*.db` gitignored; `.env.example`; MIT LICENSE; README) → Tasks 1, 14. ✓
- Testing: normalize fixtures (highest value), endpoint tests with mocked sources → Tasks 4, 8–11. ✓
- Out-of-scope items (auth, rate limiting, barcode, recipes, trends, CSV, multi-user, offline-write) → intentionally absent. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step contains full code. ✓

**Type consistency:** `NormalizedFood`, `SearchResult`, `Totals`, `LogEntryOut`, `DayOut`, `FavoriteOut` field names and `get_sources`/`upsert_food`/`compute_macros`/`to_normalized`/`search_foods` signatures are used identically across Tasks 3–13. The conftest override in Task 8 targets `app.routers.foods.get_sources`, which Task 9 defines (committed together). ✓
