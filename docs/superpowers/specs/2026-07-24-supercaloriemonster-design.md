# supercaloriemonster (scm) — Phase 1 MVP Design

A fully free, self-hosted calorie and macro tracking app. Built to avoid the
subscription walls and ad-driven UX of MyFitnessPal-style apps, using free
public food databases and infrastructure you control.

- **Phase 1 (this spec):** local-only, runs on your own machine via Docker.
- **Phase 2 (later):** publicly accessible without a VPN, still free to run.

This spec covers build-order steps 1–6: schema, food-source integration,
logging endpoints, minimal frontend, PWA wrapper, and local Docker deployment.

## Decisions locked during brainstorming

- **Name:** `supercaloriemonster`, `scm` for short (matches the GitHub repo).
- **Serving convention:** store **both** — per-100g canonical nutrition plus the
  source's own serving description and grams-per-serving.
- **Frontend:** vanilla JS, served as static files by FastAPI. No build step.
- **Food data:** USDA FoodData Central + Open Food Facts. USDA key from `.env`;
  if the key is missing, run OFF-only.
- **Scope:** full Phase 1 MVP (steps 1–6). Auth, rate limiting, and public
  hosting are Phase 2 and out of scope here.

## Goals

- Zero subscription cost, forever — no premium tiers, ads, or paywalled macros.
- Fast daily logging: search → tap → done.
- Accurate calorie/macro data from real databases, not crowdsourced guesses.
- Phone-first (primary use case), works well on desktop too.
- Data stays under your control: self-hosted, exportable, no vendor lock-in.
- Simple enough to maintain solo.

## MVP features

- Search foods across USDA + OFF and log them to a given date and meal.
- Daily totals: calories, protein, carbs, fat, grouped by meal.
- Edit and delete log entries.
- Quick re-log from recents and favorites.
- Basic history view of past days.

Deferred to later (clean extension points, not built now): barcode scanning,
recipe builder, weight tracking, trend charts, CSV export, multi-user, and
offline-write queueing.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Fast to build, auto Swagger docs, clean JSON handling, async for concurrent food lookups |
| ORM/DB | SQLAlchemy + SQLite | Zero-config single file; swap to Postgres later without rewriting queries |
| Frontend | Vanilla JS, served by FastAPI | Logging UI is forms and lists; no build step to maintain solo |
| PWA | manifest.json + service worker | Home-screen install; offline viewing of recent days |
| Container | Docker + Docker Compose | Portable between Mac, Pi, and a VPS with no app-code changes |

## Data model (SQLite via SQLAlchemy)

Nutrition is canonically **per-100g**; the source's serving info is stored
alongside so logging can feel natural. A log entry stores **grams** as the
source of truth, so daily totals are simple arithmetic regardless of source.

```
foods
  id             INTEGER PK
  source         TEXT       -- 'usda' | 'off' | 'manual'
  source_id      TEXT       -- original API id (NULL for manual)
  name           TEXT
  brand          TEXT NULL
  -- canonical, always per 100g:
  calories_100g  REAL
  protein_100g   REAL
  carbs_100g     REAL
  fat_100g       REAL
  -- source's serving, for intuitive logging:
  serving_desc   TEXT NULL  -- "1 cup", "1 bar"
  serving_grams  REAL NULL  -- grams in that serving; NULL if source gave none
  cached_at      TIMESTAMP
  UNIQUE(source, source_id)

logs
  id          INTEGER PK
  food_id     INTEGER FK -> foods.id
  date        DATE
  meal_type   TEXT       -- breakfast | lunch | dinner | snack
  amount_g    REAL       -- actual grams consumed (source of truth)
  created_at  TIMESTAMP

favorites
  id        INTEGER PK
  food_id   INTEGER FK -> foods.id  UNIQUE
  label     TEXT NULL
```

- The UI accepts either grams or number-of-servings (when `serving_grams`
  exists) and converts to grams before saving.
- Totals: `amount_g / 100 × <nutrient>_100g`.
- Recents are derived from `logs` (most recent distinct foods) — no extra table.

## Food-source integration

The two external APIs are isolated behind one interface so they are
interchangeable and independently testable.

```
app/sources/
  base.py        # FoodSource protocol:
                 #   search(query) -> list[NormalizedFood]
                 #   get(source_id) -> NormalizedFood | None
  usda.py        # USDAFoodSource — needs API key
  off.py         # OFFFoodSource  — no key, per-100g native, barcode-friendly
  normalize.py   # raw API JSON -> NormalizedFood (per-100g + serving shape)
```

**Search flow** (`GET /foods/search?q=...`):

