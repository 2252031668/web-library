from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zotero_web_library import app_store
from zotero_web_library.sources import SourceError, create_local_copy, create_read_only_source
from zotero_web_library.sync import mark_conflicts_for_changed_keys, prepare_sync_payloads
from zotero_web_library.web import create_app
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
    assert item["semantic"]["rating"] == ["⭐⭐"]
    assert item["semantic"]["reading_status"] == ["/reading"]
    repo.set_reading_status("ITEM0001", "unread")
    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert item["semantic"]["reading_status"] == []


def test_state_exposes_structured_fields_from_extra_and_abstract_note(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_read_only_source(zotero_fixture)
    item = next(item for item in ZoteroRepository(library).state()["items"] if item["key"] == "ITEM0001")
    assert item["structured"] == {
        "remark": "李飞飞团队",
        "title_zh": "开放词汇机器人",
        "abstract_zh": "中文摘要",
    }


def test_update_structured_field_preserves_other_blocks_and_legacy_text(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)

    repo.update_structured_field("ITEM0001", "remark", "新备注")
    repo.update_structured_field("ITEM0001", "abstract_zh", "新的中文摘要")

    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert item["structured"]["remark"] == "新备注"
    assert item["structured"]["title_zh"] == "开放词汇机器人"
    assert item["structured"]["abstract_zh"] == "新的中文摘要"
    assert "legacy: keep" in item["fields"]["extra"]
    assert "[title_zh]开放词汇机器人[title_zhend]" in item["fields"]["extra"]
    assert item["fields"]["abstractNote"].startswith("English abstract")


def test_update_structured_field_appends_missing_block_without_overwriting_field(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)

    repo.update_item_field("ITEM0001", "extra", "legacy only")
    repo.update_structured_field("ITEM0001", "title_zh", "追加标题")

    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert item["structured"]["title_zh"] == "追加标题"
    assert item["fields"]["extra"] == "legacy only\n[title_zh]追加标题[title_zhend]"


def test_update_item_field_rejects_unknown_native_field_name(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)

    with pytest.raises(ValueError, match="Zotero 原生字段不存在"):
        repo.update_item_field("ITEM0001", "title_zh", "不允许新增")


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
    app_store.upsert_tag_shortcut(library["library_id"], "#多提示词", "#2563eb")
    app_store.mark_tag_shortcuts_initialized(library["library_id"])
    app_store.delete_tag_shortcut(library["library_id"], "#多提示词")
    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert "#多提示词" in item["semantic"]["nested"]
    shortcut_tags = {item["tag"] for item in app_store.list_tag_shortcuts(library["library_id"])}
    assert "#多提示词" not in shortcut_tags


def test_tag_shortcuts_seed_from_existing_nested_tags(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    shortcuts = ZoteroRepository(library).state()["tag_shortcuts"]
    shortcut_tags = {item["tag"] for item in shortcuts}
    assert {"#VLA/端到端", "#有代码"}.issubset(shortcut_tags)
    assert app_store.tag_shortcuts_initialized(library["library_id"]) is True


def test_deleted_shortcut_does_not_reseed_after_reload(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)
    repo.state()
    app_store.delete_tag_shortcut(library["library_id"], "#有代码")
    reloaded = repo.state()
    assert "#有代码" not in {item["tag"] for item in reloaded["tag_shortcuts"]}


def test_tag_writes_use_zotero_tag_name_with_hash_prefix(zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)
    repo.add_tag("ITEM0001", "多提示词")
    repo.set_reading_status("ITEM0001", "reading")
    repo.set_rating("ITEM0001", 2)

    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert "#多提示词" in item["semantic"]["nested"]
    assert item["semantic"]["reading_status"] == ["/reading"]
    assert item["semantic"]["rating"] == ["⭐⭐"]

    with sqlite3.connect(Path(library["data_path"]) / "zotero.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        assert "type" not in {row["name"] for row in conn.execute("PRAGMA table_info(tags)").fetchall()}
        assert "type" in {row["name"] for row in conn.execute("PRAGMA table_info(itemTags)").fetchall()}
        row = conn.execute(
            """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON t.tagID = it.tagID
            JOIN items i ON i.itemID = it.itemID
            WHERE i.key = ? AND t.name = ?
            """,
            ("ITEM0001", "#多提示词"),
        ).fetchone()
        assert row is not None


def test_semantic_tag_parse_and_write_boundaries_match_current_product_scope(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    repo = ZoteroRepository(library)

    repo.add_tag("ITEM0001", "多提示词")
    repo.set_rating("ITEM0001", 4)
    repo.set_reading_status("ITEM0001", "read")

    item = next(item for item in repo.state()["items"] if item["key"] == "ITEM0001")
    assert "#多提示词" in item["semantic"]["nested"]
    assert item["semantic"]["rating"] == ["⭐⭐⭐⭐"]
    assert item["semantic"]["reading_status"] == ["/done"]
    assert item["semantic"]["venue_rank"] == ["CCF-A"]

    with sqlite3.connect(Path(library["data_path"]) / "zotero.sqlite") as conn:
        conn.row_factory = sqlite3.Row
        names = {
            row["name"]
            for row in conn.execute(
                """
                SELECT t.name
                FROM itemTags it
                JOIN tags t ON t.tagID = it.tagID
                JOIN items i ON i.itemID = it.itemID
                WHERE i.key = ?
                """,
                ("ITEM0001",),
            ).fetchall()
        }
    assert "#多提示词" in names
    assert "⭐⭐⭐⭐" in names
    assert "/done" in names
    assert "CCF-A" in names


def test_structured_field_api_updates_supported_keys_only(
    zotero_fixture: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ZOTERO_WEB_LIBRARY_DATA", str(tmp_path / "app-data"))
    library = create_local_copy(zotero_fixture)
    client = create_app().test_client()

    response = client.patch(
        f"/api/library/{library['library_id']}/items/ITEM0001/structured-field",
        json={"field": "remark", "value": "接口备注"},
    )
    assert response.status_code == 200

    invalid = client.patch(
        f"/api/library/{library['library_id']}/items/ITEM0001/structured-field",
        json={"field": "venue_rank", "value": "不允许"},
    )
    assert invalid.status_code == 400

    item = next(item for item in ZoteroRepository(library).state()["items"] if item["key"] == "ITEM0001")
    assert item["structured"]["remark"] == "接口备注"
