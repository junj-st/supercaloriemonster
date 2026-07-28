# Search Ranking — Composite Commonness + Relevance Design

Improve food-search result ordering so a **broad** query surfaces basic generic
whole foods first (search "rice" → plain white rice), while a **specific** query
is ranked by relevance. Results are also boosted by the user's own logging
history. Ordering is computed at search time from signals already available in
the USDA / Open Food Facts responses plus the local `logs` table — no schema
change, no stored ranking data.

Builds on the Phase 1 MVP (`docs/superpowers/specs/2026-07-24-supercaloriemonster-design.md`).

## Goals

- Broad, one-word queries rank basic generic whole foods first ("rice" → white rice, not a branded rice snack).
- Specific, multi-word queries rank by name relevance.
- Foods the user has logged before rank higher when they match.
- Fully automatic — no hand-curated lists to maintain.
- No database migration; ranking is computed per request.

## Decisions locked during brainstorming

- **Commonness = genericness**, not raw scan popularity. Prefer basic/whole foods (generic USDA entries, low-NOVA OFF products) over branded/processed products.
- **Personal history boost** is enabled (local, from the user's `logs`).
- **Composite scoring** approach: each result gets a numeric score; the weighting between genericness and relevance shifts by query breadth.

## Ranking model

Each candidate result is scored and results are sorted by score descending, then
deduped (keeping the highest-scored duplicate).

### Signals

**`generic_score` (0–1)** — how much a food is a basic whole food. Computed at
normalization time (the raw source dict is available there):

- **USDA** — from `dataType`: `Foundation` / `SR Legacy` / `Survey (FNDDS)` → high (~1.0); `Branded` → low (~0.2). A small bonus when `brand` is absent. Unknown `dataType` → neutral (~0.5).
- **Open Food Facts** — from `nova_group`: 1 → ~1.0, 2 → ~0.7, 3 → ~0.4, 4 → ~0.1. A small bonus when there is no brand. Missing NOVA → neutral (~0.5).
- Stored as one derived field on `NormalizedFood`; raw `dataType` / `nova_group` do not propagate further.

**`relevance` (0–1)** — computed at search time from the query and the food name plus the food's position in its source's result list:
- Name match tier: exact match (name == query) > name starts with query > all query tokens present in name > partial token overlap. Higher tier → higher base relevance.
- Source position: sources already return results in their own relevance order; earlier position contributes a small positive term (decaying with rank).

**`history_boost` (additive, ≥ 0)** — from the user's `logs`: if a candidate matches a food the user has logged (by `(source, source_id)`, or by lowercased name for manual foods), add a boost that grows with log count and saturates (so one heavily-logged food can't dominate unrelated queries).

### Query-breadth weighting

Let `n = number of whitespace-separated tokens in the query`.

- **Broad (`n == 1`)** — weight genericness heavily so basic staples win: e.g. `w_generic ≈ 0.6`, `w_relevance ≈ 0.4`.
- **Specific (`n ≥ 2`)** — weight relevance heavily: e.g. `w_generic ≈ 0.2`, `w_relevance ≈ 0.8`.

(Exact constants live in `app/sources/ranking.py` and are tunable; the tests assert the *ordering behavior*, not the specific constants.)

### Composite score

```
score = w_generic * generic_score
      + w_relevance * relevance
      + history_boost
```

Results are sorted by `score` descending. De-duplication is unchanged in key
(`(name.lower(), (brand or "").lower())`) but now keeps the **highest-scored**
occurrence because sorting happens before the dedupe pass.

## Components / file changes

- **`app/schemas.py`** — add `generic_score: float = 0.0` to `NormalizedFood`. Default 0.0 so foods produced without ranking context (recents/favorites via `to_normalized`, manual foods) are valid and unaffected.
- **`app/sources/normalize.py`**
  - `normalize_usda(item)` — read `item.get("dataType")`, set `generic_score`.
  - `normalize_off(product)` — read `product.get("nova_group")` (and brand), set `generic_score`.
  - Existing per-100g mapping and `None`-on-missing-energy behavior unchanged.
