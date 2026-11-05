"""The common form representation: locators of both formats, shared label helpers."""

from app.modules.forms.parsing.labels import leader_runs, unique_key
from app.modules.forms.parsing.schema import DocxLocator, DocxWriteMode, ParsedField, PdfLocator

FIELD = {"key": "uid", "section": "Table 1", "label": "UID", "kind": "text"}


def test_a_field_locator_is_read_by_its_format() -> None:
    docx = ParsedField.model_validate(
        {
            **FIELD,
            "locator": {
                "format": "docx",
                "table": 1,
                "row": 0,
                "cell": 1,
                "paragraph": 0,
                "mode": "in_paragraph",
            },
        }
    )
    pdf = ParsedField.model_validate(
        {
            **FIELD,
            "locator": {
                "format": "pdf",
                "page": 0,
                "box": {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                "baseline": 9,
                "font_size": 10,
            },
        }
    )

    assert isinstance(docx.locator, DocxLocator)
    assert docx.locator.mode == DocxWriteMode.IN_PARAGRAPH
    assert docx.locator.start is None
    assert isinstance(pdf.locator, PdfLocator)


def test_leader_runs_ignore_a_sentence_ending_ellipsis() -> None:
    assert leader_runs("Tender (No. …….., type of work)") == [(12, 16)]
    assert leader_runs("Name: ............") == [(6, 18)]
    assert leader_runs("and so on...") == []


def test_duplicate_labels_get_numbered_keys() -> None:
    seen: set[str] = set()

    assert unique_key("For foreign bidders: details", seen) == "for_foreign_bidders_details"
    assert unique_key("For foreign bidders: details", seen) == "for_foreign_bidders_details_2"
