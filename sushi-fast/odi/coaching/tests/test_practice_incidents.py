import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from odi.coaching import router as routes
from odi.db import odidb as db


@pytest.fixture
def incident_api(tmp_path, monkeypatch):
    path = tmp_path / "practice-incidents.db"
    db.init_db(db.BASE_DIR / "schema.sql", path)
    original = db.get_conn
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: original(path))
    monkeypatch.setattr(db, "ensure_report_schema", lambda *a, **k: None)
    db.create_user("owner", {}, db_path=path)
    db.create_user("other", {}, db_path=path)
    actor = {"id": "owner"}
    monkeypatch.setattr(routes, "get_user_id_from_jwt", lambda request: actor["id"])
    app = FastAPI()
    app.include_router(routes.router, prefix="/odi")
    return TestClient(app), actor, path


def add_stored_source(path, *, user_id="owner", step=3, expires_at=None):
    evc_session_id = str(uuid4())
    source_session_id = f"session-{user_id}"
    with db.get_conn(path) as conn:
        conn.execute(
            """INSERT INTO sessions(session_id,user_id,template_id,template,feedback,state,started_at,ended_at)
               VALUES(?,?,NULL,?,?,'completed','2026-01-01T00:00:00Z','2026-01-01T00:10:00Z')""",
            (source_session_id, user_id, json.dumps({"title": "synthetic"}), "{}"),
        )
        conn.execute(
            """INSERT INTO presentation_segments(evc_session_id,step,owner_user_id,pre_session_pin,analysis_origin,segment_json,expires_at)
               VALUES(?,?,?,NULL,?,?,?)""",
            (evc_session_id, step, user_id, "evc_live",
             json.dumps({"step": step, "transcript": "SYNTHETIC_ONLY_TRANSCRIPT", "context": {"slide": "SYNTHETIC_ONLY_SLIDE"}}),
             expires_at),
        )
        conn.execute(
            """INSERT INTO presentation_reports(report_id,evc_session_id,odi_session_id,version,feedback_json,generator,generated_at)
               VALUES(?,?,?,?,?,?,?)""",
            (f"report-{user_id}", evc_session_id, source_session_id, "v2", "{}", "synthetic-test", "2026-01-01T00:10:00Z"),
        )
    return source_session_id, evc_session_id, step


