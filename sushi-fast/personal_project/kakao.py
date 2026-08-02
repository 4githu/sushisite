import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen

from fastapi import HTTPException

from .db import connection

KAKAO_AUTH = "https://kauth.kakao.com"
KAKAO_API = "https://kapi.kakao.com"


def _now():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat()


def _request(url, *, data=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    encoded = urlencode(data).encode() if data is not None else None
    request = UrlRequest(url, data=encoded, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise HTTPException(
            status_code=400,
            detail={"code": "kakao_api_error", "message": f"카카오 API 오류: {detail}"},
        ) from exc


def _config(request):
    key = os.getenv("KAKAO_REST_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, detail={"code": "kakao_key_missing", "message": "KAKAO_REST_API_KEY가 설정되지 않았습니다."})
    if len(key) != 32 or any(character not in "0123456789abcdefABCDEF" for character in key):
        raise HTTPException(
            503,
            detail={
                "code": "kakao_rest_key_invalid",
                "message": "KAKAO_REST_API_KEY에는 앱 > 플랫폼 키에 표시되는 32자리 REST API 키를 넣어주세요. 현재 값은 다른 종류의 키입니다.",
            },
        )
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI", "").strip() or str(request.url_for("kakao_callback"))
    return key, redirect_uri


def create_connect_url(user_id, request, return_to):
    key, redirect_uri = _config(request)
    state = secrets.token_urlsafe(32)
    expires = _now() + timedelta(minutes=10)
    safe_return = return_to if return_to.startswith("/") and not return_to.startswith("//") else "/personal-project/aura"
    with connection() as conn:
        conn.execute("DELETE FROM personal_kakao_oauth_states WHERE expires_at < ?", (_iso(_now()),))
        conn.execute(
            "INSERT INTO personal_kakao_oauth_states(state,user_id,return_to,expires_at) VALUES(?,?,?,?)",
            (state, user_id, safe_return, _iso(expires)),
        )
        conn.commit()
    query = urlencode({"client_id": key, "redirect_uri": redirect_uri, "response_type": "code", "scope": "talk_message", "state": state})
    return {"url": f"{KAKAO_AUTH}/oauth/authorize?{query}", "redirectUri": redirect_uri}


def finish_connect(code, state, request):
    key, redirect_uri = _config(request)
    with connection() as conn:
        row = conn.execute("SELECT * FROM personal_kakao_oauth_states WHERE state=?", (state,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) < _now():
            raise HTTPException(400, "만료되었거나 잘못된 카카오 연결 요청입니다.")
        conn.execute("DELETE FROM personal_kakao_oauth_states WHERE state=?", (state,))
        conn.commit()
    data = {"grant_type": "authorization_code", "client_id": key, "redirect_uri": redirect_uri, "code": code}
    secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
    if secret:
        data["client_secret"] = secret
    tokens = _request(f"{KAKAO_AUTH}/oauth/token", data=data)
    profile = _request(f"{KAKAO_API}/v2/user/me", token=tokens["access_token"])
    access_exp = _now() + timedelta(seconds=int(tokens.get("expires_in", 0)))
    refresh_exp = _now() + timedelta(seconds=int(tokens.get("refresh_token_expires_in", 0)))
    with connection() as conn:
        conn.execute(
            """INSERT INTO personal_kakao_connections
               (user_id,kakao_user_id,access_token,refresh_token,access_expires_at,refresh_expires_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
               kakao_user_id=excluded.kakao_user_id, access_token=excluded.access_token,
               refresh_token=excluded.refresh_token, access_expires_at=excluded.access_expires_at,
               refresh_expires_at=excluded.refresh_expires_at, updated_at=CURRENT_TIMESTAMP""",
            (row["user_id"], str(profile.get("id", "")), tokens["access_token"], tokens.get("refresh_token"), _iso(access_exp), _iso(refresh_exp)),
        )
        conn.commit()
    return row["return_to"]


def _access_token(user_id, request):
    key, _ = _config(request)
    with connection() as conn:
        row = conn.execute("SELECT * FROM personal_kakao_connections WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(409, detail={"code": "kakao_not_connected", "message": "먼저 카카오톡 계정을 연결해주세요."})
    if datetime.fromisoformat(row["access_expires_at"]) > _now() + timedelta(minutes=2):
        return row["access_token"]
    data = {"grant_type": "refresh_token", "client_id": key, "refresh_token": row["refresh_token"]}
    secret = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
    if secret:
        data["client_secret"] = secret
    tokens = _request(f"{KAKAO_AUTH}/oauth/token", data=data)
    access_exp = _now() + timedelta(seconds=int(tokens.get("expires_in", 0)))
    with connection() as conn:
        conn.execute(
            "UPDATE personal_kakao_connections SET access_token=?, refresh_token=COALESCE(?,refresh_token), access_expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (tokens["access_token"], tokens.get("refresh_token"), _iso(access_exp), user_id),
        )
        conn.commit()
    return tokens["access_token"]


def status(user_id):
    with connection() as conn:
        row = conn.execute("SELECT kakao_user_id FROM personal_kakao_connections WHERE user_id=?", (user_id,)).fetchone()
    return {"connected": bool(row), "kakaoUserId": row["kakao_user_id"] if row else None}


def send_me(user_id, request, title, description, link_url, image_urls=None):
    token = _access_token(user_id, request)
    images = image_urls or []
    if not images:
        templates = [{"object_type": "text", "text": f"{title}\n\n{description}".strip(), "link": {"web_url": link_url, "mobile_web_url": link_url}, "button_title": "리포트 열기"}]
    else:
        templates = []
        total = len(images)
        for index, image_url in enumerate(images):
            templates.append({
                "object_type": "feed",
                "content": {
                    "title": f"{title} ({index + 1}/{total})" if total > 1 else title,
                    "description": description if index == 0 else f"리포트 {index + 1}페이지",
                    "image_url": image_url,
                    "image_width": 1240,
                    "image_height": 1754,
                    "link": {"web_url": link_url, "mobile_web_url": link_url},
                },
                "button_title": "리포트 열기",
            })
    sent = 0
    for template in templates:
        result = _request(f"{KAKAO_API}/v2/api/talk/memo/default/send", token=token, data={"template_object": json.dumps(template, ensure_ascii=False)})
        if result.get("result_code") == 0:
            sent += 1
    return {"sent": sent == len(templates), "sentCount": sent, "totalCount": len(templates)}
