from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .api import router
from .config import get_settings
from .db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)
app.include_router(router)
built_web = Path(__file__).parents[1] / "web" / "dist"
if built_web.exists():
    app.mount("/console", StaticFiles(directory=built_web, html=True), name="console")


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/console/" if built_web.exists() else "/docs")
