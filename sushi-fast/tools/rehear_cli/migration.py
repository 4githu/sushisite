"""Byte-preserving private archive and public hash-only inventory. Never deletes sources."""
import hashlib
import json
import os
from pathlib import Path

LEGACY_ROOTS = ("latency_benchmark_with_outputs", "live_latency_benchmark")
PRIVATE_ROOT = "artifacts/rehear-private/legacy-benchmarks"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def category(path):
    if path.suffix.lower() in {".wav", ".mp3", ".m4a"}:
        return "recorded_evidence"
    if path.name == "PRESENTATION_SCRIPTS.md" or "data" in path.parts:
        return "case"
    if "results" in path.parts:
        return "historical_result"
    if path.suffix in {".py", ".md", ".txt"}:
        return "measurement_definition"
    return "supporting_metadata"


def migrate(root: Path, manifest: Path):
    archive = root / PRIVATE_ROOT
    if archive.exists() or manifest.exists():
        raise ValueError("migration destination already exists; verify it instead of overwriting")
    archive.mkdir(parents=True, mode=0o700)
    entries, private_index = [], []
    for name in LEGACY_ROOTS:
        source = root / "sushi-fast" / name
        if not source.is_dir():
            raise ValueError("legacy source directory is missing")
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise ValueError("review symlink before migration")
            if not path.is_file():
                continue
            relative = path.relative_to(source).as_posix()
            path_hash = sha(relative.encode())
            destination = f"{PRIVATE_ROOT}/{name}/{path_hash}{path.suffix}"
            target = root / destination
            target.parent.mkdir(mode=0o700, exist_ok=True)
            data = path.read_bytes()
            with target.open("xb") as stream:
                os.chmod(target, 0o600)
                stream.write(data)
            entries.append({"source_root": name, "source_path_sha256": path_hash,
                "destination": destination, "sha256": sha(data), "size": len(data),
                "category": category(path.relative_to(source)), "privacy": "private_unreviewed_content"})
            private_index.append({"source_root": name, "relative_source": relative, "destination": destination})
    index = archive / "source-index.json"
    index.write_text(json.dumps(private_index, indent=2) + "\n")
    os.chmod(index, 0o600)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"schema_version": "legacy-benchmark-inventory.v1",
        "private_index_sha256": sha(index.read_bytes()), "files": entries}, indent=2) + "\n")
    return verify_inventory(root, manifest, require_sources=True)


def verify_inventory(root: Path, manifest: Path, *, require_sources=False):
    inventory = json.loads(manifest.read_text())
    index_path = root / PRIVATE_ROOT / "source-index.json"
    if sha(index_path.read_bytes()) != inventory["private_index_sha256"]:
        raise ValueError("private source index hash differs")
    index = json.loads(index_path.read_text())
    mapped = {(e["source_root"], sha(e["relative_source"].encode())): e for e in index}
    entries = inventory["files"]
    if len(mapped) != len(index) or len(entries) != len(index):
        raise ValueError("inventory completeness differs")
    seen, original_count = set(), 0
    for item in entries:
        key = (item["source_root"], item["source_path_sha256"])
        if key in seen or key not in mapped or item["source_root"] not in LEGACY_ROOTS:
            raise ValueError("inventory mapping differs")
        seen.add(key)
        original = mapped[key]
        if original["destination"] != item["destination"]:
            raise ValueError("inventory destination differs")
        target = root / item["destination"]
        if not target.resolve().is_relative_to((root / PRIVATE_ROOT).resolve()):
            raise ValueError("archive path escapes private root")
        data = target.read_bytes()
        if sha(data) != item["sha256"] or len(data) != item["size"]:
            raise ValueError("archive content differs")
        source_root = root / "sushi-fast" / item["source_root"]
        if source_root.exists() or require_sources:
            source = source_root / original["relative_source"]
            if not source.resolve().is_relative_to(source_root.resolve()):
                raise ValueError("source path escapes legacy root")
            if sha(source.read_bytes()) != item["sha256"]:
                raise ValueError("source content differs")
            original_count += 1
    for name in LEGACY_ROOTS:
        source = root / "sushi-fast" / name
        if source.exists():
            actual = {sha(p.relative_to(source).as_posix().encode()) for p in source.rglob("*") if p.is_file()}
            expected = {i["source_path_sha256"] for i in entries if i["source_root"] == name}
            if actual != expected:
                raise ValueError("source inventory is incomplete")
    return {"verified_files": len(entries), "verified_source_files": original_count,
        "categories": {e["category"] for e in entries}, "bytes": sum(e["size"] for e in entries)}
