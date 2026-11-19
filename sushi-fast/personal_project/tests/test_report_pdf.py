import fitz

from personal_project.report_pdf import render_pdf


def test_pdf_keeps_individual_paragraph_indentation():
    report = {
        "studentName": "Indent Test",
        "contentJson": {
            "blocks": [
                {"type": "paragraph", "depth": 1, "children": [{"text": "first level"}]},
                {"type": "paragraph", "depth": 2, "children": [{"text": "second level"}]},
            ]
        },
    }

    pdf = fitz.open(stream=render_pdf(report, []), filetype="pdf")
    first = pdf[0].search_for("first level")[0]
    second = pdf[0].search_for("second level")[0]

    assert second.x0 - first.x0 >= 12
