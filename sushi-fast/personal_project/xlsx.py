from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def _cell(column: str, row: int, value) -> str:
    if isinstance(value, (int, float)):
        return f'<c r="{column}{row}"><v>{value}</v></c>'
    return f'<c r="{column}{row}" t="inlineStr"><is><t>{escape(str(value or ""))}</t></is></c>'


def settlement_workbook(data: dict) -> bytes:
    headers = ["날짜", "학교", "회차", "금액", "지급", "리포트"]
    rows = [headers]
    for item in data["items"]:
        report_statuses = [
            target["report"]["status"] if target["report"] else "미작성"
            for target in item.get("targets", [])
        ]
        rows.append([
            item["startTime"][:10], item.get("schoolName", item.get("studentName", "")),
            f"{item.get('roundNumber', '')}회차" if item.get("roundNumber") else "",
            item["amount"], item["paymentStatus"],
            ", ".join(report_statuses)
            if report_statuses
            else item["report"]["status"] if item.get("report") else "미작성",
        ])
    rows.append(["", "", "합계", data["totalAmount"], "", ""])
    sheet_rows = []
    columns = "ABCDEF"
    for number, values in enumerate(rows, 1):
        cells = "".join(_cell(columns[index], number, value) for index, value in enumerate(values))
        sheet_rows.append(f'<row r="{number}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(sheet_rows) + '</sheetData></worksheet>'
    )
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="월별 정산" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return output.getvalue()
