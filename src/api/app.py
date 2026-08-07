from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.logging_setup import setup_logging
from src.api.routes import (
    health,
    auth,
    user,
    portfolio,
    broker,
    account,
    strategy,
    index,
    service_telegram,
    task,
    bond,
)


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(title="ShadowTrader API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(service_telegram.router)
    app.include_router(user.router)
    app.include_router(portfolio.router)
    app.include_router(broker.router)
    app.include_router(account.router)
    app.include_router(strategy.router)
    app.include_router(index.router)
    app.include_router(task.router)
    app.include_router(bond.router)

    return app