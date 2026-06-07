# Web Library

A standalone Zotero-compatible web library viewer and local-copy editor.

This project is intentionally separate from Guangming AI Workbench. It focuses only on browsing a local Zotero library in a dense web UI, parsing semantic tags, and editing a safe local copy when needed.

## Features

- Zotero-like three-pane library interface.
- Collection tree display with nested folders.
- Dense item table with configurable visible columns and column order.
- Semantic tag parsing for `#` labels, reading status, ratings, and other structured tags.
- Library-level shortcut tag palette for fast tag assignment.
- Reading status display: unread, reading, and done.
- Local-copy editing for tags, ratings, collections, and UI metadata.
- Read-only source connection for safely browsing an existing Zotero data directory.
- Attachment badges for PDFs, notes, HTML snapshots, images, and links.

## Source Modes

### Read-only connection

Reads a selected Zotero data directory, for example:

```text
C:\Users\<you>\Zotero
```

This mode does not write to the source `zotero.sqlite`, `storage/`, or any other Zotero source file.

### Local copy

Copies `zotero.sqlite` and `storage/` into the app-managed data directory. Edits are applied only to that copy.

Direct writes to the original Zotero `zotero.sqlite` are intentionally unsupported. Zotero allows reading the local SQLite database, but modifying it directly is unsafe.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Run

```powershell
uv sync
uv run python -m zotero_web_library.web
```

Open:

```text
http://127.0.0.1:5088
```

## Test

```powershell
uv run pytest
```

## App Data

By default, the app stores metadata and local copies under:

```text
./app-data/
  app.sqlite
  libraries/
    <library-id>/
      zotero.sqlite
      storage/
      source.json
```

`app-data/` is ignored by Git because it can contain private Zotero library data and copied attachments.

## Safety Notes

- Do not commit `app-data/`.
- Do not commit copied Zotero databases or attachments.
- Use read-only mode when browsing your real Zotero library.
- Use local-copy mode when you want editable experiments without touching the source library.

