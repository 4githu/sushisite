"""Playlist storage and the official YouTube Data API boundary."""
import os
import re
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import HTTPException

from .db import connection

YOUTUBE_ROOT = "https://www.googleapis.com/youtube/v3"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,80}$")
MAX_TRACKS = 1000


def playlist_id_from_url(value: str) -> str:
    url = urlparse(value.strip())
    if url.scheme not in ("http", "https") or (url.hostname or "").lower() not in (
        "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"
    ):
        raise HTTPException(400, "유튜브 재생목록 링크를 입력해주세요.")
    playlist_id = parse_qs(url.query).get("list", [""])[0]
    if not ID_RE.fullmatch(playlist_id):
        raise HTTPException(400, "재생목록 링크에서 목록 ID를 찾지 못했습니다.")
    return playlist_id


def video_id_from_url(value: str) -> str:
    url = urlparse(value.strip())
    host = (url.hostname or "").lower()
    if url.scheme not in ("http", "https"):
        raise HTTPException(400, "유튜브 영상 링크를 입력해주세요.")
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        video_id = parse_qs(url.query).get("v", [""])[0] if url.path == "/watch" else url.path.removeprefix("/shorts/").removeprefix("/embed/")
    elif host in ("youtu.be", "www.youtu.be"):
        video_id = url.path.strip("/")
    else:
        video_id = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise HTTPException(400, "영상 링크에서 영상 ID를 찾지 못했습니다.")
    return video_id


def google_account(user_id: int, account_id: int) -> dict:
    with connection() as db:
        row = db.execute("SELECT * FROM google_accounts WHERE id=? AND user_id=?", (account_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "연결된 Google 계정을 찾지 못했습니다.")
    return dict(row)


def youtube_get(path: str, params: dict, user_id: int, account_id: int | None = None) -> dict:
    headers = {}
    if account_id is not None:
        from auth.google_oauth import access_token
        headers["Authorization"] = "Bearer " + access_token(google_account(user_id, account_id))
    else:
        api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(503, "YouTube API 키가 설정되지 않았습니다. Google 계정을 연결하거나 관리자에게 문의해주세요.")
        params["key"] = api_key
    try:
        response = httpx.get(YOUTUBE_ROOT + path, params=params, headers=headers, timeout=20)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "유튜브에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.") from exc
    if response.status_code in (401, 403):
        try:
            reasons = {item.get("reason") for item in response.json().get("error", {}).get("errors", [])}
        except (ValueError, TypeError, AttributeError):
            reasons = set()
        if "accessNotConfigured" in reasons:
            raise HTTPException(503, "Google Cloud 프로젝트에서 YouTube Data API v3가 활성화되지 않았습니다. 프로젝트 관리자에게 API 활성화를 요청해주세요.")
        if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}:
            raise HTTPException(429, "YouTube API 사용 한도에 도달했습니다. 잠시 후 다시 시도해주세요.")
        raise HTTPException(502, "유튜브 계정의 목록을 읽을 권한이 없거나 YouTube API 요청이 거부되었습니다.")
    if response.status_code == 404:
        if path == "/playlists" and params.get("mine") == "true":
            try:
                reasons = {item.get("reason") for item in response.json().get("error", {}).get("errors", [])}
            except (ValueError, TypeError, AttributeError):
                reasons = set()
            if "channelNotFound" in reasons:
                return {"items": []}
        raise HTTPException(404, "유튜브 재생목록 또는 영상을 찾지 못했습니다.")
    if response.status_code >= 400:
        raise HTTPException(502, "유튜브 목록을 가져오지 못했습니다.")
    return response.json()


