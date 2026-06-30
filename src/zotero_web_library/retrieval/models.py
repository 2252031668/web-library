from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from zotero_web_library.metadata_import import ImportedItem


@dataclass
class RetrievedCandidate:
    source: str
    external_id: str
    item: ImportedItem
    raw: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    landing_url: str = ""
    pdf_url: str = ""
    also_seen_in: list[str] = field(default_factory=list)

    def as_dict(self, *, include_raw: bool = False) -> dict[str, Any]:
        fields = self.item.fields
        sources = source_names(self)
        payload = {
            "source": self.source,
            "external_id": self.external_id,
            "item_type": self.item.item_type,
            "title": fields.get("title", ""),
            "year": year_from_fields(fields),
            "venue": venue_from_fields(fields),
            "abstract": fields.get("abstractNote", ""),
            "creators": [creator.__dict__ for creator in self.item.creators],
            "tags": self.item.tags,
            "identifiers": self.item.identifiers,
            "item": self.item.as_dict(),
            "confidence": self.confidence,
            "confidence_label": confidence_label(self.confidence),
            "evidence": self.evidence,
            "rank_reasons": rank_reasons(self),
            "landing_url": self.landing_url or fields.get("url", ""),
            "pdf_url": self.pdf_url,
            "also_seen_in": self.also_seen_in,
            "sources": sources,
            "source_count": len(sources),
            "multi_source": len(sources) > 1,
        }
        if include_raw:
            payload["raw"] = self.raw
        return payload


@dataclass
class SourceSearchResult:
    source: str
    ok: bool
    candidates: list[RetrievedCandidate] = field(default_factory=list)
    error: str = ""
    error_kind: str = ""
    action: str = ""
    elapsed_ms: int = 0
    rate_limit_wait_ms: int = 0
    rate_limit_seconds: float = 0.0

    def stats_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "count": len(self.candidates),
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "rate_limit_wait_ms": self.rate_limit_wait_ms,
            "rate_limit_seconds": self.rate_limit_seconds,
        }
        if self.error_kind:
            payload["error_kind"] = self.error_kind
        if self.action:
            payload["action"] = self.action
        return payload


def year_from_fields(fields: dict[str, str]) -> str:
    value = str(fields.get("date") or "")
    for index in range(max(0, len(value) - 3)):
        chunk = value[index : index + 4]
        if chunk.isdigit():
            return chunk
    return ""


def venue_from_fields(fields: dict[str, str]) -> str:
    for key in ("publicationTitle", "proceedingsTitle", "conferenceName", "repository"):
        value = str(fields.get(key) or "").strip()
        if value:
            return value
    return ""


def source_names(candidate: RetrievedCandidate) -> list[str]:
    values: list[str] = []
    for source in [candidate.source, *candidate.also_seen_in]:
        if source and source not in values:
            values.append(source)
    return values


def confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "高可信"
    if confidence >= 0.65:
        return "中可信"
    return "低可信"


def rank_reasons(candidate: RetrievedCandidate) -> list[str]:
    identifiers = candidate.item.identifiers
    reasons: list[str] = []
    strong_labels = [
        ("doi", "DOI"),
        ("pmid", "PMID"),
        ("pmcid", "PMCID"),
        ("arxiv", "arXiv ID"),
        ("ads_bibcode", "ADS Bibcode"),
        ("isbn", "ISBN"),
    ]
    matched = [label for key, label in strong_labels if identifiers.get(key)]
    if matched:
        reasons.append(f"强标识符：{' / '.join(matched)}")
    if candidate.also_seen_in:
        sources = " / ".join([candidate.source, *candidate.also_seen_in])
        reasons.append(f"多源命中：{sources}")
    if candidate.confidence >= 0.85:
        reasons.append("元数据置信度高")
    elif candidate.confidence >= 0.65:
        reasons.append("元数据置信度中")
    if candidate.pdf_url:
        reasons.append("包含 PDF 链接")
    if candidate.landing_url or candidate.item.fields.get("url"):
        reasons.append("包含来源页")
    for evidence in candidate.evidence:
        if evidence and evidence not in reasons and evidence not in matched:
            reasons.append(evidence)
    return reasons or ["基础元数据"]
