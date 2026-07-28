# Search Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank food-search results by a composite of genericness, name relevance, and the user's logging history, with weighting that shifts by query breadth — so "rice" surfaces plain white rice while specific queries rank by relevance.

**Architecture:** Add a derived `generic_score` to `NormalizedFood` (computed at normalization from USDA `dataType` / OFF `nova_group`). A new pure `app/sources/ranking.py` scores each candidate; `search_foods` sorts by score and dedupes keeping the best. The search endpoint feeds in a history index built from the `logs` table. No schema change, no stored ranking data.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx, pytest.

## Global Constraints

- **Commonness = genericness**, not scan popularity: prefer basic/whole foods over branded/processed.
- **`generic_score`** is a float `0.0–1.0` on `NormalizedFood`, default `0.0`; it is computed, never stored in the DB.
- **Composite score:** `score = w_generic*generic_score + w_relevance*relevance + history_boost`, sorted descending; dedupe (`(name.lower(), (brand or "").lower())`) keeps the highest-scored occurrence.
- **Query breadth:** 1 token → weight genericness higher; 2+ tokens → weight relevance higher. Exact weight constants live in `ranking.py` and are tunable; **tests assert ordering behavior, not the constants.**
- **Backwards compatible:** `search_foods(..., history=None)` — `None`/empty history means no boost; existing behavior for a blank query and the `partial` flag is unchanged.
- **Graceful degradation:** missing `dataType`/`nova_group` → neutral `generic_score` (~0.5); missing history → no boost. Ranking never raises on missing fields.
- **No DB migration**; history comes from the existing `logs`/`foods` tables.
- History index key scheme (shared by `crud.log_history` and `ranking.history_boost`): `("id", source, source_id) -> count` (only when `source_id` is not None) and `("name", name.lower()) -> count`.

---

## File Structure

```
app/
  schemas.py          # + generic_score field on NormalizedFood
  crud.py             # + log_history(db)
  sources/
    normalize.py      # compute generic_score (usda dataType, off nova_group)
    off.py            # request nova_group in search
    ranking.py        # NEW — pure scoring functions
    search.py         # score + sort + dedupe-keep-best; history param
  routers/
    foods.py          # search endpoint builds + passes history
tests/
  fixtures/
    usda_search.json  # + dataType
    off_search.json   # + nova_group
  test_normalize.py   # generic_score assertions
  test_sources.py     # OFF requests nova_group
  test_ranking.py     # NEW — pure-function tests
  test_crud.py        # log_history
  test_search.py      # rewritten ranking behavior
  test_foods_api.py   # history boost through the endpoint
```

Work on branch `feat/search-ranking` (already created). Activate the venv (`. .venv/bin/activate`) before running pytest. Git identity is configured locally — `git commit` normally.

---

### Task 1: `generic_score` — schema field + normalization

**Files:**
- Modify: `app/schemas.py`, `app/sources/normalize.py`
- Modify (fixtures): `tests/fixtures/usda_search.json`, `tests/fixtures/off_search.json`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `NormalizedFood.generic_score: float = 0.0`. `normalize_usda`/`normalize_off` set it: USDA from `dataType` (Foundation/SR Legacy/Survey → 1.0; Branded → 0.2; else 0.5; +0.05 if no brand, capped 1.0), OFF from `nova_group` (1→1.0, 2→0.7, 3→0.4, 4→0.1; missing→0.5; +0.05 if no brand, capped 1.0).

- [ ] **Step 1: Add the field to `NormalizedFood` in `app/schemas.py`**

Add `generic_score` as the last field of `NormalizedFood`:

```python
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
    generic_score: float = 0.0
```

- [ ] **Step 2: Add `dataType` to the USDA fixtures** (`tests/fixtures/usda_search.json`)

Add a `"dataType"` key to each `foods[]` entry (additive — existing assertions still hold): entry 0 (fdcId 171077) → `"SR Legacy"`; entry 1 (fdcId 999999) → `"SR Legacy"`; entry 2 (fdcId 171078) → `"Branded"`. For example, entry 0 becomes:

