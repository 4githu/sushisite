#!/usr/bin/env python3
"""Offline developer checks; not a model runner or proof of Unity behavior."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

FORMAT_VERSION = 1
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", ".svelte-kit",
                "__pycache__", ".pytest_cache", "artifacts", "Library", "Temp", "obj"}
UNITY_SUFFIXES = {".cs", ".unity", ".prefab", ".asset", ".asmdef", ".meta"}
DEPENDENCIES = {"pytest": "pytest", "fastapi": "fastapi", "httpx": "httpx",
                "pydantic": "pydantic", "numpy": "numpy"}
STAGE_TESTS = {
    "audience": "test_audience_count_contract.py",
    "timing": "test_playback_freshness.py",
    "assessment": "test_rehear_assessment_boundary.py",
    "integrity": "test_report_integrity.py",
}
FROZEN_FUNCTIONS = {
    "sushi-fast/odi/EVC/state_engine.py": ["compute_state_delta", "negative_change_sensitivity",
                                         "individual_negative_sensitivity", "update_audience_state"],
    "sushi-fast/odi/EVC/schema.py": ["clamp"],
}
RUN_DIR = Path("artifacts/rehear-harness")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def walk_files(root: Path):
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for name in dirs + files:
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"symlink requires explicit review: {(Path(directory) / name).relative_to(root)}")
        for name in sorted(files):
            yield Path(directory) / name


def require_repo(repo: Path) -> None:
    required = ["sushi-app", "sushi-fast/odi/EVC/schema.py", "sushi-fast/odi/EVC/router.py",
                "sushi-fast/odi/EVC/state_engine.py", "sushi-fast/odi/EVC/clip_pool.json"]
    missing = [name for name in required if not (repo / name).exists()]
    if missing:
        raise ValueError("sushisite root not found; missing: " + ", ".join(missing))


def protected_hashes(repo: Path) -> dict[str, str]:
    hashes = {}
    for path in walk_files(repo):
        relative = path.relative_to(repo)
        if relative.parts[0] == "sushi-app" or path.suffix.lower() in UNITY_SUFFIXES or str(relative) == "sushi-fast/odi/EVC/clip_pool.json":
            hashes[relative.as_posix()] = sha256(path)
    return dict(sorted(hashes.items()))


def frozen_function_hashes(repo: Path) -> dict[str, str]:
    hashes = {}
    for name, functions in FROZEN_FUNCTIONS.items():
        tree = ast.parse((repo / name).read_text(encoding="utf-8"))
        found = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for function in functions:
            if function not in found:
                raise ValueError(f"protected function missing: {name}:{function}")
            dumped = ast.dump(found[function], include_attributes=False)
            hashes[f"{name}:{function}"] = hashlib.sha256(dumped.encode()).hexdigest()
    return hashes


def api_routes(repo: Path) -> list[str]:
    tree = ast.parse((repo / "sushi-fast/odi/EVC/router.py").read_text(encoding="utf-8"))
    routes = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                target = decorator.func
                if isinstance(target.value, ast.Name) and target.value.id == "router" and target.attr in {"get", "post", "put", "patch", "delete"}:
                    if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                        raise ValueError("route path is no longer a literal; review required")
                    routes.append(f"{target.attr.upper()} {decorator.args[0].value}")
    if not routes:
        raise ValueError("no EVC routes found")
    return sorted(routes)


def snapshot(repo: Path) -> dict:
    require_repo(repo)
    return {"format": FORMAT_VERSION, "protected_files": protected_hashes(repo),
            "frozen_functions": frozen_function_hashes(repo), "routes": api_routes(repo)}


def dependency_status() -> dict:
    result = {}
    for module, distribution in DEPENDENCIES.items():
        present = importlib.util.find_spec(module) is not None
        try:
            version = importlib.metadata.version(distribution) if present else None
        except importlib.metadata.PackageNotFoundError:
            version = "unknown"
        result[module] = {"available": present, "version": version}
    if result["pydantic"]["available"]:
        version = result["pydantic"]["version"]
        if version == "unknown" or int(version.split(".")[0]) < 2:
            result["pydantic"]["available"] = False
    return result


def import_violations(repo: Path) -> list[str]:
    errors = []
    scopes = [(repo / "sushi-fast/odi/EVC", False), (repo / "sushi-fast/rehear_ai", True)]
    for root, core in scopes:
        if not root.exists():
            continue
        for path in walk_files(root):
            if path.suffix != ".py" or "tests" in path.relative_to(root).parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module] if node.module else [alias.name for alias in node.names]
                for name in names:
                    parts = name.split(".")
                    forbidden = "tools" in parts or any(part.startswith("rehear_harness") for part in parts)
                    if core:
                        forbidden = forbidden or parts[0] in {"odi", "fastapi", "sqlalchemy", "firebase_admin"}
                    if forbidden:
                        errors.append(f"{path.relative_to(repo)}:{node.lineno} imports {name}")
    return errors


def compare_baseline(before: dict, after: dict) -> list[str]:
    if before.get("format") != FORMAT_VERSION:
        raise ValueError("unsupported baseline format")
    for field in ("protected_files", "frozen_functions", "routes"):
        if field not in before or not before[field]:
            raise ValueError(f"incomplete baseline: {field}")
    errors = []
    for field in ("protected_files", "frozen_functions"):
        old, new = before[field], after[field]
        for key in sorted(set(old) | set(new)):
            if key not in old:
                errors.append(f"ADDED {field}: {key}")
            elif key not in new:
                errors.append(f"REMOVED {field}: {key}")
            elif old[key] != new[key]:
                errors.append(f"CHANGED {field}: {key}")
    if before["routes"] != after["routes"]:
        errors.append("EVC route set changed")
    return errors


def stage_test_paths(repo: Path, suite: str) -> list[Path]:
    directory = repo / "sushi-fast/odi/EVC/tests"
    originals = sorted(path for path in directory.glob("test_*.py") if path.name not in STAGE_TESTS.values())
    if suite in {"original", "all"} and not originals:
        raise ValueError("existing EVC test suite not found")
    selected = list(originals) if suite in {"original", "all"} else []
    stages = list(STAGE_TESTS) if suite == "all" else ([suite] if suite in STAGE_TESTS else [])
    for stage in stages:
        path = directory / STAGE_TESTS[stage]
        if not path.is_file():
            raise ValueError(f"not implemented: {path.relative_to(repo)}; missing tests are not PASS")
        selected.append(path)
    return selected


OFFLINE_PLUGIN = '''import json, os, socket
from pathlib import Path

def deny(*args, **kwargs):
    raise RuntimeError("Offline harness: socket connection blocked; inject a fake provider")

socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.create_connection = deny
socket.getaddrinfo = deny

def pytest_sessionfinish(session, exitstatus):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = terminal.stats if terminal else {}
    data = {"collected": session.testscollected, "exitstatus": int(exitstatus),
            **{key: len(stats.get(key, [])) for key in
               ("passed", "failed", "skipped", "error", "xfailed", "xpassed")}}
    Path(os.environ["REHEAR_HARNESS_TEST_REPORT"]).write_text(json.dumps(data), encoding="utf-8")
'''


def run_tests(repo: Path, suite: str) -> tuple[int, dict]:
    paths = stage_test_paths(repo, suite)
    dependencies = dependency_status()
    missing = [key for key, value in dependencies.items() if not value["available"]]
    if missing:
        raise ValueError("test environment incomplete: " + ", ".join(missing))
    with tempfile.TemporaryDirectory(prefix="rehear-offline-") as temporary:
        temp = Path(temporary)
        (temp / "rehear_harness_offline_plugin.py").write_text(OFFLINE_PLUGIN, encoding="utf-8")
        report_path = temp / "pytest-report.json"
        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env.pop("PYTEST_ADDOPTS", None)
        env["PYTHONPATH"] = os.pathsep.join([str(temp), str(repo / "sushi-fast"), env.get("PYTHONPATH", "")])
        env["REHEAR_HARNESS_TEST_REPORT"] = str(report_path)
        command = [sys.executable, "-m", "pytest", "-p", "rehear_harness_offline_plugin",
                   "-q", "--tb=short", *[str(path.relative_to(repo / "sushi-fast")) for path in paths]]
        started = time.monotonic()
        completed = subprocess.run(command, cwd=repo / "sushi-fast", env=env, check=False)
        stats = json.loads(report_path.read_text()) if report_path.exists() else {}
        result = {"suite": suite, "command": command, "returncode": completed.returncode,
                  "elapsed_seconds": round(time.monotonic() - started, 6), "pytest": stats,
                  "socket_network_blocked": True, "real_model_verified": False,
                  "unity_verified": False}
        if completed.returncode:
            return 1, {"status": "FAIL", **result}
        if not stats or not stats.get("collected") or stats.get("passed", 0) != stats["collected"] or any(stats.get(key, 0) for key in ("skipped", "xfailed", "xpassed", "error", "failed")):
            return 2, {"status": "INCOMPLETE", **result}
        return 0, {"status": "PASS_SELECTED_TESTS", **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "capture", "guard"):
        commands.add_parser(name)
    test = commands.add_parser("test")
    test.add_argument("--suite", choices=["original", *STAGE_TESTS, "all"], required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        require_repo(repo)
        baseline = repo / RUN_DIR / "baseline.json"
        if args.command == "doctor":
            deps = dependency_status()
            ready = all(value["available"] for value in deps.values())
            result = {"status": "READY_FOR_OFFLINE_TESTS" if ready else "INCOMPLETE_ENVIRONMENT",
                      "python": sys.version.split()[0], "dependencies": deps,
                      "baseline_exists": baseline.exists(), "model_or_unity_tested": False}
            code = 0 if ready else 2
        elif args.command == "capture":
            if baseline.exists():
                raise ValueError("baseline already exists; refusing overwrite. Use guard; do not rebaseline failures")
            result = snapshot(repo)
            result["captured_at"] = datetime.now(timezone.utc).isoformat()
            write_json(baseline, result)
            result = {"status": "CAPTURED_NOT_PRODUCT_TESTED", "protected_file_count": len(result["protected_files"]),
                      "frozen_function_count": len(result["frozen_functions"]), "baseline": str(RUN_DIR / "baseline.json")}
            code = 0
        elif args.command == "guard":
            if not baseline.exists():
                raise ValueError("baseline missing; capture before product changes")
            before = json.loads(baseline.read_text(encoding="utf-8"))
            errors = compare_baseline(before, snapshot(repo)) + import_violations(repo)
            result = {"status": "FAIL" if errors else "PASS_PROTECTED_BOUNDARIES_ONLY", "violations": errors,
                      "full_contract_or_unity_verified": False}
            code = 1 if errors else 0
        else:
            code, result = run_tests(repo, args.suite)
    except (ValueError, OSError, SyntaxError, json.JSONDecodeError) as exc:
        code, result = 2, {"status": "BLOCKED_OR_INCOMPLETE", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (repo / "sushi-fast/odi/EVC").is_dir():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        write_json(repo / RUN_DIR / f"{stamp}-{args.command}.json", {"exit_code": code, **result})
    return code


if __name__ == "__main__":
    raise SystemExit(main())
