import json

from personal_project.make_report_test.gemini_report_service import GeminiReportService


def _input_from_request(text: str) -> dict:
    marker = "[아우라 입력 JSON]\n"
    return json.loads(text.split(marker, 1)[1])


def test_request_projects_duplicate_document_metadata_and_target_pii():
    blocks = [
        {
            "id": "block-test",
            "type": "paragraph",
            "depth": 0,
            "children": [
                {"type": "text", "text": "합성 학습문장", "highlightColor": "#fef08a"}
            ],
        },
        {
            "id": "table-test",
            "type": "table",
            "depth": 1,
            "rows": [[{"id": "cell-test", "blocks": [
                {"type": "paragraph", "children": [
                    {"type": "text", "text": "합성 표 내용", "highlightColor": "#fdba74"}
                ]}
            ]}]],
        },
    ]
    report_input = {
        "schemaVersion": "aura.clinic-report-input.v1",
        "target": {
            "targetId": 399,
            "userId": 42,
            "schoolId": 77,
            "schoolName": "SYNTHETIC_SCHOOL_PRIVATE",
            "studentName": "SYNTHETIC_STUDENT_PRIVATE",
            "progressStage": "grade2_semester1",
            "roundNumbers": [1, 2],
            "startTime": "2026-11-09T09:00:00+09:00",
            "endTime": "2026-11-09T10:00:00+09:00",
        },
        "editorDocument": {
            "version": 1,
            "schemaVersion": 2,
            "documentId": "SYNTHETIC_DOCUMENT_PRIVATE",
            "createdAt": "SYNTHETIC_CREATED_AT_PRIVATE",
            "updatedAt": "SYNTHETIC_UPDATED_AT_PRIVATE",
            "blocks": blocks,
            "richContent": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": "합성 학습문장", "marks": [
                        {"type": "highlight", "attrs": {"color": "#fef08a"}}
                    ]}
                ]}],
            },
        },
        "options": {
            "scoreMode": "auto",
            "requestedScoreMode": "auto",
            "scoreFormatSnapshot": {
                "id": 19, "name": "합성 평가", "items": ["개념 이해"],
                "source": "SYNTHETIC_SOURCE_PRIVATE",
            },
            "assessmentItems": [{"name": "개념 이해", "score": 5}],
            "highlightSemantics": {
                "yellow": "fixed", "orange": "unfixed", "peach": "not_reasked"
            },
            "includeQuestionChecks": False,
        },
        "questionChecks": {"SYNTHETIC_QUESTION_PRIVATE": True},
    }
    score_format = {
        "id": 19, "name": "합성 평가", "items": ["개념 이해"],
        "source": "SYNTHETIC_SOURCE_PRIVATE",
    }

    text = GeminiReportService._request_text(report_input, "auto", score_format)
    sent = _input_from_request(text)

    assert sent["editorDocument"]["blocks"] == blocks
    assert "richContent" not in sent["editorDocument"]
    assert sent["target"] == {
        "progressStage": "grade2_semester1", "roundNumbers": [1, 2]
    }
    assert sent["options"]["highlightSemantics"] == report_input["options"]["highlightSemantics"]
    assert sent["options"]["scoreFormatSnapshot"] == {
        "name": "합성 평가", "items": ["개념 이해"]
    }
    assert sent["options"]["assessmentItems"] == [{"name": "개념 이해", "score": 5}]
    assert "questionChecks" not in sent
    assert "SYNTHETIC_STUDENT_PRIVATE" not in text
    assert "SYNTHETIC_SCHOOL_PRIVATE" not in text
    assert "SYNTHETIC_DOCUMENT_PRIVATE" not in text
    assert "SYNTHETIC_SOURCE_PRIVATE" not in text
    assert "2026-11-09T09:00:00+09:00" not in text


def test_request_keeps_rich_document_only_when_blocks_are_empty():
    rich = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "legacy synthetic learning text"}
        ]}],
    }
    report_input = {
        "schemaVersion": "aura.clinic-report-input.v1",
        "target": {"progressStage": "accepted", "roundNumbers": []},
        "editorDocument": {
            "blocks": [], "richContent": rich, "documentId": "REMOVE_ME"
        },
        "options": {"scoreMode": "none", "includeQuestionChecks": False},
    }

    sent = _input_from_request(GeminiReportService._request_text(report_input, "none", None))

    assert sent["editorDocument"] == {"richContent": rich}
    assert "legacy synthetic learning text" in json.dumps(sent, ensure_ascii=False)
    assert "REMOVE_ME" not in json.dumps(sent, ensure_ascii=False)


def test_request_preserves_question_checks_only_when_explicitly_enabled():
    report_input = {
        "schemaVersion": "aura.clinic-report-input.v1",
        "target": {},
        "editorDocument": {"blocks": [], "richContent": None},
        "options": {"scoreMode": "none", "includeQuestionChecks": True},
        "questionChecks": {"synthetic-item": True},
    }

    sent = _input_from_request(GeminiReportService._request_text(report_input, "none", None))

    assert sent["questionChecks"] == {"synthetic-item": True}
