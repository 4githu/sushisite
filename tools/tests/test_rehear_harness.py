"""Harness tests only. Run: python3 -m unittest discover -s tools/tests -v"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "rehear_harness.py"
spec = importlib.util.spec_from_file_location("rehear_harness_under_test", SCRIPT)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.put("sushi-app/src/app.svelte", "unchanged\n")
        self.put("sushi-fast/odi/EVC/clip_pool.json", "{}")
        self.put("sushi-fast/odi/EVC/schema.py", "def clamp(x):\n    return x\n")
        self.put("sushi-fast/odi/EVC/state_engine.py", "\n".join(
            f"def {name}(x):\n    return x\n" for name in h.FROZEN_FUNCTIONS["sushi-fast/odi/EVC/state_engine.py"]))
        self.put("sushi-fast/odi/EVC/router.py", '@router.post("/update")\nasync def update():\n    pass\n')
        self.put("sushi-fast/odi/EVC/tests/test_existing.py", "def test_existing():\n    assert True\n")

    def put(self, name, body):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def main(self, command):
        with contextlib.redirect_stdout(io.StringIO()):
            return h.main(["--repo", str(self.repo), command])

    def test_baseline_cannot_be_overwritten(self):
        self.assertEqual(self.main("capture"), 0)
        baseline = self.repo / h.RUN_DIR / "baseline.json"
        original = baseline.read_bytes()
        self.assertEqual(self.main("capture"), 2)
        self.assertEqual(baseline.read_bytes(), original)

    def test_unchanged_guard_and_backend_addition_pass(self):
        self.assertEqual(self.main("capture"), 0)
        self.put("sushi-fast/odi/EVC/audience_config.py", "def count():\n    return 12\n")
        self.assertEqual(self.main("guard"), 0)

    def test_frontend_change_add_delete_and_unity_change_are_detected(self):
        before = h.snapshot(self.repo)
        self.put("sushi-app/src/app.svelte", "changed")
        self.put("sushi-app/src/new.svelte", "new")
        self.put("Unity/Assets/Actor.cs", "class Actor {}")
        errors = h.compare_baseline(before, h.snapshot(self.repo))
        self.assertTrue(any("CHANGED" in error for error in errors))
        self.assertEqual(sum("ADDED" in error for error in errors), 2)
        (self.repo / "sushi-app/src/app.svelte").unlink()
        self.assertTrue(any("REMOVED" in error for error in h.compare_baseline(before, h.snapshot(self.repo))))

    def test_calculation_and_route_drift_are_detected(self):
        before = h.snapshot(self.repo)
        self.put("sushi-fast/odi/EVC/schema.py", "def clamp(x):\n    return 0\n")
        self.put("sushi-fast/odi/EVC/router.py", '@router.post("/changed")\nasync def update():\n    pass\n')
        errors = h.compare_baseline(before, h.snapshot(self.repo))
        self.assertTrue(any("frozen_functions" in error for error in errors))
        self.assertIn("EVC route set changed", errors)

    def test_runtime_tool_and_core_service_imports_are_detected(self):
        self.put("sushi-fast/odi/EVC/new.py", "from tools.rehear_cli import main\n")
        self.put("sushi-fast/rehear_ai/bad.py", "from odi.EVC import schema\n")
        self.assertEqual(len(h.import_violations(self.repo)), 2)

    def test_missing_stage_tests_are_not_success(self):
        with self.assertRaisesRegex(ValueError, "not implemented"):
            h.stage_test_paths(self.repo, "audience")
        self.assertEqual(len(h.stage_test_paths(self.repo, "original")), 1)

    def test_incomplete_baseline_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete baseline"):
            h.compare_baseline({"format": 1}, h.snapshot(self.repo))

    def test_symlink_is_not_followed(self):
        (self.repo / "sushi-app/src/link").symlink_to(self.repo / "sushi-fast", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            h.snapshot(self.repo)

    def test_offline_plugin_blocks_socket_calls(self):
        plugin = self.put("plugin.py", h.OFFLINE_PLUGIN)
        probe = "import runpy,socket;runpy.run_path(__import__('sys').argv[1]);socket.create_connection(('127.0.0.1',9))"
        run = subprocess.run([sys.executable, "-c", probe, str(plugin)], capture_output=True, text=True)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("socket connection blocked", run.stderr)

    def test_cli_missing_baseline_is_nonzero(self):
        self.assertEqual(self.main("guard"), 2)

    def run_mock_pytest(self, stats, process_code=0):
        def fake_run(command, **kwargs):
            Path(kwargs["env"]["REHEAR_HARNESS_TEST_REPORT"]).write_text(json.dumps(stats))
            self.assertEqual(kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")
            self.assertIn("rehear_harness_offline_plugin", command)
            return subprocess.CompletedProcess(command, process_code)
        with patch.object(h, "dependency_status", return_value={"pytest": {"available": True}}), patch.object(h.subprocess, "run", side_effect=fake_run):
            return h.run_tests(self.repo, "original")

    def test_runner_distinguishes_pass_skip_and_failure(self):
        complete = {"collected": 1, "passed": 1}
        code, result = self.run_mock_pytest(complete)
        self.assertEqual((code, result["status"]), (0, "PASS_SELECTED_TESTS"))
        code, result = self.run_mock_pytest({"collected": 1, "skipped": 1})
        self.assertEqual((code, result["status"]), (2, "INCOMPLETE"))
        code, result = self.run_mock_pytest({"collected": 1, "failed": 1}, 1)
        self.assertEqual((code, result["status"]), (1, "FAIL"))

    def test_runner_does_not_pass_without_collection_report(self):
        code, result = self.run_mock_pytest({})
        self.assertEqual((code, result["status"]), (2, "INCOMPLETE"))
        code, result = self.run_mock_pytest({"collected": 2, "passed": 1})
        self.assertEqual((code, result["status"]), (2, "INCOMPLETE"))


if __name__ == "__main__":
    unittest.main()
