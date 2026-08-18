import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import agent, cases, dashboard, knowledge
from business_config import BUSINESS_CONFIG
from config import get_settings
from database.init_db import init_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(title=BUSINESS_CONFIG["app_name"], version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"}),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard.router)
app.include_router(cases.router)
app.include_router(knowledge.router)
app.include_router(agent.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "competition_mode": settings.competition_mode, "llm_configured": bool(settings.llm_api_key)}


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled request error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "服务暂时不可用，请稍后重试"})