```json
{
  "fdcId": 171077,
  "dataType": "SR Legacy",
  "description": "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
  "brandOwner": null,
  "foodNutrients": [
    {"nutrientId": 1008, "nutrientNumber": "208", "nutrientName": "Energy", "unitName": "KCAL", "value": 165.0},
    {"nutrientId": 1003, "nutrientNumber": "203", "nutrientName": "Protein", "unitName": "G", "value": 31.0},
    {"nutrientId": 1005, "nutrientNumber": "205", "nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 0.0},
    {"nutrientId": 1004, "nutrientNumber": "204", "nutrientName": "Total lipid (fat)", "unitName": "G", "value": 3.57}
  ]
}
```

Add `"dataType": "SR Legacy"` to entry 1 and `"dataType": "Branded"` to entry 2 (leave their other fields unchanged).

- [ ] **Step 3: Add `nova_group` to the OFF fixtures** (`tests/fixtures/off_search.json`)

Add `"nova_group": 4` to the Nutella product (code `3017620422003`). Leave the no-energy product and the energy-only product (`code "111"`) without a `nova_group` (tests the missing-signal path).

- [ ] **Step 4: Write the failing tests in `tests/test_normalize.py`**

```python
def test_normalize_usda_generic_score_from_datatype():
    item = _load("usda_search.json")["foods"][0]   # SR Legacy, no brand
    assert normalize_usda(item).generic_score == 1.0
    branded = _load("usda_search.json")["foods"][2]  # Branded (energy-only)
    assert normalize_usda(branded).generic_score == 0.2


def test_normalize_off_generic_score_from_nova():
    prod = _load("off_search.json")["products"][0]   # Nutella, nova 4, brand Ferrero
    assert normalize_off(prod).generic_score == 0.1
    energy_only = _load("off_search.json")["products"][2]  # no nova, no brand
    assert normalize_off(energy_only).generic_score == 0.55
```

- [ ] **Step 5: Run to verify they fail**

Run: `pytest tests/test_normalize.py -k generic_score -v`
Expected: FAIL (`generic_score` currently always 0.0).

- [ ] **Step 6: Implement in `app/sources/normalize.py`**

Add near the top (after the existing USDA nutrient constants):

```python
_USDA_GENERIC_TYPES = {"Foundation", "SR Legacy", "Survey (FNDDS)"}
_OFF_NOVA_SCORE = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.1}


def _usda_generic_score(item: dict) -> float:
    dt = item.get("dataType")
    if dt in _USDA_GENERIC_TYPES:
        base = 1.0
    elif dt == "Branded":
        base = 0.2
    else:
        base = 0.5
    if not (item.get("brandOwner") or item.get("brandName")):
        base = min(1.0, base + 0.05)
    return base


def _off_generic_score(product: dict) -> float:
    nova = product.get("nova_group")
    base = 0.5
    if nova is not None:
        try:
            base = _OFF_NOVA_SCORE.get(int(nova), 0.5)
        except (TypeError, ValueError):
            base = 0.5
    if not (product.get("brands") or "").strip():
        base = min(1.0, base + 0.05)
    return base
```

Then set the field in each normalizer. In `normalize_usda`, add `generic_score=_usda_generic_score(item)` to the `NormalizedFood(...)` construction; in `normalize_off`, add `generic_score=_off_generic_score(product)`.

- [ ] **Step 7: Run the tests**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS (existing + 2 new).

- [ ] **Step 8: Commit**

```bash
git add app/schemas.py app/sources/normalize.py tests/fixtures/usda_search.json tests/fixtures/off_search.json tests/test_normalize.py
git commit -m "feat: derive generic_score from USDA dataType and OFF nova_group"
```

---

### Task 2: OFF search requests `nova_group`

**Files:**
- Modify: `app/sources/off.py`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `OFFFoodSource.search` sends a `fields` param that includes `nova_group` (and brands), so the genericness signal is present in results. Return shape unchanged.

