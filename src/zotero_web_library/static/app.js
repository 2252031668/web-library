const ALL_COLUMNS = [
  ["title", "标题"],
  ["creators", "作者"],
  ["year", "年份"],
  ["venue", "来源"],
  ["rating", "评分"],
  ["nested", "#标签"],
  ["venue_rank", "期刊等级"],
  ["reading_status", "阅读"],
  ["plain", "普通标签"],
  ["collections", "文件夹"],
];

const DEFAULT_COLUMNS = ["title", "creators", "year", "venue", "rating", "nested", "venue_rank", "reading_status", "collections"];
const READ_TAGS = new Set(["/done", "done", "已读", "read"]);
const READING_TAGS = new Set(["/reading", "reading", "在读"]);

const state = {
  libraryId: "",
  library: null,
  items: [],
  collections: [],
  tagShortcuts: [],
  filteredItems: [],
  selectedItem: null,
  selectedCollectionKey: "",
  selectedTags: new Map(),
  columns: [],
  columnDraft: [],
  columnWidths: {},
  search: "",
  plainCollapsed: true,
  activePopoverItemKey: "",
};

function postJSON(url, payload, method = "POST") {
  return fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(async (response) => {
    const data = await response.json();
    if (!response.ok || data.ok === false) throw new Error(data.error || "请求失败");
    return data;
  });
}

function deleteJSON(url, payload = {}) {
  return postJSON(url, payload, "DELETE");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function tagColor(tag) {
  let hash = 0;
  for (let i = 0; i < tag.length; i += 1) hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0;
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 72% 42%)`;
}

function normalizeHashTag(tag) {
  const value = String(tag || "").trim().replace(/\s+/g, " ");
  if (!value) return "";
  if (value.startsWith("#") || value.startsWith("/")) return value;
  return `#${value}`;
}

function displayHashTag(tag) {
  const value = String(tag || "").trim();
  return value.startsWith("#") ? value.slice(1) : value;
}

function textOf(values) {
  return (values || []).join(" / ");
}

function readingStatus(item) {
  const values = (item.semantic?.reading_status || []).map((value) => String(value).toLowerCase());
  if (values.some((value) => READ_TAGS.has(value))) return { key: "read", label: "已读", tag: "/done" };
  if (values.some((value) => READING_TAGS.has(value))) return { key: "reading", label: "在读", tag: "/reading" };
  return { key: "unread", label: "未读", tag: "" };
}

function itemValue(item, key) {
  switch (key) {
    case "title": return item.title || "未命名文献";
    case "creators": return item.creators_display || "";
    case "year": return item.year || "";
    case "venue": return item.venue || item.type || "";
    case "rating": return textOf(item.semantic.rating);
    case "nested": return textOf(item.semantic.nested);
    case "venue_rank": return textOf(item.semantic.venue_rank);
    case "reading_status": return readingStatus(item).label;
    case "plain": return textOf(item.semantic.plain);
    case "collections": return textOf((item.collections || []).map((collection) => collection.name));
    default: return "";
  }
}

function setupSourceForms() {
  document.querySelectorAll("[data-source-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());
      const mode = form.dataset.mode;
      const url = mode === "local-copy" ? "/api/sources/local-copy" : "/api/sources/read-only";
      const button = form.querySelector("button");
      const oldText = button.textContent;
      button.textContent = "处理中...";
      button.disabled = true;
      try {
        const data = await postJSON(url, payload);
        window.location.href = `/library/${data.library.library_id}`;
      } catch (error) {
        window.alert(error.message);
      } finally {
        button.textContent = oldText;
        button.disabled = false;
      }
    });
  });
  document.querySelectorAll("[data-delete-source]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.preventDefault();
      const id = button.dataset.deleteSource;
      if (!window.confirm(button.dataset.confirm || "确认删除这个配置？")) return;
      try {
        await deleteJSON(`/api/sources/${id}?confirm=1`);
        window.location.reload();
      } catch (error) {
        window.alert(error.message);
      }
    });
  });
}

