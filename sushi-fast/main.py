from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from odi.router import router as odi_router
from auth.router import router as auth_router
from Legendaryvowels.router import router as Legendaryvowels_router
from personal_project.router import router as personal_project_router
from odi.db import odidb
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Ensure additive report tables exist and make interrupted jobs retryable after restart.
odidb.ensure_report_schema()
odidb.recover_stale_report_jobs()

app.include_router(auth_router)
app.include_router(odi_router)
app.include_router(Legendaryvowels_router)
app.include_router(personal_project_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9000",
        "http://localhost:5173",
        "https://chobab.app",
        "https://aura.chobab.app",
        "https://rehear.chobab.app",
        "https://territories-tickets-donna-twist.trycloudflare.com",
    ],
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
