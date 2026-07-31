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