function sortedCollections() {
  const byParent = new Map();
  state.collections.forEach((collection) => {
    const parent = collection.parent_id || "";
    if (!byParent.has(parent)) byParent.set(parent, []);
    byParent.get(parent).push(collection);
  });
  byParent.forEach((list) => list.sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN")));
  const result = [];
  function visit(parent, depth) {
    (byParent.get(parent) || []).forEach((collection) => {
      result.push({ ...collection, depth });
      visit(collection.collection_id, depth + 1);
    });
  }
  visit("", 0);
  return result;
}

function renderTree() {
  const tree = document.querySelector("[data-tree]");
  if (!tree) return;
  const countsByCollection = new Map();
  state.items.forEach((item) => {
    (item.collections || []).forEach((collection) => {
      countsByCollection.set(collection.key, (countsByCollection.get(collection.key) || 0) + 1);
    });
  });
  const nodes = [
    { key: "", name: "全部条目", depth: 0, count: state.items.length },
    { key: "__recent", name: "最近添加", depth: 0, count: state.items.length },
    { key: "__unfiled", name: "未分类条目", depth: 0, count: state.items.filter((item) => !item.collections.length).length },
    { key: "__trash", name: "回收站", depth: 0, count: state.items.filter((item) => item.deleted).length },
    ...sortedCollections().map((collection) => ({ ...collection, count: countsByCollection.get(collection.key) || 0 })),
  ];
  tree.innerHTML = nodes.map((node) => `
    <button class="tree-node ${state.selectedCollectionKey === node.key ? "active" : ""}" data-tree-key="${node.key}" style="--depth:${node.depth || 0}">
      <span class="label">${escapeHtml(node.name)}</span><span>${node.count}</span>
    </button>
  `).join("");
  tree.querySelectorAll("[data-tree-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCollectionKey = button.dataset.treeKey;
      applyFilters();
    });
  });
  const parentSelect = document.querySelector("[data-parent-select]");
  if (parentSelect) {
    parentSelect.innerHTML = `<option value="">根目录</option>` + sortedCollections().map((collection) => {
      const indent = "　".repeat(collection.depth || 0);
      return `<option value="${collection.key}">${indent}${escapeHtml(collection.name)}</option>`;
    }).join("");
  }
}

function renderTagFilters() {
  const buckets = ["rating", "nested", "venue_rank", "reading_status", "plain"];
  buckets.forEach((bucket) => {
    const host = document.querySelector(`[data-semantic-filter="${bucket}"]`);
    if (!host) return;
    if (bucket === "plain" && state.plainCollapsed) {
      host.innerHTML = "";
      return;
    }
    const counts = new Map();
    state.items.forEach((item) => {
      if (bucket === "reading_status") {
        const label = readingStatus(item).label;
        counts.set(label, (counts.get(label) || 0) + 1);
        return;
      }
      (item.semantic[bucket] || []).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
    });
    let entries = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "zh-Hans-CN"));
    const search = document.querySelector("[data-tag-search]")?.value?.trim().toLowerCase() || "";
    if (bucket === "plain" && search) entries = entries.filter(([tag]) => tag.toLowerCase().includes(search));
    host.innerHTML = entries.slice(0, bucket === "plain" ? 80 : 60).map(([tag, count]) => {
      const selected = state.selectedTags.get(bucket)?.has(tag);
      const color = bucket === "nested" || bucket === "plain" ? `style="--tag-color:${tagColor(tag)}"` : "";
      const label = bucket === "nested" ? displayHashTag(tag) : tag;
      return `<button class="tag-chip ${selected ? "active" : ""}" ${color} data-bucket="${bucket}" data-tag="${escapeHtml(tag)}">${escapeHtml(label)} ${count}</button>`;
    }).join("") || `<span class="muted">无</span>`;
    host.querySelectorAll("[data-tag]").forEach((button) => {
      button.addEventListener("click", () => {
        const set = state.selectedTags.get(bucket) || new Set();
        if (set.has(button.dataset.tag)) set.delete(button.dataset.tag);
        else set.add(button.dataset.tag);
        state.selectedTags.set(bucket, set);
        applyFilters();
      });
    });
  });
}

