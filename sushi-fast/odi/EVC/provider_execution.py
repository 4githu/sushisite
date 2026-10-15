"""Bound actual provider threads, including calls that outlive their async timeout."""
from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from .config import EVC_PROVIDER_WORKERS


class ProviderCapacityError(RuntimeError):
    pass


class ProviderExecutor:
    def __init__(self, max_workers=4):
        self._slots = threading.BoundedSemaphore(max_workers)
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evc-provider")
        self._lock = threading.Lock()
        self.in_flight = 0

    def _finished(self, _future):
        with self._lock:
            self.in_flight -= 1
        self._slots.release()

    async def run(self, call, *, timeout_s):
        if not self._slots.acquire(blocking=False):
            raise ProviderCapacityError("segment/STT provider capacity reached; retry later")
        with self._lock:
            self.in_flight += 1
        try:
            future = self._pool.submit(call)
        except BaseException:
            self._finished(None)
            raise
        future.add_done_callback(self._finished)
        wrapped = asyncio.wrap_future(future)
        # Retrieve late exceptions even when the waiting request has timed out.
        wrapped.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        return await asyncio.wait_for(asyncio.shield(wrapped), timeout=timeout_s)

    def close(self):
        self._pool.shutdown(wait=True)


provider_executor = ProviderExecutor(EVC_PROVIDER_WORKERS)
