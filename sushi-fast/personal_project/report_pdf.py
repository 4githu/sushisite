"""Server-side PDF and page rendering for Aura clinic reports."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Any

import fitz


from .academic import STAGE_LABELS


def _stage_label(value: Any) -> str:
    stage = str(value or "")
    # Historical records may contain this misspelling; do not rewrite stored data.
    return STAGE_LABELS.get(stage.replace("semestar", "semester"), stage)


def _safe(value: Any) -> str:
    return escape(str(value or ""), quote=True).replace("\n", "<br>")


def _format_short_date(value: Any) -> str:
    try:
        date = datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).astimezone()
        return f"{date.month}월 {date.day}일"
    except (TypeError, ValueError):
        return str(value or "")


def _format_clock(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return str(value or "")


def _chunk_html(chunk: dict[str, Any]) -> str:
    text = _safe(chunk.get("text", ""))
    styles = ["color:#111111"]
    if chunk.get("bold"):
        styles.append("font-weight:700")
    if chunk.get("italic"):
        styles.append("font-style:italic")
    if chunk.get("underline"):
        styles.append("text-decoration:underline")
    if chunk.get("strike"):
        styles.append("text-decoration:line-through")
    size = chunk.get("fontSize")
    if size in (12, 16, 20, 28):
        styles.append(f"font-size:{size}px")
    if chunk.get("highlightColor"):
        color = str(chunk["highlightColor"])
        if len(color) == 7 and color.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in color[1:]):
            styles.append(f"background-color:{color}")
    return f'<span style="{";".join(styles)}">{text}</span>'


def _indent_style(block: dict[str, Any]) -> str:
    try:
        indent = max(0, min(8, int(block.get("depth", 0) or 0)))
    except (TypeError, ValueError):
        indent = 0
    return f' style="margin-left:{indent * 24}px"' if indent else ""


def _text_block(block: dict[str, Any]) -> str:
    content = "".join(_chunk_html(chunk) for chunk in block.get("children", [])) or "&nbsp;"
    kind = block.get("type")
    style = _indent_style(block)
    if kind == "heading":
        level = block.get("level", 2)
        tag = "h3" if level in (2, 3) else "h2"
        return f"<{tag}{style}>{content}</{tag}>"
    if kind == "blockquote":
        return f"<blockquote{style}>{content}</blockquote>"
    if kind == "codeBlock":
        return f"<pre{style}>{content}</pre>"
    if kind in ("bulletList", "orderedList"):
        tag = "ol" if kind == "orderedList" else "ul"
        return f"<{tag}{style}><li>{content}</li></{tag}>"
    return f"<p{style}>{content}</p>"


def _document_html(document: Any) -> str:
    if not isinstance(document, dict):
        return ""
    sections: list[str] = []
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        if block.get("type") != "table":
            sections.append(_text_block(block))
            continue
        rows = []
        for row in block.get("rows", []):
            cells = []
            for cell in row:
                cell_blocks = cell.get("blocks", []) if isinstance(cell, dict) else []
                cells.append("<td>" + "".join(_text_block(child) for child in cell_blocks) + "</td>")
            if cells:
                rows.append("<tr>" + "".join(cells) + "</tr>")
        if rows:
            style = _indent_style(block)
            sections.append(f'<table class="appendix-table"{style}>' + "".join(rows) + "</table>")
    return "".join(sections)


def _image_html(attachments: list[dict[str, Any]], kind: str, asset_dir: Path) -> str:
    images = []
    for index, item in enumerate(attachments):
        if item.get("kind") != kind:
            continue
        path = item.get("path")
        if not path or not Path(path).is_file():
            continue
        extension = {"image/png": ".png", "image/webp": ".webp"}.get(item.get("mimeType"), ".jpg")
        relative_name = f"images/{kind}-{index}{extension}"
        destination = asset_dir / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        name = f"assets/{relative_name}"
        images.append(f'<img src="{name}" alt="{_safe(item.get("name"))}">')
    return "".join(images)


def _html(report: dict[str, Any], attachments: list[dict[str, Any]], asset_dir: Path) -> str:
    generated = report.get("generatedReportJson") or {}
    target = report
    assessment = generated.get("assessment") or report.get("assessmentJson") or {}
    items = assessment.get("items") or []
    paragraphs = (generated.get("learningContent") or {}).get("paragraphs") or []
    if not paragraphs and generated.get("learningContent", {}).get("text"):
        paragraphs = [generated["learningContent"]["text"]]

    summary_rows = [
        ("구분", f'{target.get("schoolName", "")} {_stage_label(target.get("progressStage"))} {target.get("roundLabel", "")}', "강의수강도", target.get("lectureProgress", "-")),
        ("이름", target.get("studentName", ""), "강의이해도", target.get("lectureComprehension", "-")),
        ("수업날짜", _format_short_date(target.get("startTime")), "클리닉 전 암기", target.get("memoryBefore", "-")),
        ("시간", f'{_format_clock(target.get("startTime"))}~{_format_clock(target.get("endTime"))}', "클리닉 후 암기", target.get("memoryAfter", "-")),
    ]
    summary = "".join(
        f"<tr><th>{_safe(a)}</th><td>{_safe(b)}</td><th>{_safe(c)}</th><td>{_safe(d)}</td></tr>"
        for a, b, c, d in summary_rows
    )
    assessment_html = ""
    if items:
        names = "".join(f'<div>{_safe(item.get("name"))}</div>' for item in items if isinstance(item, dict))
        scores = "".join(f'<div>{_safe(item.get("score"))}</div>' for item in items if isinstance(item, dict))
        assessment_html = f'<section class="report-section assessment-section"><h2>학습내용 암기 정도 평가</h2><table><tbody><tr><th>{names}</th><td>{scores}</td></tr></tbody></table></section>'

    blank = _image_html(attachments, "blank_test", asset_dir)
    problem = _image_html(attachments, "problem_solving", asset_dir)
    problem_note = generated.get("problemSolvingNote") or ""
    learning_content = "".join(f"<p>{_safe(paragraph)}</p>" for paragraph in paragraphs if str(paragraph).strip())
    document_html = _document_html(report.get("contentJson"))
    appendix_html = ""
    if document_html:
        appendix_html = f"""<section class="report-section pdf-appendix"><h2>(부록) 이번 단원 학습 내용</h2>
        <p class="appendix-notice">제가 개인적으로 수업 내용을 정리했으나 사소한 오류가 있을 수 있습니다.<br>클리닉을 진행하며 학생이 잘 모르는 부분을 형광으로 표시해뒀습니다.</p>
        <div class="text-editor-card"><div class="text-editor-surface">{document_html}</div></div></section>"""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
    @page {{ size: A4 portrait; margin: 10mm; }}
    html, body {{ margin: 0; padding: 0; background: #fff; }}
    body {{ font-family: Arial, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif; color: #111; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    article {{ box-sizing: border-box; width: 100%; min-height: 0; margin: 0 auto; padding: 0; background: #fff; color: #111; }}
    article h1 {{ margin: 0 0 18px; font-size: 32px; font-weight: 500; }}
    article .summary-table, article .report-section {{ margin: 0; }}
    article h2 {{ margin: 0; padding: 8px 9px; border: 1px solid #9a9a9a; border-top: 0; font-size: 16px; font-weight: 500; }}
    article p {{ margin: 0 0 5px; font-size: 13px; line-height: 1.7; white-space: pre-wrap; color: #111; }}
    article table {{ width: 100%; border-collapse: collapse; }}
    article th, article td {{ padding: 7px 8px; border: 1px solid #9a9a9a; font-size: 13px; font-weight: 400; color: #111; }}
    article .summary-table th:nth-child(1) {{ width: 90px; }}
    article .summary-table th:nth-child(3) {{ width: 150px; }}
    article .summary-table td:nth-child(4) {{ width: 42px; text-align: center; }}
    article .assessment-section th {{ text-align: left; }}
    article .assessment-section td {{ width: 48px; text-align: center; }}
    article .assessment-section div {{ min-height: 21px; line-height: 1.55; }}
    article .learning-section > div, article .image-section > .image-grid, article .pdf-appendix > .appendix-notice, article .image-section > .not-submitted {{ padding: 9px; border: 1px solid #9a9a9a; border-top: 0; }}
    article img {{ display: block; max-width: 100%; margin: 12px auto; }}
    article .image-section h2 {{ break-after: avoid-page; }}
    article .image-grid {{ display: grid; grid-template-columns: 1fr; align-items: start; gap: 4px; }}
    article .image-grid img {{ width: 100%; height: auto; margin: 0; object-fit: contain; break-inside: avoid; page-break-inside: avoid; }}
    article .problem-image-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    article .problem-image-grid img {{ max-height: 420px; }}
    article .pdf-appendix .text-editor-toolbar {{ display: none !important; }}
    article .pdf-appendix .text-editor-card {{ padding: 9px; border: 1px solid #9a9a9a; border-top: 0; border-radius: 0; box-shadow: none; color: #111; }}
    article .pdf-appendix .text-editor-surface {{ height: auto; min-height: 0; padding: 4px 10px; overflow: visible; font-size: 12px; }}
    article .text-editor-surface, article .personal-editor, article .tiptap, article .text-editor-card * {{ color: #111 !important; }}
    article .appendix-block {{ margin: 0; padding: 0; border: 0; box-shadow: none; }}
    article .appendix-table {{ margin: 0; }}
    @media print {{ article {{ margin: 0; box-shadow: none; }} .page-break-avoid {{ break-inside: avoid; }} }}
    </style></head><body><article class="pdf-preview">
    <h1>⊙ {_safe(target.get('studentName'))} 클리닉 리포트</h1>
    <table class="summary-table"><tbody>{summary}</tbody></table>
    {assessment_html}
    <section class="report-section learning-section"><h2>클리닉 학습 내용, 부족한 점</h2><div>{learning_content}</div></section>
    <section class="report-section image-section"><h2>백지 테스트 결과</h2>{f'<div class="image-grid">{blank}</div>' if blank else '<p class="not-submitted">백지테스트를 제출하지 않았습니다.</p>'}</section>
    {f'<section class="report-section image-section"><h2>문제풀이</h2><div class="image-grid problem-image-grid">{problem}{f"<p>{_safe(problem_note)}</p>" if problem_note else ""}</div></section>' if problem or problem_note else ''}
    {appendix_html}
    </article></body></html>"""