function setupPlainToggle() {
  const toggle = document.querySelector("[data-toggle-plain-tags]");
  if (!toggle) return;
  toggle.textContent = state.plainCollapsed ? "▶ 普通标签" : "▼ 普通标签";
  document.querySelector("[data-plain-tags-body]").hidden = state.plainCollapsed;
}

function matchesSelectedTags(item) {
  for (const [bucket, tags] of state.selectedTags.entries()) {
    if (!tags.size) continue;
    const values = bucket === "reading_status" ? new Set([readingStatus(item).label]) : new Set(item.semantic[bucket] || []);
    for (const tag of tags) {
      if (!values.has(tag)) return false;
    }
  }
  return true;
}

function applyFilters() {
  const query = state.search.toLowerCase();
  state.filteredItems = state.items.filter((item) => {
    if (state.selectedCollectionKey === "__unfiled" && item.collections.length) return false;
    if (state.selectedCollectionKey === "__trash" && !item.deleted) return false;
    if (state.selectedCollectionKey && !state.selectedCollectionKey.startsWith("__")) {
      if (!item.collections.some((collection) => collection.key === state.selectedCollectionKey)) return false;
    }
    if (!matchesSelectedTags(item)) return false;
    if (query) {
      const haystack = [item.title, item.creators_full_display, item.creators_display, item.venue, item.tags.join(" ")].join(" ").toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });
  renderTree();
  setupPlainToggle();
  renderTagFilters();
  renderTable();
}

function attachmentBadgeClass(label, missing = false) {
  if (missing) return "missing";
  return String(label || "file").toLowerCase().replace(/[^a-z]/g, "") || "file";
}

function renderTitleCell(item) {
  const badges = (item.attachment_badges || []).map((badge) => {
    const cls = attachmentBadgeClass(badge.label, badge.missing);
    const title = badge.missing ? "附件文件缺失" : "";
    return `<span class="attachment-badge ${cls}" title="${title}">${escapeHtml(badge.label)} ${badge.count}</span>`;
  }).join("");
  return `
    <div class="title-line">
      <span>${escapeHtml(item.title || "未命名文献")}</span>
      ${badges}
    </div>
  `;
}

function ratingCount(item) {
  const current = item.rating || "";
  const stars = [...current].filter((char) => ["★", "⭐", "🌟"].includes(char)).length;
  return stars || Number(current.replace(/\D/g, "")) || 0;
}

function paintRating(host, value) {
  host.querySelectorAll("[data-rating]").forEach((button) => {
    button.classList.toggle("lit", Number(button.dataset.rating) <= value);
  });
}

function renderRatingCell(item) {
  const count = ratingCount(item);
  if (!state.library?.editable) return `<span class="rating-readonly">${"★".repeat(count)}${"★".repeat(Math.max(0, 5 - count)).replace(/★/g, "☆")}</span>`;
  return `<div class="rating-control" data-rating-item="${item.key}" data-current-rating="${count}">
    ${[1, 2, 3, 4, 5].map((value) => `<button type="button" data-rating="${value}" class="${value <= count ? "lit" : ""}">★</button>`).join("")}
  </div>`;
}

function renderNestedCell(item) {
  const tags = item.semantic.nested || [];
  const chips = tags.map((tag) => `
    <button class="colored-tag tag-cell-chip" type="button" data-tag-popover="${item.key}" data-focus-tag="${escapeHtml(tag)}" style="--tag-color:${tagColor(tag)}" title="${escapeHtml(tag)}">
      ${escapeHtml(displayHashTag(tag))}
    </button>`).join("");
  const add = state.library?.editable ? `<button class="add-tag-chip" type="button" data-tag-popover="${item.key}">+ 标签</button>` : "";
  return `${chips}${add}`;
}

function renderReadingCell(item) {
  const status = readingStatus(item);
  const editable = Boolean(state.library?.editable);
  return `<button class="reading-chip ${status.key}" type="button" ${editable ? `data-reading-popover="${item.key}"` : "disabled"}>${status.label}</button>`;
}

function renderTableCell(item, key) {
  if (key === "title") return renderTitleCell(item);
  if (key === "rating") return renderRatingCell(item);
  if (key === "nested") return renderNestedCell(item);
  if (key === "reading_status") return renderReadingCell(item);
  if (key === "plain") {
    return (item.semantic[key] || []).map((tag) => `<span class="colored-tag" style="--tag-color:${tagColor(tag)}">${escapeHtml(tag)}</span>`).join(" ");
  }
  return escapeHtml(itemValue(item, key));
}

function renderTable() {
  const head = document.querySelector("[data-table-head]");
  const body = document.querySelector("[data-table-body]");
  if (!head || !body) return;
  const labels = new Map(ALL_COLUMNS);
  const columns = (state.columns.length ? state.columns : DEFAULT_COLUMNS).filter((key) => labels.has(key));
  head.innerHTML = `<tr>${columns.map((key) => `
    <th data-column-key="${key}" style="${state.columnWidths[key] ? `width:${state.columnWidths[key]}px` : ""}">
      <span>${labels.get(key) || key}</span><span class="resize-handle" data-resize-column="${key}"></span>
    </th>`).join("")}</tr>`;
  body.innerHTML = state.filteredItems.map((item) => `
    <tr data-item-key="${item.key}" class="${state.selectedItem?.key === item.key ? "selected" : ""}">
      ${columns.map((key) => `<td class="${key === "title" ? "title-cell" : ""}" style="${state.columnWidths[key] ? `width:${state.columnWidths[key]}px` : ""}">${renderTableCell(item, key)}</td>`).join("")}
    </tr>
  `).join("");
  body.querySelectorAll("[data-item-key]").forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("button")) return;
      state.selectedItem = state.items.find((item) => item.key === row.dataset.itemKey);
      renderTable();
      renderDetail();
    });
  });
  body.querySelectorAll("[data-tag-popover]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    state.activePopoverItemKey = button.dataset.tagPopover;
    renderTagPopover(button);
  }));
  body.querySelectorAll("[data-reading-popover]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation();
    renderReadingPopover(button);
  }));
  body.querySelectorAll("[data-rating-item]").forEach((host) => {
    const current = Number(host.dataset.currentRating || 0);
    host.querySelectorAll("button").forEach((button) => {
      button.addEventListener("mouseenter", () => paintRating(host, Number(button.dataset.rating)));
      button.addEventListener("click", async (event) => {
        event.stopPropagation();
        await postJSON(`/api/library/${state.libraryId}/items/${host.dataset.ratingItem}/rating`, { rating: Number(button.dataset.rating) }, "PATCH");
        await loadState();
      });
    });
    host.addEventListener("mouseleave", () => paintRating(host, current));
  });
  setupColumnResize();
  document.querySelector("[data-visible-count]").textContent = String(state.filteredItems.length);
  document.querySelector("[data-total-count]").textContent = String(state.items.length);
}

