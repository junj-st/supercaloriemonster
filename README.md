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

The container publishes on `127.0.0.1` only, because **scm has no authentication**. To use it
from your phone or other devices, put a reverse proxy with auth in front of it (e.g. Caddy with
`basic_auth`, or Tailscale) instead of exposing port 8000 directly.

The container runs as UID 1000. If your host's `./data` directory is owned by a different user,
`chown 1000 data` once.

## Run locally (without Docker)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt   # app deps + pytest/ruff
uvicorn app.main:app --reload
```

## Configuration

| Env var        | Default | Purpose |
|----------------|---------|---------|
| `USDA_API_KEY` | (unset) | Free key from https://fdc.nal.usda.gov/api-key-signup.html. Unset → OFF-only. |

Your data lives in `data/scm.db` (gitignored). The database runs in WAL mode, so copying the
`.db` file alone while the app is running can miss recent writes. Back up with:

```bash
sqlite3 data/scm.db ".backup data/scm-backup-$(date +%F).db"
```

## Tests

```bash
pytest -v
ruff check .
```

Tests use a throwaway database and never touch `data/scm.db`. CI runs both on every PR, plus a
Docker build and health-check smoke test.

## API

Interactive docs at http://localhost:8000/docs.

## License

MIT — see [LICENSE](LICENSE).
