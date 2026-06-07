from __future__ import annotations

from typing import Any

from . import app_store


def prepare_sync_payloads(library_id: str) -> list[dict[str, Any]]:
    """Return safe future-sync candidates without writing to any Zotero source sqlite."""
    payloads: list[dict[str, Any]] = []
    for entry in app_store.pending_journal(library_id):
        payloads.append(
            {
                "journal_id": entry["journal_id"],
                "status": entry["status"],
                "operation": entry["operation"],
                "object_kind": entry["object_kind"],
                "object_key": entry["object_key"],
                "payload": entry["payload"],
                "target": "zotero_api_candidate",
            }
        )
    return payloads


def mark_conflicts_for_changed_keys(library_id: str, changed_keys: set[str]) -> list[int]:
    conflicted: list[int] = []
    for entry in app_store.pending_journal(library_id):
        if entry["object_key"] in changed_keys:
            app_store.mark_conflicted(library_id, int(entry["journal_id"]))
            conflicted.append(int(entry["journal_id"]))
    return conflicted