function setupColumnResize() {
  document.querySelectorAll("[data-resize-column]").forEach((handle) => {
    handle.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const key = handle.dataset.resizeColumn;
      const th = handle.closest("th");
      const startX = event.clientX;
      const startWidth = th.getBoundingClientRect().width;
      const onMove = (moveEvent) => {
        state.columnWidths[key] = Math.max(60, Math.round(startWidth + moveEvent.clientX - startX));
        renderTable();
      };
      const onUp = async () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        await postJSON(`/api/library/${state.libraryId}/preferences/column-widths`, { widths: state.columnWidths });
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });
}

function positionPanel(panel, anchor, width = 360) {
  const rect = anchor.getBoundingClientRect();
  panel.style.left = `${Math.max(12, Math.min(window.innerWidth - width - 12, rect.left))}px`;
  panel.style.top = `${rect.bottom + 8}px`;
}

function renderTagPopover(anchor) {
  const item = state.items.find((value) => value.key === state.activePopoverItemKey);
  if (!item) return;
  const existing = new Set(item.tags || []);
  let panel = document.querySelector("[data-tag-popover-panel]");
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "tag-popover";
    panel.dataset.tagPopoverPanel = "1";
    document.body.appendChild(panel);
  }
  positionPanel(panel, anchor);
  panel.innerHTML = `
    <div class="popover-head">
      <strong>快捷标签</strong>
      <button type="button" data-close-popover>×</button>
    </div>
    <div class="shortcut-grid">
      ${state.tagShortcuts.map((shortcut) => {
        const tag = normalizeHashTag(shortcut.tag);
        return `
        <label class="shortcut-pill" style="--tag-color:${tagColor(tag)}" title="${escapeHtml(tag)}">
          <input type="checkbox" data-toggle-item-tag="${escapeHtml(tag)}" ${existing.has(tag) ? "checked" : ""}>
          <span>${escapeHtml(displayHashTag(tag))}</span>
          <button type="button" data-delete-shortcut="${escapeHtml(tag)}" title="从快捷表删除">×</button>
        </label>`;
      }).join("") || `<span class="muted">还没有快捷标签</span>`}
    </div>
    <form class="inline-form" data-popover-new-tag>
      <input name="tag" placeholder="新增标签，例如 VLA/端到端">
      <button type="submit">添加</button>
    </form>
  `;
  panel.querySelector("[data-close-popover]").addEventListener("click", () => panel.remove());
  panel.querySelectorAll("[data-toggle-item-tag]").forEach((input) => input.addEventListener("change", async () => {
    const tag = normalizeHashTag(input.dataset.toggleItemTag);
    if (input.checked) await postJSON(`/api/library/${state.libraryId}/items/${item.key}/tags`, { tag });
    else await deleteJSON(`/api/library/${state.libraryId}/items/${item.key}/tags`, { tag });
    await loadState();
    renderTagPopover(anchor);
  }));
  panel.querySelectorAll("[data-delete-shortcut]").forEach((button) => button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    await deleteJSON(`/api/library/${state.libraryId}/tag-shortcuts`, { tag: normalizeHashTag(button.dataset.deleteShortcut) });
    await loadState();
    renderTagPopover(anchor);
  }));
  panel.querySelector("[data-popover-new-tag]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const tag = normalizeHashTag(new FormData(event.currentTarget).get("tag"));
    if (!tag || tag === "#") return;
    await postJSON(`/api/library/${state.libraryId}/tag-shortcuts`, { tag });
    await postJSON(`/api/library/${state.libraryId}/items/${item.key}/tags`, { tag });
    await loadState();
    renderTagPopover(anchor);
  });
}

