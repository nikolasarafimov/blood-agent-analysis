from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


_DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()

    if not raw:
        return list(_DEFAULT_CORS_ORIGINS)

    origins = list(dict.fromkeys(
        value.strip().rstrip("/")
        for value in raw.split(",")
        if value.strip()
    ))

    if "*" in origins:
        if len(origins) != 1:
            raise ValueError("CORS wildcard must not be combined with other origins")
        return ["*"]

    for origin in origins:
        try:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or not parsed.netloc
            ):
                raise ValueError("Invalid CORS origin")
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(
                "CORS_ALLOW_ORIGINS must contain HTTP(S) origins without paths"
            ) from exc

    return origins


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from db.sqlite_db import init_db as init_agent_db

    init_agent_db()
    yield


def create_app() -> FastAPI:
    load_dotenv(override=False)

    from app.routes import router

    application = FastAPI(
        title="Blood Analysis Agent API",
        description=(
            "API for blood test document ingestion, OCR, anonymization, "
            "structured laboratory data extraction, and LOINC enrichment."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    allow_origins = _cors_origins()
    allow_credentials = _env_flag("CORS_ALLOW_CREDENTIALS", default=False)

    if "*" in allow_origins:
        allow_credentials = False

    application.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    application.include_router(router)
    return application


app = create_app()


@app.get("/health", summary="Health check")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "blood-analysis-agent-api",
        "version": "1.0.0",
    }