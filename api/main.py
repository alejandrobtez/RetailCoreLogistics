"""
api/main.py — RetailCore Predictions API
=============================================================================
FastAPI que expone el modelo de predicción de fallos de entrega.

Arrancar:
    uvicorn api.main:app --reload --port 8000

Docs interactivas:
    http://localhost:8000/docs
=============================================================================
"""
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.routers import predict
from api.services.predictor import load_model

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(
    title="RetailCore Delivery Predictions API",
    description=(
        "Predicción de fallos de entrega de última milla. "
        "18.000 paquetes/día · Madrid · Barcelona · Valencia · Sevilla"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(predict.router)

# Serve the operator dashboard at /dashboard
if _DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/dashboard/")
