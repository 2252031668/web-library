from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1


RATING_RE = re.compile(r"^(?:#Rating/)?([1-5])$")
STAR_RE = re.compile(r"^[★☆⭐🌟]{1,5}$")
VENUE_RE = re.compile(
    r"^(?:#Venue/)?(?:(CCF[-/ ]?[ABC])|(JCR\s*Q[1-4])|(中科院[一二三四1-4]区)|(SCI|EI|北核|CSCD))$",
    re.IGNORECASE,
)
READING_RE = re.compile(r"^(?:/)?(done|todo|to-read|read|unread|reading|未读|已读|待读)$", re.IGNORECASE)
COLOR_PALETTE = [
    "#2563eb",
    "#059669",
    "#dc2626",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#be123c",
    "#4f46e5",
    "#15803d",
    "#c2410c",
]


@dataclass(frozen=True)
class SemanticTags:
    rating: list[str]
    nested: list[str]
    venue_rank: list[str]
    code_status: list[str]
    reading_status: list[str]
    plain: list[str]
    raw: list[str]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "rating": self.rating,
            "nested": self.nested,
            "venue_rank": self.venue_rank,
            "code_status": self.code_status,
            "reading_status": self.reading_status,
            "plain": self.plain,
            "raw": self.raw,
        }


def _clean(tag: str) -> str:
    return " ".join(str(tag or "").strip().split())


def parse_tags(tags: list[str] | tuple[str, ...], custom_rules: list[dict[str, str]] | None = None) -> SemanticTags:
    buckets = {
        "rating": [],
        "nested": [],
        "venue_rank": [],
        "code_status": [],
        "reading_status": [],
        "plain": [],
    }
    raw: list[str] = []
    for value in tags or []:
        tag = _clean(value)
        if not tag:
            continue
        raw.append(tag)
        normalized = tag.replace(" ", "")
        custom_bucket = _custom_bucket(tag, custom_rules or [])
        if custom_bucket and custom_bucket in buckets:
            buckets[custom_bucket].append(tag)
        elif STAR_RE.match(normalized) or RATING_RE.match(normalized):
            buckets["rating"].append(tag)
        elif VENUE_RE.match(tag):
            buckets["venue_rank"].append(tag)
        elif READING_RE.match(tag):
            buckets["reading_status"].append(tag)
        elif tag.startswith("#") and "/" in tag:
            buckets["nested"].append(tag)
        elif tag.startswith("#"):
            buckets["nested"].append(tag)
        else:
            buckets["plain"].append(tag)
    return SemanticTags(raw=raw, **buckets)


def first_value(values: list[str]) -> str:
    return values[0] if values else ""


def stable_tag_color(tag: str) -> str:
    digest = sha1(str(tag or "").strip().encode("utf-8")).hexdigest()
    return COLOR_PALETTE[int(digest[:8], 16) % len(COLOR_PALETTE)]


def normalize_hash_tag(tag: str) -> str:
    value = _clean(tag)
    if not value:
        return ""
    if value.startswith("#"):
        body = _clean(value[1:])
        return f"#{body}" if body else ""
    if value.startswith("/"):
        return value
    return f"#{value}"


def display_hash_tag(tag: str) -> str:
    value = _clean(tag)
    return value[1:] if value.startswith("#") else value


def rating_number(tags: list[str] | tuple[str, ...]) -> int:
    parsed = parse_tags(tags)
    if not parsed.rating:
        return 0
    value = parsed.rating[0].strip()
    rating_match = RATING_RE.match(value)
    if rating_match:
        return int(rating_match.group(1))
    return min(5, max(0, sum(1 for char in value if char in {"★", "⭐", "🌟"})))


def rating_tag(value: int) -> str:
    rating = max(0, min(5, int(value)))
    return "⭐" * rating if rating else ""


def _custom_bucket(tag: str, rules: list[dict[str, str]]) -> str:
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        pattern = str(rule.get("pattern") or "")
        bucket = str(rule.get("bucket") or "")
        if not pattern or not bucket:
            continue
        try:
            if re.search(pattern, tag):
                return bucket
        except re.error:
            continue
    return ""
