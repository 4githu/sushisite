from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import random
import secrets
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID, uuid4

from .schema import AudienceRuntimeState, SlideInfo, SmartStartOptions
from .config import EVC_MAX_SESSIONS, EVC_SESSION_TTL_S
from .state_engine import create_agent_rngs, initialize_audiences


class SessionStoreError(RuntimeError):
    pass


class SessionNotFoundError(SessionStoreError):
    pass


class InvalidSessionTokenError(SessionStoreError):
    pass


class SessionCapacityError(SessionStoreError):
    pass


@dataclass
class SessionRecord:
    session_id: UUID
    token_digest: bytes
    presentation_title: str
    topic_interest: float
    prior_knowledge: float
    seed: int
    audiences: list[AudienceRuntimeState]
    rngs: dict[str, random.Random]
    slides: list[SlideInfo]
    slide_file_path: str | None
    created_at: datetime
    updated_at: datetime
    last_access_monotonic: float
    step: int = 0
    accepted_client_time_s: float = 0.0
    segment_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    request_cache: OrderedDict[UUID, object] = field(default_factory=OrderedDict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class SessionStore:
    def __init__(
        self,
        ttl_s: int = 7200,
        max_sessions: int = 100,
        monotonic_clock=time.monotonic,
    ) -> None:
        if ttl_s <= 0:
            raise ValueError("ttl_s must be positive")
        if max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        self.ttl_s = ttl_s
        self.max_sessions = max_sessions
        self._clock = monotonic_clock
        self._sessions: dict[UUID, SessionRecord] = {}
        self._store_lock = asyncio.Lock()

    async def create_session(
        self,
        options: SmartStartOptions,
        slides: list[SlideInfo] | None = None,
        slide_file_path: str | None = None,
    ) -> tuple[SessionRecord, str]:
        async with self._store_lock:
            self._cleanup_expired_locked()
            if len(self._sessions) >= self.max_sessions:
                raise SessionCapacityError("maximum active EVC session count reached")

            seed = options.seed if options.seed is not None else secrets.randbits(31)
            rngs = create_agent_rngs(seed)
            audiences = initialize_audiences(options, seed, rngs=rngs)
            raw_token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            record = SessionRecord(
                session_id=uuid4(),
                token_digest=_digest_token(raw_token),
                presentation_title=options.presentation_title,
                topic_interest=options.topic_interest,
                prior_knowledge=options.prior_knowledge,
                seed=seed,
                audiences=audiences,
                rngs=rngs,
                slides=list(slides or []),
                slide_file_path=slide_file_path,
                created_at=now,
                updated_at=now,
                last_access_monotonic=self._clock(),
            )
            self._sessions[record.session_id] = record
            return record, raw_token

    async def get_authorized_session(self, session_id: UUID, token: str) -> SessionRecord:
        async with self._store_lock:
            self._cleanup_expired_locked()
            record = self._sessions.get(session_id)
            if record is None:
                raise SessionNotFoundError(f"EVC session does not exist: {session_id}")
            if not hmac.compare_digest(record.token_digest, _digest_token(token)):
                raise InvalidSessionTokenError("invalid EVC session token")
            record.last_access_monotonic = self._clock()
            record.updated_at = datetime.now(timezone.utc)
            return record

    @asynccontextmanager
    async def locked_session(
        self,
        session_id: UUID,
        token: str,
    ) -> AsyncIterator[SessionRecord]:
        record = await self.get_authorized_session(session_id, token)
        async with record.lock:
            if self._is_expired(record):
                async with self._store_lock:
                    self._remove_session_locked(session_id)
                raise SessionNotFoundError(f"EVC session expired: {session_id}")
            yield record
            record.last_access_monotonic = self._clock()
            record.updated_at = datetime.now(timezone.utc)

    async def delete_session(self, session_id: UUID, token: str) -> None:
        record = await self.get_authorized_session(session_id, token)
        async with record.lock:
            async with self._store_lock:
                self._remove_session_locked(session_id)

    async def active_count(self) -> int:
        async with self._store_lock:
            self._cleanup_expired_locked()
            return len(self._sessions)

    def expires_in_s(self, record: SessionRecord) -> int:
        remaining = self.ttl_s - (self._clock() - record.last_access_monotonic)
        return max(0, int(remaining))

    def _is_expired(self, record: SessionRecord) -> bool:
        return self._clock() - record.last_access_monotonic >= self.ttl_s

    def _cleanup_expired_locked(self) -> None:
        expired_ids = [
            session_id
            for session_id, record in self._sessions.items()
            if self._is_expired(record)
        ]
        for session_id in expired_ids:
            self._remove_session_locked(session_id)

    def _remove_session_locked(self, session_id: UUID) -> None:
        record = self._sessions.pop(session_id, None)
        if record is None or not record.slide_file_path:
            return
        path = Path(record.slide_file_path)
        try:
            if path.is_file():
                os.remove(path)
        except OSError:
            pass


def _digest_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


session_store = SessionStore(ttl_s=EVC_SESSION_TTL_S, max_sessions=EVC_MAX_SESSIONS)