1. Query USDA and OFF **concurrently** (async).
2. Normalize both result sets to the per-100g shape.
3. Merge into one ranked list — prefer USDA for generic matches, OFF for
   branded. Heuristic: branded results rank in the OFF-preferred lane, generic
   names rank USDA first. De-dupe obvious overlaps by name + brand.
4. Return results **without writing to the DB** — search results are ephemeral.

**Caching:** a food is persisted to `foods` only when actually **logged or
favorited**, not on every search. The client sends the full normalized food
object on log-create; the backend upserts into `foods` (on
`UNIQUE(source, source_id)`) and creates the log. Anything logged never needs a
repeat API call; the table stays free of never-used search hits.

**Failure handling:** if one source times out or errors, search returns the
other's results plus a `partial: true` flag rather than failing the whole
request. Missing USDA key → skip USDA, log a warning, OFF still works.

## API surface (FastAPI)

```
GET    /foods/search?q=...   → concurrent USDA+OFF, merge; {results, partial}
POST   /foods/manual         → add a manually-entered food (persists)

POST   /logs                 → body: full food object + {date, meal_type, amount_g};
                               upsert food, create log, return log w/ computed macros
PUT    /logs/{id}            → edit amount_g / meal_type / date
DELETE /logs/{id}
GET    /logs/day/{date}      → entries grouped by meal + daily totals

GET    /favorites            → list (joined with foods)
POST   /favorites            → body: full food object → upsert food + favorite
DELETE /favorites/{id}

GET    /recents              → distinct foods from recent logs (quick re-log)
```

Interactive Swagger docs at `/docs` for free.

## Frontend (vanilla JS, phone-first PWA)

```
static/
  index.html      # single page; section switching in JS (no router)
  app.js          # fetch calls, render, state
  style.css       # mobile-first, minimal
  manifest.json   # PWA install
  sw.js           # service worker
```

Three views, shown/hidden in JS:

- **Today** (default): daily totals bar (cal/P/C/F), entries grouped by meal, a
  `+` to add.
- **Search/Add**: type → results → tap → set grams-or-servings and meal → save.
  Recents and favorites shown when the search box is empty for one-tap re-log.
- **History**: date picker → that day's `logs/day/{date}` view.

**PWA:** `manifest.json` enables home-screen install; the service worker caches
the app shell and last-viewed days so past logs are viewable offline. Writes
require connectivity in the MVP (no offline-write queue yet).

## Project structure

```
supercaloriemonster/
  app/
    main.py            # FastAPI app, static mount, router include
    db.py              # SQLAlchemy engine/session, SQLite
    models.py          # ORM: Food, Log, Favorite
    schemas.py         # Pydantic request/response models
    config.py          # Pydantic Settings (env-driven)
    routers/
      foods.py         # search, manual
      logs.py          # CRUD + day summary
      favorites.py     # favorites + recents
    sources/           # base, usda, off, normalize
  static/              # index.html, app.js, style.css, manifest.json, sw.js
  tests/
  data/                # scm.db lives here (gitignored, Docker volume)
  .env.example         # USDA_API_KEY=...
  .gitignore           # .env, data/*.db
  Dockerfile
  docker-compose.yml
  requirements.txt
  README.md
  LICENSE              # MIT
```

## Testing (pytest, TDD)

- **Unit — highest value:** `normalize.py` against saved sample USDA/OFF JSON
  fixtures, since normalization is where source quirks bite. Macro math
  (grams → totals).
- **Integration:** endpoints via FastAPI `TestClient` against a temp SQLite
  file. External APIs are **mocked** with saved fixtures so tests are fast and
  offline. The `FoodSource` protocol makes injecting fakes trivial.

## Config & deployment

- Settings from env via Pydantic Settings; `USDA_API_KEY` from `.env`. Missing
  key → OFF-only with a logged warning.
- `docker-compose.yml`: one service (FastAPI/uvicorn), `data/` bind-mounted so
  `scm.db` survives restarts. `docker compose up` → `http://localhost:8000`.
- The same image redeploys to Fly.io or Railway unchanged in Phase 2.

## Git & open-sourcing hygiene (from commit #1)

- `.gitignore` excludes `.env` and `data/*.db` — real logs and secrets never
  committed.
- `.env.example` committed in place of `.env`.
- MIT `LICENSE`.
- README with setup instructions, tech-stack summary, and a screenshot slot.

## Out of scope (Phase 2 and beyond)

Auth (even a hardcoded password), rate limiting on `/foods/search`, public
hosting, barcode scanning, recipe builder, weight tracking, trend charts, CSV
export, multi-user, and offline-write queueing. The food-source interface and
per-100g data model are designed so these layer on without rework.
