from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import router

from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Blood Agent API",
    description="AI-powered blood test analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
if __name__ == "__main__":
    import uvicorn

    print("Starting Blood Agent API...")
    print("Swagger UI: http://localhost:8000/docs")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )