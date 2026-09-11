import pytest

from odi.db.router import validate_presentation_template_for_start


def test_presentation_start_requires_uploaded_slide_pdf():
    with pytest.raises(ValueError, match="발표 자료 PDF"):
        validate_presentation_template_for_start(
            {"type": "presentation", "files": {"slide": None}}
        )


def test_presentation_start_accepts_slide_storage_path():
    validate_presentation_template_for_start(
        {
            "type": "presentation",
            "files": {"slide": {"storage_path": "storage/odi/users/7/temp/slides/deck.pdf"}},
        }
    )