- **`app/sources/off.py`** — include `nova_group` (and brands) in the search request `fields`/params so the NOVA signal is present in results. Default sort stays relevance (do not switch to popularity sort).
- **`app/sources/usda.py`** — no request change needed (`dataType` is already returned); it is read by `normalize_usda`.
- **`app/sources/ranking.py`** (new) — pure, unit-testable functions:
  - `query_weights(query: str) -> tuple[float, float]` → `(w_generic, w_relevance)`.
  - `relevance(query: str, name: str, position: int) -> float`.
  - `history_boost(food: NormalizedFood, history: dict) -> float`.
  - `score(food: NormalizedFood, query: str, position: int, history: dict) -> float`.
- **`app/sources/search.py`** — `search_foods(query, sources, client, history=None) -> SearchResult`:
  - Gather each source's results concurrently (unchanged), tracking each result's position within its own source list.
  - Score every candidate via `ranking.score(...)`.
  - Sort by score descending; dedupe (keeps highest-scored).
  - `partial` flag behavior unchanged (a source that errors → `partial=True`, others still used).
  - `history` defaults to `None` (treated as empty), so existing callers/tests keep working.
- **`app/crud.py`** — `log_history(db: Session) -> dict`: one aggregate query over `logs` joined to `foods`, returning a light index for boosting — keyed by `(source, source_id)` and by lowercased `name`, valued by log count.
- **`app/routers/foods.py`** — the `GET /foods/search` endpoint gains `db: Session = Depends(get_db)`, builds `history = crud.log_history(db)`, and passes it to `search_foods`. Blank-query short-circuit unchanged.

## Data flow

```
GET /foods/search?q=...
  → get_sources() (USDA if key present + OFF)
  → history = crud.log_history(db)           # user's logged foods + counts
  → search_foods(q, sources, client, history)
        → each source .search() concurrently  → NormalizedFood[] (with generic_score)
        → ranking.score() per candidate (uses query breadth, name relevance,
          generic_score, history)
        → sort desc, dedupe (keep best)
  → SearchResult{results, partial}
```

## Error handling

- A source that errors or times out is skipped and `partial=True` (unchanged).
- Missing ranking signals degrade gracefully: absent `dataType`/`nova_group` → neutral `generic_score`; empty/absent history → no boost. Ranking never raises on missing fields.

## Testing

- **`tests/test_normalize.py`** — `generic_score` is set correctly: USDA generic `dataType`s → high, `Branded` → low; OFF NOVA 1 → high, NOVA 4 → low; missing signals → neutral. (Extend existing USDA/OFF fixtures with a `dataType` / `nova_group` field.)
- **`tests/test_ranking.py`** (new) — pure-function tests:
  - `query_weights`: 1-token query weights genericness higher; 2+-token query weights relevance higher.
  - `relevance`: exact > prefix > all-tokens > partial; earlier position ≥ later.
  - `score` ordering: for a broad query, a high-`generic_score` food outranks a branded better-name-match; for a specific multi-word query, the best name match outranks a generic one; a food in history outranks an otherwise-equal food not in history.
- **`tests/test_search.py`** — `search_foods` with fake sources: broad query orders generic first; specific query orders relevance first; `history` boost changes order; dedupe keeps the highest-scored duplicate; `partial` still set when a source raises.
- **`tests/test_foods_api.py`** — endpoint test: after logging a food, searching a matching broad term ranks that food at/near the top (history boost through the real endpoint + DB).

## Out of scope

- Scan-count / real-world popularity ranking (explicitly rejected in favor of genericness).
- Curated staples lists.
- Cross-user/global popularity, learning-to-rank, or persisted ranking scores.
- Any change to logging, favorites, or the food schema.
