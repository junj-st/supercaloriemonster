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


def test_manifest_served():
    resp = client.get("/static/manifest.json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "supercaloriemonster"
    assert body["display"] == "standalone"
    assert body["start_url"] == "/"
    assert body["short_name"] == "scm"
    assert isinstance(body["icons"], list) and len(body["icons"]) > 0


def test_service_worker_served():
    resp = client.get("/static/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_service_worker_served_at_root():
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]


def test_icon_served():
    resp = client.get("/static/icon.svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]


def test_app_js_has_custom_badge():
    js = client.get("/static/app.js").text
    assert "badge-custom" in js
    assert 'source === "manual"' in js


def test_style_has_custom_badge():
    assert "badge-custom" in client.get("/static/style.css").text


def test_foods_tab_present():
    html = client.get("/").text  # root serves the app shell (index.html)
    assert 'data-view="foods"' in html
    assert 'id="view-foods"' in html


def test_app_js_loads_foods():
    js = client.get("/static/app.js").text
    assert "function loadFoods" in js
    assert "/foods/manual" in js
