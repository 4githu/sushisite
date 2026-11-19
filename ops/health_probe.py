"""Small read-only origin/edge probe. No credentials or response bodies are stored."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import statistics
import subprocess

TARGETS = {
    "frontend": ("http://127.0.0.1:5173/", {200}),
    "backend": ("http://127.0.0.1:8000/api/healthz", {200}),
    "chobab": ("https://chobab.app/", {200}),
    "aura": ("https://aura.chobab.app/", {200, 303, 307, 308}),
    "rehear": ("https://rehear.chobab.app/", {200, 303, 307, 308}),
    "public_api": ("https://chobab.app/api/healthz", {200}),
}


def probe(item):
    name, (url, expected) = item
    try:
        result = subprocess.run([
            "/usr/bin/curl", "-sS", "--max-time", "12", "--connect-timeout", "5",
            "-D", "-", "-o", "/dev/null", "-w", "%{json}", url,
        ], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"target": name, "ok": False, "status": 0, "curl_exit": 28,
                "ttfb_ms": 0, "total_ms": 15000}
    raw_headers, _, raw_json = result.stdout.rpartition("\n")
    headers = {}
    for line in raw_headers.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            headers[key.lower()] = value.strip()
    try:
        data = json.loads(raw_json)
    except ValueError:
        data = {}
    return {"target": name, "ok": result.returncode == 0 and data.get("http_code") in expected,
            "status": data.get("http_code", 0), "curl_exit": result.returncode,
            "edge": headers.get("cf-ray", "").rsplit("-", 1)[-1],
            "dns_ms": round(data.get("time_namelookup", 0) * 1000, 1),
            "tls_ready_ms": round(data.get("time_appconnect", 0) * 1000, 1),
            "ttfb_ms": round(data.get("time_starttransfer", 0) * 1000, 1),
            "total_ms": round(data.get("time_total", 0) * 1000, 1)}


def snapshot():
    with ThreadPoolExecutor(max_workers=6) as pool:
        readings = list(pool.map(probe, TARGETS.items()))
    try:
        metrics = subprocess.run(["/usr/bin/curl", "-sS", "--max-time", "3",
                                  "http://127.0.0.1:20241/metrics"], capture_output=True, text=True, timeout=5)
        metric_lines = metrics.stdout.splitlines()
    except subprocess.TimeoutExpired:
        metric_lines = []
    tunnel_connections = None
    for line in metric_lines:
        if line.startswith("cloudflared_tunnel_ha_connections "):
            tunnel_connections = int(float(line.split()[-1]))
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "readings": readings,
            "tunnel_connections": tunnel_connections,
            "ok": all(r["ok"] for r in readings) and tunnel_connections == 4}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--record-dir", type=Path)
    args = parser.parse_args()
    if args.record_dir:
        args.record_dir.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("health")
        logger.setLevel(logging.INFO)
        logger.addHandler(RotatingFileHandler(args.record_dir / "health.jsonl", maxBytes=2_000_000, backupCount=3))
    samples = []
    for _ in range(args.samples):
        sample = snapshot()
        samples.append(sample)
        if args.record_dir:
            logger.info(json.dumps(sample))
            temp = args.record_dir / "status.tmp"
            temp.write_text(json.dumps(sample, indent=2) + "\n")
            temp.replace(args.record_dir / "status.json")
        print(json.dumps(sample), flush=True)
    if len(samples) > 1:
        print(json.dumps({name: {"median_ttfb_ms": statistics.median(
            r["ttfb_ms"] for s in samples for r in s["readings"] if r["target"] == name),
            "failures": sum(not r["ok"] for s in samples for r in s["readings"] if r["target"] == name)}
            for name in TARGETS}, indent=2))
