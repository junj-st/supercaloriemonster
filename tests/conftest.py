import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.schemas import NormalizedFood


class FakeSource:
    """A controllable in-test food source. Set .results / .boom per test."""

    def __init__(self, name="usda"):
        self.name = name
        self.results: list[NormalizedFood] = []
        self.boom = False

    async def search(self, query, client):
        if self.boom:
            raise RuntimeError("boom")
        return self.results

    async def get(self, source_id, client):
        for r in self.results:
            if r.source_id == source_id:
                return r
        return None


@pytest.fixture
def fake_sources():
    return [FakeSource()]


@pytest.fixture
def client(fake_sources):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def _get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # get_sources is defined in app/routers/foods.py (Task 9)
    from app.routers.foods import get_sources

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_sources] = lambda: fake_sources
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
