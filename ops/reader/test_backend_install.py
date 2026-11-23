from pathlib import Path

import pytest

from install_backend import mount_router


def test_mount_preserves_all_existing_routes():
    candidate = (Path(__file__).parents[2] / 'sushi-fast/personal_project/router.py').read_text()
    old = ('from . import workspace\n\n'
           '@router.get("/kakao/status")\ndef kakao_status():\n    return "keep"\n'
           '@router.post("/unrelated")\ndef other():\n    return "unchanged"\n')
    result = mount_router(old, candidate)
    assert '@router.post("/reader/translate")' in result
    assert '@router.post("/reader/explain-image")' in result
    assert result.endswith(old[old.index('@router.get'):])
    assert result.count('Depends(current_user_id)') == 2


def test_refuses_duplicate_or_changed_router():
    candidate = (Path(__file__).parents[2] / 'sushi-fast/personal_project/router.py').read_text()
    with pytest.raises(RuntimeError):
        mount_router(candidate, candidate)
    with pytest.raises(RuntimeError):
        mount_router('unfamiliar router', candidate)