- [ ] **Step 1: Write the failing test in `tests/test_sources.py`**

```python
async def test_off_search_requests_nova_group():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"products": []})

    src = OFFFoodSource(base_url="https://off.test")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await src.search("rice", client)
    assert "nova_group" in captured["url"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_sources.py::test_off_search_requests_nova_group -v`
Expected: FAIL (`nova_group` not in the request).

- [ ] **Step 3: Add the `fields` param in `app/sources/off.py`**

In `OFFFoodSource.search`, change the params to include the fields:

```python
resp = await client.get(
    f"{self.base_url}/cgi/search.pl",
    params={
        "search_terms": query,
        "json": 1,
        "page_size": 20,
        "fields": "code,product_name,brands,serving_quantity,serving_size,nutriments,nova_group",
    },
)
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_sources.py -v`
Expected: PASS (existing source tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add app/sources/off.py tests/test_sources.py
git commit -m "feat: request nova_group in Open Food Facts search"
```

---

### Task 3: Ranking module (pure functions)

**Files:**
- Create: `app/sources/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `app.schemas.NormalizedFood`.
- Produces:
  - `query_weights(query: str) -> tuple[float, float]` → `(w_generic, w_relevance)`; 1 token → `(0.6, 0.4)`, else `(0.2, 0.8)`.
  - `relevance(query: str, name: str, position: int) -> float` (0–1): exact > prefix > all-tokens > partial, plus a small decaying position term.
  - `history_boost(food: NormalizedFood, history: dict) -> float` (≥0, saturating): uses the shared key scheme.
  - `score(food: NormalizedFood, query: str, position: int, history: dict) -> float`.

- [ ] **Step 1: Write the failing tests in `tests/test_ranking.py`**

```python
from app.schemas import NormalizedFood
from app.sources import ranking


def _food(name, source="usda", sid="1", generic=0.5):
    return NormalizedFood(source=source, source_id=sid, name=name,
                          calories_100g=1, protein_100g=1, carbs_100g=1, fat_100g=1,
                          generic_score=generic)


def test_query_weights_broad_vs_specific():
    wg1, wr1 = ranking.query_weights("rice")
    wg2, wr2 = ranking.query_weights("basmati rice pilaf")
    assert wg1 > wr1        # broad: genericness dominates
    assert wr2 > wg2        # specific: relevance dominates


def test_relevance_tiers():
    assert ranking.relevance("rice", "rice", 0) > ranking.relevance("rice", "rice pilaf", 0)
    assert ranking.relevance("rice", "rice pilaf", 0) > ranking.relevance("rice", "wild rice blend", 0)
    # earlier position ranks at least as high as a later one, all else equal
    assert ranking.relevance("rice", "rice", 0) >= ranking.relevance("rice", "rice", 5)


def test_broad_query_prefers_generic():
    generic = _food("Rice, white, cooked", sid="1", generic=1.0)
    branded = _food("Rice snack bar", source="off", sid="2", generic=0.1)
    sg = ranking.score(generic, "rice", 0, {})
    sb = ranking.score(branded, "rice", 0, {})
    assert sg > sb


def test_specific_query_prefers_relevance():
    exact = _food("Basmati rice pilaf", sid="1", generic=0.2)
    generic = _food("Rice, white, cooked", sid="2", generic=1.0)
    se = ranking.score(exact, "basmati rice pilaf", 0, {})
    sgen = ranking.score(generic, "basmati rice pilaf", 1, {})
    assert se > sgen


def test_history_boost_raises_score():
    food = _food("Brown rice", source="usda", sid="9", generic=0.5)
    history = {("id", "usda", "9"): 3}
    assert ranking.score(food, "rice", 0, history) > ranking.score(food, "rice", 0, {})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_ranking.py -v`
Expected: FAIL (`No module named 'app.sources.ranking'`).

- [ ] **Step 3: Implement `app/sources/ranking.py`**

```python
import math

from app.schemas import NormalizedFood


def query_weights(query: str) -> tuple[float, float]:
    """(w_generic, w_relevance). Broad (1 token) favors genericness."""
    if len(query.split()) <= 1:
        return (0.6, 0.4)
    return (0.2, 0.8)


def relevance(query: str, name: str, position: int) -> float:
    q = (query or "").strip().lower()
    nm = (name or "").strip().lower()
    if not q or not nm:
        base = 0.0
    elif nm == q:
        base = 1.0
    elif nm.startswith(q):
        base = 0.85
    else:
        q_tokens = q.split()
        n_tokens = set(nm.split())
        if q_tokens and all(t in n_tokens for t in q_tokens):
            base = 0.7
        elif q_tokens:
            base = 0.4 * sum(1 for t in q_tokens if t in n_tokens) / len(q_tokens)
        else:
            base = 0.0
    pos_term = 0.1 / (1 + max(0, position))
    return min(1.0, base + pos_term)


def history_boost(food: NormalizedFood, history: dict) -> float:
    if not history:
        return 0.0
    count = 0
    if food.source_id is not None:
        count = history.get(("id", food.source, food.source_id), 0)
    if count == 0:
        count = history.get(("name", (food.name or "").lower()), 0)
    if count <= 0:
        return 0.0
    return min(0.5, 0.15 * math.log2(1 + count))


def score(food: NormalizedFood, query: str, position: int, history: dict) -> float:
    w_generic, w_relevance = query_weights(query)
    return (
        w_generic * food.generic_score
        + w_relevance * relevance(query, food.name, position)
        + history_boost(food, history)
    )
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_ranking.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/sources/ranking.py tests/test_ranking.py
git commit -m "feat: add composite search-ranking scoring module"
```

---

### Task 4: `log_history` CRUD helper

**Files:**
- Modify: `app/crud.py`
- Test: `tests/test_crud.py`

**Interfaces:**
- Consumes: `app.models` (Food, Log).
- Produces: `log_history(db: Session) -> dict` — aggregates `logs` joined to `foods` by food, returning `{("id", source, source_id): count, ("name", name.lower()): count}` (the `("id", …)` key only when `source_id` is not None).

- [ ] **Step 1: Write the failing test in `tests/test_crud.py`**

```python
from datetime import date, datetime, timezone

from app.crud import log_history, upsert_food
from app.models import Log


def test_log_history_counts_by_food():
    db = _session()
    food = upsert_food(db, _food())  # source="usda", source_id="1", name="Rice"
    for _ in range(2):
        db.add(Log(food_id=food.id, date=date(2026, 7, 28), meal_type="lunch",
                   amount_g=100, created_at=datetime.now(timezone.utc)))
    db.commit()
    hist = log_history(db)
    assert hist[("id", "usda", "1")] == 2
    assert hist[("name", "rice")] == 2
```

(`_session` and `_food` already exist in `tests/test_crud.py`.)

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_crud.py::test_log_history_counts_by_food -v`
Expected: FAIL (`cannot import name 'log_history'`).

- [ ] **Step 3: Implement `log_history` in `app/crud.py`**

Add (with `from sqlalchemy import func, select` — `select` is already imported; add `func`):

```python
def log_history(db: Session) -> dict:
    rows = db.execute(
        select(Food.source, Food.source_id, Food.name, func.count(Log.id))
        .join(Log, Log.food_id == Food.id)
        .group_by(Food.id)
    ).all()
    hist: dict = {}
    for source, source_id, name, count in rows:
        if source_id is not None:
            hist[("id", source, source_id)] = count
        key = ("name", (name or "").lower())
        hist[key] = hist.get(key, 0) + count
    return hist
```

Add `from app.models import Food, Log` (currently only `Food` is imported) at the top of `app/crud.py`.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_crud.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add app/crud.py tests/test_crud.py
git commit -m "feat: add log_history index for personal search boosting"
```

---

### Task 5: Score, sort, and dedupe in `search_foods`

**Files:**
- Modify: `app/sources/search.py`
- Test: `tests/test_search.py` (rewrite for ranking behavior)

**Interfaces:**
- Consumes: `ranking.score`, `SearchResult`, `NormalizedFood`, `FoodSource`.
- Produces: `search_foods(query, sources, client, history=None) -> SearchResult` — scores every candidate (tracking its position within its source), sorts by score descending, dedupes keeping the highest-scored. `partial` unchanged.

- [ ] **Step 1: Rewrite `tests/test_search.py`**

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


def _food(name, brand=None, source="usda", sid=None, generic=0.5):
    return NormalizedFood(source=source, source_id=sid or name, name=name, brand=brand,
                          calories_100g=100, protein_100g=1, carbs_100g=1, fat_100g=1,
                          generic_score=generic)


async def test_partial_flag_when_source_fails():
    usda = _FakeSource("usda", [_food("Rice", generic=1.0)])
    off = _FakeSource("off", boom=True)
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [usda, off], client)
    assert res.partial is True
    assert [f.name for f in res.results] == ["Rice"]


