
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
