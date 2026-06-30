from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from ..utils import now_iso


RETRIEVAL_REHEARSAL_KIT_SCHEMA = "web-library.retrieval-rehearsal-kit/v1"
RETRIEVAL_REHEARSAL_CONFIG_BUNDLE_SCHEMA = "web-library.retrieval-config-bundle/v1"
RETRIEVAL_REHEARSAL_QUERIES = ["robot catalyst", "graph protein", "spectroscopy battery"]

LOCAL_FIELD_MAP = {
    "title": "record_name",
    "date": "pub_year",
    "doi": "doi_value",
    "authors": "author_list",
    "abstract": "summary_text",
    "tags": "tag_terms",
    "url": "landing_page",
    "venue": "venue_name",
    "item_type": "zotero_kind",
    "external_id": "source_key",
    "pdf_url": "pdf_link",
}
SQLITE_FIELD_MAP = {
    "title": "headline",
    "date": "year_value",
    "doi": "doi_token",
    "authors": "people",
    "abstract": "abstract_text",
    "tags": "topic_terms",
    "url": "landing",
    "venue": "venue_name",
    "item_type": "kind",
    "external_id": "uid",
    "pdf_url": "pdf_link",
}
MANIFEST_FIELD_MAP = {
    "title": "metadata.title_text",
    "date": "metadata.issued_year",
    "doi": "metadata.ids.doi",
    "authors": "metadata.contributors",
    "abstract": "metadata.abstract",
    "tags": "labels",
    "url": "links.landing",
    "venue": "container",
    "item_type": "kind",
    "external_id": "object_id",
    "pdf_url": "links.pdf",
}

REHEARSAL_RECORDS = [
    {
        "slug": "robot-catalyst",
        "title": "Robot Catalyst Screening for AI4S Materials",
        "year": "2026",
        "doi": "10.6060/AI4S-REH-001",
        "authors": "Ada Chen; Bo Li",
        "abstract": "Robot catalyst metadata for AI4S retrieval rehearsal and batch validation.",
        "keywords": "robot; catalyst; AI4S",
        "url": "https://example.test/ai4s/rehearsal/robot-catalyst",
        "venue": "AI4S Rehearsal Corpus",
        "item_type": "dataset",
        "pdf_url": "https://example.test/ai4s/rehearsal/robot-catalyst.pdf",
    },
    {
        "slug": "graph-protein",
        "title": "Graph Protein Interaction Benchmarks",
        "year": "2025",
        "doi": "10.6060/AI4S-REH-002",
        "authors": "Cjh Wang; Dana Xu",
        "abstract": "Graph protein benchmark metadata for heterogeneous source mapping.",
        "keywords": "graph; protein; benchmark",
        "url": "https://example.test/ai4s/rehearsal/graph-protein",
        "venue": "AI4S Rehearsal Corpus",
        "item_type": "dataset",
        "pdf_url": "https://example.test/ai4s/rehearsal/graph-protein.pdf",
    },
    {
        "slug": "spectroscopy-battery",
        "title": "Spectroscopy Battery Failure Reports",
        "year": "2024",
        "doi": "10.6060/AI4S-REH-003",
        "authors": "Eve Zhou; Finn Qian",
        "abstract": "Spectroscopy battery reports for metadata retrieval smoke tests.",
        "keywords": "spectroscopy; battery; failure",
        "url": "https://example.test/ai4s/rehearsal/spectroscopy-battery",
        "venue": "AI4S Rehearsal Corpus",
        "item_type": "report",
        "pdf_url": "https://example.test/ai4s/rehearsal/spectroscopy-battery.pdf",
    },
]

SQLITE_QUERY = (
    "SELECT uid, headline, year_value, doi_token, people, abstract_text, topic_terms, "
    "landing, venue_name, kind, pdf_link "
    "FROM records "
    "WHERE headline LIKE :like_query OR abstract_text LIKE :like_query OR topic_terms LIKE :like_query "
    "LIMIT :limit"
)


