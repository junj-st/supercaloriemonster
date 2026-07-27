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
