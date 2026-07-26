from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_serves_app_shell():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "supercaloriemonster" in resp.text.lower()


def test_static_assets_served():
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert "text/javascript" in resp.headers["content-type"] or "application/javascript" in resp.headers["content-type"]

    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
