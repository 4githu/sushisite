from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from odi.router import router as odi_router
from auth.router import router as auth_router
from Legendaryvowels.router import router as Legendaryvowels_router
from personal_project.router import router as personal_project_router
from personal_project.workspace_router import router as workspace_router
from personal_project.drive_router import router as drive_router
from personal_project.player.router import router as player_router
from personal_project.drive import cleanup_expired, cleanup_pending
from auth.google_oauth import router as google_oauth_router
from ai_office_gateway import install_ai_office_gateway
from personal_project.google_calendar import run_worker, stop_worker
import threading
from odi.db import odidb
from fastapi.middleware.cors import CORSMiddleware
from runtime_health import RuntimeHealthMiddleware

app = FastAPI()
app.add_middleware(RuntimeHealthMiddleware)

# Ensure additive report tables exist and make interrupted jobs retryable after restart.
odidb.ensure_report_schema()
odidb.recover_stale_report_jobs()
with odidb.get_conn() as conn:
    conn.execute("UPDATE practice_attempts SET state='failed', error='분석이 중단되었습니다. 현재 녹음으로 다시 시도해 주세요.' WHERE state IN ('queued','analyzing')")

app.include_router(auth_router)
app.include_router(odi_router)
app.include_router(Legendaryvowels_router)
app.include_router(personal_project_router)
app.include_router(workspace_router)
app.include_router(drive_router)
app.include_router(player_router)
app.include_router(google_oauth_router)

@app.on_event('startup')
def start_calendar_sync():
    stop_worker.clear()
    threading.Thread(target=run_worker,daemon=True,name='google-calendar-sync').start()
    def clean_drive():
        while not stop_worker.is_set():
            try:
                cleanup_expired()
                cleanup_pending()
            except Exception:
                # A transient database error must not stop future expiry passes.
                pass
            stop_worker.wait(15 * 60)
    threading.Thread(target=clean_drive,daemon=True,name='personal-drive-cleanup').start()

@app.on_event('shutdown')
def stop_calendar_sync():
    stop_worker.set()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9000",
        "http://localhost:5173",
        "https://chobab.app",
        "https://aura.chobab.app",
        "https://rehear.chobab.app",
        "https://rehear.kr",
        "https://calender.chobab.app",
        "https://calendar.chobab.app",
        "https://netaq.chobab.app",
        "https://ai.chobab.app",
        "https://territories-tickets-donna-twist.trycloudflare.com",
    ],
    allow_origin_regex=r"https://.*\.trycloudflare\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# `ai.chobab.app` is routed to this service. The gateway verifies Sushi's
# session and its account-to-system binding before proxying any Hermes route.
install_ai_office_gateway(app)
