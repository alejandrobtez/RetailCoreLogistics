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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import predict
from api.services.predictor import load_model


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
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(predict.router)