def safe_rehearsal_library_id(library_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", str(library_id or "library")).strip("-")
    return safe or "library"


def rehearsal_root(base_dir: Path, library_id: str) -> Path:
    return Path(base_dir) / "retrieval-rehearsal" / safe_rehearsal_library_id(library_id)


def write_local_csv(path: Path) -> None:
    fieldnames = [
        "source_key",
        "record_name",
        "pub_year",
        "doi_value",
        "author_list",
        "summary_text",
        "tag_terms",
        "landing_page",
        "venue_name",
        "zotero_kind",
        "pdf_link",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in REHEARSAL_RECORDS:
            writer.writerow(
                {
                    "source_key": f"csv-{record['slug']}",
                    "record_name": record["title"],
                    "pub_year": record["year"],
                    "doi_value": record["doi"],
                    "author_list": record["authors"],
                    "summary_text": record["abstract"],
                    "tag_terms": record["keywords"],
                    "landing_page": record["url"],
                    "venue_name": record["venue"],
                    "zotero_kind": record["item_type"],
                    "pdf_link": record["pdf_url"],
                }
            )


def write_manifest(path: Path) -> None:
    payload = {
        "schema": "web-library.retrieval-rehearsal-manifest/v1",
        "generated_at": now_iso(),
        "objects": [
            {
                "object_id": f"manifest-{record['slug']}",
                "kind": record["item_type"],
                "container": record["venue"],
                "labels": [part.strip() for part in record["keywords"].split(";")],
                "metadata": {
                    "title_text": record["title"],
                    "issued_year": record["year"],
                    "ids": {"doi": record["doi"]},
                    "contributors": record["authors"],
                    "abstract": record["abstract"],
                },
                "links": {
                    "landing": record["url"],
                    "pdf": record["pdf_url"],
                },
            }
            for record in REHEARSAL_RECORDS
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_sqlite(path: Path) -> None:
    if path.exists():
        path.unlink()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE records (
              uid TEXT PRIMARY KEY,
              headline TEXT NOT NULL,
              year_value TEXT,
              doi_token TEXT,
              people TEXT,
              abstract_text TEXT,
              topic_terms TEXT,
              landing TEXT,
              venue_name TEXT,
              kind TEXT,
              pdf_link TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO records (
              uid, headline, year_value, doi_token, people, abstract_text,
              topic_terms, landing, venue_name, kind, pdf_link
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"sqlite-{record['slug']}",
                    record["title"],
                    record["year"],
                    record["doi"],
                    record["authors"],
                    record["abstract"],
                    record["keywords"],
                    record["url"],
                    record["venue"],
                    record["item_type"],
                    record["pdf_url"],
                )
                for record in REHEARSAL_RECORDS
            ],
        )
        conn.commit()


def rehearsal_config_bundle(configs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": RETRIEVAL_REHEARSAL_CONFIG_BUNDLE_SCHEMA,
        "generated_at": now_iso(),
        "redacted": False,
        "sources": {
            "localfile": {
                "label": "Local CSV/JSONL",
                "source": "rehearsal",
                "configured": True,
                "paths": configs["localfile"]["paths"],
                "field_map": configs["localfile"]["field_map"],
                "config": configs["localfile"],
            },
            "sqlite": {
                "label": "SQLite",
                "source": "rehearsal",
                "configured": True,
                "config": configs["sqlite"],
            },
            "manifest": {
                "label": "Object Manifest",
                "source": "rehearsal",
                "configured": True,
                "config": configs["manifest"],
            },
        },
        "notes": [
            "Generated rehearsal sources use public synthetic metadata.",
            "Paths point to files under WEB_LIBRARY_DATA_DIR/retrieval-rehearsal.",
        ],
    }


def write_retrieval_rehearsal_kit(base_dir: Path, library_id: str) -> dict[str, Any]:
    root = rehearsal_root(base_dir, library_id)
    root.mkdir(parents=True, exist_ok=True)
    csv_path = root / "local-metadata.csv"
    sqlite_path = root / "catalog.sqlite"
    manifest_path = root / "object-manifest.json"
    write_local_csv(csv_path)
    write_sqlite(sqlite_path)
    write_manifest(manifest_path)
    configs = {
        "localfile": {"paths": [str(csv_path)], "field_map": LOCAL_FIELD_MAP},
        "sqlite": {
            "label": "Rehearsal SQLite",
            "path": str(sqlite_path),
            "query": SQLITE_QUERY,
            "field_map": SQLITE_FIELD_MAP,
        },
        "manifest": {
            "label": "Rehearsal Object Manifest",
            "manifest_path": str(manifest_path),
            "items_path": "objects",
            "field_map": MANIFEST_FIELD_MAP,
        },
    }
    return {
        "schema": RETRIEVAL_REHEARSAL_KIT_SCHEMA,
        "generated_at": now_iso(),
        "library_id": library_id,
        "root": str(root),
        "queries": RETRIEVAL_REHEARSAL_QUERIES,
        "files": [
            {"kind": "localfile_csv", "path": str(csv_path), "rows": len(REHEARSAL_RECORDS)},
            {"kind": "sqlite", "path": str(sqlite_path), "rows": len(REHEARSAL_RECORDS), "table": "records"},
            {"kind": "object_manifest", "path": str(manifest_path), "rows": len(REHEARSAL_RECORDS)},
        ],
        "configs": configs,
        "config_bundle": rehearsal_config_bundle(configs),
        "sources": ["localfile", "sqlite", "manifest"],
        "message": "Generated rehearsal CSV, SQLite and Object Manifest sources.",
    }
