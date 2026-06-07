from __future__ import annotations

from zotero_web_library.semantic_tags import display_hash_tag, normalize_hash_tag, parse_tags, stable_tag_color


def test_semantic_tags_split_rating_nested_reading_venue_and_plain() -> None:
    parsed = parse_tags(["★★★★★", "#VLA/端到端", "CCF-A", "#有代码", "/done", "普通标签"]).as_dict()
    assert parsed["rating"] == ["★★★★★"]
    assert parsed["nested"] == ["#VLA/端到端", "#有代码"]
    assert parsed["venue_rank"] == ["CCF-A"]
    assert parsed["code_status"] == []
    assert parsed["reading_status"] == ["/done"]
    assert parsed["plain"] == ["普通标签"]


def test_custom_semantic_rule_maps_tag_to_bucket() -> None:
    parsed = parse_tags(["顶会"], [{"bucket": "venue_rank", "pattern": "^顶会$", "enabled": True}]).as_dict()
    assert parsed["venue_rank"] == ["顶会"]


def test_stable_tag_color_is_deterministic() -> None:
    assert stable_tag_color("#VLA") == stable_tag_color("#VLA")
    assert stable_tag_color("#VLA").startswith("#")


def test_hash_tag_normalization_and_display() -> None:
    assert normalize_hash_tag("多提示词") == "#多提示词"
    assert normalize_hash_tag("#多提示词") == "#多提示词"
    assert normalize_hash_tag("# 多提示词") == "#多提示词"
    assert normalize_hash_tag("/done") == "/done"
    assert display_hash_tag("#多提示词") == "多提示词"
