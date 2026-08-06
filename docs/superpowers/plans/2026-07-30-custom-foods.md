# Custom Foods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users create, manage (list/edit/delete), and search their own custom food items, with correct History behavior.

**Architecture:** Snapshot each food's macros onto the `Log` row at log time so edits/deletes of a custom food never rewrite past History. Expose CRUD endpoints under `/foods/manual`. Inject the user's matching custom foods at the top of search results (mirroring the existing staples prepend). Add a "Foods" tab + an "Add custom food" flow to the neo-brutalist PWA, with a per-serving/per-100g input toggle and a "Custom" badge in search.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (typed `Mapped`), SQLite, Pydantic v2, vanilla-JS PWA, pytest + FastAPI `TestClient`.

## Global Constraints

- Python: SQLAlchemy 2.0 typed models (`Mapped[...]`, `mapped_column`); Pydantic v2 (`BaseModel`, `field_validator`).
- Datetimes: timezone-aware — `datetime.now(timezone.utc)`. Never naive.
- Backend endpoint contract for macros is **per-100g**; per-serving↔per-100g conversion happens only in the frontend.
- Custom foods are `Food` rows with `source="manual"`, `source_id=None`, dedup'd by (name, brand) via `crud._find_existing` (already implemented).
- Service worker is network-first with versioned assets: when `static/*` changes, bump the `?v=nb1` query on the CSS/JS refs in `static/index.html`.
- Frontend is neo-brutalist (thick borders, hard offset shadows, macro color blocks, mono numerals). Tokens live in `static/style.css`. Do NOT revert to the superseded `docs/frontend-styling-guide.md`.
- Keep the whole suite green (currently 65 tests) and warning-free.

---

## File Structure

- `app/models.py` — add snapshot columns to `Log`; make `Log.food_id` nullable.
- `app/db.py` — add idempotent `_migrate(engine)`; call it from `init_db()`.
- `app/schemas.py` — add `ManualFoodOut`; make `LogEntryOut.food_id` nullable.
- `app/crud.py` — add `custom_matches(db, query)`; `compute_macros` reused for `Log` snapshots via duck typing.
- `app/routers/logs.py` — snapshot on create; read snapshot in `_entry_out`/day query (drop the `Food` join).
- `app/routers/foods.py` — add `GET`/`PUT`/`DELETE /foods/manual`; wire `custom_matches` into search.
- `app/sources/search.py` — accept `custom_foods` and prepend ahead of staple.
- `static/index.html` — Foods nav tab + view, custom-food form modal, bumped asset version.
- `static/app.js` — Custom badge, Foods view (list/edit/delete), add-food form + toggle, add-view button.
- `static/style.css` — badge + form styles.
- Tests: `tests/test_db_migrate.py` (new), plus additions to `tests/test_logs_api.py`, `tests/test_foods_api.py`, `tests/test_crud.py`, `tests/test_search.py`, `tests/test_static.py`.

---

### Task 1: Log snapshot columns + migration/backfill

**Files:**
- Modify: `app/models.py` (Log model)
- Modify: `app/db.py` (add `_migrate`, call from `init_db`)
- Test: `tests/test_db_migrate.py` (create)

**Interfaces:**
- Produces: `Log` gains columns `name`, `brand`, `calories_100g`, `protein_100g`, `carbs_100g`, `fat_100g`, `serving_desc`, `serving_grams`; `Log.food_id` becomes `int | None`. `app.db._migrate(engine) -> None` — idempotent ALTER+backfill for pre-existing `logs` tables.

- [ ] **Step 1: Write the failing test**

Create `tests/test_db_migrate.py`:

```python
from sqlalchemy import create_engine

from app.db import _migrate


def _old_schema(engine):
    with engine.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE foods (id INTEGER PRIMARY KEY, source TEXT, source_id TEXT,"
            " name TEXT, brand TEXT, calories_100g FLOAT, protein_100g FLOAT,"
            " carbs_100g FLOAT, fat_100g FLOAT, serving_desc TEXT, serving_grams FLOAT,"
            " cached_at TIMESTAMP)"
        )
        c.exec_driver_sql(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY, food_id INTEGER, date DATE,"
            " meal_type TEXT, amount_g FLOAT, created_at TIMESTAMP)"
        )
        c.exec_driver_sql(
            "INSERT INTO foods (id, source, name, calories_100g, protein_100g,"
            " carbs_100g, fat_100g) VALUES (1,'manual','Stew',120,9,6,5)"
        )
        c.exec_driver_sql(
            "INSERT INTO logs (id, food_id, date, meal_type, amount_g, created_at)"
            " VALUES (1,1,'2026-07-28','lunch',100,'2026-07-28')"
        )


def test_migrate_adds_columns_and_backfills(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _old_schema(engine)

    _migrate(engine)

    with engine.begin() as c:
        cols = {r[1] for r in c.exec_driver_sql("PRAGMA table_info(logs)")}
        assert {"name", "calories_100g", "serving_grams"} <= cols
        row = c.exec_driver_sql(
            "SELECT name, calories_100g FROM logs WHERE id=1"
        ).fetchone()
    assert row[0] == "Stew"
    assert row[1] == 120


def test_migrate_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _old_schema(engine)
    _migrate(engine)
    _migrate(engine)  # must not raise
    with engine.begin() as c:
        row = c.exec_driver_sql("SELECT name FROM logs WHERE id=1").fetchone()
    assert row[0] == "Stew"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_migrate.py -v`
