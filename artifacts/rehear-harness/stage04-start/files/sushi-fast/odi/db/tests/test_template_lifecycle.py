import copy
import json
import sqlite3
from pathlib import Path
import pytest
from fastapi import HTTPException
from odi.db import odidb as db
from odi.db import template_service as service


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    path = tmp_path / "odi.db"
    db.init_db(db.BASE_DIR / "schema.sql", path)
    original = db.get_conn
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: original(path))
    monkeypatch.setattr(db, "ensure_report_schema", lambda *a, **k: None)
    db.create_user("u", {})
    monkeypatch.setattr(
        service, "commit_template_files", lambda user, draft: (copy.deepcopy(draft), {})
    )
    return path


def draft(title="Original"):
    return {
        "type": "presentation",
        "environment": {"title": title, "duration_minutes": 2},
        "files": {},
        "audience": {},
    }


def test_changed_execution_preserves_id_and_baseline(isolated):
    saved = service.save_baseline("u", draft(), new_id="original")
    changed = {**saved["template"], "environment": {"title": "Only this run"}}
    result = service.prepare("u", changed, "original", "request", 30)
    assert result["template"]["template_id"] == "original"
    assert (
        result["pre_session"]["template_snapshot"]["environment"]["title"]
        == "Only this run"
    )
    assert db.get_template("original")["template"]["environment"]["title"] == "Original"
    assert db.get_template("original")["use_count"] == 1
    again = service.prepare("u", changed, "original", "request", 30)
    assert again["pin_code"] == result["pin_code"]
    assert db.get_template("original")["use_count"] == 1
    with pytest.raises(HTTPException) as exc:
        service.prepare("u", draft("different"), "original", "request", 30)
    assert exc.value.status_code == 409


def test_baseline_save_does_not_change_running_or_past_report(isolated):
    saved = service.save_baseline("u", draft(), new_id="original")
    first = service.prepare("u", saved["template"], "original", "first", 30)
    db.claim_pre_session(first["pin_code"])
    service.save_baseline("u", draft("New default"), "original", 1)
    session_id = db.finish_linked_pre_session(
        pin_code=first["pin_code"],
        user_id="u",
        template_id="original",
        feedback={"score": {"overall_score": 0}},
    )
    assert db.get_session(session_id)["template"]["environment"]["title"] == "Original"
    assert db.get_template("original")["version"] == 2
    assert db.get_session(session_id)["feedback"]["score"]["overall_score"] == 0
    with pytest.raises(HTTPException) as exc:
        service.save_baseline("u", draft("stale"), "original", 1)
    assert exc.value.status_code == 409


def test_new_environment_id_and_cross_owner(isolated):
    result = service.prepare("u", draft(), None, "new", 30)
    again = service.prepare("u", draft(), None, "new", 30)
    assert result["pin_code"] == again["pin_code"]
    assert len(db.list_templates_by_owner("u")) == 1
    db.create_user("other", {})
    with pytest.raises(HTTPException):
        service.prepare(
            "other", draft(), result["template"]["template_id"], "foreign", 30
        )


def test_history_paginates_beyond_200(isolated):
    for _ in range(205):
        db.create_session_with_snapshot(
            "u", draft(), feedback={"score": {"overall_score": 80}}
        )
    first = db.list_sessions_by_user("u", limit=200)
    last = db.list_sessions_by_user("u", limit=200, offset=200)
    assert len(first) == 200 and len(last) == 5
    assert len({r["session_id"] for r in first + last}) == 205


def test_saved_templates_do_not_expire(isolated):
    service.save_baseline("u", draft(), new_id="saved")
    with db.get_conn() as conn:
        conn.execute("UPDATE templates SET created_at='2020-01-01'")
    assert db.delete_expired_unlinked_templates("u", []) == []
    assert db.get_template("saved") is not None