function renderReadingPopover(anchor) {
  const item = state.items.find((value) => value.key === anchor.dataset.readingPopover);
  if (!item) return;
  let panel = document.querySelector("[data-reading-popover-panel]");
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "reading-popover";
    panel.dataset.readingPopoverPanel = "1";
    document.body.appendChild(panel);
  }
  positionPanel(panel, anchor, 180);
  const current = readingStatus(item).key;
  const options = [
    ["unread", "未读"],
    ["reading", "在读"],
    ["read", "已读"],
  ];
  panel.innerHTML = options.map(([key, label]) => `<button type="button" class="${key === current ? "active" : ""}" data-reading-status="${key}">${label}</button>`).join("");
  panel.querySelectorAll("[data-reading-status]").forEach((button) => button.addEventListener("click", async () => {
    await postJSON(`/api/library/${state.libraryId}/items/${item.key}/reading-status`, { status: button.dataset.readingStatus }, "PATCH");
    panel.remove();
    await loadState();
  }));
}

function renderDetail() {
  const detail = document.querySelector("[data-detail]");
  const type = document.querySelector("[data-detail-type]");
  const item = state.selectedItem;
  if (!detail || !item) return;
  type.textContent = item.type || "";
  const editable = Boolean(state.library?.editable);
  detail.className = "detail-scroll";
  detail.innerHTML = `
    <section class="detail-card">
      <h3>${escapeHtml(item.title)}</h3>
      <p class="muted">${escapeHtml(item.creators_full_display || item.creators_display)} · ${escapeHtml(item.year)} · ${escapeHtml(item.venue || item.type)}</p>
      <p>${escapeHtml(item.fields.abstractNote || "暂无摘要")}</p>
    </section>
    <section class="detail-card">
      <h3>语义标签</h3>
      <div class="field-grid">
        <span>评分</span><strong>${escapeHtml(textOf(item.semantic.rating) || "-")}</strong>
        <span>#标签</span><strong>${(item.semantic.nested || []).map((tag) => `<span class="colored-tag" style="--tag-color:${tagColor(tag)}" title="${escapeHtml(tag)}">${escapeHtml(displayHashTag(tag))}</span>`).join(" ") || "-"}</strong>
        <span>阅读状态</span><strong><span class="reading-chip ${readingStatus(item).key}">${readingStatus(item).label}</span></strong>
        <span>期刊等级</span><strong>${escapeHtml(textOf(item.semantic.venue_rank) || "-")}</strong>
        <span>普通标签</span><strong>${escapeHtml(textOf(item.semantic.plain) || "-")}</strong>
      </div>
      ${editable ? `
      <form class="inline-form" data-add-tag-form>
        <input name="tag" placeholder="新增 # 标签，例如 VLA/端到端">
        <button type="submit">添加</button>
      </form>` : `<p class="muted">只读连接模式不能修改标签。</p>`}
    </section>
    <section class="detail-card">
      <h3>附件与笔记</h3>
      ${(item.attachments || []).map((attachment) => `
        <p class="attachment-line">
          ${attachment.openable ? `<a href="/api/library/${state.libraryId}/attachments/${attachment.key}" target="_blank">${escapeHtml(attachment.display_label)}</a>` : `<span class="muted" title="附件文件缺失或不可直接打开">${escapeHtml(attachment.display_label)}</span>`}
          <span class="attachment-badge ${attachmentBadgeClass(attachment.kind, attachment.status === "missing")}">${escapeHtml(attachment.kind)} · ${attachment.status === "missing" ? "缺失" : escapeHtml(attachment.status)}</span>
        </p>
      `).join("") || `<p class="muted">没有文件附件</p>`}
      ${(item.notes || []).map((note) => `<p><strong>Note</strong> ${escapeHtml(note.note.replace(/<[^>]*>/g, " ").slice(0, 500))}</p>`).join("")}
    </section>
    <section class="detail-card">
      <h3>所在文件夹</h3>
      <div class="field-grid">
        <span>当前</span><strong>${escapeHtml(textOf((item.collections || []).map((collection) => collection.name)) || "未分类")}</strong>
      </div>
      ${editable ? `
      <form class="inline-form" data-membership-form>
        <select name="collection_key">
          ${state.collections.map((collection) => `<option value="${collection.key}">${escapeHtml(collection.name)}</option>`).join("")}
        </select>
        <select name="enabled">
          <option value="true">加入</option>
          <option value="false">移出</option>
        </select>
        <button type="submit">应用</button>
      </form>` : `<p class="muted">只读连接模式不能调整文件夹归属。</p>`}
    </section>
    <section class="detail-card">
      <h3>原生字段</h3>
      <div class="field-grid">${Object.entries(item.fields).map(([key, value]) => `<span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong>`).join("")}</div>
      ${editable ? `
      <form class="inline-form" data-edit-field-form>
        <select name="field">
          <option value="title">title</option>
          <option value="publicationTitle">publicationTitle</option>
          <option value="date">date</option>
          <option value="DOI">DOI</option>
          <option value="url">url</option>
          <option value="abstractNote">abstractNote</option>
          <option value="extra">extra</option>
        </select>
        <input name="value" placeholder="新值">
        <button type="submit">保存</button>
      </form>` : ""}
    </section>
  `;
  detail.querySelector("[data-add-tag-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    payload.tag = normalizeHashTag(payload.tag);
    await postJSON(`/api/library/${state.libraryId}/items/${item.key}/tags`, payload);
    await postJSON(`/api/library/${state.libraryId}/tag-shortcuts`, { tag: payload.tag });
    await loadState();
  });
  detail.querySelector("[data-edit-field-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    await postJSON(`/api/library/${state.libraryId}/items/${item.key}/field`, payload, "PATCH");
    await loadState();
  });
  detail.querySelector("[data-membership-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    payload.enabled = payload.enabled === "true";
    await postJSON(`/api/library/${state.libraryId}/items/${item.key}/collections`, payload);
    await loadState();
  });
}

