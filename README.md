# Web Library

A standalone Zotero-compatible web library viewer and local-copy editor.

This project is intentionally separate from Guangming AI Workbench. It focuses on browsing a local Zotero library in a dense three-pane web UI, parsing semantic tags from native Zotero tags, and editing only a safe local copy when needed.

## Current Capabilities

- Zotero-style three-pane interface: collection tree, dense item table, and detail panel.
- Nested collection tree with tag filters for rating, `#` tags, venue rank, reading status, and plain tags.
- Configurable table columns, column widths, and compact bulk-action toolbar layout.
- Row selection with persistent multi-select state across filtering, folder switches, and local state refreshes.
- Semantic tag parsing from Zotero native tags for:
  - `#` tags
  - reading status
  - rating
  - venue / conference rank
- Library-level shared shortcut tags for fast `#` tag assignment.
- Structured field extraction and editing for:
  - `remark`
  - `title_zh`
  - `abstract_zh`
- Attachment badges for PDFs, HTML snapshots, notes, images, and links.
- Note preview folding in the detail panel.
- Read-only source connection for safe browsing of a real Zotero data directory.
- Editable local-copy mode that writes only to an app-managed clone.

## Source Modes

### Read-only connection

Reads a selected Zotero data directory, for example:

```text
C:\Users\<you>\Zotero
```

This mode never writes to the source `zotero.sqlite`, `storage/`, or any other Zotero source file.

### Local copy

Copies `zotero.sqlite` and `storage/` into the app-managed data directory. All edits are applied only to that copy.

Direct writes to the original Zotero `zotero.sqlite` are intentionally unsupported. Zotero allows reading the local SQLite database, but modifying it directly is unsafe.

## Data Rules

- Zotero native `zotero.sqlite` is the only source of bibliographic truth.
- `#` tags, ratings, reading status, and venue rank are all derived from Zotero native tags in `tags.name`.
- The app does not add custom Zotero schema fields or mutate Zotero table structure.
- App-only metadata such as shortcut tags and UI preferences are stored in `app-data/app.sqlite`.

Detailed field and writeback rules are documented in [docs/data-mapping.md](/C:/Users/27216/Desktop/project/web-library/docs/data-mapping.md).

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

The repo includes `.python-version` set to `3.12`.

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

