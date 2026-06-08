from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def create_fixture_zotero(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "storage" / "ATTACH01").mkdir(parents=True)
    (root / "storage" / "ATTACH01" / "paper.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (root / "storage" / "HTML01").mkdir(parents=True)
    (root / "storage" / "HTML01" / "snapshot.html").write_text("<html></html>", encoding="utf-8")
    (root / "storage" / "IMAGE01").mkdir(parents=True)
    (root / "storage" / "IMAGE01" / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    conn = sqlite3.connect(root / "zotero.sqlite")
    conn.executescript(
        """
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INTEGER, dateAdded TEXT, dateModified TEXT, libraryID INTEGER, key TEXT, version INTEGER, synced INTEGER);
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER, PRIMARY KEY (itemID, fieldID));
        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT, fieldMode INTEGER);
        CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
        CREATE TABLE itemCreators (itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER);
        CREATE TABLE collections (collectionID INTEGER PRIMARY KEY, collectionName TEXT, parentCollectionID INTEGER, libraryID INTEGER, key TEXT, version INTEGER, synced INTEGER);
        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER, orderIndex INTEGER, PRIMARY KEY (collectionID, itemID));
        CREATE TABLE tags (tagID INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE itemTags (itemID INTEGER, tagID INTEGER, type INTEGER, PRIMARY KEY (itemID, tagID));
        CREATE TABLE itemAttachments (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, linkMode INTEGER, path TEXT, contentType TEXT, charsetID INTEGER);
        CREATE TABLE itemNotes (itemID INTEGER PRIMARY KEY, parentItemID INTEGER, note TEXT, title TEXT);
        CREATE TABLE deletedItems (itemID INTEGER PRIMARY KEY);
        """
    )
    conn.executemany("INSERT INTO itemTypes VALUES (?, ?)", [(1, "journalArticle"), (2, "attachment"), (3, "note")])
    conn.executemany(
        "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, 1, "2026-01-01", "2026-01-02", 1, "ITEM0001", 0, 1),
            (2, 2, "2026-01-01", "2026-01-02", 1, "ATTACH01", 0, 1),
            (3, 3, "2026-01-01", "2026-01-02", 1, "NOTE0001", 0, 1),
            (4, 2, "2026-01-01", "2026-01-02", 1, "MISS0001", 0, 1),
            (5, 2, "2026-01-01", "2026-01-02", 1, "HTML01", 0, 1),
            (6, 2, "2026-01-01", "2026-01-02", 1, "IMAGE01", 0, 1),
        ],
    )
    fields = [(1, "title"), (2, "date"), (3, "publicationTitle"), (4, "DOI"), (5, "abstractNote"), (6, "extra")]
    values = [
        (1, "OpenVLA"),
        (2, "2024-09-05"),
        (3, "arXiv"),
        (4, "10.48550/arXiv.2406.09246"),
        (5, "English abstract.\n[abstract_zh]中文摘要[abstract_zhend]"),
        (6, "[remark]李飞飞团队[remarkend]\n[title_zh]开放词汇机器人[title_zhend]\nlegacy: keep"),
    ]
    conn.executemany("INSERT INTO fields VALUES (?, ?)", fields)
    conn.executemany("INSERT INTO itemDataValues VALUES (?, ?)", values)
    conn.executemany("INSERT INTO itemData VALUES (1, ?, ?)", [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)])
    conn.execute("INSERT INTO creatorTypes VALUES (1, 'author')")
    conn.execute("INSERT INTO creators VALUES (1, 'Moo Jin', 'Kim', 0)")
    conn.execute("INSERT INTO itemCreators VALUES (1, 1, 1, 0)")
    conn.executemany(
        "INSERT INTO collections VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(1, "VLA", None, 1, "COLL0001", 0, 1), (2, "端到端", 1, 1, "COLL0002", 0, 1)],
    )
    conn.execute("INSERT INTO collectionItems VALUES (2, 1, 0)")
    conn.executemany("INSERT INTO tags VALUES (?, ?)", [(1, "★★★★★"), (2, "#VLA/端到端"), (3, "#有代码"), (4, "CCF-A"), (5, "/done")])
    conn.executemany("INSERT INTO itemTags VALUES (1, ?, 0)", [(1,), (2,), (3,), (4,), (5,)])
    conn.execute("INSERT INTO itemAttachments VALUES (2, 1, 1, 'storage:paper.pdf', 'application/pdf', NULL)")
    conn.execute("INSERT INTO itemAttachments VALUES (4, 1, 1, 'storage:missing.pdf', 'application/pdf', NULL)")
    conn.execute("INSERT INTO itemAttachments VALUES (5, 1, 1, 'storage:snapshot.html', 'text/html', NULL)")
    conn.execute("INSERT INTO itemAttachments VALUES (6, 1, 1, 'storage:image.png', 'image/png', NULL)")
    conn.execute("INSERT INTO itemNotes VALUES (3, 1, '<p>note</p>', 'Note')")
    conn.commit()
    conn.close()
    return root


@pytest.fixture()
def zotero_fixture(tmp_path: Path) -> Path:
    return create_fixture_zotero(tmp_path / "Zotero")
