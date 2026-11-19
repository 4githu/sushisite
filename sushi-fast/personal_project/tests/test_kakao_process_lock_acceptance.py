"""The UI lock must serialize independent server processes too."""
import multiprocessing
from personal_project.kakao_process_lock import KakaoProcessLock


def _try_acquire(path, results):
    lock = KakaoProcessLock(path)
    acquired = lock.acquire(blocking=False)
    results.put(acquired)
    if acquired:
        lock.release()


def test_independent_processes_cannot_operate_together(tmp_path):
    ctx = multiprocessing.get_context('spawn')
    path = str(tmp_path / 'kakao.lock')
    lock = KakaoProcessLock(path)
    with lock:
        result = ctx.Queue()
        worker = ctx.Process(target=_try_acquire, args=(path, result))
        worker.start()
        worker.join(10)
        assert worker.exitcode == 0
        assert result.get(timeout=2) is False
    result = ctx.Queue()
    worker = ctx.Process(target=_try_acquire, args=(path, result))
    worker.start()
    worker.join(10)
    assert worker.exitcode == 0
    assert result.get(timeout=2) is True
