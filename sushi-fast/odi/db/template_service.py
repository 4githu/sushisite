"""Stable template identities and immutable PIN execution snapshots."""

import hashlib
import json
import threading
from fastapi import HTTPException
from odi.db import odidb as db
from odi.files.service import (
    commit_template_files,
    path_from_storage_path,
    STORAGE_ROOT,
    normalize_files,
)

_lock = threading.RLock()


def checked_files(user_id, draft):
    files = normalize_files(draft.get("files"))
    for role, ref in files.items():
        if role == "script" and isinstance(files.get("script_content"), str):
            continue
        if not isinstance(ref, dict) or not ref.get("storage_path"):
            continue
        path = path_from_storage_path(ref["storage_path"])
        owner_root = (STORAGE_ROOT / "users" / str(user_id)).resolve()
        if owner_root not in path.parents:
            raise HTTPException(403, "현재 사용자의 자료만 사용할 수 있습니다.")
        if not path.is_file():
            raise HTTPException(
                422, "저장한 자료가 만료되었습니다. 자료를 다시 업로드해 주세요."
            )


def save_baseline(user_id, draft, template_id=None, expected_version=None, new_id=None):
    db.ensure_report_schema()
    create_hash = hashlib.sha256(
        json.dumps(draft, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with _lock:
        row = db.get_template(template_id) if template_id else None
        if template_id and (not row or str(row["owner_id"]) != user_id):
            raise HTTPException(404, "템플릿을 찾을 수 없습니다.")
        if row and (expected_version is None or row["version"] != expected_version):
            raise HTTPException(
                409, "다른 화면에서 환경이 변경되었습니다. 다시 불러와 주세요."
            )
        if not template_id and new_id:
            existing = db.get_template(new_id)
            if existing:
                if str(existing["owner_id"]) == user_id:
                    with db.get_conn() as conn:
                        previous = conn.execute(
                            "SELECT create_request_hash FROM templates WHERE template_id=?",
                            (new_id,),
                        ).fetchone()[0]
                    if previous != create_hash:
                        raise HTTPException(
                            409,
                            "저장 요청 내용이 변경되었습니다. 템플릿을 다시 불러와 주세요.",
                        )
                    return existing
                raise HTTPException(409, "이미 사용 중인 환경 ID입니다.")
        checked_files(user_id, draft)
        saved, _ = commit_template_files(user_id, draft)
        if row:
            saved.update(id=template_id, template_id=template_id, owner_id=user_id)
            with db.get_conn() as conn:
                changed = conn.execute(
                    "UPDATE templates SET template=?, version=version+1, updated_at=? WHERE template_id=? AND version=?",
                    (db.json_dumps(saved), db.utc_now(), template_id, expected_version),
                )
                if changed.rowcount != 1:
                    raise HTTPException(
                        409, "환경이 변경되었습니다. 다시 불러와 주세요."
                    )
        else:
            template_id = db.create_template(user_id, saved, new_id)
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE templates SET create_request_hash=? WHERE template_id=?",
                    (create_hash, template_id),
                )
        result = db.get_template(template_id)
        db.update_recent_template(user_id, result["template"])
        return result


def prepare(user_id, draft, template_id, request_id, expires_minutes):
    db.ensure_report_schema()
    key = f"{user_id}:{request_id}" if request_id else None
    fingerprint = hashlib.sha256(
        json.dumps([template_id, draft], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    with _lock:
        if key:
            with db.get_conn() as conn:
                prior = conn.execute(
                    "SELECT pin_code, request_hash FROM pre_sessions WHERE request_key=?",
                    (key,),
                ).fetchone()
            if prior:
                if prior["request_hash"] != fingerprint:
                    raise HTTPException(
                        409, "같은 요청 ID에 다른 환경을 사용할 수 없습니다."
                    )
                return prepared_response(prior["pin_code"])
        baseline = db.get_template(template_id) if template_id else None
        if template_id and (not baseline or str(baseline["owner_id"]) != user_id):
            raise HTTPException(
                404, "원본 템플릿을 찾을 수 없습니다. 새 환경으로 만들어 주세요."
            )
        checked_files(user_id, draft)
        snapshot, _ = commit_template_files(user_id, draft)
        pin = db.generate_unique_pin()
        template_id = template_id or db.make_id("template")
        snapshot.update(
            id=template_id,
            template_id=template_id,
            owner_id=user_id,
            version=baseline["version"] if baseline else 1,
        )
        with db.get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if key:
                prior = conn.execute(
                    "SELECT pin_code,request_hash FROM pre_sessions WHERE request_key=?",
                    (key,),
                ).fetchone()
                if prior:
                    if prior["request_hash"] != fingerprint:
                        raise HTTPException(
                            409, "같은 요청 ID에 다른 환경을 사용할 수 없습니다."
                        )
                    return prepared_response(prior["pin_code"])
            if not baseline:
                conn.execute(
                    "INSERT INTO templates(template_id,owner_id,template) VALUES(?,?,?)",
                    (template_id, user_id, db.json_dumps(snapshot)),
                )
            conn.execute(
                "INSERT INTO pre_sessions(pin_code,template_id,expires_at,template_snapshot,request_key,request_hash) VALUES(?,?,?,?,?,?)",
                (
                    pin,
                    template_id,
                    db.utc_after_minutes(expires_minutes),
                    db.json_dumps(snapshot),
                    key,
                    fingerprint,
                ),
            )
            conn.execute(
                "UPDATE templates SET last_used_at=?, use_count=use_count+1 WHERE template_id=?",
                (db.utc_now(), template_id),
            )
            conn.execute(
                "UPDATE users SET recent_template=? WHERE user_id=?",
                (db.json_dumps(snapshot), user_id),
            )
        return prepared_response(pin)


def prepared_response(pin):
    pre = db.get_pre_session_by_pin(pin)
    snapshot = pre["template_snapshot"]
    return {
        "pin_code": pin,
        "pre_session": pre,
        "template": {"template_id": pre["template_id"], "template": snapshot},
        "file_bundle": {
            "file_bundle_id": snapshot.get("file_bundle_id"),
            "file_bundle_path": snapshot.get("file_bundle_path"),
            "expires_at": snapshot.get("file_bundle_expires_at"),
            "files": snapshot.get("files"),
        },
    }


def protected_storage_paths():
    """Protect saved assets and still-active PINs from temporary bundle cleanup."""
    db.ensure_report_schema()
    with db.get_conn() as conn:
        values = [r[0] for r in conn.execute("SELECT template FROM templates")]
        values += [r[0] for r in conn.execute("SELECT template FROM sessions")]
        values += [
            r[0]
            for r in conn.execute(
                "SELECT template_snapshot FROM pre_sessions WHERE (state='running' OR (state='waiting' AND expires_at>?))",
                (db.utc_now(),),
            )
        ]
    paths = []

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in (
                    "storage_path",
                    "image_manifest_path",
                    "file_bundle_path",
                    "slide_path",
                    "paper_path",
                    "script_path",
                ) and isinstance(item, str):
                    try:
                        paths.append(path_from_storage_path(item))
                    except HTTPException:
                        continue  # Legacy invalid paths must not disable all cleanup.
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for raw in values:
        if raw:
            visit(json.loads(raw))
    return paths
