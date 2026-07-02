from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def app_data_dir() -> Path:
    configured = os.environ.get("WEB_LIBRARY_DATA_DIR")
    return Path(configured).expanduser().resolve() if configured else BASE_DIR / "app-data"


def app_db_path() -> Path:
    return app_data_dir() / "app.sqlite"


def libraries_dir() -> Path:
    return app_data_dir() / "libraries"


def library_dir(library_id: str) -> Path:
    return libraries_dir() / str(library_id)


def library_workspace_dir(library_id: str) -> Path:
    return library_dir(library_id) / "workspace"


def library_search_runs_dir(library_id: str) -> Path:
    return library_workspace_dir(library_id) / "search-runs"
