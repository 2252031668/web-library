from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlockSpec:
    key: str
    start: str
    end: str
    field_name: str


BLOCK_SPECS = {
    "remark": BlockSpec("remark", "[remark]", "[remarkend]", "extra"),
    "title_zh": BlockSpec("title_zh", "[title_zh]", "[title_zhend]", "extra"),
    "abstract_zh": BlockSpec("abstract_zh", "[abstract_zh]", "[abstract_zhend]", "abstractNote"),
}


def source_field_for_block(block_key: str) -> str:
    try:
        return BLOCK_SPECS[block_key].field_name
    except KeyError as exc:
        raise ValueError("未知结构化字段。") from exc


def extract_block(text: str, block_key: str) -> str:
    spec = _spec(block_key)
    value = str(text or "")
    if value.count(spec.start) == 0 and value.count(spec.end) == 0:
        return ""
    if value.count(spec.start) != 1 or value.count(spec.end) != 1:
        return ""
    start_index = value.find(spec.start)
    end_index = value.find(spec.end)
    body_start = start_index + len(spec.start)
    if start_index < 0 or end_index < body_start:
        return ""
    return value[body_start:end_index].strip()


def extract_structured_fields(extra_text: str, abstract_note: str) -> dict[str, str]:
    return {
        "remark": extract_block(extra_text, "remark"),
        "title_zh": extract_block(extra_text, "title_zh"),
        "abstract_zh": extract_block(abstract_note, "abstract_zh"),
    }


def upsert_block(text: str, block_key: str, content: str) -> str:
    spec = _spec(block_key)
    value = str(text or "")
    clean_content = str(content or "").strip()
    start_index, end_index = _find_valid_block(value, spec)
    replacement = f"{spec.start}{clean_content}{spec.end}"
    if start_index is not None and end_index is not None:
        return f"{value[:start_index]}{replacement}{value[end_index:]}"
    if not value:
        return replacement
    separator = "" if value.endswith(("\n", "\r")) else "\n"
    return f"{value}{separator}{replacement}"


def _spec(block_key: str) -> BlockSpec:
    try:
        return BLOCK_SPECS[block_key]
    except KeyError as exc:
        raise ValueError("未知结构化字段。") from exc


def _find_valid_block(text: str, spec: BlockSpec) -> tuple[int | None, int | None]:
    value = str(text or "")
    if value.count(spec.start) != 1 or value.count(spec.end) != 1:
        return None, None
    start_index = value.find(spec.start)
    end_tag_index = value.find(spec.end)
    if start_index < 0 or end_tag_index < start_index + len(spec.start):
        return None, None
    return start_index, end_tag_index + len(spec.end)
