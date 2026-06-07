from __future__ import annotations

import hashlib
import random
import string
from datetime import datetime, timezone
from pathlib import Path


ZOTERO_KEY_ALPHABET = string.ascii_uppercase + string.digits


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_key(length: int = 8) -> str:
    return "".join(random.choice(ZOTERO_KEY_ALPHABET) for _ in range(length))


def file_fingerprint(path: Path) -> str:
    stat = path.stat()
    text = f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()
