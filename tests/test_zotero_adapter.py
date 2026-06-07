from __future__ import annotations

from pathlib import Path

import pytest

from zotero_web_library import app_store
from zotero_web_library.sources import SourceError, create_local_copy, create_read_only_source
from zotero_web_library.sync import mark_conflicts_for_changed_keys, prepare_sync_payloads
from zotero_web_library.zotero_adapter import ZoteroRepository


def test_adapter_reads_items_collections_tags_and_attachments(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_read_only_source(zotero_fixture)
    repo = ZoteroRepository(library)
    state = repo.state()
    assert state["collections"][0]["name"] == "VLA"
    assert state["items"][0]["title"] == "OpenVLA"
    assert state["items"][0]["semantic"]["rating"] == ["★★★★★"]
    assert "#有代码" in state["items"][0]["semantic"]["nested"]
    assert "/done" in state["items"][0]["semantic"]["reading_status"]
    assert state["items"][0]["attachments"][0]["resolved_path"].endswith("storage\\ATTACH01\\paper.pdf") or state["items"][0]["attachments"][0]["resolved_path"].endswith("storage/ATTACH01/paper.pdf")
    assert state["items"][0]["attachments"][0]["kind"] == "pdf"
    assert state["items"][0]["attachments"][0]["status"] == "openable"
    assert any(attachment["status"] == "missing" for attachment in state["items"][0]["attachments"])
    assert any(badge["label"] == "PDF" for badge in state["items"][0]["attachment_badges"])
    assert any(badge["label"] == "Note" for badge in state["items"][0]["attachment_badges"])


def test_read_only_blocks_edits(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_read_only_source(zotero_fixture)
    with pytest.raises(SourceError):
        ZoteroRepository(library).create_collection("New")


def test_local_copy_allows_collection_and_field_edits(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)
    repo.create_collection("New")
    repo.update_item_field("ITEM0001", "title", "Changed")
    repo.add_tag("ITEM0001", "New/Tag")
    repo.set_rating("ITEM0001", 2)
    repo.set_reading_status("ITEM0001", "reading")
    state = repo.state()
    assert any(collection["name"] == "New" for collection in state["collections"])
    item = next(item for item in state["items"] if item["key"] == "ITEM0001")
    assert item["title"] == "Changed"
    assert "#New/Tag" in item["semantic"]["nested"]
    assert item["semantic"]["rating"] == ["★★"]
    assert item["semantic"]["reading_status"] == ["/reading"]
    repo.set_reading_status("ITEM0001", "unread")
    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert item["semantic"]["reading_status"] == []


def test_local_copy_reparents_collection_and_prepares_sync_payloads(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)
    repo.create_collection("Parent")
    state = repo.state()
    parent = next(collection for collection in state["collections"] if collection["name"] == "Parent")
    repo.reparent_collection("COLL0001", parent["key"])
    repo.set_collection_membership("ITEM0001", "COLL0001", False)
    payloads = prepare_sync_payloads(library["library_id"])
    assert any(payload["operation"] == "reparent_collection" for payload in payloads)
    assert any(payload["operation"] == "set_collection_membership" for payload in payloads)
    conflicted = mark_conflicts_for_changed_keys(library["library_id"], {"COLL0001"})
    assert conflicted


def test_deleting_shortcut_does_not_remove_item_tag(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)
    repo.add_tag("ITEM0001", "多提示词")
    app_store.upsert_tag_shortcut(library["library_id"], "多提示词", "#2563eb")
    app_store.delete_tag_shortcut(library["library_id"], "#多提示词")
    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert "#多提示词" in item["semantic"]["nested"]
    assert app_store.list_tag_shortcuts(library["library_id"]) == []
