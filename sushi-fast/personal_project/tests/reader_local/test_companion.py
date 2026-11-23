import json
import unittest

from personal_project.reader_local import Companion, MAX_BODY_BYTES


class FakeProvider:
    def __init__(self, translations=None, error=None):
        self.translations = translations
        self.error = error
        self.calls = []

    def translate(self, segments, target_language):
        self.calls.append((segments, target_language))
        if self.error is not None:
            raise self.error
        return self.translations


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.now = [100.0]
        self.provider = FakeProvider([
            {"id": "b", "text": "Fake B"},
            {"id": "a", "text": "Fake A"},
        ])
        self.companion = Companion(
            self.provider,
            browser_origin="https://reader.example.test",
            pairing_code="synthetic-pair-code",
            clock=lambda: self.now[0],
            token_factory=lambda: "synthetic-csrf-token",
        )
        self.origin = "https://reader.example.test"
        self.host = "127.0.0.1:43123"

    def request(self, path, body=b"", *, origin=None, pairing=None, host=None):
        headers = {}
        if pairing is not None:
            headers["X-Reader-Pairing"] = pairing
        return self.companion.handle(
            "POST" if path != "/health" else "GET",
            path,
            origin=self.origin if origin is None else origin,
            host=self.host if host is None else host,
            headers=headers,
            body=body,
        )

    def pair(self, code="synthetic-pair-code", *, origin=None):
        return self.request(
            "/pair",
            json.dumps({"pairing_code": code}).encode(),
            origin=origin,
        )

    def test_health_is_minimal_and_reports_loopback_only(self):
        response = self.request("/health")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, {"status": "ok", "scope": "loopback"})

    def test_pairing_code_expires_before_it_is_used(self):
        self.now[0] += 301
        response = self.pair()
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["error"], "pairing_unavailable")

    def test_wrong_origin_is_rejected_even_with_pairing_code(self):
        response = self.pair(origin="https://attacker.example.test")
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["error"], "origin_not_allowed")

    def test_wrong_origin_cannot_translate_after_successful_pairing(self):
        self.pair()
        response = self.request(
            "/translate",
            json.dumps({"segments": [{"id": "a", "text": "Synthetic text"}]}).encode(),
            origin="https://attacker.example.test",
            pairing="synthetic-csrf-token",
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(self.provider.calls, [])

    def test_missing_pairing_is_rejected(self):
        response = self.request(
            "/translate",
            json.dumps({"segments": [{"id": "a", "text": "Synthetic text"}]}).encode(),
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["error"], "pairing_required")

    def test_pairing_expires(self):
        self.assertEqual(self.pair().status, 200)
        self.now[0] += 301
        response = self.request(
            "/translate",
            json.dumps({"segments": [{"id": "a", "text": "Synthetic text"}]}).encode(),
            pairing="synthetic-csrf-token",
        )
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body["error"], "pairing_expired")

    def test_pairing_code_is_one_time_and_csrf_token_is_not_reissued(self):
        first = self.pair()
        second = self.pair()
        self.assertEqual(first.status, 200)
        self.assertEqual(second.status, 403)
        self.assertEqual(second.body["error"], "pairing_unavailable")

    def test_oversized_input_is_rejected_before_provider_call(self):
        response = self.request("/translate", b"x" * (MAX_BODY_BYTES + 1), pairing="synthetic-csrf-token")
        self.assertEqual(response.status, 413)
        self.assertEqual(self.provider.calls, [])

    def test_segment_ids_are_strict_and_unique(self):
        self.pair()
        for bad_id in ("", "contains space", "line\nbreak", "x" * 129):
            payload = {"segments": [{"id": bad_id, "text": "Synthetic text"}]}
            response = self.request(
                "/translate", json.dumps(payload).encode(), pairing="synthetic-csrf-token"
            )
            self.assertEqual(response.status, 400)
        duplicate = {"segments": [
            {"id": "same", "text": "Synthetic one"},
            {"id": "same", "text": "Synthetic two"},
        ]}
        response = self.request(
            "/translate", json.dumps(duplicate).encode(), pairing="synthetic-csrf-token"
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(response.body["error"], "duplicate_segment_id")
        self.assertEqual(self.provider.calls, [])

    def test_provider_result_is_returned_in_input_order(self):
        self.assertEqual(self.pair().status, 200)
        payload = {"target_language": "Korean", "segments": [
            {"id": "a", "text": "Synthetic A"},
            {"id": "b", "text": "Synthetic B"},
        ]}
        response = self.request(
            "/translate", json.dumps(payload).encode(), pairing="synthetic-csrf-token"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, {"translations": [
            {"id": "a", "text": "Fake A"},
            {"id": "b", "text": "Fake B"},
        ]})

    def test_unknown_provider_ids_are_rejected(self):
        self.provider.translations = [
            {"id": "extra", "text": "Fake"},
            {"id": "a", "text": "Fake A"},
        ]
        self.pair()
        payload = {"segments": [
            {"id": "a", "text": "Synthetic A"},
            {"id": "b", "text": "Synthetic B"},
        ]}
        response = self.request(
            "/translate", json.dumps(payload).encode(), pairing="synthetic-csrf-token"
        )
        self.assertEqual(response.status, 502)
        self.assertEqual(response.body["error"], "translation_failed")

    def test_provider_failures_are_sanitized(self):
        source = "SYNTHETIC-PRIVATE-SOURCE"
        self.provider.error = RuntimeError(source)
        self.pair()
        payload = {"segments": [{"id": "a", "text": source}]}
        response = self.request(
            "/translate", json.dumps(payload).encode(), pairing="synthetic-csrf-token"
        )
        self.assertEqual(response.status, 502)
        self.assertNotIn(source, json.dumps(response.body))
        self.assertEqual(response.body, {"error": "translation_failed"})


if __name__ == "__main__":
    unittest.main()
