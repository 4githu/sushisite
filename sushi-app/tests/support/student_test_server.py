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
# This module refuses the production database; its fixed identity is local QA only.
from personal_project.router import router as personal_router, current_user_id
from aura_editor_fixture import router as aura_fixture
app.include_router(aura_fixture)
app.include_router(personal_router)
app.dependency_overrides[current_user_id] = lambda: 7890
@app.get('/auth/isjwt')
def qa_identity():
    return {'sub':'7890','data':{'id':'7890','name':'검수 계정','email':'review@example.com'},'exp':9999999999}

# Local-only fixture accepts writes from the dedicated development frontend.
from personal_project.community_v2 import write_origin
app.dependency_overrides[write_origin] = lambda: None