async def test_broad_query_ranks_generic_first():
    usda = _FakeSource("usda", [_food("Rice snack bar", generic=0.1)])
    off = _FakeSource("off", [_food("Rice, white, cooked", source="off", generic=1.0)])
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [usda, off], client)
    assert res.partial is False
    assert res.results[0].name == "Rice, white, cooked"


async def test_specific_query_ranks_relevance_first():
    generic = _FakeSource("usda", [_food("Rice, white, cooked", generic=1.0)])
    specific = _FakeSource("off", [_food("Basmati rice pilaf", source="off", generic=0.2)])
    async with httpx.AsyncClient() as client:
        res = await search_foods("basmati rice pilaf", [generic, specific], client)
    assert res.results[0].name == "Basmati rice pilaf"


async def test_history_boost_reorders():
    a = _food("White rice", sid="1", generic=0.5)
    b = _food("Brown rice", sid="2", generic=0.5)
    src = _FakeSource("usda", [a, b])
    history = {("id", "usda", "2"): 4}
    async with httpx.AsyncClient() as client:
        res = await search_foods("rice", [src], client, history)
    assert res.results[0].name == "Brown rice"


async def test_dedupe_keeps_highest_scored():
    low = _food("Milk", sid="1", generic=0.1)
    high = _food("milk", sid="2", generic=1.0)   # same name/brand key, higher generic
    src = _FakeSource("usda", [low, high])
    async with httpx.AsyncClient() as client:
        res = await search_foods("milk", [src], client)
    assert len(res.results) == 1
    assert res.results[0].generic_score == 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_search.py -v`
Expected: FAIL (current `search_foods` ignores `generic_score`/history and takes no `history` arg).

- [ ] **Step 3: Rewrite `app/sources/search.py`**

```python
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
```

(This removes the old `_rank_key` function; `_dedupe` is retained.)

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_search.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the whole suite to catch fallout**

Run: `pytest -q`
Expected: all pass. (If a pre-existing test asserted the old alphabetical ordering, it lives only in `tests/test_search.py`, which was rewritten here.)

- [ ] **Step 6: Commit**

```bash
git add app/sources/search.py tests/test_search.py
git commit -m "feat: rank search results by composite score with history"
```

---

### Task 6: Feed history from the search endpoint

**Files:**
- Modify: `app/routers/foods.py`
- Test: `tests/test_foods_api.py`

**Interfaces:**
- Consumes: `crud.log_history`, `get_db`, `search_foods`.
- Produces: `GET /foods/search` builds `history = crud.log_history(db)` and passes it to `search_foods`. Blank-query short-circuit unchanged.

- [ ] **Step 1: Write the failing test in `tests/test_foods_api.py`**

```python
def test_search_boosts_logged_food(client, fake_sources):
    # Log "Brown rice" (usda/2) so it gains history weight.
    client.post("/logs", json={
        "food": {"source": "usda", "source_id": "2", "name": "Brown rice",
                 "calories_100g": 110, "protein_100g": 2, "carbs_100g": 23,
                 "fat_100g": 1, "serving_desc": "100g", "serving_grams": 100},
        "date": "2026-07-28", "meal_type": "lunch", "amount_g": 100,
    })
    # Search returns a non-logged generic and the logged food, same generic_score.
    fake_sources[0].results = [
        NormalizedFood(source="usda", source_id="1", name="White rice",
                       calories_100g=130, protein_100g=2.7, carbs_100g=28,
                       fat_100g=0.3, generic_score=0.5),
        NormalizedFood(source="usda", source_id="2", name="Brown rice",
                       calories_100g=110, protein_100g=2, carbs_100g=23,
                       fat_100g=1, generic_score=0.5),
    ]
    body = client.get("/foods/search", params={"q": "rice"}).json()
    assert body["results"][0]["name"] == "Brown rice"