def test_additive_migration_backfills_snapshot(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            "CREATE TABLE users(user_id TEXT PRIMARY KEY,auth_id TEXT,recent_template TEXT,config TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE templates(template_id TEXT PRIMARY KEY,owner_id TEXT,template TEXT,created_at TEXT,updated_at TEXT); CREATE TABLE pre_sessions(pin_code TEXT PRIMARY KEY,template_id TEXT,session_id TEXT,state TEXT,expires_at TEXT,created_at TEXT);"
        )
        conn.execute(
            "INSERT INTO templates(template_id,owner_id,template) VALUES(?,?,?)",
            ("t", "u", json.dumps(draft())),
        )
        conn.execute(
            "INSERT INTO pre_sessions(pin_code,template_id) VALUES('1234','t')"
        )
    db.init_db(db.BASE_DIR / "schema.sql", path)
    db.init_db(db.BASE_DIR / "schema.sql", path)
    with db.get_conn(path) as conn:
        assert (
            json.loads(
                conn.execute("SELECT template_snapshot FROM pre_sessions").fetchone()[0]
            )
            == draft()
        )
        assert conn.execute("SELECT version FROM templates").fetchone()[0] == 1


def test_create_save_retry_is_idempotent_and_changed_payload_conflicts(isolated):
    first = service.save_baseline("u", draft(), new_id="new-save")
    assert (
        service.save_baseline("u", draft(), new_id="new-save")["template_id"]
        == first["template_id"]
    )
    assert len(db.list_templates_by_owner("u")) == 1
    with pytest.raises(HTTPException) as exc:
        service.save_baseline("u", draft("different"), new_id="new-save")
    assert exc.value.status_code == 409


def test_finish_same_pin_twice_preserves_first_report(isolated):
    pre = service.prepare("u", draft(), None, "finish-once", 30)
    pin = pre["pin_code"]
    tid = pre["pre_session"]["template_id"]
    db.claim_pre_session(pin)
    first = db.finish_linked_pre_session(
        pin_code=pin,
        user_id="u",
        template_id=tid,
        feedback={"score": {"overall_score": 80}},
    )
    second = db.finish_linked_pre_session(
        pin_code=pin,
        user_id="u",
        template_id=tid,
        feedback={"score": {"overall_score": 0}},
    )
    assert first == second
    assert db.get_session(first)["feedback"]["score"]["overall_score"] == 80


def test_attachment_copy_is_retryable_and_script_sections_preserved(
    tmp_path, monkeypatch
):
    from odi.files import service as files

    upload = tmp_path / "upload.pdf"
    upload.write_bytes(b"uploaded-file")
    monkeypatch.setattr(files, "ensure_user_temp_path", lambda *args: upload)
    monkeypatch.setattr(files, "as_storage_path", str)
    destinations = [tmp_path / "first", tmp_path / "retry"]
    for dest in destinations:
        dest.mkdir()
        result = files.move_temp_file_to_bundle(
            "u", {"storage_path": "upload.pdf"}, dest, "slide.pdf"
        )
        assert Path(result["storage_path"]).read_bytes() == b"uploaded-file"
    assert upload.exists()
    sections = [{"slide": 1, "text": "원문"}]
    assert (
        files.normalize_files({"script_sections": sections})["script_sections"]
        == sections
    )


def test_saved_and_historical_assets_are_protected(isolated):
    saved = service.save_baseline("u", draft(), new_id="protected")
    from odi.files.service import as_storage_path

    path = as_storage_path(
        service.STORAGE_ROOT / "users/u/bundles/saved/files/script.txt"
    )
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE templates SET template=? WHERE template_id=?",
            (
                json.dumps({**draft(), "files": {"script": {"storage_path": path}}}),
                "protected",
            ),
        )
    assert service.path_from_storage_path(path) in service.protected_storage_paths()


def test_legacy_file_paths_and_explicit_script_clear(tmp_path, monkeypatch):
    from odi.files import service as files

    normalized = files.normalize_files(
        {"slide_path": "odi/files/storage/users/u/old.pdf"}
    )
    assert normalized["slide"]["storage_path"].endswith("/old.pdf")
    monkeypatch.setattr(files, "STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(files, "as_storage_path", str)
    snapshot, _ = files.commit_template_files(
        "u",
        {
            "files": {
                "script": {"storage_path": "old-script.txt", "status": "committed"},
                "script_content": "",
            }
        },
    )
    assert snapshot["files"]["script"] is None