function setupColumnsPanel() {
  document.querySelectorAll("[data-open-columns]").forEach((button) => button.addEventListener("click", () => {
    const active = new Set(state.columns);
    state.columnDraft = [...state.columns, ...ALL_COLUMNS.map(([key]) => key).filter((key) => !active.has(key))];
    renderColumnPanel();
    document.querySelector("[data-column-panel]").hidden = false;
  }));
  document.querySelector("[data-close-columns]")?.addEventListener("click", () => {
    document.querySelector("[data-column-panel]").hidden = true;
  });
  document.querySelector("[data-save-columns]")?.addEventListener("click", async () => {
    const columns = [...document.querySelectorAll("[data-column-check]")]
      .filter((input) => input.checked)
      .map((input) => input.value);
    await postJSON(`/api/library/${state.libraryId}/preferences/columns`, { columns });
    state.columns = columns;
    document.querySelector("[data-column-panel]").hidden = true;
    renderTable();
  });
}

function renderColumnPanel() {
  const host = document.querySelector("[data-column-list]");
  const active = new Set(state.columns);
  const ordered = state.columnDraft.length ? state.columnDraft : [...state.columns, ...ALL_COLUMNS.map(([key]) => key).filter((key) => !active.has(key))];
  const labels = new Map(ALL_COLUMNS);
  host.innerHTML = ordered.map((key, index) => `
    <label class="column-row">
      <input type="checkbox" data-column-check value="${key}" ${active.has(key) ? "checked" : ""}>
      <span>${labels.get(key) || key}</span>
      <button type="button" data-col-up="${index}">↑</button>
      <button type="button" data-col-down="${index}">↓</button>
    </label>
  `).join("");
  function move(index, delta) {
    const checked = new Map([...host.querySelectorAll("[data-column-check]")].map((input) => [input.value, input.checked]));
    const keys = [...host.querySelectorAll("[data-column-check]")].map((input) => input.value);
    const next = index + delta;
    if (next < 0 || next >= keys.length) return;
    [keys[index], keys[next]] = [keys[next], keys[index]];
    state.columnDraft = keys;
    state.columns = keys.filter((key) => checked.get(key));
    renderColumnPanel();
  }
  host.querySelectorAll("[data-col-up]").forEach((button) => button.addEventListener("click", () => move(Number(button.dataset.colUp), -1)));
  host.querySelectorAll("[data-col-down]").forEach((button) => button.addEventListener("click", () => move(Number(button.dataset.colDown), 1)));
}

