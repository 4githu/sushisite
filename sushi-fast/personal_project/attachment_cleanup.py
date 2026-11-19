"""Internal, read-only assessment of journalled Aura attachment deletion candidates.

No HTTP route or automatic sweep is intentionally provided.
"""
import hashlib
import os
import re
import stat
from pathlib import Path

_STORAGE_NAME = re.compile(r"[0-9a-f]{32}\.(?:png|jpg|webp)\Z")
_MAX_BYTES = 15 * 1024 * 1024


def _fingerprint(root, owner, report, name):
    """Open every path component without following links; hash only a bounded regular file."""
    opened = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened.append(fd)
        for part in (str(owner), str(report)):
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            opened.append(fd)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        opened.append(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_BYTES:
            return None
        digest = hashlib.sha256()
        while chunk := os.read(fd, 65536):
            digest.update(chunk)
            if os.lseek(fd, 0, os.SEEK_CUR) > _MAX_BYTES:
                return None
        return info.st_size, digest.hexdigest()
    finally:
        for fd in reversed(opened):
            os.close(fd)


def assess(conn, root: Path, journal_id: int):
    row = conn.execute(
        "SELECT * FROM aura_attachment_cleanup_journal WHERE id = ?", (journal_id,)
    ).fetchone()
    if row is None:
        return {"id": journal_id, "classification": "ambiguous", "reason": "no_journal"}
    result = {"id": row["id"], "classification": "ambiguous", "reason": "unverified"}
    if row["status"] != "pending":
        result.update(classification="unsafe", reason="not_pending")
        return result
    owner, report, name = row["user_id"], row["target_report_id"], row["storage_name"]
    if (type(owner) is not int or owner <= 0 or type(report) is not int or report <= 0
            or not isinstance(name, str) or not _STORAGE_NAME.fullmatch(name)
            or row["byte_size"] < 0):
        result.update(classification="unsafe", reason="invalid_identity")
        return result
    if conn.execute("SELECT 1 FROM aura_report_attachments WHERE storage_name = ? LIMIT 1", (name,)).fetchone():
        result.update(classification="unsafe", reason="live_reference")
        return result
    root = Path(root)
    path = root / str(owner) / str(report) / name
    if not root.is_absolute() or root.is_symlink() or root.resolve() != root:
        result.update(classification="unsafe", reason="root_not_canonical")
        return result
    if not path.is_relative_to(root):
        result.update(classification="unsafe", reason="path_escape")
        return result
    for component in (root / str(owner), root / str(owner) / str(report), path):
        try:
            mode = component.lstat().st_mode
        except FileNotFoundError:
            result.update(classification="missing", reason="path_missing")
            return result
        except OSError:
            result.update(classification="ambiguous", reason="stat_failed")
            return result
        if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) if component == path else stat.S_ISDIR(mode)):
            result.update(classification="unsafe", reason="unsafe_component")
            return result
    if not row["file_sha256"]:
        result.update(classification="ambiguous", reason="no_fingerprint")
        return result
    try:
        fingerprint = _fingerprint(root, owner, report, name)
    except OSError:
        result.update(classification="ambiguous", reason="read_failed")
        return result
    if fingerprint is None or fingerprint != (row["byte_size"], row["file_sha256"]):
        result.update(classification="unsafe", reason="fingerprint_mismatch")
        return result
    result.update(classification="safe", reason="verified")
    return result


def snapshot(root: Path, owner: int, report: int, name: str):
    """Fingerprint a candidate at deletion time; never follow suspicious components."""
    if not isinstance(name, str) or not _STORAGE_NAME.fullmatch(name) or owner <= 0 or report <= 0:
        return None
    try:
        if Path(root).is_symlink() or Path(root).resolve() != Path(root):
            return None
        fingerprint = _fingerprint(root, owner, report, name)
        return fingerprint[1] if fingerprint else None
    except OSError:
        return None
