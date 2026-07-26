import logging

from fastapi import FastAPI

from app.db import init_db
from app.routers import foods, logs

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="supercaloriemonster")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(foods.router)
app.include_router(logs.router)
