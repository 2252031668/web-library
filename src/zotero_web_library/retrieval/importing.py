from __future__ import annotations

from typing import Any

from zotero_web_library.metadata_import import (
    ImportedCreator,
    ImportedItem,
    normalize_ads_bibcode,
    normalize_arxiv_id,
    normalize_doi,
    normalize_isbn,
    normalize_pmcid,
    normalize_pmid,
)


class CandidateImportError(ValueError):
    pass


def imported_items_from_candidates(candidates: Any) -> list[ImportedItem]:
    if not isinstance(candidates, list):
        raise CandidateImportError("candidates 必须是数组。")
    items = [imported_item_from_candidate(candidate) for candidate in candidates]
    if not items:
        raise CandidateImportError("请选择要导入的候选条目。")
    return items


def imported_item_from_candidate(candidate: Any) -> ImportedItem:
    if not isinstance(candidate, dict):
        raise CandidateImportError("候选条目格式无效。")
    payload = candidate.get("item") if isinstance(candidate.get("item"), dict) else candidate
    if not isinstance(payload, dict):
        raise CandidateImportError("候选条目缺少 item 数据。")
    item_type = str(payload.get("item_type") or "").strip()
    if not item_type:
        raise CandidateImportError("候选条目缺少 item_type。")

    fields = _string_dict(payload.get("fields") or {})
    _fill_field(fields, "title", candidate.get("title"))
    _fill_field(fields, "abstractNote", candidate.get("abstract"))
    _fill_field(fields, "url", candidate.get("landing_url"))

    raw_identifiers = _string_dict(candidate.get("identifiers") or {})
    raw_identifiers.update(_string_dict(payload.get("identifiers") or {}))
    identifiers = _normalized_identifiers(fields, raw_identifiers)
    _backfill_identifier_fields(fields, identifiers)
    _append_identifier_extra(fields, identifiers)

    creator_payloads = payload.get("creators") or candidate.get("creators") or []
    creators = [_creator_from_payload(value) for value in creator_payloads if isinstance(value, dict)]
    tag_payloads = payload.get("tags") or candidate.get("tags") or []
    tags = [str(value).strip() for value in tag_payloads if str(value).strip()]
    source = str(payload.get("source") or candidate.get("source") or "retrieval").strip() or "retrieval"
    return ImportedItem(
        item_type=item_type,
        fields=fields,
        creators=[creator for creator in creators if creator.last_name],
        tags=tags,
        identifiers=identifiers,
        source=source,
    )


def _fill_field(fields: dict[str, str], key: str, value: Any) -> None:
    clean = str(value or "").strip()
    if clean and not fields.get(key):
        fields[key] = clean


def _normalized_identifiers(fields: dict[str, str], identifiers: dict[str, str]) -> dict[str, str]:
    haystack = "\n".join(str(value or "") for value in fields.values())
    values = {
        "doi": normalize_doi(identifiers.get("doi", "") or fields.get("DOI", "") or haystack),
        "pmid": normalize_pmid(identifiers.get("pmid", "") or fields.get("PMID", "") or fields.get("extra", "")),
        "pmcid": normalize_pmcid(identifiers.get("pmcid", "") or fields.get("PMCID", "") or fields.get("extra", "")),
        "arxiv": normalize_arxiv_id(identifiers.get("arxiv", "") or fields.get("extra", "") or fields.get("url", "") or fields.get("DOI", "")),
        "ads_bibcode": normalize_ads_bibcode(identifiers.get("ads_bibcode", "") or fields.get("extra", "")),
        "isbn": normalize_isbn(identifiers.get("isbn", "") or fields.get("ISBN", "")),
    }
    return {key: value for key, value in values.items() if value}


def _backfill_identifier_fields(fields: dict[str, str], identifiers: dict[str, str]) -> None:
    if identifiers.get("doi") and not fields.get("DOI"):
        fields["DOI"] = identifiers["doi"]
    if identifiers.get("isbn") and not fields.get("ISBN"):
        fields["ISBN"] = identifiers["isbn"]


def _append_identifier_extra(fields: dict[str, str], identifiers: dict[str, str]) -> None:
    labels = {
        "pmid": "PMID",
        "pmcid": "PMCID",
        "arxiv": "arXiv",
        "ads_bibcode": "ADS Bibcode",
    }
    existing = fields.get("extra", "")
    extra_lines = [existing] if existing else []
    existing_lower = existing.casefold()
    for key, label in labels.items():
        value = identifiers.get(key, "")
        line = f"{label}: {value}" if value else ""
        if line and line.casefold() not in existing_lower:
            extra_lines.append(line)
    if extra_lines:
        fields["extra"] = "\n".join(extra_lines)


def _creator_from_payload(payload: dict[str, Any]) -> ImportedCreator:
    first_name = str(payload.get("first_name") or payload.get("firstName") or "").strip()
    last_name = str(payload.get("last_name") or payload.get("lastName") or "").strip()
    creator_type = str(payload.get("creator_type") or payload.get("creatorType") or "author").strip() or "author"
    name = str(payload.get("name") or "").strip()
    if name and not last_name:
        if "," in name:
            last_name, first_name = [part.strip() for part in name.split(",", 1)]
        else:
            parts = name.split()
            if len(parts) == 1:
                last_name = parts[0]
            elif parts:
                first_name = " ".join(parts[:-1])
                last_name = parts[-1]
    return ImportedCreator(first_name=first_name, last_name=last_name, creator_type=creator_type)


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, raw in value.items():
        clean_key = str(key).strip()
        if not clean_key or raw is None:
            continue
        clean_value = str(raw).strip()
        if clean_value:
            cleaned[clean_key] = clean_value
    return cleaned
