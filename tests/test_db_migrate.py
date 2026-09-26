import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

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


def _legacy_schema_not_null_food_id(engine):
    """Mirrors a pre-branch MVP DB: logs.food_id is NOT NULL and there are no
    snapshot columns yet."""
    with engine.begin() as c:
        c.exec_driver_sql(
            "CREATE TABLE foods (id INTEGER PRIMARY KEY, source TEXT, source_id TEXT,"
            " name TEXT, brand TEXT, calories_100g FLOAT, protein_100g FLOAT,"
            " carbs_100g FLOAT, fat_100g FLOAT, serving_desc TEXT, serving_grams FLOAT,"
            " cached_at TIMESTAMP)"
        )
        c.exec_driver_sql(
            "CREATE TABLE logs (id INTEGER PRIMARY KEY, food_id INTEGER NOT NULL,"
            " date DATE, meal_type TEXT, amount_g FLOAT, created_at TIMESTAMP,"
            " FOREIGN KEY(food_id) REFERENCES foods (id))"
        )
        c.exec_driver_sql(
            "INSERT INTO foods (id, source, name, calories_100g, protein_100g,"
            " carbs_100g, fat_100g) VALUES (1,'manual','Stew',120,9,6,5)"
        )
        c.exec_driver_sql(
            "INSERT INTO logs (id, food_id, date, meal_type, amount_g, created_at)"
            " VALUES (1,1,'2026-07-28','lunch',100,'2026-07-28')"
        )


def test_migrate_relaxes_food_id_not_null(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _legacy_schema_not_null_food_id(engine)

    _migrate(engine)

    with engine.begin() as c:
        row = c.exec_driver_sql(
            "SELECT id, food_id, name, calories_100g, amount_g FROM logs WHERE id=1"
        ).fetchone()
        assert row == (1, 1, "Stew", 120, 100)

    # This is the exact operation the delete route performs and that was
    # failing with sqlite3.IntegrityError on pre-branch databases.
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE logs SET food_id=NULL WHERE food_id=1")
        result = c.exec_driver_sql("SELECT food_id FROM logs WHERE id=1").fetchone()
    assert result[0] is None

    with engine.begin() as c:
        info = list(c.exec_driver_sql("PRAGMA table_info(logs)"))
        notnull = {r[1]: r[3] for r in info}
    assert notnull["food_id"] == 0


def test_migrate_relax_food_id_not_null_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _legacy_schema_not_null_food_id(engine)

    _migrate(engine)
    _migrate(engine)  # must not raise, and must stay nullable

    with engine.begin() as c:
        info = list(c.exec_driver_sql("PRAGMA table_info(logs)"))
        notnull = {r[1]: r[3] for r in info}
        assert notnull["food_id"] == 0
        row = c.exec_driver_sql("SELECT name FROM logs WHERE id=1").fetchone()
    assert row[0] == "Stew"


def test_migrate_rebuild_nulls_dangling_food_id(tmp_path):
    """Pre-FK databases can hold logs whose food was deleted. The rebuild runs
    with foreign_keys=ON, so it must null those out rather than fail."""
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _legacy_schema_not_null_food_id(engine)
    with engine.connect() as c:
        c.exec_driver_sql("PRAGMA foreign_keys=OFF")  # simulate pre-FK writes
        c.exec_driver_sql(
            "INSERT INTO logs (id, food_id, date, meal_type, amount_g, created_at)"
            " VALUES (2,99,'2026-07-28','dinner',50,'2026-07-28')"
        )
        c.commit()

    _migrate(engine)

    with engine.begin() as c:
        rows = c.exec_driver_sql("SELECT id, food_id FROM logs ORDER BY id").fetchall()
    assert rows == [(1, 1), (2, None)]


def test_foreign_keys_are_enforced(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    _legacy_schema_not_null_food_id(engine)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.exec_driver_sql(
                "INSERT INTO logs (id, food_id, date, meal_type, amount_g, created_at)"
                " VALUES (3,99,'2026-07-28','dinner',50,'2026-07-28')"
            )
