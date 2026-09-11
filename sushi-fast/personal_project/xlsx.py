from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from .pricing import (
    clinic_hourly_cost,
    clinic_settlement_amount,
    duration_hours,
    parent_charge_per_student,
    parent_group_charge,
)


KST = timezone(timedelta(hours=9))
def _column_name(index: int) -> str:
    """Return Excel's A, B, ... AA column name for a zero-based index."""
    result = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(column: str, row: int, value, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, (int, float)):
        return f'<c r="{column}{row}"{style_attr}><v>{value}</v></c>'
    text = escape(str(value or ""))
    return (
        f'<c r="{column}{row}"{style_attr} t="inlineStr">'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def _formula_cell(column: str, row: int, formula: str, cached_value, style: int = 0) -> str:
    style_attr = f' s="{style}"' if style else ""
    return (
        f'<c r="{column}{row}"{style_attr}>'
        f'<f>{escape(formula)}</f><v>{cached_value}</v></c>'
    )


def _local_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def _duration_hours(item: dict) -> float:
    start = _local_time(item["startTime"])
    end = _local_time(item["endTime"])
    return duration_hours(start, end)


def _parent_charge(item: dict) -> int:
    return parent_charge_per_student(
        item.get("progressStage", "accepted"),
        _local_time(item["startTime"]),
        _local_time(item["endTime"]),
        len(item.get("targets", [])),
        bool(item.get("parentFreeForThreePlus", False)),
    )


def _hourly_cost(item: dict) -> int:
    return clinic_hourly_cost(item.get("progressStage", "accepted"), len(item.get("targets", [])))


def _parent_group_cost(item: dict) -> int:
    return parent_group_charge(
        item.get("progressStage", "accepted"),
        _local_time(item["startTime"]),
        _local_time(item["endTime"]),
        len(item.get("targets", [])),
        bool(item.get("parentFreeForThreePlus", False)),
    )


def _assistant_pay(item: dict) -> int:
    return clinic_settlement_amount(
        item.get("progressStage", "accepted"),
        _local_time(item["startTime"]),
        _local_time(item["endTime"]),
        len(item.get("targets", [])),
    )


def _school_display_name(school_name: str) -> str:
    match = re.fullmatch(r"(서울|경기|한성)(\d{2})(.*)", school_name.strip())
    return f"{match.group(2)}{match.group(1)}{match.group(3)}" if match else school_name.strip()


def _settlement_groups(items: list[dict]) -> list[list[dict]]:
    """Group a student's sessions across academic terms when the rate is the same."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in items:
        student_names = tuple(sorted(target["studentName"].strip() for target in item.get("targets", [])))
        key = (
            item["schoolId"],
            student_names,
            _hourly_cost(item),
            bool(item.get("parentFreeForThreePlus", False)),
        )
        groups[key].append(item)
    return [
        sorted(group, key=lambda item: item["startTime"])
        for _, group in sorted(
            groups.items(),
            key=lambda entry: (entry[1][0]["schoolName"], entry[0][1], entry[1][0]["startTime"]),
        )
    ]


def settlement_workbook(data: dict, assistant_name: str = "김지후") -> bytes:
    """Create the assistant-facing monthly clinic settlement workbook."""
    assistant_name = assistant_name.strip() or "김지후"
    assistant_label = assistant_name if assistant_name.endswith("조교") else f"{assistant_name}조교"
    groups = _settlement_groups(data["items"])
    max_sessions = max((len(group) for group in groups), default=1)
    session_start_column = 2
    summary_start_column = session_start_column + max_sessions
    rows: list[tuple[list, int]] = [
        ([f"{data['year']}년 {data['month']}월 {assistant_label} 클리닉 정산"], 3),
    ]
    formula_cells: dict[tuple[int, int], tuple[str, int | float]] = {}
    assistant_pay_cells: list[tuple[str, int]] = []

    for group in groups:
        first = group[0]
        date_row = ["", ""]
        time_row = [
            _school_display_name(first["schoolName"]),
            ", ".join(target["studentName"] for target in first.get("targets", [])),
        ]
        for item in group:
            start = _local_time(item["startTime"])
            end = _local_time(item["endTime"])
            date_row.append(f"{start.month}월 {start.day}일")
            time_row.append(f"{start:%H:%M} ~ {end:%H:%M}")
        date_row.extend([""] * (max_sessions - len(group)))
        time_row.extend([""] * (max_sessions - len(group)))

        total_hours = sum(_duration_hours(item) for item in group)
        clinic_cost = sum(_parent_group_cost(item) for item in group)
        assistant_pay = sum(_assistant_pay(item) for item in group)
        date_row.extend(["시간당 클리닉 비용", "총 클리닉 시간", "클리닉 정산 비용", "조교 페이"])
        time_row.extend([
            _hourly_cost(first),
            total_hours,
            clinic_cost,
            assistant_pay,
        ])
        time_row_number = len(rows) + 2
        rate_column = _column_name(summary_start_column)
        hours_column = _column_name(summary_start_column + 1)
        clinic_cost_column = _column_name(summary_start_column + 2)
        assistant_pay_column = _column_name(summary_start_column + 3)
        # 시간은 Excel 수식으로 계산하지 않는다. 서버에서 확정한 30분 단위 숫자를
        # 그대로 쓰므로 2, 2.5처럼 표시되며 음수 시간이나 부동소수점 오차가 없다.
        billing_formula = (
            "0"
            if clinic_cost == 0
            else f"{rate_column}{time_row_number}*{hours_column}{time_row_number}"
        )
        formula_cells[(time_row_number, summary_start_column + 2)] = (billing_formula, clinic_cost)
        formula_cells[(time_row_number, summary_start_column + 3)] = (
            f"{rate_column}{time_row_number}*{hours_column}{time_row_number}",
            assistant_pay,
        )
        assistant_pay_cells.append((assistant_pay_column, time_row_number))
        rows.extend([(date_row, 2), (time_row, 0), ([], 0)])

    total_amount = sum(_assistant_pay(item) for item in data["items"])
    total_row_number = len(rows) + 2
    total_formula = "SUM(" + ",".join(f"{column}{row}" for column, row in assistant_pay_cells) + ")"
    formula_cells[(total_row_number, 2)] = (total_formula, total_amount)
    formula_cells[(total_row_number + 1, 2)] = (
        f"ROUND(C{total_row_number}*96.7%,0)",
        round(total_amount * 0.967),
    )
    rows.extend([
        ([], 0),
        (["학원 → 조교 입금 금액", "총", total_amount], 1),
        (["", "3.3% 세액공제 후", round(total_amount * 0.967)], 1),
    ])

    sheet_rows = []
    for row_number, (values, row_style) in enumerate(rows, 1):
        cells = "".join(
            _formula_cell(
                _column_name(index), row_number, *formula_cells[(row_number, index)], row_style
            )
            if (row_number, index) in formula_cells
            else _cell(_column_name(index), row_number, value, row_style)
            for index, value in enumerate(values)
        )
        height = ' ht="36" customHeight="1"' if row_number > 1 else ' ht="28" customHeight="1"'
        sheet_rows.append(f'<row r="{row_number}"{height}>{cells}</row>')

    last_column = _column_name(summary_start_column + 3)
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cols><col min="1" max="1" width="20" customWidth="1"/>'
        '<col min="2" max="2" width="28" customWidth="1"/>'
        f'<col min="3" max="{summary_start_column}" width="16" customWidth="1"/>'
        f'<col min="{summary_start_column + 1}" max="{summary_start_column + 4}" width="18" customWidth="1"/>'
        '</cols><sheetData>' + "".join(sheet_rows) + '</sheetData>'
        f'<mergeCells count="1"><mergeCell ref="A1:{last_column}1"/></mergeCells>'
        '</worksheet>'
    )
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF1DDD3"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="2"><border/><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/></border></borders>
  <cellXfs count="4"><xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="0" borderId="1" applyBorder="1" applyFont="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="1" applyBorder="1" applyFont="1" applyFill="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="0" borderId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf></cellXfs>
</styleSheet>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="월별 정산" sheetId="1" r:id="rId1"/></sheets><calcPr calcId="191029" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>"""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()
