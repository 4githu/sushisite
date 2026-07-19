# odi/files/service.py

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from fastapi import HTTPException, UploadFile


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_ROOT = (BASE_DIR / "storage" / "odi").resolve()

TEMP_EXPIRE_DAYS = 1
BUNDLE_EXPIRE_DAYS = 7
PDF_RENDER_DPI = 200

ALLOWED_ROLES = {"slide", "paper", "script"}
ALLOWED_SUFFIX_BY_ROLE = {
    "slide": {".pdf"},
    "paper": {".pdf"},
    "script": {".txt", ".md"},
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_after_days_iso(days: int) -> str:
    return (utc_now() + timedelta(days=days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_upload_id() -> str:
    return f"upload_{uuid4().hex[:16]}"


def make_bundle_id() -> str:
    return f"bundle_{uuid4().hex[:16]}"


def as_storage_path(path: Path) -> str:
    return path.resolve().relative_to(BASE_DIR).as_posix()


def path_from_storage_path(storage_path: str) -> Path:
    candidate = (BASE_DIR / storage_path).resolve()
    root = STORAGE_ROOT.resolve()

    if candidate != root and root not in candidate.parents:
        raise HTTPException(status_code=400, detail="허용되지 않은 파일 경로입니다.")

    return candidate


def ensure_role(role: str) -> None:
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 역할입니다: {role}")


def ensure_suffix(role: str, filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()

    if suffix not in ALLOWED_SUFFIX_BY_ROLE[role]:
        allowed = ", ".join(sorted(ALLOWED_SUFFIX_BY_ROLE[role]))
        raise HTTPException(status_code=400, detail=f"{role} 파일은 {allowed} 형식만 업로드할 수 있습니다.")

    return suffix


def ensure_user_temp_path(user_id: str, storage_path: str) -> Path:
    path = path_from_storage_path(storage_path)
    user_temp_root = (STORAGE_ROOT / "users" / str(user_id) / "temp").resolve()

    if user_temp_root not in path.parents:
        raise HTTPException(status_code=400, detail="현재 유저의 임시 파일만 세션 파일로 확정할 수 있습니다.")

    return path


def get_pdf_page_count(pdf_path: Path) -> int | None:
    try:
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        doc.close()
        return page_count
    except Exception:
        return None


async def save_temp_upload(user_id: str, role: str, upload: UploadFile) -> dict[str, Any]:
    ensure_role(role)

    original_name = upload.filename or "upload"
    suffix = ensure_suffix(role, original_name)

    upload_id = make_upload_id()
    upload_dir = STORAGE_ROOT / "users" / str(user_id) / "temp" / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    target_path = upload_dir / f"original{suffix}"

    size_bytes = 0

    try:
        with target_path.open("wb") as out:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break

                size_bytes += len(chunk)
                out.write(chunk)
    finally:
        await upload.close()

    page_count = get_pdf_page_count(target_path) if suffix == ".pdf" else None

    return {
        "storage_path": as_storage_path(target_path),
        "original_name": original_name,
        "mime_type": upload.content_type,
        "size_bytes": size_bytes,
        "status": "temp",
        "uploaded_at": utc_now_iso(),
        "expires_at": utc_after_days_iso(TEMP_EXPIRE_DAYS),
        "page_count": page_count,
        "image_manifest_path": None,
    }


def render_pdf_to_images(pdf_path: Path, output_dir: Path, original_name: str, dpi: int = PDF_RENDER_DPI) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    images: list[dict[str, Any]] = []

    try:
        for index, page in enumerate(doc, start=1):
            image_name = f"image_{index}.png"
            image_path = output_dir / image_name

            pix = page.get_pixmap(dpi=dpi)
            pix.save(image_path)

            images.append(
                {
                    "index": index,
                    "filename": image_name,
                    "storage_path": as_storage_path(image_path),
                    "width": pix.width,
                    "height": pix.height,
                }
            )

        manifest = {
            "original_name": original_name,
            "page_count": doc.page_count,
            "dpi": dpi,
            "images": images,
        }

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "page_count": doc.page_count,
            "image_manifest_path": as_storage_path(manifest_path),
            "images": images,
        }
    finally:
        doc.close()


def move_temp_file_to_bundle(
    user_id: str,
    file_ref: dict[str, Any],
    bundle_files_dir: Path,
    final_name: str,
) -> dict[str, Any]:
    storage_path = file_ref.get("storage_path")

    if not storage_path:
        return file_ref

    source_path = ensure_user_temp_path(user_id, storage_path)

    if not source_path.exists():
        raise HTTPException(status_code=400, detail=f"임시 파일을 찾을 수 없습니다: {storage_path}")

    target_path = bundle_files_dir / final_name

    if target_path.exists():
        target_path.unlink()

    shutil.move(str(source_path), str(target_path))

    next_ref = {
        **file_ref,
        "storage_path": as_storage_path(target_path),
        "status": "committed",
        "expires_at": utc_after_days_iso(BUNDLE_EXPIRE_DAYS),
    }

    try:
        parent = source_path.parent
        if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
    except Exception:
        pass

    return next_ref


def write_script_content(bundle_files_dir: Path, script_content: str) -> dict[str, Any]:
    target_path = bundle_files_dir / "script.txt"
    target_path.write_text(script_content, encoding="utf-8")

    return {
        "storage_path": as_storage_path(target_path),
        "original_name": "script.txt",
        "mime_type": "text/plain",
        "size_bytes": target_path.stat().st_size,
        "status": "committed",
        "uploaded_at": utc_now_iso(),
        "expires_at": utc_after_days_iso(BUNDLE_EXPIRE_DAYS),
        "page_count": None,
        "image_manifest_path": None,
    }


def normalize_files(files: dict[str, Any] | None) -> dict[str, Any]:
    files = files or {}

    return {
        "slide": files.get("slide"),
        "paper": files.get("paper"),
        "script": files.get("script"),
        "script_content": files.get("script_content"),
    }


def commit_template_files(user_id: str, template: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle_id = make_bundle_id()

    bundle_root = STORAGE_ROOT / "users" / str(user_id) / "bundles" / bundle_id
    bundle_files_dir = bundle_root / "files"
    slide_images_dir = bundle_root / "slide_images"

    bundle_files_dir.mkdir(parents=True, exist_ok=True)

    next_template = json.loads(json.dumps(template, ensure_ascii=False))
    files = normalize_files(next_template.get("files"))

    slide_ref = files.get("slide")
    if slide_ref and slide_ref.get("storage_path") and slide_ref.get("status") == "temp":
        committed_slide = move_temp_file_to_bundle(
            user_id=user_id,
            file_ref=slide_ref,
            bundle_files_dir=bundle_files_dir,
            final_name="slide.pdf",
        )

        slide_path = path_from_storage_path(committed_slide["storage_path"])
        image_result = render_pdf_to_images(
            pdf_path=slide_path,
            output_dir=slide_images_dir,
            original_name=committed_slide.get("original_name") or "slide.pdf",
        )

        committed_slide = {
            **committed_slide,
            "page_count": image_result["page_count"],
            "image_manifest_path": image_result["image_manifest_path"],
        }

        files["slide"] = committed_slide

    paper_ref = files.get("paper")
    if paper_ref and paper_ref.get("storage_path") and paper_ref.get("status") == "temp":
        files["paper"] = move_temp_file_to_bundle(
            user_id=user_id,
            file_ref=paper_ref,
            bundle_files_dir=bundle_files_dir,
            final_name="paper.pdf",
        )

    script_ref = files.get("script")
    script_content = files.get("script_content")

    if script_ref and script_ref.get("storage_path") and script_ref.get("status") == "temp":
        files["script"] = move_temp_file_to_bundle(
            user_id=user_id,
            file_ref=script_ref,
            bundle_files_dir=bundle_files_dir,
            final_name="script.txt",
        )
    elif isinstance(script_content, str) and script_content.strip():
        files["script"] = write_script_content(bundle_files_dir, script_content)

    next_template["files"] = files
    next_template["file_bundle_id"] = bundle_id
    next_template["file_bundle_path"] = as_storage_path(bundle_root)
    next_template["file_bundle_expires_at"] = utc_after_days_iso(BUNDLE_EXPIRE_DAYS)

    bundle_info = {
        "file_bundle_id": bundle_id,
        "file_bundle_path": as_storage_path(bundle_root),
        "expires_at": next_template["file_bundle_expires_at"],
        "files": files,
    }

    return next_template, bundle_info


def delete_path_if_exists(path: Path) -> bool:
    if not path.exists():
        return False

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()

    return True


def cleanup_expired_storage() -> dict[str, Any]:
    now = utc_now()
    deleted_paths: list[str] = []

    users_root = STORAGE_ROOT / "users"

    if not users_root.exists():
        return {"deleted_count": 0, "deleted_paths": []}

    for expires_file in users_root.glob("**/.expires.json"):
        try:
            data = json.loads(expires_file.read_text(encoding="utf-8"))
            expires_at = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
            target_path = path_from_storage_path(data["target_path"])

            if expires_at <= now and delete_path_if_exists(target_path):
                deleted_paths.append(as_storage_path(target_path))
        except Exception:
            continue

    return {
        "deleted_count": len(deleted_paths),
        "deleted_paths": deleted_paths,
    }