from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from odi.router import router as odi_router
from auth.router import router as auth_router
from Legendaryvowels.router import router as Legendaryvowels_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.include_router(auth_router)
app.include_router(odi_router)
app.include_router(Legendaryvowels_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
