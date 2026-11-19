"""An attachment waiting on disk/SQLite must not freeze unrelated requests."""
import asyncio
import threading

from starlette.requests import Request
from personal_project import router


def test_attachment_save_does_not_block_event_loop(monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    def blocked_save(*args):
        entered.set()
        assert release.wait(2), "event loop could not run while attachment was saved"
        return {"id": 1}

    monkeypatch.setattr(router.repository, "save_target_report_attachment", blocked_save)

    async def run():
        async def receive():
            return {"type": "http.request", "body": b"image", "more_body": False}
        request = Request({"type": "http", "headers": [(b"content-type", b"image/png")]}, receive)
        task = asyncio.create_task(router.upload_target_report_attachment(1, request, "test", "a.png", 1))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)
            assert entered.is_set()
        finally:
            release.set()
        assert await task == {"id": 1}
    asyncio.run(run())
