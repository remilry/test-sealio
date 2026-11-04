from scripts.db_schema import OUTPUT, render


def test_the_schema_doc_is_up_to_date() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == render(), (
        "docs/DB_SCHEMA.md is out of date: run `make db-schema`."
    )
