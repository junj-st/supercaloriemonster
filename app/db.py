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


def init_db() -> None:
    import app.models  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)
    _migrate(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