Expected: FAIL with `ImportError: cannot import name '_migrate'`.

- [ ] **Step 3: Add snapshot columns to the Log model**

In `app/models.py`, replace the `Log` class body's columns so it reads:

```python
class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String)
    amount_g: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    # Macros snapshotted at log time — History is independent of later food edits/deletes.
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    calories_100g: Mapped[float] = mapped_column(Float, default=0.0)
    protein_100g: Mapped[float] = mapped_column(Float, default=0.0)
    carbs_100g: Mapped[float] = mapped_column(Float, default=0.0)
    fat_100g: Mapped[float] = mapped_column(Float, default=0.0)
    serving_desc: Mapped[str | None] = mapped_column(String, nullable=True)
    serving_grams: Mapped[float | None] = mapped_column(Float, nullable=True)

    food: Mapped["Food"] = relationship()
```

- [ ] **Step 4: Add `_migrate` and call it from `init_db`**

In `app/db.py`, add after the `engine`/`SessionLocal` setup:

```python
_LOG_SNAPSHOT_COLUMNS = {
    "name": "VARCHAR",
    "brand": "VARCHAR",
    "calories_100g": "FLOAT",
    "protein_100g": "FLOAT",
    "carbs_100g": "FLOAT",
    "fat_100g": "FLOAT",
    "serving_desc": "VARCHAR",
    "serving_grams": "FLOAT",
}


def _migrate(bind=engine) -> None:
    """Idempotently add snapshot columns to a pre-existing `logs` table and
    backfill them from the referenced food. New databases are created with the
    columns already present by `create_all`, so this is a no-op for them."""
    with bind.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(logs)")}
        if not cols:
            return
        added = False
        for name, coltype in _LOG_SNAPSHOT_COLUMNS.items():
            if name not in cols:
                conn.exec_driver_sql(f"ALTER TABLE logs ADD COLUMN {name} {coltype}")
                added = True
        if added:
            conn.exec_driver_sql(
                """
                UPDATE logs SET
                  name = (SELECT f.name FROM foods f WHERE f.id = logs.food_id),
                  brand = (SELECT f.brand FROM foods f WHERE f.id = logs.food_id),
                  calories_100g = (SELECT f.calories_100g FROM foods f WHERE f.id = logs.food_id),
                  protein_100g = (SELECT f.protein_100g FROM foods f WHERE f.id = logs.food_id),
                  carbs_100g = (SELECT f.carbs_100g FROM foods f WHERE f.id = logs.food_id),
                  fat_100g = (SELECT f.fat_100g FROM foods f WHERE f.id = logs.food_id),
                  serving_desc = (SELECT f.serving_desc FROM foods f WHERE f.id = logs.food_id),
                  serving_grams = (SELECT f.serving_grams FROM foods f WHERE f.id = logs.food_id)
                WHERE calories_100g IS NULL AND food_id IN (SELECT id FROM foods)
                """
            )
```

Then update `init_db()` to run the migration after `create_all`:

```python
def init_db() -> None:
    import app.models  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)
    _migrate(engine)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db_migrate.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Run the full suite (schema change is broad)**

Run: `pytest -q`
Expected: PASS, no warnings. (Existing log tests still pass — `create_all` builds the new columns; snapshot values are written starting in Task 2.)

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/db.py tests/test_db_migrate.py
git commit -m "feat: snapshot columns on Log + idempotent migration"
```

---

### Task 2: Snapshot macros on log-create; read snapshot in History

**Files:**
- Modify: `app/schemas.py:68-78` (`LogEntryOut.food_id` → nullable)
- Modify: `app/routers/logs.py` (`_entry_out`, `create_log`, `update_log`, `day_summary`)
- Test: `tests/test_logs_api.py`

**Interfaces:**
- Consumes: `Log` snapshot columns (Task 1); `crud.compute_macros(src, amount_g)` reads `.calories_100g`/`.protein_100g`/`.carbs_100g`/`.fat_100g` — works on a `Log` by duck typing.
- Produces: `_entry_out(log: Log) -> LogEntryOut` (no `Food` arg). Day totals and entries derive from the log snapshot only.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_logs_api.py`:

```python
def test_history_frozen_after_food_edit(client):
    # Log a manual food at 120 cal/100g, 100 g -> 120 cal.
    client.post("/logs", json={
        "food": {"source": "manual", "source_id": None, "name": "Stew",
                 "calories_100g": 120, "protein_100g": 9, "carbs_100g": 6,
                 "fat_100g": 5, "serving_desc": "1 bowl", "serving_grams": 350},
        "date": "2026-07-28", "meal_type": "lunch", "amount_g": 100,
    })
    # Edit the same manual food's macros via re-POST (upsert by name+brand).
    client.post("/foods/manual", json={
        "name": "Stew", "calories_100g": 999, "protein_100g": 1,
        "carbs_100g": 1, "fat_100g": 1,
    })
    # Past History must still reflect the snapshot (120), not 999.
    day = client.get("/logs/day/2026-07-28").json()
    assert day["totals"]["calories"] == 120.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logs_api.py::test_history_frozen_after_food_edit -v`
Expected: FAIL — totals recompute from the edited food (999) instead of the snapshot.

- [ ] **Step 3: Make `LogEntryOut.food_id` nullable**

In `app/schemas.py`, change the `LogEntryOut` field:

```python
class LogEntryOut(BaseModel):
    id: int
    food_id: int | None
    name: str
    brand: str | None
    meal_type: str
    amount_g: float
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
```

- [ ] **Step 4: Snapshot on create and read snapshot everywhere in `logs.py`**

Rewrite `app/routers/logs.py` so `_entry_out` takes only the log, `create_log` snapshots the posted food, `update_log` no longer refetches the food, and `day_summary` stops joining `Food`:

```python
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import compute_macros, upsert_food
from app.db import get_db
from app.models import Log
from app.schemas import (
    MEAL_ORDER,
    DayOut,
    LogCreate,
    LogEntryOut,
    LogUpdate,
    Totals,
)