def test_incident_creation_references_owned_stored_segment_without_copying_source(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)

    response = client.post(
        "/odi/coaching/practice/incidents",
        json={
            "source_session_id": source_session_id,
            "source_step": step,
            "idempotency_key": "synthetic-request-1",
        },
    )

    assert response.status_code == 201, response.text
    incident_id = response.json()["incident_id"]
    assert response.json()["source_status"] == "available"
    detail = client.get(f"/odi/coaching/practice/incidents/{incident_id}")
    assert detail.status_code == 200
    assert detail.json()["source"] == {
        "source_session_id": source_session_id,
        "evc_session_id": evc_session_id,
        "source_step": step,
    }
    with db.get_conn(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pre_sessions").fetchone()[0] == 0
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(practice_incidents)")}
        incident_row = dict(conn.execute("SELECT * FROM practice_incidents WHERE incident_id=?", (incident_id,)).fetchone())
    assert not columns.intersection({"transcript", "slide_text", "segment_json", "snapshot_json"})
    assert "SYNTHETIC_ONLY_TRANSCRIPT" not in json.dumps(incident_row)


def test_incident_retry_is_idempotent_and_conflicting_key_is_rejected(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    payload = {"source_session_id": source_session_id, "source_step": step,
               "idempotency_key": "same-key"}
    first = client.post("/odi/coaching/practice/incidents", json=payload)
    retry = client.post("/odi/coaching/practice/incidents", json=payload)
    assert first.status_code == 201
    assert retry.status_code == 200
    assert retry.json()["incident_id"] == first.json()["incident_id"]
    conflict = client.post("/odi/coaching/practice/incidents", json={**payload, "source_step": step + 1})
    assert conflict.status_code == 409
    with db.get_conn(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_incidents").fetchone()[0] == 1


def test_incident_rejects_foreign_owner_bad_report_link_and_expired_source(incident_api):
    client, actor, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    payload = {"source_session_id": source_session_id, "source_step": step,
               "idempotency_key": "ownership-check"}
    actor["id"] = "other"
    assert client.post("/odi/coaching/practice/incidents", json=payload).status_code == 404
    actor["id"] = "owner"
    with db.get_conn(path) as conn:
        conn.execute("UPDATE presentation_segments SET owner_user_id='other' WHERE evc_session_id=?", (evc_session_id,))
    assert client.post("/odi/coaching/practice/incidents", json=payload).status_code == 404
    with db.get_conn(path) as conn:
        conn.execute("UPDATE presentation_segments SET owner_user_id='owner',expires_at='2000-01-01T00:00:00Z' WHERE evc_session_id=?", (evc_session_id,))
    assert client.post("/odi/coaching/practice/incidents", json=payload).status_code == 404
    other_session_id, _, _ = add_stored_source(path, user_id="other")
    with db.get_conn(path) as conn:
        conn.execute("UPDATE presentation_segments SET expires_at=NULL WHERE evc_session_id=?", (evc_session_id,))
        conn.execute("UPDATE presentation_reports SET odi_session_id=? WHERE evc_session_id=?", (other_session_id, evc_session_id))
    assert client.post("/odi/coaching/practice/incidents", json=payload).status_code == 404
    with db.get_conn(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM practice_incidents").fetchone()[0] == 0


def test_deleted_source_marks_incident_unavailable_without_deleting_existing_run(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    incident = client.post("/odi/coaching/practice/incidents", json={
        "source_session_id": source_session_id,
        "source_step": step, "idempotency_key": "delete-source",
    })
    run = client.post("/odi/coaching/practice/runs", json={
        "metric_id": "speech_rate", "source_session_id": source_session_id, "origin": "manual",
    })
    assert incident.status_code == 201
    assert run.status_code == 200
    with db.get_conn(path) as conn:
        conn.execute("DELETE FROM presentation_segments WHERE evc_session_id=? AND step=?", (evc_session_id, step))
    detail = client.get(f"/odi/coaching/practice/incidents/{incident.json()['incident_id']}")
    assert detail.status_code == 200
    assert detail.json()["source_status"] == "unavailable"
    assert detail.json()["unavailable_reason"] == "source_segment_missing"
    assert client.get(f"/odi/coaching/practice/runs/{run.json()['run_id']}").status_code == 200


def test_incident_details_are_owner_scoped(incident_api):
    client, actor, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    incident = client.post("/odi/coaching/practice/incidents", json={
        "source_session_id": source_session_id,
        "source_step": step, "idempotency_key": "detail-owner",
    })
    actor["id"] = "other"
    assert client.get(f"/odi/coaching/practice/incidents/{incident.json()['incident_id']}").status_code == 404


def test_client_cannot_supply_evc_id_for_server_side_source_resolution(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    response = client.post("/odi/coaching/practice/incidents", json={
        "source_session_id": source_session_id, "source_step": step,
        "idempotency_key": "no-client-evc", "evc_session_id": evc_session_id,
    })
    assert response.status_code == 422


def test_unknown_source_origin_is_not_upgraded_by_client_claim(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    with db.get_conn(path) as conn:
        row = conn.execute(
            "SELECT segment_json FROM presentation_segments WHERE evc_session_id=? AND step=?",
            (evc_session_id, step),
        ).fetchone()
        segment = json.loads(row["segment_json"])
        segment["analysis_origin"] = "unknown"
        conn.execute(
            "UPDATE presentation_segments SET analysis_origin=NULL,segment_json=? WHERE evc_session_id=? AND step=?",
            (json.dumps(segment), evc_session_id, step),
        )

    response = client.post("/odi/coaching/practice/incidents", json={
        "source_session_id": source_session_id,
        "source_step": step, "idempotency_key": "unknown-origin",
        "analysis_origin": "evc_live",
    })
    assert response.status_code == 422


def test_incident_schema_initializer_is_idempotent_and_preserves_synthetic_rows(incident_api):
    client, _, path = incident_api
    source_session_id, evc_session_id, step = add_stored_source(path)
    incident = client.post("/odi/coaching/practice/incidents", json={
        "source_session_id": source_session_id,
        "source_step": step, "idempotency_key": "initializer-check",
    })
    assert incident.status_code == 201

    def counts():
        with db.get_conn(path) as conn:
            names = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )]
            return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}

    before = counts()
    db.init_db(db.BASE_DIR / "schema.sql", path)
    db.init_db(db.BASE_DIR / "schema.sql", path)
    assert counts() == before
    with db.get_conn(path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_legacy_segments_migrate_with_unknown_origin_and_keep_source_row(tmp_path):
    path = tmp_path / "legacy-segments.db"
    with db.get_conn(path) as conn:
        conn.execute("""CREATE TABLE presentation_segments (
            evc_session_id TEXT NOT NULL, step INTEGER NOT NULL, owner_user_id TEXT,
            pre_session_pin TEXT, segment_json TEXT NOT NULL, expires_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY(evc_session_id,step))""")
        conn.execute(
            "INSERT INTO presentation_segments(evc_session_id,step,segment_json) VALUES('legacy-evc',1,'{}')"
        )

    db.init_db(db.BASE_DIR / "schema.sql", path)

    with db.get_conn(path) as conn:
        row = conn.execute(
            "SELECT segment_json,analysis_origin FROM presentation_segments WHERE evc_session_id='legacy-evc' AND step=1"
        ).fetchone()
        assert dict(row) == {"segment_json": "{}", "analysis_origin": None}

