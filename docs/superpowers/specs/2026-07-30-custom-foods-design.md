# Custom Foods — Design Spec

**Date:** 2026-07-30
**Feature:** #2 of the original 3-feature request (custom food items UI + searchable)
**Status:** Approved design, ready for implementation plan
**Branch:** to be created off `main` (e.g. `feat/custom-foods`)

## Goal

Let users create, manage, and search their own custom food items. A
`POST /foods/manual` endpoint already exists but no UI reaches it, and saved
manual foods do not appear in search. This feature closes both gaps and adds
full management (list / edit / delete).

## Decisions (from brainstorming)

1. **Scope:** Full CRUD + a dedicated "My Foods" management view.
2. **Input model:** Add/edit form has a **toggle** — enter macros either
   per-serving or per-100g. Conversion to per-100g happens in the frontend;
   the backend contract stays per-100g.
3. **Placement:** Both entry points — a contextual "Add custom food" button in
   the Add view (where search fails) *and* a dedicated Foods nav tab for
   management.
4. **Search ranking:** A matching custom food ranks **top, above everything**
   (including curated staples), and is shown with a **"Custom" badge** so it is
   not confused with USDA/OFF results.
5. **History model:** Macros are **snapshotted onto each log entry at log
   time**. This is the root-cause fix (see below), making edit affect only
   future logs and delete a safe hard-delete.

## Root-cause context: why snapshotting

Today `Log` stores only `food_id` + `amount_g`, and totals are computed live
from the current `Food` row (`crud.compute_macros`). Consequences:

- **Editing** a custom food's macros silently rewrites *past* History.
- **Deleting** a custom food breaks History for days that referenced it.

Any delete rule would just be patching this. Snapshotting the macros onto the
log entry at write time fixes the cause: past entries keep the numbers the user
actually logged, independent of later edits or deletes.

## Data model changes

### `Log` — new snapshot columns (`app/models.py`)

| Column           | Type            | Notes                                   |
|------------------|-----------------|-----------------------------------------|
| `name`           | str, nullable   | Display without joining `Food`          |
| `brand`          | str, nullable   |                                         |
| `calories_100g`  | float           | Per-100g basis captured at log time     |
| `protein_100g`   | float           |                                         |
| `carbs_100g`     | float           |                                         |
| `fat_100g`       | float           |                                         |
| `serving_desc`   | str, nullable   | Display only                            |
| `serving_grams`  | float, nullable | Display only                            |
| `food_id`        | **nullable**    | Was non-null; nulled when a food is deleted |

Totals are computed from the log's **own** snapshot × `amount_g`, never from
the live `Food`.

### `Food` — unchanged

Custom foods remain `source="manual"` rows, already dedup'd by name+brand via
`crud._find_existing`. No `hidden` column (snapshotting replaces the need for
soft-delete).

### Migration & backfill

`init_db()` uses `Base.metadata.create_all`, which creates missing tables but
does **not** add columns to an existing `logs` table. Add an idempotent
`_migrate()` step called from `init_db()`:

1. For each new column, check `PRAGMA table_info(logs)`; `ALTER TABLE logs ADD
   COLUMN ...` only if absent.
2. Backfill existing `logs` rows from their joined `Food` (name, brand, the
   four per-100g values, serving fields) where the snapshot columns are null.

Idempotent and safe to run on every startup.

## Backend endpoints (`app/routers/foods.py`)

| Method & path              | Purpose                                             |
|----------------------------|-----------------------------------------------------|
| `POST /foods/manual`       | **Exists** — create (per-100g `ManualFoodIn`). Keep.|
| `GET /foods/manual`        | List all `source="manual"` foods for My Foods view. |
| `PUT /foods/manual/{id}`   | Edit a custom food (affects future logs only).      |
| `DELETE /foods/manual/{id}`| Null referencing `Log.food_id`, then hard-delete.   |

- The per-serving↔per-100g conversion lives in the **frontend**; the endpoint
  contract stays per-100g and clean.
- Delete manually sets `Log.food_id = NULL` for referencing rows (SQLite FK
  enforcement is off by default), so History survives via snapshots.
- Validation: name required; macros ≥ 0; `serving_grams` > 0 when provided.
  Unknown id → 404; bad payload → 422 (Pydantic).

### Log-create flow (`app/routers/logs.py`, `app/crud.py`)

At log-creation time, snapshot the food's current name/brand/per-100g
macros/serving fields onto the new `Log` row. Day/History rendering
(`LogEntryOut`, day totals) reads from the snapshot instead of joining `Food`.

## Search integration

**Approach: mirror the existing staples mechanism.** Add
`custom_matches(query, db)` returning matching `source="manual"` foods; in
`search_foods`, **prepend** them ahead of everything (the same position the
`staple` is prepended), then run `_dedupe`. Ordering: custom foods first, then
staple, then scored external results. Guarantees "always top" without scorer
tuning.

**Rejected:** a `LocalFoodSource(FoodSource)`. The `FoodSource` abstraction is
for external HTTP sources (`search` takes an `httpx.AsyncClient`, not a DB
session), and routing custom foods through the composite scorer would not
guarantee top placement. Prepending is the established in-repo pattern.

Note: `search_foods` / the search endpoint will need a DB session to reach
`custom_matches` (the route already depends on `get_db`).

## Frontend (`static/`)

- **"Custom" badge:** `renderResults` (and recents) show a small hard-bordered
  neo-brutalist tag on `source === "manual"` rows, consistent with existing
  macro blocks. Tokens in `static/style.css`.
- **Add-view button:** a persistent "Can't find it? **+ Add custom food**"
  button below results opens the create form (modal, reusing the existing
  dialog pattern).
- **Foods tab:** a 4th nav item → My Foods list. Each row: tap-to-log (reuse
  `openLogDialog`) plus Edit / Delete actions; an "Add custom food" button at
  top.
- **Create/edit form:** per-serving ↔ per-100g **toggle** (radio). Per-serving
  mode converts to per-100g before POST/PUT. Edit prefills existing values; if
  `serving_grams` exists, it can prefill in per-serving mode.
- **SW cache:** bump the `?v=nb1` query on `index.html`'s CSS/JS links to
  `?v=nb2` (service worker is network-first; versioned assets must be bumped
  when `static/*` changes).

## Error handling

- Form: inline validation messages (reuse the dialog `hint` pattern); failed
  saves show "Could not save."
- Delete: confirm prompt; note that past logged entries are kept.
- API: 404 (unknown id on PUT/DELETE), 422 (bad payload).

## Testing

**Backend**
- Snapshot-on-log: totals stay frozen after the food's macros are edited.
- Delete: referencing `Log.food_id` set null; History totals unchanged.
- `GET`/`PUT`/`DELETE /foods/manual` happy paths + 404/422.
- `custom_matches`: prepend ordering and `_dedupe` interaction (custom leads,
  same-named external hit dropped).
- Migration/backfill: idempotent; backfills existing rows correctly.

**Frontend**
- Extend `tests/test_static.py` for new markup (badge, Foods tab, form,
  bumped asset version).

Keep the suite green (currently 65 tests).

## Out of scope (YAGNI)

- Unhide / recover deleted foods (delete is a hard-delete by design).
- Editing non-manual (USDA/OFF) foods.
- Barcode / label OCR entry.
- Bulk import/export of custom foods.