async function loadState() {
  const data = await fetch(`/api/library/${state.libraryId}/state`).then((response) => response.json());
  if (!data.ok) throw new Error(data.error || "加载失败");
  state.library = data.library;
  state.items = data.items || [];
  state.collections = data.collections || [];
  state.tagShortcuts = data.tag_shortcuts || [];
  state.columns = (data.library.columns || DEFAULT_COLUMNS).filter((key) => new Map(ALL_COLUMNS).has(key));
  state.columnWidths = data.library.column_widths || {};
  state.plainCollapsed = data.library.plain_tags_collapsed !== false;
  if (state.selectedItem) state.selectedItem = state.items.find((item) => item.key === state.selectedItem.key) || null;
  document.querySelector("[data-unsynced]").textContent = `未同步 ${data.library.unsynced_count || 0}`;
  document.querySelector("[data-create-collection-form]").hidden = !data.library.editable;
  applyFilters();
  renderDetail();
}

function renderGlobalShortcutPanel(anchor) {
  let panel = document.querySelector("[data-tag-popover-panel]");
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "tag-popover";
    panel.dataset.tagPopoverPanel = "1";
    document.body.appendChild(panel);
  }
  positionPanel(panel, anchor);
  panel.innerHTML = `
    <div class="popover-head">
      <strong>快捷标签表</strong>
      <button type="button" data-close-popover>×</button>
    </div>
    <div class="shortcut-grid">
      ${state.tagShortcuts.map((shortcut) => {
        const tag = normalizeHashTag(shortcut.tag);
        return `<span class="shortcut-pill" style="--tag-color:${tagColor(tag)}"><span>${escapeHtml(displayHashTag(tag))}</span><button type="button" data-delete-shortcut="${escapeHtml(tag)}">×</button></span>`;
      }).join("") || `<span class="muted">还没有快捷标签</span>`}
    </div>
    <form class="inline-form" data-global-new-tag>
      <input name="tag" placeholder="新增标签，例如 多提示词">
      <button type="submit">添加</button>
    </form>
  `;
  panel.querySelector("[data-close-popover]").addEventListener("click", () => panel.remove());
  panel.querySelectorAll("[data-delete-shortcut]").forEach((button) => button.addEventListener("click", async () => {
    await deleteJSON(`/api/library/${state.libraryId}/tag-shortcuts`, { tag: normalizeHashTag(button.dataset.deleteShortcut) });
    await loadState();
    renderGlobalShortcutPanel(anchor);
  }));
  panel.querySelector("[data-global-new-tag]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const tag = normalizeHashTag(new FormData(event.currentTarget).get("tag"));
    if (!tag || tag === "#") return;
    await postJSON(`/api/library/${state.libraryId}/tag-shortcuts`, { tag });
    await loadState();
    renderGlobalShortcutPanel(anchor);
  });
}

function setupLibraryPage() {
  const root = document.querySelector("[data-library-page]");
  if (!root) return;
  state.libraryId = root.dataset.libraryId;
  document.querySelector("[data-table-search]")?.addEventListener("input", (event) => {
    state.search = event.target.value;
    applyFilters();
  });
  document.querySelector("[data-tag-search]")?.addEventListener("input", renderTagFilters);
  document.querySelector("[data-toggle-plain-tags]")?.addEventListener("click", async () => {
    state.plainCollapsed = !state.plainCollapsed;
    await postJSON(`/api/library/${state.libraryId}/preferences/plain-tags`, { collapsed: state.plainCollapsed });
    applyFilters();
  });
  document.querySelector("[data-create-collection-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    await postJSON(`/api/library/${state.libraryId}/collections`, payload);
    event.currentTarget.reset();
    await loadState();
  });
  document.querySelector("[data-manage-shortcuts]")?.addEventListener("click", (event) => {
    renderGlobalShortcutPanel(event.currentTarget);
  });
  setupColumnsPanel();
  loadState().catch((error) => window.alert(error.message));
}

setupSourceForms();
setupLibraryPage();
