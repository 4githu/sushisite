"""Set isolation before pytest imports any test module or application module."""
import os
import tempfile
from pathlib import Path
# Never inherit a service's production DB, even when module collection order changes.
os.environ['PERSONAL_PROJECT_DB_PATH']=str(Path(tempfile.mkdtemp(prefix='personal-pytest-'))/'test.sqlite')
os.environ['PERSONAL_RESOURCE_ROOT']=str(Path(tempfile.mkdtemp(prefix='personal-resources-pytest-')))
os.environ['DISABLE_KAKAO_BRIDGE']='1'
os.environ['DISABLE_TREND_REFRESH']='1'

def pytest_collection_finish(session):
    from personal_project.db import DB_PATH
    if 'personal-pytest-' not in str(DB_PATH) and 'tests-' not in str(DB_PATH):
        raise RuntimeError('Refusing tests against a non-test database: '+str(DB_PATH))
