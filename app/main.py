import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import favorites, foods, logs

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="supercaloriemonster", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(foods.router)
app.include_router(logs.router)
app.include_router(favorites.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("static/index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse("static/sw.js", media_type="application/javascript")
