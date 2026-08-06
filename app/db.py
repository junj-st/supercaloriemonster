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
        info = list(conn.exec_driver_sql("PRAGMA table_info(logs)"))
        if not info:
            return
        cols = {row[1] for row in info}
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

        # SQLite's ALTER TABLE ADD COLUMN cannot relax an existing NOT NULL
        # constraint, and SQLite has no ALTER COLUMN. On pre-branch DBs
        # `logs.food_id` is still physically NOT NULL even though the model
        # (and freshly-created DBs) treat it as nullable. Rebuild the table
        # to drop that constraint.
        food_id_notnull = any(
            row[1] == "food_id" and row[3] == 1 for row in info
        )
        if food_id_notnull:
            conn.exec_driver_sql("ALTER TABLE logs RENAME TO _logs_old")
            conn.exec_driver_sql(
                "CREATE TABLE logs ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " food_id INTEGER,"
                " date DATE NOT NULL,"
                " meal_type VARCHAR NOT NULL,"
                " amount_g FLOAT NOT NULL,"
                " created_at DATETIME NOT NULL,"
                " name VARCHAR,"
                " brand VARCHAR,"
                " calories_100g FLOAT,"
                " protein_100g FLOAT,"
                " carbs_100g FLOAT,"
                " fat_100g FLOAT,"
                " serving_desc VARCHAR,"
                " serving_grams FLOAT,"
                " FOREIGN KEY(food_id) REFERENCES foods (id)"
                ")"
            )
            conn.exec_driver_sql(
                "INSERT INTO logs (id, food_id, date, meal_type, amount_g, created_at,"
                " name, brand, calories_100g, protein_100g, carbs_100g, fat_100g,"
                " serving_desc, serving_grams) "
                "SELECT id, food_id, date, meal_type, amount_g, created_at,"
                " name, brand, calories_100g, protein_100g, carbs_100g, fat_100g,"
                " serving_desc, serving_grams FROM _logs_old"
            )
            conn.exec_driver_sql("DROP TABLE _logs_old")


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
