from __future__ import annotations

from zotero_web_library.structured_text import extract_block, extract_structured_fields, source_field_for_block, upsert_block


def test_extract_structured_fields_reads_configured_blocks() -> None:
    values = extract_structured_fields(
        "[remark]团队备注[remarkend]\n[title_zh]中文标题[title_zhend]\nlegacy: keep",
        "English abstract\n[abstract_zh]中文摘要[abstract_zhend]",
    )
    assert values == {
        "remark": "团队备注",
        "title_zh": "中文标题",
        "abstract_zh": "中文摘要",
    }


def test_extract_block_ignores_invalid_or_repeated_blocks() -> None:
    assert extract_block("[remark]only start", "remark") == ""
    assert extract_block("[remark]a[remarkend][remark]b[remarkend]", "remark") == ""


def test_upsert_block_replaces_target_without_overwriting_other_text() -> None:
    original = "[remark]旧备注[remarkend]\n[title_zh]旧标题[title_zhend]\nlegacy: keep"
    updated = upsert_block(original, "remark", "新备注")
    assert updated == "[remark]新备注[remarkend]\n[title_zh]旧标题[title_zhend]\nlegacy: keep"


def test_upsert_block_appends_when_target_missing() -> None:
    original = "legacy: keep"
    updated = upsert_block(original, "title_zh", "中文标题")
    assert updated == "legacy: keep\n[title_zh]中文标题[title_zhend]"


def test_source_field_for_block_matches_documented_sources() -> None:
    assert source_field_for_block("remark") == "extra"
    assert source_field_for_block("title_zh") == "extra"
    assert source_field_for_block("abstract_zh") == "abstractNote"
