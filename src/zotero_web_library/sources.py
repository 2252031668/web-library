from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import app_store
from .paths import libraries_dir
from .utils import file_fingerprint, new_key, normalize_path, now_iso


READ_ONLY = "read_only_connection"
LOCAL_COPY = "local_copy"


class SourceError(ValueError):
    pass


def validate_zotero_dir(path: str | Path) -> dict[str, Any]:
    root = normalize_path(path)
    sqlite_path = root / "zotero.sqlite"
    storage_path = root / "storage"
    if not root.exists() or not root.is_dir():
        raise SourceError("请选择存在的 Zotero 数据目录。")
    if not sqlite_path.exists():
        raise SourceError("目录中没有 zotero.sqlite，无法作为 Zotero 数据目录。")
    return {
        "root": root,
        "sqlite_path": sqlite_path,
        "storage_path": storage_path if storage_path.exists() else None,
        "fingerprint": file_fingerprint(sqlite_path),
    }


def normalized_source_path(path: str | Path) -> str:
    return str(normalize_path(path)).casefold()


def find_existing_source(path: str | Path, mode: str) -> dict[str, Any] | None:
    source_key = normalized_source_path(path)
    for library in app_store.list_all_libraries():
        if library.get("mode") != mode:
            continue
        if normalized_source_path(library.get("source_path", "")) != source_key:
            continue
        if mode == LOCAL_COPY and not (Path(library["data_path"]) / "zotero.sqlite").exists():
            continue
        return library
    return None


def _seed_shortcuts_for_library(record: dict[str, Any]) -> dict[str, Any]:
    from .zotero_adapter import ZoteroRepository

    ZoteroRepository(record).ensure_tag_shortcuts_seeded(force=True)
    return record


def create_read_only_source(path: str | Path, *, name: str | None = None) -> dict[str, Any]:
    info = validate_zotero_dir(path)
    existing = find_existing_source(info["root"], READ_ONLY)
    if existing:
        if name:
            existing["name"] = name
            return app_store.upsert_library(existing)
        return existing
    library_id = f"ro-{new_key(10).lower()}"
    record = app_store.upsert_library(
        {
            "library_id": library_id,
            "name": name or f"只读连接：{info['root'].name}",
            "mode": READ_ONLY,
            "source_path": info["root"],
            "data_path": info["root"],
            "source_fingerprint": info["fingerprint"],
        }
    )
    return _seed_shortcuts_for_library(record)


def create_local_copy(path: str | Path, *, name: str | None = None) -> dict[str, Any]:
    info = validate_zotero_dir(path)
    existing = find_existing_source(info["root"], LOCAL_COPY)
    if existing:
        if name:
            existing["name"] = name
            return app_store.upsert_library(existing)
        return existing
    library_id = f"copy-{new_key(10).lower()}"
    target = libraries_dir() / library_id
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(info["sqlite_path"], target / "zotero.sqlite")
    if info["storage_path"]:
        shutil.copytree(info["storage_path"], target / "storage")
    source_json = {
        "source_path": str(info["root"]),
        "source_fingerprint": info["fingerprint"],
        "copied_at": now_iso(),
    }
    (target / "source.json").write_text(json.dumps(source_json, ensure_ascii=False, indent=2), encoding="utf-8")
    record = app_store.upsert_library(
        {
            "library_id": library_id,
            "name": name or f"本地副本：{info['root'].name}",
            "mode": LOCAL_COPY,
            "source_path": info["root"],
            "data_path": target,
            "source_fingerprint": info["fingerprint"],
        }
    )
    return _seed_shortcuts_for_library(record)


def delete_source(library_id: str) -> dict[str, Any]:
    library = app_store.get_library(library_id)
    if not library:
        raise SourceError("文库不存在。")
    data_path = Path(library["data_path"])
    if library["mode"] == LOCAL_COPY:
        root = libraries_dir().resolve()
        target = data_path.resolve()
        if root not in [target, *target.parents]:
            raise SourceError("本地副本路径不在应用管理目录内，拒绝删除。")
        if target.exists():
            shutil.rmtree(target)
    app_store.delete_library_record(library_id)
    return library


def sqlite_path_for(library: dict[str, Any]) -> Path:
    return Path(library["data_path"]) / "zotero.sqlite"


def storage_path_for(library: dict[str, Any]) -> Path:
    return Path(library["data_path"]) / "storage"


def ensure_editable(library: dict[str, Any]) -> None:
    if library.get("mode") != LOCAL_COPY:
        raise SourceError("只读连接模式不能修改字段、标签、文件夹或附件。请先创建本地副本。")
