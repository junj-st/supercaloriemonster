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

- **USDA** — from `dataType`: `Foundation` / `SR Legacy` (basic reference foods) → high (~1.0); `Survey (FNDDS)` (prepared dietary-recall dishes) → mid (~0.6, below reference foods — see the granularity note in the Addendum); `Branded` → low (~0.2). A small bonus when `brand` is absent. Unknown `dataType` → neutral (~0.5).
- **Open Food Facts** — from `nova_group`: 1 → ~1.0, 2 → ~0.7, 3 → ~0.4, 4 → ~0.1. A small bonus when there is no brand. Missing NOVA → neutral (~0.5).
- Stored as one derived field on `NormalizedFood`; raw `dataType` / `nova_group` do not propagate further.

**`relevance` (0–1)** — computed at search time from the query and the food name plus the food's position in its source's result list:
- Name match tier: exact match (name == query) > name starts with query > all query tokens present in name > partial token overlap. Higher tier → higher base relevance.
- Source position: sources already return results in their own relevance order; earlier position contributes a small positive term (decaying with rank).

**`history_boost` (additive, ≥ 0)** — from the user's `logs`: if a candidate matches a food the user has logged, add a boost that grows with log count and saturates (so one heavily-logged food can't dominate unrelated queries). Matching is by `(source, source_id)` first; if that misses, it falls back to an **exact lowercased-name** match against any logged food (not only manual foods). The name fallback is intentional: an exact same-name match is effectively the same food across sources/IDs, so it should inherit the history boost. Because the fallback requires the full name to match exactly, its blast radius is narrow.

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
- Cross-user/global popularity, learning-to-rank, or persisted ranking scores.
- Any change to logging, favorites, or the food schema.

## Addendum — curated staples booster (added after smoke-testing)

**Discovery:** During live smoke-testing, the composite ranking correctly ranks
generic foods above branded ones, but did NOT achieve the flagship goal
("rice" → classic white rice first). Verified against the live USDA API: for the
bare term "rice", USDA's own relevance returns branded "RICE" and FNDDS prepared
dishes ("Dirty rice", "Rice pilaf", "Rice crackers") first, and the basic
SR Legacy "Rice, white, … cooked" is **not in the top 50 of 141** results even
when filtered to `dataType=Foundation,SR Legacy`. Because the staple is never in
the candidate window, no reranking or `dataType` biasing can surface it — this is
a retrieval limitation of USDA's free search, not a ranking bug.

**Decision:** Add a small **curated staples layer** that *supplies* the canonical
staple for common one-word foods (the composite ranking remains the primary
mechanism for everything else). This is a targeted booster, not a replacement.

**Design:**
- A local seed module `app/sources/staples.py` holds ~25–30 common foods. Each entry has: `triggers` (exact query terms that surface it, e.g. `["rice", "white rice"]`), and a canonical `NormalizedFood` with real per-100g nutrition, `source="usda"` + the real `fdcId`, `generic_score=1.0`. Seed nutrition/`fdcId` values are fetched once from the live USDA API at implementation time and baked in as static data (so runtime stays offline and reliable); each entry cites its source `fdcId`.
- `staple_for(query: str) -> NormalizedFood | None` returns the staple whose `triggers` exactly contain the normalized (lowercased, stripped) query. Multi-word/specific queries that don't match a trigger return `None` and fall through to the composite.
- In `search_foods`: after the composite sort + dedupe, if `staple_for(query)` returns a staple, it is placed **first**, de-duplicated against any source result for the same `(name.lower(), brand.lower())` so it replaces rather than duplicates a matching source hit.
- `source="staple"` is NOT used — staples reuse `source="usda"` with the real `fdcId`, so logging/upsert/dedupe behave identically to any USDA food.

**Rationale for local seed over live targeted fetch:** reliability and offline
support (PWA ethos), no extra API call per search, and immunity to USDA's
relevance burying the staple. Trade-off: ~30 stable nutrition values maintained
locally.

**Testing (addendum):**
- `tests/test_staples.py` — `staple_for` returns the right staple for trigger terms, `None` for non-triggers and multi-word specific queries; every seed entry is a valid `NormalizedFood` with `source="usda"`, a non-empty `fdcId`, positive calories, and `generic_score == 1.0`.
- `tests/test_search.py` — a query matching a staple trigger places that staple first even when the fake sources return only branded/unrelated results; a non-trigger query is unaffected; a source result for the same food is de-duplicated (staple wins its slot, no duplicate row).


### Genericness granularity (shipped with the addendum)

Alongside the curated staples, `_usda_generic_score` was refined so basic
reference foods outrank prepared dietary-recall dishes: **Foundation / SR Legacy
→ 1.0**, **Survey (FNDDS) → 0.6**, **Branded → 0.2**, unknown → 0.5 (the +0.05
no-brand bonus still applies). This helps the long tail of queries that have no
curated staple — e.g. "lentils" ranks "Lentils, cooked" (SR Legacy) above
"Lentil soup" (FNDDS). Note: staples are injected unconditionally (not scored),
so their `generic_score=1.0` is not consulted during injection; it is set for
consistency and in case injection ever becomes score-based.
