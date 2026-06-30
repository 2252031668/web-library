from __future__ import annotations

import re

from .models import RetrievedCandidate, year_from_fields
from zotero_web_library.metadata_import import (
    normalize_ads_bibcode,
    normalize_arxiv_id,
    normalize_doi,
    normalize_isbn,
    normalize_pmcid,
    normalize_pmid,
)


def strong_identifier_keys(candidate: RetrievedCandidate) -> list[str]:
    item = candidate.item
    fields = item.fields
    identifiers = item.identifiers
    haystack = "\n".join(str(value or "") for value in fields.values())
    values = {
        "doi": normalize_doi(identifiers.get("doi", "") or fields.get("DOI", "") or haystack),
        "pmid": normalize_pmid(identifiers.get("pmid", "") or fields.get("PMID", "") or fields.get("extra", "")),
        "pmcid": normalize_pmcid(identifiers.get("pmcid", "") or fields.get("PMCID", "") or fields.get("extra", "")),
        "arxiv": normalize_arxiv_id(identifiers.get("arxiv", "") or fields.get("extra", "") or fields.get("url", "") or fields.get("DOI", "")),
        "ads_bibcode": normalize_ads_bibcode(identifiers.get("ads_bibcode", "") or fields.get("extra", "")),
        "isbn": normalize_isbn(identifiers.get("isbn", "") or fields.get("ISBN", "")),
    }
    return [f"{key}:{value}" for key, value in values.items() if value]


def weak_dedupe_keys(candidate: RetrievedCandidate) -> list[str]:
    title_key = normalized_title(candidate.item.fields.get("title", ""))
    if len(title_key) < 12:
        return []
    year = year_from_fields(candidate.item.fields)
    first_creator = normalized_creator(candidate)
    keys: list[str] = []
    if year and first_creator:
        keys.append(f"title-year-author:{title_key}:{year}:{first_creator}")
    elif year:
        keys.append(f"title-year:{title_key}:{year}")
    return keys


def candidate_merge_keys(candidate: RetrievedCandidate) -> list[str]:
    return [*strong_identifier_keys(candidate), *weak_dedupe_keys(candidate)]


def merge_candidates(candidates: list[RetrievedCandidate]) -> list[RetrievedCandidate]:
    merged: list[RetrievedCandidate] = []
    index: dict[str, RetrievedCandidate] = {}
    for candidate in candidates:
        keys = candidate_merge_keys(candidate)
        existing = next((index[key] for key in keys if key in index), None)
        if existing is None:
            merged.append(candidate)
            for key in keys:
                index[key] = candidate
            continue
        _merge_into(existing, candidate)
        for key in candidate_merge_keys(existing):
            index[key] = existing
        for key in keys:
            index[key] = existing
    return sorted(merged, key=_sort_key)


def _merge_into(target: RetrievedCandidate, incoming: RetrievedCandidate) -> None:
    if incoming.source != target.source and incoming.source not in target.also_seen_in:
        target.also_seen_in.append(incoming.source)
    target.confidence = max(target.confidence, incoming.confidence)
    for evidence in incoming.evidence:
        if evidence not in target.evidence:
            target.evidence.append(evidence)
    for key, value in incoming.item.identifiers.items():
        target.item.identifiers.setdefault(key, value)
    for key, value in incoming.item.fields.items():
        if value and not target.item.fields.get(key):
            target.item.fields[key] = value
    if incoming.pdf_url and not target.pdf_url:
        target.pdf_url = incoming.pdf_url
    if incoming.landing_url and not target.landing_url:
        target.landing_url = incoming.landing_url


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def normalized_creator(candidate: RetrievedCandidate) -> str:
    if not candidate.item.creators:
        return ""
    creator = candidate.item.creators[0]
    value = creator.last_name or " ".join([creator.first_name, creator.last_name]).strip()
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _sort_key(candidate: RetrievedCandidate) -> tuple[int, int, float, str]:
    has_identifier = 1 if strong_identifier_keys(candidate) else 0
    source_count = len({candidate.source, *candidate.also_seen_in})
    return (-has_identifier, -source_count, -candidate.confidence, candidate.item.fields.get("title", "").casefold())