def collection_for(user_id: int, collection_id: int) -> dict:
    with connection() as db:
        row = db.execute("SELECT * FROM collections WHERE id=? AND user_id=?", (collection_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "재생목록을 찾지 못했습니다.")
    return dict(row)


def list_collections(user_id: int) -> list[dict]:
    with connection() as db:
        rows = db.execute("""SELECT c.*, COUNT(t.id) AS track_count FROM collections c
            LEFT JOIN tracks t ON t.collection_id=c.id WHERE c.user_id=?
            GROUP BY c.id ORDER BY c.updated_at DESC,c.id DESC""", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def collection_detail(user_id: int, collection_id: int) -> dict:
    item = collection_for(user_id, collection_id)
    with connection() as db:
        item["sources"] = [dict(row) for row in db.execute(
            "SELECT id,playlist_id,title,source_url,account_id FROM sources WHERE collection_id=? ORDER BY id", (collection_id,))]
        item["tracks"] = [dict(row) for row in db.execute(
            """SELECT id,source_id,video_id,title,channel_title,thumbnail_url,position,weight,enabled
               FROM tracks WHERE collection_id=? ORDER BY position,id""", (collection_id,))]
    return item


def import_playlist(user_id: int, collection_id: int, url: str, account_id: int | None) -> dict:
    collection_for(user_id, collection_id)
    playlist_id = playlist_id_from_url(url)
    playlist = youtube_get("/playlists", {"part": "snippet", "id": playlist_id, "maxResults": 1}, user_id, account_id)
    if not playlist.get("items"):
        raise HTTPException(404, "목록을 찾지 못했습니다. 비공개 목록이면 해당 Google 계정을 선택해주세요.")
    title = playlist["items"][0]["snippet"]["title"]
    entries = []
    page = None
    while True:
        params = {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if page:
            params["pageToken"] = page
        batch = youtube_get("/playlistItems", params, user_id, account_id)
        for item in batch.get("items", []):
            snippet = item.get("snippet") or {}
            video_id = (item.get("contentDetails") or {}).get("videoId") or (snippet.get("resourceId") or {}).get("videoId")
            if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) and snippet.get("title") not in ("Deleted video", "Private video"):
                thumbnails = snippet.get("thumbnails") or {}
                entries.append((video_id, snippet.get("title") or "제목 없음", snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle") or "", (thumbnails.get("medium") or thumbnails.get("default") or {}).get("url") or ""))
        if len(entries) > MAX_TRACKS:
            raise HTTPException(400, "한 번에 가져올 수 있는 영상은 최대 1,000개입니다.")
        page = batch.get("nextPageToken")
        if not page:
            break
    if not entries:
        raise HTTPException(400, "재생할 수 있는 영상이 이 목록에 없습니다.")
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT COUNT(*) FROM tracks WHERE collection_id=?", (collection_id,)).fetchone()[0]
        if count + len(entries) > MAX_TRACKS:
            raise HTTPException(400, "사용자 목록 하나에는 최대 1,000곡을 담을 수 있습니다.")
        source_id = db.execute("INSERT INTO sources(collection_id,playlist_id,title,source_url,account_id) VALUES(?,?,?,?,?)",
            (collection_id, playlist_id, title, f"https://www.youtube.com/playlist?list={playlist_id}", account_id)).lastrowid
        db.executemany("""INSERT INTO tracks(collection_id,source_id,video_id,title,channel_title,thumbnail_url,position)
            VALUES(?,?,?,?,?,?,?)""", [(collection_id, source_id, *entry, count + index) for index, entry in enumerate(entries)])
        db.execute("UPDATE collections SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (collection_id,))
    return collection_detail(user_id, collection_id)


def add_video(user_id: int, collection_id: int, url: str, account_id: int | None = None) -> dict:
    collection_for(user_id, collection_id)
    video_id = video_id_from_url(url)
    data = youtube_get("/videos", {"part": "snippet,status", "id": video_id}, user_id, account_id)
    items = data.get("items") or []
    if not items or items[0].get("status", {}).get("embeddable") is False:
        raise HTTPException(400, "이 영상은 웹사이트에서 재생할 수 없습니다.")
    snippet = items[0]["snippet"]
    thumbs = snippet.get("thumbnails") or {}
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        count = db.execute("SELECT COUNT(*) FROM tracks WHERE collection_id=?", (collection_id,)).fetchone()[0]
        if count >= MAX_TRACKS:
            raise HTTPException(400, "사용자 목록 하나에는 최대 1,000곡을 담을 수 있습니다.")
        db.execute("""INSERT INTO tracks(collection_id,video_id,title,channel_title,thumbnail_url,position)
            VALUES(?,?,?,?,?,?)""", (collection_id, video_id, snippet.get("title") or "제목 없음",
            snippet.get("channelTitle") or "", (thumbs.get("medium") or thumbs.get("default") or {}).get("url") or "", count))
        db.execute("UPDATE collections SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (collection_id,))
    return collection_detail(user_id, collection_id)


def owned_playlists(user_id: int, account_id: int) -> list[dict]:
    result = []
    page = None
    while True:
        params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = youtube_get("/playlists", params, user_id, account_id)
        result.extend({"id": item["id"], "title": item["snippet"]["title"], "count": item.get("contentDetails", {}).get("itemCount", 0)} for item in data.get("items", []))
        page = data.get("nextPageToken")
        if not page or len(result) >= 500:
            break
    return result[:500]
