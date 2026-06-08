from __future__ import annotations

from pathlib import Path


def test_frontend_contains_refined_interaction_hooks() -> None:
    root = Path(__file__).resolve().parents[1]
    app_js = (root / "src" / "zotero_web_library" / "static" / "app.js").read_text(encoding="utf-8")
    app_css = (root / "src" / "zotero_web_library" / "static" / "app.css").read_text(encoding="utf-8")
    library_html = (root / "src" / "zotero_web_library" / "templates" / "library.html").read_text(encoding="utf-8")
    assert "data-current-tag-toggle" in app_js
    assert "data-shortcut-add-tag" in app_js
    assert "data-shortcut-form" in app_js
    assert "form-action-btn" in app_js
    assert "\"remark\", \"备注\"" in app_js
    assert "\"title_zh\", \"中文标题\"" in app_js
    assert "\"abstract_zh\", \"中文摘要\"" in app_js
    assert "tag-delete-btn" in app_js
    assert "tag-icon-btn" in app_js
    assert "function renderTagPopover" in app_js
    assert "function rerenderActiveTagPopover" in app_js
    assert "function renderStructuredCell" in app_js
    assert "function ratingLabelFromValues" in app_js
    assert "const RATING_STAR = \"⭐\"" in app_js
    assert "const RATING_CONTROL_STAR = \"⭐\"" in app_js
    assert "const ITEM_TYPE_META" in app_js
    assert "const ITEM_TYPE_ALIASES" in app_js
    assert "function normalizeItemTypeKey" in app_js
    assert "function itemTypeMeta" in app_js
    assert "function itemTypeLabel" in app_js
    assert "computerProgram" in app_js
    assert "webpage" in app_js
    assert "magazineArticle" in app_js
    assert "newspaperArticle" in app_js
    assert "webPage: \"webpage\"" in app_js
    assert "software: \"computerProgram\"" in app_js
    assert "data-edit-structured-cell" in app_js
    assert "data-save-structured-cell" in app_js
    assert "/structured-field" in app_js
    assert "selectedItemKeys: new Set()" in app_js
    assert "data-toggle-select-all" in app_js
    assert "data-row-select" in app_js
    assert "notifyFeatureInProgress" in app_js
    assert "data-selected-count" in app_js
    assert "data-bulk-action" in app_js
    assert "function renderTitleCell" in app_js
    assert "title-primary" in app_js
    assert "title-secondary" in app_js
    assert "data-add-tag-form" not in app_js
    assert "renderGlobalShortcutPanel" not in app_js
    assert "data-resize-column" in app_js
    assert "data-rating-item" in app_js
    assert "querySelectorAll(\"[data-open-columns]\")" in app_js
    assert "data-reading-popover" in app_js
    assert "class=\"reading-option" in app_js
    assert "data-semantic-filter=\"type\"" in library_html
    assert "type-badge" in app_js
    assert "normalizeHashTag" in app_js
    assert "attachment_badges" in app_js
    assert "笔记" in app_js
    assert "data-note-toggle" in app_js
    assert "function notePreview" in app_js
    assert "没有笔记" in app_js
    assert "路" not in app_js
    assert "data-manage-shortcuts" not in library_html
    assert "data-add-tag-form" not in library_html
    assert "data-shortcut-form" not in library_html
    assert "data-selected-count" in library_html
    assert "data-bulk-actions" in library_html
    assert "本地副本可编辑" not in library_html
    assert "本地副本" in library_html
    assert "topbar-meta" in library_html
    assert "添加条目" in library_html
    assert "删除" in library_html
    assert "添加附件" in library_html
    assert "文献下载" in library_html
    assert "期刊&会议等级查询" in library_html
    assert "引用导出" in library_html
    assert "文献矩阵" in library_html
    assert "知识库问答" in library_html
    assert "button:hover ~ button" not in app_css
    assert ".form-action-btn" in app_css
    assert ".structured-cell-editor" in app_css
    assert ".structured-cell-actions .form-action-btn" in app_css
    assert ".structured-cell-editor input" in app_css
    assert ".structured-detail-form" in app_css
    assert ".shortcut-pill-toggle .tag-delete-btn" in app_css
    assert ".reading-option" in app_css
    assert ".type-badge" in app_css
    assert ".title-primary" in app_css
    assert ".title-secondary" in app_css
    assert ".title-text" in app_css
    assert ".type-group-academic" in app_css
    assert ".note-line" in app_css
    assert ".note-toggle-btn" in app_css
    assert ".item-table th > span:first-child" in app_css
    assert ".selection-col" in app_css
    assert ".selection-toggle-btn" in app_css
    assert ".row-checkbox" in app_css
    assert ".bulk-actions" in app_css
    assert ".bulk-action-btn" in app_css
    assert ".table-stats" in app_css
    assert ".topbar-meta" in app_css
    assert "overflow-x: hidden" in app_css
    assert "grid-template-columns: minmax(72px, 110px) minmax(0, 1fr)" in app_css
    assert ".field-grid strong" in app_css
    assert ".detail-card p" in app_css
    assert ".attachment-line a" in app_css
    assert "overflow-wrap: anywhere" in app_css
    assert "data-toggle-plain-tags" in library_html
    assert "code_status" not in library_html
