"""Production binding for the reviewed owner-scoped settlement request service."""
from fastapi import APIRouter
from .parent_settlements import ParentSettlements, build_router as build_parent_router
from . import native_kakao
from .db import DB_PATH
from .settlement_requests import KakaoBridgeTextOnly, SettlementRequests, build_router


def _search_exact(room):
    # kakao_bridge imports router's auth helpers; import it only after startup.
    from .kakao_bridge import invoke
    return invoke("search", room=room, redact_errors=True)


def _send_text(room, text):
    from .kakao_bridge import invoke
    return invoke("send", room=room, text=text, files=[], redact_errors=True)


def bind_settlement_router(owner_dependency, read_owner_dependency=None):
    bridge = KakaoBridgeTextOnly(_search_exact, _send_text, operation_lock=native_kakao._send_lock)
    service = SettlementRequests(DB_PATH, bridge)
    router = APIRouter()
    router.include_router(build_router(service, owner_dependency))
    router.include_router(build_parent_router(ParentSettlements(service), owner_dependency, read_owner_dependency or owner_dependency))
    return router
