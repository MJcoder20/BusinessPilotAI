
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import products
from app.api import customers
from app.api import sales_orders
from app.api import ai
from app.api import conversations
from app.api.invoices import router as invoices_router
from app.api.analytics import router as analytics_router

from app.ai.agent import (
    initialize_agent_storage,
    close_agent_storage,
)
import logging
from sqlalchemy import text
from app.core.database import engine
from fastapi import FastAPI, HTTPException
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize PostgreSQL checkpoint storage.
    initialize_agent_storage()

    yield

    # Close PostgreSQL connection pool.
    close_agent_storage()


app = FastAPI(
    title="BusinessPilot AI",
    description="Enterprise AI Business Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "message": "Welcome to BusinessPilot AI"
    }


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy"
    }

@app.get("/api/v1/health/ready")
def readiness_check():
    database_status = "connected"
    ollama_status = "available"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "disconnected"

    try:
        import urllib.request

        url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"

        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                ollama_status = "unavailable"
            else:
                import json

                ollama_data = json.loads(response.read().decode())

                available_models = [
                    model["name"]
                    for model in ollama_data.get("models", [])
                ]

                if settings.ollama_model not in available_models:
                    ollama_status = "model_not_found"

    except Exception:
        ollama_status = "unavailable"

    if database_status != "connected" or ollama_status != "available":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "database": database_status,
                "ollama": ollama_status,
            },
        )

    return {
        "status": "ready",
        "database": database_status,
        "ollama": ollama_status,
    }

app.include_router(customers.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(sales_orders.router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
