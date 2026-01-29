import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from db.sqlite_db import init_db as init_agent_db

load_dotenv()

app = FastAPI(
    title="Blood Agent API",
    description="AI-powered blood test analysis",
    version="1.0.0",
)

origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = ["*"] if origins.strip() == "*" else [o.strip() for o in origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    # Initialize the DB schema used by the blood-agent package (documents + lab_rows)
    init_agent_db()

app.include_router(router)

@app.get("/health")
def health():
    return {"ok": True}