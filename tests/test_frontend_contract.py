from __future__ import annotations

from pathlib import Path


def test_frontend_contains_refined_interaction_hooks() -> None:
    root = Path(__file__).resolve().parents[1]
    app_js = (root / "src" / "zotero_web_library" / "static" / "app.js").read_text(encoding="utf-8")
    app_css = (root / "src" / "zotero_web_library" / "static" / "app.css").read_text(encoding="utf-8")
    library_html = (root / "src" / "zotero_web_library" / "templates" / "library.html").read_text(encoding="utf-8")
    assert "data-tag-popover" in app_js
    assert "function renderNestedCell" in app_js
    assert "function renderTitleCell" in app_js
    assert "data-tag-popover" not in app_js.split("function renderTitleCell", 1)[1].split("function ratingCount", 1)[0]
    assert "data-resize-column" in app_js
    assert "data-rating-item" in app_js
    assert "querySelectorAll(\"[data-open-columns]\")" in app_js
    assert "data-reading-popover" in app_js
    assert "normalizeHashTag" in app_js
    assert "attachment_badges" in app_js
    assert "button:hover ~ button" not in app_css
    assert "HTML?" not in app_js
    assert "data-toggle-plain-tags" in library_html
    assert "code_status" not in library_html