router = APIRouter(prefix="/logs", tags=["logs"])


def _entry_out(log: Log) -> LogEntryOut:
    # compute_macros reads .*_100g; a Log carries those snapshot fields.
    m = compute_macros(log, log.amount_g)
    return LogEntryOut(
        id=log.id, food_id=log.food_id, name=log.name, brand=log.brand,
        meal_type=log.meal_type, amount_g=log.amount_g,
        calories=m.calories, protein_g=m.protein_g,
        carbs_g=m.carbs_g, fat_g=m.fat_g,
    )


@router.post("", response_model=LogEntryOut, status_code=201)
def create_log(body: LogCreate, db: Session = Depends(get_db)) -> LogEntryOut:
    food = upsert_food(db, body.food)  # keep the Food catalog for search history/dedup
    log = Log(
        food_id=food.id, date=body.date, meal_type=body.meal_type,
        amount_g=body.amount_g, created_at=datetime.now(timezone.utc),
        name=body.food.name, brand=body.food.brand,
        calories_100g=body.food.calories_100g, protein_100g=body.food.protein_100g,
        carbs_100g=body.food.carbs_100g, fat_100g=body.food.fat_100g,
        serving_desc=body.food.serving_desc, serving_grams=body.food.serving_grams,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _entry_out(log)


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
    return _entry_out(log)


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
    logs = db.execute(select(Log).where(Log.date == day)).scalars().all()
    meals: dict[str, list[LogEntryOut]] = {m: [] for m in MEAL_ORDER}
    totals = Totals()
    for log in logs:
        entry = _entry_out(log)
        meals.setdefault(entry.meal_type, []).append(entry)
        totals.calories = round(totals.calories + entry.calories, 1)
        totals.protein_g = round(totals.protein_g + entry.protein_g, 1)
        totals.carbs_g = round(totals.carbs_g + entry.carbs_g, 1)
        totals.fat_g = round(totals.fat_g + entry.fat_g, 1)
    return DayOut(date=day, meals=meals, totals=totals)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_logs_api.py -v`
Expected: PASS (new frozen-history test + existing log tests).

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS, no warnings.

- [ ] **Step 7: Commit**

```bash
git add app/schemas.py app/routers/logs.py tests/test_logs_api.py
git commit -m "feat: snapshot macros onto log entries; History reads snapshot"
```

---

### Task 3: `GET /foods/manual` — list custom foods

**Files:**
- Modify: `app/schemas.py` (add `ManualFoodOut`)
- Modify: `app/routers/foods.py` (add list route)
- Test: `tests/test_foods_api.py`

**Interfaces:**
- Produces: `ManualFoodOut` (all `ManualFoodIn` fields plus `id: int`). `GET /foods/manual -> list[ManualFoodOut]`, newest first.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_foods_api.py`:

```python
def test_list_manual_foods(client):
    client.post("/foods/manual", json={
        "name": "Stew", "calories_100g": 120, "protein_100g": 9,
        "carbs_100g": 6, "fat_100g": 5,
    })
    resp = client.get("/foods/manual")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Stew"
    assert isinstance(body[0]["id"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foods_api.py::test_list_manual_foods -v`
Expected: FAIL with 405 (Method Not Allowed) — no GET route yet.

- [ ] **Step 3: Add the `ManualFoodOut` schema**

In `app/schemas.py`, add after `ManualFoodIn`:

```python
class ManualFoodOut(BaseModel):
    id: int
    name: str
    brand: str | None = None
    calories_100g: float
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    serving_desc: str | None = None
    serving_grams: float | None = None
```

- [ ] **Step 4: Add the list route**

In `app/routers/foods.py`, update the schema import line to include `ManualFoodOut` and add `select` + `Food`:

```python
from sqlalchemy import select

from app.models import Food
from app.schemas import ManualFoodIn, ManualFoodOut, NormalizedFood, SearchResult
```

Then add below the existing `manual` route:

```python
@router.get("/manual", response_model=list[ManualFoodOut])
def list_manual(db: Session = Depends(get_db)) -> list[ManualFoodOut]:
    foods = db.execute(
        select(Food).where(Food.source == "manual").order_by(Food.id.desc())
    ).scalars().all()
    return [ManualFoodOut(**{c: getattr(f, c) for c in (
        "id", "name", "brand", "calories_100g", "protein_100g",
        "carbs_100g", "fat_100g", "serving_desc", "serving_grams")}) for f in foods]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_foods_api.py::test_list_manual_foods -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schemas.py app/routers/foods.py tests/test_foods_api.py
git commit -m "feat: GET /foods/manual lists custom foods"
```

---

### Task 4: `PUT /foods/manual/{id}` — edit a custom food

**Files:**
- Modify: `app/routers/foods.py` (add edit route)
- Test: `tests/test_foods_api.py`

**Interfaces:**
- Consumes: `ManualFoodIn` (Task deps), `ManualFoodOut` (Task 3).
- Produces: `PUT /foods/manual/{food_id}` with a `ManualFoodIn` body -> `ManualFoodOut`; 404 if the id is not a `source="manual"` food.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_foods_api.py`:

```python
def test_edit_manual_food(client):
    created = client.post("/foods/manual", json={
        "name": "Stew", "calories_100g": 120, "protein_100g": 9,
        "carbs_100g": 6, "fat_100g": 5,
    }).json()
    fid = client.get("/foods/manual").json()[0]["id"]

    resp = client.put(f"/foods/manual/{fid}", json={
        "name": "Beef stew", "calories_100g": 140, "protein_100g": 11,
        "carbs_100g": 7, "fat_100g": 6,
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Beef stew"
    assert resp.json()["calories_100g"] == 140

    assert client.put("/foods/manual/9999", json={
        "name": "X", "calories_100g": 1, "protein_100g": 1,
        "carbs_100g": 1, "fat_100g": 1,
    }).status_code == 404
    _ = created  # created payload unused beyond triggering the row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foods_api.py::test_edit_manual_food -v`
Expected: FAIL with 405 — no PUT route yet.

- [ ] **Step 3: Add the edit route**

In `app/routers/foods.py`, add after `list_manual`:

```python
@router.put("/manual/{food_id}", response_model=ManualFoodOut)
def edit_manual(food_id: int, body: ManualFoodIn, db: Session = Depends(get_db)) -> ManualFoodOut:
    food = db.get(Food, food_id)
    if food is None or food.source != "manual":
        raise HTTPException(status_code=404, detail="custom food not found")
    for field, value in body.model_dump().items():
        setattr(food, field, value)
    db.commit()
    db.refresh(food)
    return ManualFoodOut(**{c: getattr(food, c) for c in (
        "id", "name", "brand", "calories_100g", "protein_100g",
        "carbs_100g", "fat_100g", "serving_desc", "serving_grams")})
```

Add `HTTPException` to the FastAPI import at the top of the file:

```python
from fastapi import APIRouter, Depends, HTTPException
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_foods_api.py::test_edit_manual_food -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/routers/foods.py tests/test_foods_api.py
git commit -m "feat: PUT /foods/manual/{id} edits a custom food"
```

---

### Task 5: `DELETE /foods/manual/{id}` — delete, preserving History

**Files:**
- Modify: `app/routers/foods.py` (add delete route)
- Test: `tests/test_foods_api.py`

**Interfaces:**
- Produces: `DELETE /foods/manual/{food_id}` -> 204. Sets `Log.food_id = NULL` on referencing rows, then hard-deletes the `Food`. 404 if not a `source="manual"` food.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_foods_api.py`:

```python
def test_delete_manual_preserves_history(client):
    client.post("/logs", json={
        "food": {"source": "manual", "source_id": None, "name": "Stew",
                 "calories_100g": 120, "protein_100g": 9, "carbs_100g": 6,
                 "fat_100g": 5, "serving_desc": None, "serving_grams": None},
        "date": "2026-07-28", "meal_type": "lunch", "amount_g": 100,
    })
    fid = client.get("/foods/manual").json()[0]["id"]

    assert client.delete(f"/foods/manual/{fid}").status_code == 204
    # Gone from the list...
    assert client.get("/foods/manual").json() == []
    # ...but past History totals are intact (snapshot survives).
    day = client.get("/logs/day/2026-07-28").json()
    assert day["totals"]["calories"] == 120.0
    # Unknown id -> 404.
    assert client.delete("/foods/manual/9999").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_foods_api.py::test_delete_manual_preserves_history -v`
Expected: FAIL with 405 — no DELETE route yet.

- [ ] **Step 3: Add the delete route**

In `app/routers/foods.py`, add `Response` to the FastAPI import and `update` to the SQLAlchemy import:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
```

Then add after `edit_manual`:

```python
from app.models import Log  # add to the models import at top: `from app.models import Food, Log`


@router.delete("/manual/{food_id}", status_code=204)
def delete_manual(food_id: int, db: Session = Depends(get_db)) -> Response:
    food = db.get(Food, food_id)
    if food is None or food.source != "manual":
        raise HTTPException(status_code=404, detail="custom food not found")
    # Detach logs so History (which reads its own snapshot) survives the delete.
    db.execute(update(Log).where(Log.food_id == food_id).values(food_id=None))
    db.delete(food)
    db.commit()
    return Response(status_code=204)
```

(Consolidate the models import at the top of the file to `from app.models import Food, Log`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_foods_api.py::test_delete_manual_preserves_history -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, no warnings.

- [ ] **Step 6: Commit**

```bash
git add app/routers/foods.py tests/test_foods_api.py
git commit -m "feat: DELETE /foods/manual/{id} preserves History via snapshots"
```

---

### Task 6: Surface matching custom foods at the top of search

**Files:**
- Modify: `app/crud.py` (add `custom_matches`)
- Modify: `app/sources/search.py` (accept + prepend `custom_foods`)
- Modify: `app/routers/foods.py` (`search` route wires it in)
- Test: `tests/test_crud.py`, `tests/test_foods_api.py`

**Interfaces:**
- Consumes: `crud.to_normalized(food) -> NormalizedFood` (existing).
- Produces: `crud.custom_matches(db, query) -> list[NormalizedFood]` — `source="manual"` foods whose lowercased name contains any whitespace token of the lowercased query. `search_foods(query, sources, client, history=None, custom_foods=None)` prepends `custom_foods` ahead of the staple; `_dedupe` then drops same-(name,brand) source hits.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_crud.py` (reuse the file's existing `_session()` helper and add `custom_matches` to the `app.crud` import at the top):

```python
def test_custom_matches_finds_by_token():
    db = _session()
    upsert_food(db, NormalizedFood(
        source="manual", source_id=None, name="Grandma Beef Stew",
        calories_100g=120, protein_100g=9, carbs_100g=6, fat_100g=5))
    upsert_food(db, NormalizedFood(
        source="usda", source_id="7", name="Beef, ground",
        calories_100g=250, protein_100g=26, carbs_100g=0, fat_100g=15))

    out = custom_matches(db, "beef bowl")
    assert [f.name for f in out] == ["Grandma Beef Stew"]  # only the manual row
    assert custom_matches(db, "salad") == []
```

(Update the import line in `tests/test_crud.py` to
`from app.crud import compute_macros, custom_matches, log_history, to_normalized, upsert_food`.)

Add to `tests/test_foods_api.py`:

```python
def test_custom_food_leads_search(client, fake_sources):
    client.post("/foods/manual", json={
        "name": "Beef stew", "calories_100g": 120, "protein_100g": 9,
        "carbs_100g": 6, "fat_100g": 5,
    })
    fake_sources[0].results = [_food("Beef broth", sid="9")]
    body = client.get("/foods/search", params={"q": "beef"}).json()
    assert body["results"][0]["name"] == "Beef stew"
    assert body["results"][0]["source"] == "manual"
```

Note: `tests/test_crud.py` builds sessions with a local `_session()` helper (not a fixture) — reuse it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crud.py::test_custom_matches_finds_by_token tests/test_foods_api.py::test_custom_food_leads_search -v`
Expected: FAIL — `custom_matches` undefined; custom food not surfaced.

- [ ] **Step 3: Implement `custom_matches`**

In `app/crud.py`, add (uses the existing `select`, `Food` imports):

```python
def custom_matches(db: Session, query: str) -> list[NormalizedFood]:
    tokens = [t for t in query.lower().split() if t]
    if not tokens:
        return []
    rows = db.execute(select(Food).where(Food.source == "manual")).scalars().all()
    out: list[NormalizedFood] = []
    for f in rows:
        name = (f.name or "").lower()
        if any(tok in name for tok in tokens):
            out.append(to_normalized(f))
    return out
```

- [ ] **Step 4: Prepend custom foods in `search_foods`**

In `app/sources/search.py`, change the signature and the prepend block:

```python
async def search_foods(
    query: str,
    sources: list[FoodSource],
    client: httpx.AsyncClient,
    history: dict | None = None,
    custom_foods: list[NormalizedFood] | None = None,
) -> SearchResult:
    history = history or {}
    ...  # unchanged gather/score body
    merged = [food for _, food in scored]
    staple = staples.staple_for(query)
    if staple is not None:
        merged = [staple] + merged   # staple leads external hits
    if custom_foods:
        merged = list(custom_foods) + merged   # user's own foods lead everything
    return SearchResult(results=_dedupe(merged), partial=partial)
```

- [ ] **Step 5: Wire it into the search route**

In `app/routers/foods.py`, update the `search` handler to fetch and pass custom foods:

```python
    history = crud.log_history(db)
    custom = crud.custom_matches(db, q.strip())
    async with httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": "supercaloriemonster/1.0 (https://github.com/junj-st/supercaloriemonster)"},
    ) as client:
        return await search_foods(q.strip(), sources, client, history, custom)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_crud.py::test_custom_matches_finds_by_token tests/test_foods_api.py::test_custom_food_leads_search -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: PASS, no warnings.

- [ ] **Step 8: Commit**

```bash
git add app/crud.py app/sources/search.py app/routers/foods.py tests/test_crud.py tests/test_foods_api.py
git commit -m "feat: surface matching custom foods at top of search"
```

---

### Task 7: Frontend — "Custom" badge in search results & recents

**Files:**
- Modify: `static/app.js` (`renderResults`, `loadQuickLists`)
- Modify: `static/style.css` (badge)
- Modify: `static/index.html` (bump asset version to `?v=nb2`)
- Test: `tests/test_static.py`

**Interfaces:**
- Consumes: search results carry `source` (`"manual"` for custom foods).
- Produces: rows with `source === "manual"` render a `<span class="badge-custom">Custom</span>`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_static.py` (this module fetches asset content over HTTP via the existing module-level `client = TestClient(app)`):

```python
def test_app_js_has_custom_badge():
    js = client.get("/static/app.js").text
    assert "badge-custom" in js
    assert 'source === "manual"' in js


def test_style_has_custom_badge():
    assert "badge-custom" in client.get("/static/style.css").text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static.py -k custom_badge -v`
Expected: FAIL — strings absent.

- [ ] **Step 3: Add the badge in `renderResults`**

In `static/app.js`, replace the `renderResults` row template so manual foods show a badge (add a `badge` helper near the top-of-file helpers):

```javascript
const badge = (f) => (f.source === "manual" ? '<span class="badge-custom">Custom</span>' : "");
```

```javascript
function renderResults(el, foods) {
  if (!foods.length) { $(el).innerHTML = '<div class="note">No matches found.</div>'; return; }
  $(el).innerHTML = foods.map((f, i) => `
    <div class="log-row tappable" data-i="${i}">
      <div class="log-main"><div class="name">${esc(f.name)}${badge(f)}</div><div class="meta">${esc(f.brand || "generic")} · ${num(f.calories_100g)} cal/100g</div></div>
      <span class="add-mark">+</span>
    </div>`).join("");
  $(el).querySelectorAll(".log-row").forEach((row) =>
    row.addEventListener("click", () => openLogDialog(foods[row.dataset.i])));
}
```

Also add `${badge(f)}` after the name in the recents/favorites `section` template inside `loadQuickLists`:

```javascript
  const section = (title, foods) => foods.length
    ? `<div class="section-label">${title}</div>` + foods.map((f, i) =>
        `<div class="log-row tappable" data-list="${title}" data-i="${i}"><div class="log-main"><div class="name">${esc(f.name)}${badge(f)}</div></div><span class="add-mark">+</span></div>`).join("")
    : "";
```

- [ ] **Step 4: Style the badge**

In `static/style.css`, add (neo-brutalist: hard border + offset, uppercase mono):

```css
.badge-custom {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  font-family: var(--mono, monospace);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border: 2px solid var(--ink, #111);
  box-shadow: 2px 2px 0 var(--ink, #111);
  background: var(--accent, #ffd84d);
  color: var(--ink, #111);
}
```

(Match the actual token names in `style.css`; keep the fallbacks so it renders regardless.)

- [ ] **Step 5: Bump the asset version**

In `static/index.html`, change both refs from `?v=nb1` to `?v=nb2`:

```html
  <link rel="stylesheet" href="/static/style.css?v=nb2" />
  ...
  <script src="/static/app.js?v=nb2"></script>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_static.py -k custom_badge -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add static/app.js static/style.css static/index.html tests/test_static.py
git commit -m "feat: Custom badge on custom-food search/recents rows"
```

---

### Task 8: Frontend — "Foods" tab with My Foods list (view, delete, tap-to-log)

**Files:**
- Modify: `static/index.html` (nav button + `#view-foods` section)
- Modify: `static/app.js` (view switch case + `loadFoods`)
- Modify: `static/style.css` (list row actions, if needed)
- Test: `tests/test_static.py`

**Interfaces:**
- Consumes: `GET /foods/manual`, `DELETE /foods/manual/{id}`, existing `openLogDialog(food)`.
- Produces: a `data-view="foods"` nav button and a `#view-foods` section; `loadFoods()` renders each custom food with tap-to-log, an Edit button (wired in Task 9), and a Delete button.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_static.py`:

```python
def test_foods_tab_present():
    html = client.get("/").text  # root serves the app shell (index.html)
    assert 'data-view="foods"' in html
    assert 'id="view-foods"' in html


def test_app_js_loads_foods():
    js = client.get("/static/app.js").text
    assert "function loadFoods" in js
    assert "/foods/manual" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static.py -k "foods_tab or loads_foods" -v`
Expected: FAIL — markup/function absent.

- [ ] **Step 3: Add the nav button and view section**

In `static/index.html`, add the nav button after the History button:

```html
      <button data-view="foods">Foods</button>
```

And add the section after `#view-history` (inside `<main>`):

```html
    <section id="view-foods" class="view hidden">
      <div class="section-label">My foods</div>
      <button class="btn-primary" id="add-custom-food">+ Add custom food</button>
      <div id="foods-list"></div>
    </section>
```

- [ ] **Step 4: Add the view-switch case and `loadFoods`**

In `static/app.js`, extend the nav click handler to load the foods view:

```javascript
    if (btn.dataset.view === "foods") loadFoods();
```

Then add `loadFoods` (near `loadQuickLists`). Tapping a row logs the food; Delete removes it after confirm; the Edit button carries `data-edit` for Task 9 to wire:

```javascript
async function loadFoods() {
  const foods = await api("/foods/manual");
  const list = $("#foods-list");
  if (!foods.length) { list.innerHTML = '<div class="note">No custom foods yet.</div>'; return; }
  list.innerHTML = foods.map((f, i) => `
    <div class="log-row">
      <div class="log-main tappable" data-log="${i}"><div class="name">${esc(f.name)}<span class="badge-custom">Custom</span></div><div class="meta">${num(f.calories_100g)} cal/100g</div></div>
      <div class="log-right">
        <button class="food-edit" data-edit="${i}" aria-label="Edit ${esc(f.name)}">Edit</button>
        <button class="del" data-del-food="${f.id}" aria-label="Delete ${esc(f.name)}">${TRASH}</button>
      </div>
    </div>`).join("");
  list.querySelectorAll("[data-log]").forEach((el) =>
    el.addEventListener("click", () => openLogDialog(foods[el.dataset.log])));
  list.querySelectorAll("[data-del-food]").forEach((b) =>
    b.addEventListener("click", async () => {
      if (!confirm("Delete this custom food? Past logged entries are kept.")) return;
      await fetch("/foods/manual/" + b.dataset.delFood, { method: "DELETE" });
      loadFoods();
    }));
  list.querySelectorAll("[data-edit]").forEach((b) =>
    b.addEventListener("click", () => openFoodForm(foods[b.dataset.edit])));  // openFoodForm defined in Task 9
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_static.py -k "foods_tab or loads_foods" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add static/index.html static/app.js tests/test_static.py
git commit -m "feat: Foods tab lists custom foods with delete and tap-to-log"
```

Note: `loadFoods` references `openFoodForm`, defined in Task 9. If executing/reviewing tasks in isolation, the button handler is inert until Task 9 lands — the view still loads, lists, deletes, and logs.

---

### Task 9: Frontend — create/edit form with per-serving/per-100g toggle

**Files:**
- Modify: `static/index.html` (food-form modal)
- Modify: `static/app.js` (`openFoodForm`, toggle + submit; wire add buttons)
- Modify: `static/style.css` (form/toggle, if needed)
- Test: `tests/test_static.py`

**Interfaces:**
- Consumes: `POST /foods/manual`, `PUT /foods/manual/{id}`, `loadFoods()` (Task 8), the two "Add custom food" buttons (`#add-custom-food` in the Foods view; a new one in the Add view).
- Produces: `openFoodForm(food)` — opens the modal; `food` omitted = create, `food` present = edit. Per-serving mode converts to per-100g before submit.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_static.py`:

```python
def test_food_form_present():
    html = client.get("/").text
    assert 'id="food-form-dialog"' in html
    assert 'name="basis"' in html  # per-serving / per-100g toggle


def test_app_js_has_food_form():
    js = client.get("/static/app.js").text
    assert "function openFoodForm" in js
    assert "per100" in js and "serving" in js
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static.py -k food_form -v`
Expected: FAIL — markup/function absent.

- [ ] **Step 3: Add the form modal markup**

In `static/index.html`, add after the `#log-dialog` block:

```html
  <div id="food-form-dialog" class="hidden">
    <div class="dialog-card">
      <h3 id="food-form-title">Add custom food</h3>
      <label>Name <input id="food-name" type="text" /></label>
      <label>Brand (optional) <input id="food-brand" type="text" /></label>

      <div class="basis-toggle">
        <label><input type="radio" name="basis" value="per100" checked /> Per 100 g</label>
        <label><input type="radio" name="basis" value="serving" /> Per serving</label>
      </div>

      <label class="basis-serving hidden">Serving size (g) <input id="food-serving-grams" type="number" min="0" step="1" /></label>
      <label class="basis-serving hidden">Serving desc (e.g. 1 bar) <input id="food-serving-desc" type="text" /></label>

      <label><span id="lbl-cal">Calories / 100 g</span> <input id="food-cal" type="number" min="0" step="1" /></label>
      <label><span id="lbl-pro">Protein / 100 g</span> <input id="food-pro" type="number" min="0" step="0.1" /></label>
      <label><span id="lbl-carb">Carbs / 100 g</span> <input id="food-carb" type="number" min="0" step="0.1" /></label>
      <label><span id="lbl-fat">Fat / 100 g</span> <input id="food-fat" type="number" min="0" step="0.1" /></label>

      <div id="food-form-hint" class="hint"></div>
      <div class="dialog-actions">
        <button id="food-form-cancel">Cancel</button>
        <button id="food-form-save">Save</button>
      </div>
    </div>
  </div>
```

Also add an "Add custom food" button to the Add view, after `#search-results` in `#view-search`:

```html
      <button class="btn-secondary" id="add-custom-food-search">Can't find it? + Add custom food</button>
```

- [ ] **Step 4: Implement the form logic in `app.js`**

Add to `static/app.js` (after `loadFoods`). Handles create vs edit, the basis toggle relabel/show-hide, per-serving→per-100g conversion, and submit:

```javascript
let editingFoodId = null;

function currentBasis() {
  const r = document.querySelector('input[name="basis"]:checked');
  return r ? r.value : "per100";
}

function applyBasisLabels() {
  const per100 = currentBasis() === "per100";
  const suffix = per100 ? "/ 100 g" : "/ serving";
  $("#lbl-cal").textContent = "Calories " + suffix;
  $("#lbl-pro").textContent = "Protein " + suffix;
  $("#lbl-carb").textContent = "Carbs " + suffix;
  $("#lbl-fat").textContent = "Fat " + suffix;
  document.querySelectorAll(".basis-serving").forEach((el) => el.classList.toggle("hidden", per100));
}

document.querySelectorAll('input[name="basis"]').forEach((r) =>
  r.addEventListener("change", applyBasisLabels));

function openFoodForm(food) {
  editingFoodId = food ? food.id : null;
  $("#food-form-title").textContent = food ? "Edit custom food" : "Add custom food";
  $("#food-name").value = food ? food.name : "";
  $("#food-brand").value = food && food.brand ? food.brand : "";
  document.querySelector('input[name="basis"][value="per100"]').checked = true; // edit prefill is per-100g
  $("#food-serving-grams").value = food && food.serving_grams ? food.serving_grams : "";
  $("#food-serving-desc").value = food && food.serving_desc ? food.serving_desc : "";
  $("#food-cal").value = food ? food.calories_100g : "";
  $("#food-pro").value = food ? food.protein_100g : "";
  $("#food-carb").value = food ? food.carbs_100g : "";
  $("#food-fat").value = food ? food.fat_100g : "";
  const hint = $("#food-form-hint"); hint.textContent = ""; hint.classList.remove("error");
  applyBasisLabels();
  $("#food-form-dialog").classList.remove("hidden");
}

function readFoodForm() {
  const hint = $("#food-form-hint");
  const name = $("#food-name").value.trim();
  if (!name) { hint.textContent = "Name is required"; hint.classList.add("error"); return null; }
  const nums = ["#food-cal", "#food-pro", "#food-carb", "#food-fat"].map((s) => parseFloat($(s).value));
  if (nums.some((n) => !Number.isFinite(n) || n < 0)) {
    hint.textContent = "Enter valid macros (0 or more)"; hint.classList.add("error"); return null;
  }
  let [cal, pro, carb, fat] = nums;
  const desc = $("#food-serving-desc").value.trim() || null;
  const grams = parseFloat($("#food-serving-grams").value);
  const hasServing = Number.isFinite(grams) && grams > 0;
  if (currentBasis() === "serving") {
    if (!hasServing) { hint.textContent = "Enter a serving size in grams"; hint.classList.add("error"); return null; }
    const k = 100 / grams; // convert per-serving -> per-100g
    cal *= k; pro *= k; carb *= k; fat *= k;
  }
  return {
    name, brand: $("#food-brand").value.trim() || null,
    calories_100g: Math.round(cal * 10) / 10, protein_100g: Math.round(pro * 10) / 10,
    carbs_100g: Math.round(carb * 10) / 10, fat_100g: Math.round(fat * 10) / 10,
    serving_desc: desc, serving_grams: hasServing ? grams : null,
  };
}

$("#food-form-cancel").addEventListener("click", () => $("#food-form-dialog").classList.add("hidden"));
$("#food-form-save").addEventListener("click", async () => {
  const payload = readFoodForm();
  if (!payload) return;
  const hint = $("#food-form-hint");
  const url = editingFoodId ? "/foods/manual/" + editingFoodId : "/foods/manual";
  const method = editingFoodId ? "PUT" : "POST";
  try {
    const resp = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!resp.ok) { hint.textContent = "Could not save. Please try again."; hint.classList.add("error"); return; }
  } catch (e) {
    hint.textContent = "Could not save. Please try again."; hint.classList.add("error"); return;
  }
  $("#food-form-dialog").classList.add("hidden");
  loadFoods();
});

$("#add-custom-food").addEventListener("click", () => openFoodForm(null));
$("#add-custom-food-search").addEventListener("click", () => openFoodForm(null));
```

- [ ] **Step 5: Style the toggle/serving rows (if needed)**

In `static/style.css`, add minimal styling consistent with the existing dialog:

```css
.basis-toggle { display: flex; gap: 16px; margin: 8px 0; }
.basis-toggle label { display: inline-flex; align-items: center; gap: 6px; }
.btn-secondary { margin-top: 12px; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_static.py -k food_form -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: PASS, no warnings.

- [ ] **Step 8: Manual smoke check**

Run: `uvicorn app.main:app --reload`, open http://localhost:8000. In the Foods tab: add a custom food (try both per-100g and per-serving), confirm it appears; search for it and confirm it leads with a Custom badge; log it; edit it; delete it and confirm History for a prior day is unchanged. Hard-refresh to confirm the `?v=nb2` bump served fresh assets.

- [ ] **Step 9: Commit**

```bash
git add static/index.html static/app.js static/style.css tests/test_static.py
git commit -m "feat: custom-food create/edit form with per-serving/per-100g toggle"
```

---

## Self-Review Notes

- **Spec coverage:** data model + migration (Task 1); snapshot-on-log + History reads snapshot (Task 2); `GET`/`PUT`/`DELETE /foods/manual` (Tasks 3–5); search prepend + `custom_matches` (Task 6); Custom badge (Task 7); Foods tab + list/delete/tap-to-log (Task 8); create/edit form + toggle + both entry points + SW bump (Task 9). Error handling and validation are embedded in Tasks 4/5/9. Testing embedded per task.
- **Type consistency:** `custom_matches(db, query)`, `search_foods(..., custom_foods=None)`, `_entry_out(log)`, `openFoodForm(food)`, `loadFoods()` are named identically wherever referenced across tasks.
- **Known cross-task reference:** Task 8's `loadFoods` calls `openFoodForm` (Task 9). Called out inline; the Foods view is fully functional except Edit until Task 9 lands.
- **Verify against real token names:** Tasks 7 & 9 use CSS custom-property fallbacks; when implementing, match the actual variable names in `static/style.css`.
- **Test-scaffolding conventions (verified):** `tests/test_static.py` fetches asset content over HTTP via a module-level `client = TestClient(app)` (`client.get("/static/app.js").text`, `client.get("/").text` for the shell) — no file reads. `tests/test_crud.py` builds sessions with a local `_session()` helper, not a fixture. `tests/test_foods_api.py`/`tests/test_logs_api.py` use the `client`/`fake_sources` fixtures from `conftest.py`.