```

Add `from app.schemas import NormalizedFood` to the test imports if not present.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_foods_api.py::test_search_boosts_logged_food -v`
Expected: FAIL (endpoint does not build/pass history yet; both foods score equally and insertion order wins → "White rice" first).

- [ ] **Step 3: Update the search endpoint in `app/routers/foods.py`**

Add imports at the top: `from app.db import get_db`, `from app import crud`, and `from sqlalchemy.orm import Session`. Update the endpoint:

```python
@router.get("/search", response_model=SearchResult)
async def search(
    q: str = "",
    sources: list[FoodSource] = Depends(get_sources),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> SearchResult:
    if not q.strip():
        return SearchResult(results=[], partial=False)
    history = crud.log_history(db)
    async with httpx.AsyncClient(
        timeout=settings.http_timeout,
        headers={"User-Agent": "supercaloriemonster/1.0 (https://github.com/junj-st/supercaloriemonster)"},
    ) as client:
        return await search_foods(q.strip(), sources, client, history)
```

(Keep the existing `User-Agent` header from the MVP; only `db` + `history` are new.)

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_foods_api.py -v`
Expected: PASS (existing + the boost test).

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 6: Manual smoke test**

Run: `uvicorn app.main:app --reload` (or restart the running server), then:
`curl -s "http://127.0.0.1:8000/foods/search?q=rice" | python3 -c "import sys,json;d=json.load(sys.stdin);[print(r['source'],r['name'][:40],round(r['generic_score'],2)) for r in d['results'][:8]]"`
Expected: with the USDA key active, generic white-rice entries appear at/near the top for the broad query "rice".

- [ ] **Step 7: Commit**

```bash
git add app/routers/foods.py tests/test_foods_api.py
git commit -m "feat: boost search results by personal logging history"
```

---

## Self-Review

**Spec coverage:**
- `generic_score` on `NormalizedFood`, computed from USDA `dataType` / OFF `nova_group` → Task 1. ✓
- OFF request includes `nova_group` → Task 2. ✓
- Relevance, query-breadth weighting, history boost, composite score → Task 3 (`ranking.py`). ✓
- History index from `logs` → Task 4 (`log_history`). ✓
- `search_foods` scores + sorts + dedupes-keep-best, `history` optional, `partial` unchanged → Task 5. ✓
- Endpoint builds + passes history → Task 6. ✓
- No schema/DB migration; `generic_score` default 0.0; graceful degradation → Tasks 1, 3, 5. ✓
- Tests: normalize genericness, ranking pure functions, log_history, search ordering + history + dedupe, endpoint boost → Tasks 1, 3, 4, 5, 6. ✓
- Out of scope (scan popularity, curated lists, persisted scores) → absent. ✓

**Placeholder scan:** no TBD/TODO; every code step is complete. The tunable weight constants are concrete values in `ranking.py`, and tests assert ordering, not the constants (per Global Constraints). ✓

**Type consistency:** `generic_score: float` is set by both normalizers and read by `ranking.score`; the history key scheme `("id", source, source_id)` / `("name", name.lower())` is produced by `log_history` and consumed by `history_boost` identically; `search_foods(query, sources, client, history=None)` signature matches the endpoint call in Task 6. ✓
