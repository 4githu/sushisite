from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from personal_project.router import current_user_id

from .db import connection
from . import service

router = APIRouter(prefix="/api/personal/player", tags=["personal-player"])


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    mode: Literal["ordered", "weighted"] | None = None
    repeat_mode: Literal["all", "one", "off"] | None = None
    avoid_repeat: bool | None = None
    playback_rate: float | None = Field(default=None, ge=0.25, le=8)


class SourceImport(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    account_id: int | None = None


class VideoAdd(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    account_id: int | None = None


class TrackUpdate(BaseModel):
    weight: float | None = Field(default=None, ge=0.1, le=10, allow_inf_nan=False)
    enabled: bool | None = None


class TrackOrder(BaseModel):
    ids: list[int] = Field(max_length=1000)


@router.get("/collections")
def collections(user_id: int = Depends(current_user_id)):
    return service.list_collections(user_id)


@router.post("/collections", status_code=201)
def create_collection(data: CollectionCreate, user_id: int = Depends(current_user_id)):
    with connection() as db:
        collection_id = db.execute("INSERT INTO collections(user_id,name) VALUES(?,?)", (user_id, data.name.strip())).lastrowid
    return service.collection_detail(user_id, collection_id)


@router.get("/collections/{collection_id}")
def collection(collection_id: int, user_id: int = Depends(current_user_id)):
    return service.collection_detail(user_id, collection_id)


@router.patch("/collections/{collection_id}")
def update_collection(collection_id: int, data: CollectionUpdate, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = (changes["name"] or "").strip()
        if not changes["name"]:
            raise HTTPException(400, "목록 이름을 입력해주세요.")
    if any(value is None for value in changes.values()):
        raise HTTPException(400, "설정값을 확인해주세요.")
    if changes:
        with connection() as db:
            assignments = ",".join(f"{field}=?" for field in changes)
            db.execute(f"UPDATE collections SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (*changes.values(), collection_id, user_id))
    return service.collection_detail(user_id, collection_id)


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: int, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    with connection() as db:
        db.execute("DELETE FROM collections WHERE id=? AND user_id=?", (collection_id, user_id))
    return Response(status_code=204)


@router.post("/collections/{collection_id}/sources", status_code=201)
def import_source(collection_id: int, data: SourceImport, user_id: int = Depends(current_user_id)):
    return service.import_playlist(user_id, collection_id, data.url, data.account_id)


@router.delete("/collections/{collection_id}/sources/{source_id}", status_code=204)
def remove_source(collection_id: int, source_id: int, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    with connection() as db:
        db.execute("DELETE FROM tracks WHERE collection_id=? AND source_id=?", (collection_id, source_id))
        if not db.execute("DELETE FROM sources WHERE collection_id=? AND id=?", (collection_id, source_id)).rowcount:
            raise HTTPException(404, "원본 재생목록을 찾지 못했습니다.")
    return Response(status_code=204)


@router.post("/collections/{collection_id}/tracks", status_code=201)
def add_track(collection_id: int, data: VideoAdd, user_id: int = Depends(current_user_id)):
    return service.add_video(user_id, collection_id, data.url, data.account_id)


@router.patch("/collections/{collection_id}/tracks/{track_id}")
def update_track(collection_id: int, track_id: int, data: TrackUpdate, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes or any(value is None for value in changes.values()):
        raise HTTPException(400, "변경할 설정을 입력해주세요.")
    with connection() as db:
        assignments = ",".join(f"{field}=?" for field in changes)
        if not db.execute(f"UPDATE tracks SET {assignments} WHERE id=? AND collection_id=?",
            (*changes.values(), track_id, collection_id)).rowcount:
            raise HTTPException(404, "곡을 찾지 못했습니다.")
    return service.collection_detail(user_id, collection_id)


@router.put("/collections/{collection_id}/tracks/order")
def reorder_tracks(collection_id: int, data: TrackOrder, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    with connection() as db:
        rows = db.execute("SELECT id FROM tracks WHERE collection_id=?", (collection_id,)).fetchall()
        ids = {row["id"] for row in rows}
        if len(data.ids) != len(ids) or set(data.ids) != ids:
            raise HTTPException(400, "현재 곡 전체의 순서를 보내주세요.")
        db.executemany("UPDATE tracks SET position=? WHERE id=? AND collection_id=?",
            [(position, track_id, collection_id) for position, track_id in enumerate(data.ids)])
    return service.collection_detail(user_id, collection_id)


@router.delete("/collections/{collection_id}/tracks/{track_id}", status_code=204)
def delete_track(collection_id: int, track_id: int, user_id: int = Depends(current_user_id)):
    service.collection_for(user_id, collection_id)
    with connection() as db:
        if not db.execute("DELETE FROM tracks WHERE id=? AND collection_id=?", (track_id, collection_id)).rowcount:
            raise HTTPException(404, "곡을 찾지 못했습니다.")
    return Response(status_code=204)


@router.get("/google/accounts")
def google_accounts(user_id: int = Depends(current_user_id)):
    with connection() as db:
        return [dict(row) for row in db.execute("SELECT id,email,created_at FROM google_accounts WHERE user_id=? ORDER BY id DESC", (user_id,))]


@router.get("/google/accounts/{account_id}/playlists")
def google_playlists(account_id: int, user_id: int = Depends(current_user_id)):
    return service.owned_playlists(user_id, account_id)


@router.delete("/google/accounts/{account_id}", status_code=204)
def disconnect_google(account_id: int, user_id: int = Depends(current_user_id)):
    with connection() as db:
        if not db.execute("DELETE FROM google_accounts WHERE id=? AND user_id=?", (account_id, user_id)).rowcount:
            raise HTTPException(404, "연결된 Google 계정을 찾지 못했습니다.")
    return Response(status_code=204)
