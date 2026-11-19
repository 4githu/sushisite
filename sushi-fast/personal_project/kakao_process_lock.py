"""Cross-process, cross-thread mutex for all backend Kakao UI operations.

The caller holds this around the entire search/send transaction. A process exit
releases the kernel lock. All workers must use the same database filesystem.
"""
from __future__ import annotations

import fcntl
import os
import threading
import time
from pathlib import Path


class KakaoProcessLock:
    def __init__(self, path):
        self.path = Path(path)
        self._thread_lock = threading.Lock()
        self._fd = None

    def acquire(self, blocking=True, timeout=-1):
        if not blocking and timeout != -1:
            raise ValueError("can't specify a timeout for a non-blocking call")
        started = time.monotonic()
        if not self._thread_lock.acquire(blocking, timeout):
            return False
        fd = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            while True:
                try:
                    flags = fcntl.LOCK_EX
                    if not blocking or timeout != -1:
                        flags |= fcntl.LOCK_NB
                    fcntl.flock(fd, flags)
                    self._fd = fd
                    return True
                except BlockingIOError:
                    if not blocking or (timeout != -1 and time.monotonic() - started >= timeout):
                        os.close(fd)
                        self._thread_lock.release()
                        return False
                    time.sleep(min(0.05, max(0, timeout - (time.monotonic() - started))))
        except BaseException:
            if fd is not None:
                os.close(fd)
            self._thread_lock.release()
            raise

    def release(self):
        if self._fd is None:
            raise RuntimeError('release unlocked lock')
        fd, self._fd = self._fd, None
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
            self._thread_lock.release()

    def locked(self):
        return self._thread_lock.locked()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_):
        self.release()
