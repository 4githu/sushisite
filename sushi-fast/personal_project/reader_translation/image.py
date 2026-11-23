"""Authenticated selected-PDF-region visual explanation (no file persistence)."""
import asyncio
import base64
import binascii
import json

from fastapi import HTTPException, Request
from . import _authorize_reader_request, _bad_request, _hermes_settings, _read_request_json, _run_hermes_command

MAX_IMAGE_BYTES = 768 * 1024
MAX_REQUEST_BYTES = 1100 * 1024


def _validate_image(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('image'), dict):
        raise _bad_request('invalid_image', '이미지 데이터가 필요합니다.')
    image = payload['image']
    mime = image.get('mime_type')
    data = image.get('base64')
    if mime not in ('image/png', 'image/jpeg') or not isinstance(data, str) or len(data) > ((MAX_IMAGE_BYTES + 2) // 3) * 4:
        raise _bad_request('invalid_image', 'PNG 또는 JPEG 이미지가 필요합니다.')
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise _bad_request('invalid_image', '이미지 인코딩이 올바르지 않습니다.') from None
    if not raw or len(raw) > MAX_IMAGE_BYTES or not (raw.startswith(b'\x89PNG\r\n\x1a\n') if mime == 'image/png' else raw.startswith(b'\xff\xd8\xff')):
        raise _bad_request('invalid_image', '이미지 형식이 올바르지 않습니다.')
    clean = {'image': {'mime_type': mime, 'base64': data}}
    for name, maximum, default in [('caption', 2000, ''), ('context', 6000, ''), ('target_language', 64, 'Korean')]:
        value = payload.get(name, default)
        if not isinstance(value, str) or len(value) > maximum or (name == 'target_language' and not value.strip()):
            raise _bad_request('invalid_image_context', '이미지 문맥 또는 언어 설정이 올바르지 않습니다.')
        clean[name] = value
    return clean


async def _invoke_until_disconnect(request, payload, executable, home):
    async def watch():
        while not await request.is_disconnected():
            await asyncio.sleep(0.1)

    call = asyncio.create_task(_run_hermes_command(payload, 'paiper-reader-explain-image', executable, home))
    watcher = asyncio.create_task(watch())
    try:
        done, _ = await asyncio.wait({call, watcher}, return_when=asyncio.FIRST_COMPLETED)
        if call in done:
            return await call
        await watcher  # propagate an unexpected receive error
        raise _bad_request('request_cancelled', '요청이 취소되었습니다.', 499)
    finally:
        for task in (call, watcher):
            if not task.done():
                task.cancel()
        await asyncio.gather(call, watcher, return_exceptions=True)


async def explain_reader_image(request: Request, user_id: int):
    settings = await _authorize_reader_request(request, user_id)
    payload = _validate_image(await _read_request_json(request, max_bytes=MAX_REQUEST_BYTES))
    executable, home = settings or _hermes_settings()
    try:
        raw = await _invoke_until_disconnect(request, json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode(), executable, home)
        result = json.loads(raw)
        if not isinstance(result, dict) or set(result) != {'explanation'} or not isinstance(result['explanation'], str) or not result['explanation'].strip() or len(result['explanation']) > 16000:
            raise ValueError('invalid result')
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail={'code': 'image_provider_error', 'message': '이미지 설명 요청을 처리하지 못했습니다.'}) from None