def render_pdf(report: dict[str, Any], attachments: list[dict[str, Any]]) -> bytes:
    with TemporaryDirectory(prefix="aura-report-pdf-") as directory:
        work = Path(directory)
        asset_dir = work / "assets"
        asset_dir.mkdir()
        html_path = work / "clinic-report.html"
        output = work / "clinic-report.pdf"
        html_path.write_text(_html(report, attachments, asset_dir), encoding="utf-8")
        chrome = next((path for path in (
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ) if path.is_file()), None)
        if not chrome:
            raise RuntimeError("원본 리포트 서식 렌더러(Chrome)를 찾지 못했습니다.")
        profile = work / "chrome-profile"
        subprocess.run([
            str(chrome), "--headless=new", "--disable-gpu", "--no-sandbox",
            "--disable-dev-shm-usage", "--disable-extensions", "--no-first-run",
            "--no-default-browser-check", "--allow-file-access-from-files",
            f"--user-data-dir={profile}", "--no-pdf-header-footer",
            f"--print-to-pdf={output}", html_path.as_uri(),
        ], check=True, capture_output=True, timeout=60)
        if not output.is_file() or output.stat().st_size < 1024:
            raise RuntimeError("원본 리포트 서식 PDF가 비어 있습니다.")
        return output.read_bytes()


def render_pages(pdf_bytes: bytes, *, max_pages: int = 20) -> list[bytes]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    if document.page_count > max_pages:
        raise ValueError(f"리포트가 {document.page_count}장입니다. 한 번에 최대 {max_pages}장까지 보낼 수 있습니다.")
    pages = []
    for page in document:
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.75, 1.75), alpha=False)
        pages.append(pixmap.tobytes("jpeg", jpg_quality=88))
    return pages
