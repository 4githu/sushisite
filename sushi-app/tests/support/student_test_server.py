"""Local integration server. Run with PYTHONPATH=sushi-fast and a dedicated temporary DB."""
import os
from pathlib import Path
if not os.environ.get('PERSONAL_PROJECT_DB_PATH') or 'personal_project.db' == Path(os.environ['PERSONAL_PROJECT_DB_PATH']).name:
    raise RuntimeError('Set PERSONAL_PROJECT_DB_PATH to a dedicated test database.')
from fastapi import FastAPI
from personal_project import workspace_router as router, student_services as student
app = FastAPI()
app.include_router(router.router)
app.dependency_overrides[router.current_user_id] = lambda: 7890
student.save_profile(7890, student.Profile(is_student=True, school='서울대학교', department='컴퓨터공학부'))
