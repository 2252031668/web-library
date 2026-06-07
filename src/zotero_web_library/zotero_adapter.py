from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import app_store
from .semantic_tags import first_value, normalize_hash_tag, parse_tags, rating_tag, stable_tag_color
from .sources import ensure_editable, sqlite_path_for, storage_path_for
from .utils import new_key, now_iso


def connect_zotero(db_path: Path, *, read_only: bool = True) -> sqlite3.Connection:
    if read_only:
        uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class ZoteroRepository:
    def __init__(self, library: dict[str, Any]) -> None:
        self.library = library
        self.db_path = sqlite_path_for(library)
        self.storage_path = storage_path_for(library)

    def read_conn(self) -> sqlite3.Connection:
        return connect_zotero(self.db_path, read_only=True)

    def write_conn(self) -> sqlite3.Connection:
        ensure_editable(self.library)
        return connect_zotero(self.db_path, read_only=False)

    def schema_tables(self) -> set[str]:
        with self.read_conn() as conn:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            return {row["name"] for row in rows}

    def collections(self) -> list[dict[str, Any]]:
        with self.read_conn() as conn:
            if "collections" not in self.schema_tables():
                return []
            rows = conn.execute(
                """
                SELECT collectionID, collectionName, parentCollectionID, key
                FROM collections
                ORDER BY parentCollectionID IS NOT NULL, collectionName COLLATE NOCASE
                """
            ).fetchall()
        return [
            {
                "collection_id": row["collectionID"],
                "key": row["key"] or str(row["collectionID"]),
                "name": row["collectionName"] or "未命名文件夹",
                "parent_id": row["parentCollectionID"],
            }
            for row in rows
        ]

    def _fields_by_item(self, conn: sqlite3.Connection) -> dict[int, dict[str, str]]:
        rows = conn.execute(
            """
            SELECT d.itemID, f.fieldName, v.value
            FROM itemData d
            JOIN fields f ON f.fieldID = d.fieldID
            JOIN itemDataValues v ON v.valueID = d.valueID
            """
        ).fetchall()
        fields: dict[int, dict[str, str]] = defaultdict(dict)
        for row in rows:
            fields[int(row["itemID"])][row["fieldName"]] = row["value"] or ""
        return fields

    def _creators_by_item(self, conn: sqlite3.Connection) -> dict[int, list[dict[str, str]]]:
        if "creators" not in self.schema_tables():
            return {}
        rows = conn.execute(
            """
            SELECT ic.itemID, c.firstName, c.lastName, c.fieldMode, ct.creatorType, ic.orderIndex
            FROM itemCreators ic
            JOIN creators c ON c.creatorID = ic.creatorID
            LEFT JOIN creatorTypes ct ON ct.creatorTypeID = ic.creatorTypeID
            ORDER BY ic.itemID, ic.orderIndex
            """
        ).fetchall()
        creators: dict[int, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            name = row["lastName"] if row["fieldMode"] == 1 else " ".join([row["firstName"] or "", row["lastName"] or ""]).strip()
            creators[int(row["itemID"])].append({"name": name, "type": row["creatorType"] or "creator"})
        return creators

    def _tags_by_item(self, conn: sqlite3.Connection) -> dict[int, list[str]]:
        if "tags" not in self.schema_tables():
            return {}
        rows = conn.execute(
            """
            SELECT it.itemID, t.name
            FROM itemTags it
            JOIN tags t ON t.tagID = it.tagID
            ORDER BY t.name COLLATE NOCASE
            """
        ).fetchall()
        tags: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            tags[int(row["itemID"])].append(row["name"] or "")
        return tags

    def _collections_by_item(self, conn: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
        if "collectionItems" not in self.schema_tables():
            return {}
        rows = conn.execute(
            """
            SELECT ci.itemID, c.collectionID, c.collectionName, c.key
            FROM collectionItems ci
            JOIN collections c ON c.collectionID = ci.collectionID
            ORDER BY c.collectionName COLLATE NOCASE
            """
        ).fetchall()
        values: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            values[int(row["itemID"])].append(
                {"collection_id": row["collectionID"], "key": row["key"] or str(row["collectionID"]), "name": row["collectionName"] or ""}
            )
        return values

    def _attachments_by_parent(self, conn: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
        if "itemAttachments" not in self.schema_tables():
            return {}
        rows = conn.execute(
            """
            SELECT a.parentItemID, a.itemID, a.path, a.contentType, a.linkMode, i.key, i.dateAdded, v.value AS title
            FROM itemAttachments a
            JOIN items i ON i.itemID = a.itemID
            LEFT JOIN itemData d ON d.itemID = i.itemID AND d.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
            LEFT JOIN itemDataValues v ON v.valueID = d.valueID
            WHERE a.parentItemID IS NOT NULL
            ORDER BY i.dateAdded
            """
        ).fetchall()
        attachments: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            path = row["path"] or ""
            resolved = self.resolve_attachment_path(row["key"], path)
            kind = self.attachment_kind(path, row["contentType"] or "", row["linkMode"])
            exists = bool(resolved and Path(resolved).exists())
            status = "openable" if exists else ("external" if kind in {"link", "external"} else "missing")
            attachments[int(row["parentItemID"])].append(
                {
                    "item_id": row["itemID"],
                    "key": row["key"],
                    "path": path,
                    "display_label": self.attachment_label(path, row["title"] or ""),
                    "resolved_path": str(resolved) if resolved else "",
                    "content_type": row["contentType"] or "",
                    "link_mode": row["linkMode"],
                    "kind": kind,
                    "status": status,
                    "openable": exists,
                }
            )
        return attachments

    def _notes_by_parent(self, conn: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
        if "itemNotes" not in self.schema_tables():
            return {}
        rows = conn.execute(
            """
            SELECT n.parentItemID, n.itemID, n.note, i.key
            FROM itemNotes n
            JOIN items i ON i.itemID = n.itemID
            WHERE n.parentItemID IS NOT NULL
            ORDER BY i.dateAdded
            """
        ).fetchall()
        notes: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            notes[int(row["parentItemID"])].append({"item_id": row["itemID"], "key": row["key"], "note": row["note"] or ""})
        return notes

    def resolve_attachment_path(self, attachment_key: str, path: str) -> Path | None:
        if not path:
            return None
        if path.startswith("storage:"):
            return self.storage_path / attachment_key / path.replace("storage:", "", 1)
        candidate = Path(path)
        if candidate.is_absolute():
            return candidate
        return self.storage_path / attachment_key / path

    def attachment_kind(self, path: str, content_type: str, link_mode: int | None) -> str:
        lower_path = (path or "").lower()
        lower_type = (content_type or "").lower()
        if lower_type == "application/pdf" or lower_path.endswith(".pdf"):
            return "pdf"
        if "html" in lower_type or lower_path.endswith((".html", ".htm")):
            return "html"
        if lower_type.startswith("image/") or lower_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
            return "image"
        if lower_path.startswith(("http://", "https://")):
            return "link"
        if link_mode in {2, 3}:
            return "external"
        return "file"

    def attachment_label(self, path: str, title: str) -> str:
        if title:
            return title
        if path.startswith("storage:"):
            return path.replace("storage:", "", 1)
        return Path(path).name if path else "Attachment"

    def attachment_badges(self, attachments: list[dict[str, Any]], notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: Counter[tuple[str, bool]] = Counter()
        for attachment in attachments:
            kind = attachment.get("kind") or "file"
            label = {"pdf": "PDF", "html": "HTML", "image": "Image", "link": "Link", "external": "Link"}.get(kind, "File")
            counts[(label, attachment.get("status") == "missing")] += 1
        if notes:
            counts[("Note", False)] += len(notes)
        return [{"label": label, "count": count, "missing": missing} for (label, missing), count in counts.items()]

    def items(self) -> list[dict[str, Any]]:
        with self.read_conn() as conn:
            fields = self._fields_by_item(conn)
            creators = self._creators_by_item(conn)
            tags = self._tags_by_item(conn)
            collections = self._collections_by_item(conn)
            attachments = self._attachments_by_parent(conn)
            notes = self._notes_by_parent(conn)
            deleted_join = "LEFT JOIN deletedItems di ON di.itemID = i.itemID" if "deletedItems" in self.schema_tables() else ""
            deleted_select = "CASE WHEN di.itemID IS NULL THEN 0 ELSE 1 END AS deleted" if "deletedItems" in self.schema_tables() else "0 AS deleted"
            rows = conn.execute(
                f"""
                SELECT i.itemID, i.key, i.dateAdded, i.dateModified, t.typeName, {deleted_select}
                FROM items i
                JOIN itemTypes t ON t.itemTypeID = i.itemTypeID
                {deleted_join}
                WHERE t.typeName NOT IN ('attachment', 'note', 'annotation')
                ORDER BY i.dateModified DESC, i.itemID DESC
                """
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            item_id = int(row["itemID"])
            item_fields = fields.get(item_id, {})
            item_tags = tags.get(item_id, [])
            semantic = parse_tags(item_tags, app_store.list_semantic_rules(self.library["library_id"])).as_dict()
            creator_values = creators.get(item_id, [])
            creator_names = [creator["name"] for creator in creator_values if creator.get("name")]
            item_attachments = attachments.get(item_id, [])
            item_notes = notes.get(item_id, [])
            venue = item_fields.get("publicationTitle") or item_fields.get("proceedingsTitle") or item_fields.get("conferenceName") or item_fields.get("repository") or ""
            year = (item_fields.get("date") or "")[:4]
            values.append(
                {
                    "item_id": item_id,
                    "key": row["key"],
                    "type": row["typeName"],
                    "title": item_fields.get("title", "未命名文献"),
                    "fields": item_fields,
                    "creators": creator_values,
                    "creator_names": creator_names,
                    "creators_display": creator_names[0] if creator_names else "",
                    "creators_full_display": " / ".join(creator_names),
                    "year": year,
                    "venue": venue,
                    "tags": item_tags,
                    "semantic": semantic,
                    "tag_colors": {tag: stable_tag_color(tag) for tag in semantic["nested"] + semantic["plain"]},
                    "rating": first_value(semantic["rating"]),
                    "collections": collections.get(item_id, []),
                    "attachments": item_attachments,
                    "notes": item_notes,
                    "attachment_badges": self.attachment_badges(item_attachments, item_notes),
                    "deleted": bool(row["deleted"]),
                    "date_added": row["dateAdded"],
                    "date_modified": row["dateModified"],
                }
            )
        return values

    def state(self) -> dict[str, Any]:
        items = self.items()
        collections = self.collections()
        tag_counts = Counter(tag for item in items for tag in item["tags"])
        semantic_counts: dict[str, Counter[str]] = defaultdict(Counter)
        for item in items:
            for bucket, values in item["semantic"].items():
                if bucket == "raw":
                    continue
                for value in values:
                    semantic_counts[bucket][value] += 1
        return {
            "library": {
                **self.library,
                "editable": self.library.get("mode") == "local_copy",
                "unsynced_count": app_store.unsynced_count(self.library["library_id"]),
                "columns": app_store.column_preference(self.library["library_id"]),
                "column_widths": app_store.column_width_preference(self.library["library_id"]),
                "plain_tags_collapsed": app_store.plain_tags_collapsed(self.library["library_id"]),
            },
            "collections": collections,
            "items": items,
            "tag_counts": dict(tag_counts),
            "semantic_counts": {key: dict(counter) for key, counter in semantic_counts.items()},
            "tag_shortcuts": app_store.list_tag_shortcuts(self.library["library_id"]),
        }

    def create_collection(self, name: str, parent_key: str | None = None) -> dict[str, Any]:
        ensure_editable(self.library)
        key = new_key()
        with self.write_conn() as conn:
            parent_id = None
            if parent_key:
                row = conn.execute("SELECT collectionID FROM collections WHERE key = ?", (parent_key,)).fetchone()
                parent_id = row["collectionID"] if row else None
            conn.execute(
                """
                INSERT INTO collections (collectionName, parentCollectionID, libraryID, key, version, synced)
                VALUES (?, ?, 1, ?, 0, 0)
                """,
                (name, parent_id, key),
            )
            conn.commit()
        app_store.append_journal(self.library["library_id"], "create_collection", "collection", key, {"name": name, "parent_key": parent_key})
        return {"key": key, "name": name, "parent_key": parent_key}

    def rename_collection(self, key: str, name: str) -> None:
        ensure_editable(self.library)
        with self.write_conn() as conn:
            row = conn.execute("SELECT collectionName FROM collections WHERE key = ?", (key,)).fetchone()
            old_name = row["collectionName"] if row else ""
            conn.execute("UPDATE collections SET collectionName = ?, synced = 0 WHERE key = ?", (name, key))
            conn.commit()
        app_store.append_journal(self.library["library_id"], "rename_collection", "collection", key, {"old": old_name, "new": name})

    def reparent_collection(self, key: str, parent_key: str | None) -> None:
        ensure_editable(self.library)
        with self.write_conn() as conn:
            current = conn.execute("SELECT collectionID, parentCollectionID FROM collections WHERE key = ?", (key,)).fetchone()
            if not current:
                raise ValueError("文件夹不存在。")
            parent_id = None
            if parent_key:
                parent = conn.execute("SELECT collectionID FROM collections WHERE key = ?", (parent_key,)).fetchone()
                if not parent:
                    raise ValueError("父文件夹不存在。")
                parent_id = parent["collectionID"]
            conn.execute("UPDATE collections SET parentCollectionID = ?, synced = 0 WHERE key = ?", (parent_id, key))
            conn.commit()
        app_store.append_journal(
            self.library["library_id"],
            "reparent_collection",
            "collection",
            key,
            {"old_parent_id": current["parentCollectionID"], "new_parent_key": parent_key},
        )

    def update_item_field(self, item_key: str, field_name: str, value: str) -> None:
        ensure_editable(self.library)
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not item:
                raise ValueError("条目不存在。")
            field = conn.execute("SELECT fieldID FROM fields WHERE fieldName = ?", (field_name,)).fetchone()
            if not field:
                conn.execute("INSERT INTO fields (fieldName) VALUES (?)", (field_name,))
                field_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            else:
                field_id = field["fieldID"]
            old_row = conn.execute(
                """
                SELECT v.value FROM itemData d
                JOIN itemDataValues v ON v.valueID = d.valueID
                WHERE d.itemID = ? AND d.fieldID = ?
                """,
                (item["itemID"], field_id),
            ).fetchone()
            old_value = old_row["value"] if old_row else ""
            value_row = conn.execute("SELECT valueID FROM itemDataValues WHERE value = ?", (value,)).fetchone()
            if value_row:
                value_id = value_row["valueID"]
            else:
                conn.execute("INSERT INTO itemDataValues (value) VALUES (?)", (value,))
                value_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute("DELETE FROM itemData WHERE itemID = ? AND fieldID = ?", (item["itemID"], field_id))
            conn.execute("INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, ?, ?)", (item["itemID"], field_id, value_id))
            conn.execute("UPDATE items SET dateModified = ?, synced = 0 WHERE itemID = ?", (now_iso(), item["itemID"]))
            conn.commit()
        app_store.append_journal(
            self.library["library_id"],
            "update_item_field",
            "item",
            item_key,
            {"field": field_name, "old": old_value, "new": value},
        )

    def add_tag(self, item_key: str, tag: str) -> None:
        ensure_editable(self.library)
        tag = normalize_hash_tag(tag)
        if not tag:
            raise ValueError("标签不能为空。")
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not item:
                raise ValueError("条目不存在。")
            tag_row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (tag,)).fetchone()
            if tag_row:
                tag_id = tag_row["tagID"]
            else:
                conn.execute("INSERT INTO tags (name, type) VALUES (?, 0)", (tag,))
                tag_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO itemTags (itemID, tagID, type) VALUES (?, ?, 0)", (item["itemID"], tag_id))
            conn.execute("UPDATE items SET synced = 0 WHERE itemID = ?", (item["itemID"],))
            conn.commit()
        app_store.append_journal(self.library["library_id"], "add_tag", "item", item_key, {"tag": tag})

    def remove_tag(self, item_key: str, tag: str) -> None:
        ensure_editable(self.library)
        tag = normalize_hash_tag(tag)
        if not tag:
            raise ValueError("标签不能为空。")
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            tag_row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (tag,)).fetchone()
            if item and tag_row:
                conn.execute("DELETE FROM itemTags WHERE itemID = ? AND tagID = ?", (item["itemID"], tag_row["tagID"]))
                conn.execute("UPDATE items SET synced = 0 WHERE itemID = ?", (item["itemID"],))
                conn.commit()
        app_store.append_journal(self.library["library_id"], "remove_tag", "item", item_key, {"tag": tag})

    def set_reading_status(self, item_key: str, status: str) -> None:
        ensure_editable(self.library)
        normalized_status = str(status or "").strip().lower()
        target_tag = {"read": "/done", "done": "/done", "reading": "/reading", "unread": ""}.get(normalized_status)
        if target_tag is None:
            raise ValueError("未知阅读状态。")
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not item:
                raise ValueError("条目不存在。")
            rows = conn.execute(
                """
                SELECT t.tagID, t.name
                FROM itemTags it
                JOIN tags t ON t.tagID = it.tagID
                WHERE it.itemID = ?
                """,
                (item["itemID"],),
            ).fetchall()
            old_tags = [row["name"] for row in rows if parse_tags([row["name"]]).reading_status]
            for row in rows:
                if parse_tags([row["name"]]).reading_status:
                    conn.execute("DELETE FROM itemTags WHERE itemID = ? AND tagID = ?", (item["itemID"], row["tagID"]))
            if target_tag:
                tag_row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (target_tag,)).fetchone()
                if tag_row:
                    tag_id = tag_row["tagID"]
                else:
                    conn.execute("INSERT INTO tags (name, type) VALUES (?, 0)", (target_tag,))
                    tag_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                conn.execute("INSERT OR IGNORE INTO itemTags (itemID, tagID, type) VALUES (?, ?, 0)", (item["itemID"], tag_id))
            conn.execute("UPDATE items SET synced = 0 WHERE itemID = ?", (item["itemID"],))
            conn.commit()
        app_store.append_journal(
            self.library["library_id"],
            "set_reading_status",
            "item",
            item_key,
            {"old": old_tags, "new": target_tag, "status": normalized_status},
        )

    def set_rating(self, item_key: str, value: int) -> None:
        ensure_editable(self.library)
        value = max(0, min(5, int(value)))
        new_tag = rating_tag(value)
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            if not item:
                raise ValueError("条目不存在。")
            rows = conn.execute(
                """
                SELECT t.tagID, t.name
                FROM itemTags it
                JOIN tags t ON t.tagID = it.tagID
                WHERE it.itemID = ?
                """,
                (item["itemID"],),
            ).fetchall()
            old_tags = [row["name"] for row in rows if parse_tags([row["name"]]).rating]
            for row in rows:
                if parse_tags([row["name"]]).rating:
                    conn.execute("DELETE FROM itemTags WHERE itemID = ? AND tagID = ?", (item["itemID"], row["tagID"]))
            if new_tag:
                tag_row = conn.execute("SELECT tagID FROM tags WHERE name = ?", (new_tag,)).fetchone()
                if tag_row:
                    tag_id = tag_row["tagID"]
                else:
                    conn.execute("INSERT INTO tags (name, type) VALUES (?, 0)", (new_tag,))
                    tag_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                conn.execute("INSERT OR IGNORE INTO itemTags (itemID, tagID, type) VALUES (?, ?, 0)", (item["itemID"], tag_id))
            conn.execute("UPDATE items SET synced = 0 WHERE itemID = ?", (item["itemID"],))
            conn.commit()
        app_store.append_journal(self.library["library_id"], "set_rating", "item", item_key, {"old": old_tags, "new": new_tag})

    def set_collection_membership(self, item_key: str, collection_key: str, enabled: bool) -> None:
        ensure_editable(self.library)
        with self.write_conn() as conn:
            item = conn.execute("SELECT itemID FROM items WHERE key = ?", (item_key,)).fetchone()
            collection = conn.execute("SELECT collectionID FROM collections WHERE key = ?", (collection_key,)).fetchone()
            if not item or not collection:
                raise ValueError("条目或文件夹不存在。")
            if enabled:
                conn.execute(
                    "INSERT OR IGNORE INTO collectionItems (collectionID, itemID, orderIndex) VALUES (?, ?, 0)",
                    (collection["collectionID"], item["itemID"]),
                )
            else:
                conn.execute("DELETE FROM collectionItems WHERE collectionID = ? AND itemID = ?", (collection["collectionID"], item["itemID"]))
            conn.commit()
        app_store.append_journal(
            self.library["library_id"],
            "set_collection_membership",
            "item",
            item_key,
            {"collection_key": collection_key, "enabled": enabled},
        )
