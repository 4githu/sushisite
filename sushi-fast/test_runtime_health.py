import asyncio

import httpx
from fastapi import FastAPI
from starlette.responses import StreamingResponse

from runtime_health import RuntimeHealthMiddleware


def test_health_and_streaming_timing():
    async def run():
        app = FastAPI()
        app.add_middleware(RuntimeHealthMiddleware)

        @app.get("/stream")
        async def stream():
            async def chunks():
                yield b"one"
                await asyncio.sleep(0)
                yield b"two"
            return StreamingResponse(chunks())

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            health = await client.get("/api/healthz")
            assert health.json() == {"status": "ok"}
            assert health.headers["cache-control"] == "no-store"
            result = await client.get("/stream")
            assert result.content == b"onetwo"
            assert result.headers["server-timing"].startswith("app;dur=")
    asyncio.run(run())
