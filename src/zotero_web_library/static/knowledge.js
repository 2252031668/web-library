const knowledgeState = {
  libraries: [
    { knowledge_base_id: "kb-core", name: "核心论文知识库", item_count: 18, updated_at: "2026-07-02" },
    { knowledge_base_id: "kb-method", name: "方法综述知识库", item_count: 9, updated_at: "2026-07-01" },
    { knowledge_base_id: "kb-dataset", name: "数据与评测知识库", item_count: 12, updated_at: "2026-06-30" },
  ],
  activeId: "kb-core",
  sidebarCollapsed: false,
  matrixFields: [
    { id: "field-1", name: "研究问题", rule: "判断论文要解决的核心科学问题或工程问题。" },
    { id: "field-2", name: "方法思路", rule: "提炼论文的核心方法、模型结构、算法流程或系统设计。" },
    { id: "field-3", name: "实验设置", rule: "概括论文使用的数据集、任务场景、实验指标、基线和 ablation 设计。" },
    { id: "field-4", name: "核心结论", rule: "总结论文得到的关键发现、实验结论、有效性证明和边界条件。" },
  ],
  itemsByLibrary: {
    "kb-core": [
      { title: "多模态机器人感知综述", matrix: ["聚焦复杂场景感知", "多模态融合与时序建模", "室内导航与操作", "融合策略在泛化上更稳健"] },
      { title: "具身智能任务规划框架", matrix: ["面向长任务分解", "层级规划与反馈纠错", "长程任务基准", "规划器决定整体成功率上限"] },
      { title: "机器人操作学习的评测体系", matrix: ["统一操作评测口径", "指标体系与基准集合", "跨任务跨平台对比", "缺统一评测会放大结论偏差"] },
    ],
    "kb-method": [
      { title: "视觉语言动作模型方法对比", matrix: ["统一 VLA 方法边界", "预训练加策略微调", "多机器人迁移实验", "数据质量比模型堆叠更关键"] },
      { title: "世界模型驱动的机器人控制", matrix: ["压缩建模与预测控制", "latent world model", "仿真到真实迁移", "规划质量受状态抽象影响大"] },
      { title: "检索增强机器人决策", matrix: ["外部知识辅助决策", "RAG 加任务记忆", "开放任务测试", "检索命中率影响任务稳定性"] },
    ],
    "kb-dataset": [
      { title: "机器人操作数据集盘点", matrix: ["数据规模与标注差异", "多源数据整合", "抓取装配导航", "缺元数据会拖累复现效率"] },
      { title: "仿真评测基准集合", matrix: ["统一 benchmark 入口", "场景模板化", "公开 leaderboard", "任务定义要先于模型比较"] },
      { title: "真实环境长期执行日志", matrix: ["关注长时稳定性", "日志驱动误差归因", "月级别运行统计", "长期漂移比单次成功率更重要"] },
    ],
  },
};

function knowledgeQuery(selector) {
  return document.querySelector(selector);
}

function knowledgeStorageKey(name) {
  const libraryId = document.body.dataset.libraryId || "default";
  return `knowledge-workbench:${libraryId}:${name}`;
}

function activeKnowledgeLibrary() {
  return knowledgeState.libraries.find((entry) => entry.knowledge_base_id === knowledgeState.activeId) || knowledgeState.libraries[0];
}

function activeKnowledgeItems() {
  return knowledgeState.itemsByLibrary[knowledgeState.activeId] || [];
}

function applyKnowledgeSidebarState() {
  const workbench = knowledgeQuery("[data-knowledge-workbench]");
  const button = knowledgeQuery("[data-toggle-knowledge-sidebar]");
  workbench?.classList.toggle("sidebar-collapsed", knowledgeState.sidebarCollapsed);
  if (button) {
    button.textContent = knowledgeState.sidebarCollapsed ? "▶" : "◀";
    button.title = knowledgeState.sidebarCollapsed ? "展开列表" : "折叠列表";
    button.setAttribute("aria-label", button.title);
  }
}

function setupKnowledgeSplitters() {
  document.querySelectorAll("[data-knowledge-splitter]").forEach((splitter) => {
    splitter.addEventListener("pointerdown", (event) => {
      const side = splitter.dataset.knowledgeSplitter;
      const startX = event.clientX;
      const currentSidebar = Number.parseInt(getComputedStyle(document.documentElement).getPropertyValue("--knowledge-sidebar-width"), 10) || 280;
      const currentChat = Number.parseInt(getComputedStyle(document.documentElement).getPropertyValue("--knowledge-chat-width"), 10) || 340;
      splitter.setPointerCapture(event.pointerId);
      function onMove(moveEvent) {
        const delta = moveEvent.clientX - startX;
        if (side === "left") {
          const width = Math.max(180, Math.min(420, currentSidebar + delta));
          document.documentElement.style.setProperty("--knowledge-sidebar-width", `${width}px`);
          localStorage.setItem(knowledgeStorageKey("sidebarWidth"), String(width));
        } else {
          const width = Math.max(260, Math.min(520, currentChat - delta));
          document.documentElement.style.setProperty("--knowledge-chat-width", `${width}px`);
          localStorage.setItem(knowledgeStorageKey("chatWidth"), String(width));
        }
      }
      function onUp() {
        splitter.removeEventListener("pointermove", onMove);
        splitter.removeEventListener("pointerup", onUp);
      }
      splitter.addEventListener("pointermove", onMove);
      splitter.addEventListener("pointerup", onUp);
    });
  });
}

function renderKnowledgeList() {
  const host = knowledgeQuery("[data-knowledge-list]");
  if (!host) return;
  host.innerHTML = knowledgeState.libraries
    .map(
      (item) => `
    <button type="button" class="compact-list-item ${item.knowledge_base_id === knowledgeState.activeId ? "active" : ""}" data-knowledge-item="${item.knowledge_base_id}">
      <span class="compact-list-text">
        <strong>${item.name}</strong>
        <small>${item.item_count || 0} 条文献 · 更新于 ${String(item.updated_at || "").slice(0, 10)}</small>
      </span>
      <span class="compact-list-actions">
        <span class="compact-icon-btn">占位</span>
      </span>
    </button>
  `,
    )
    .join("");
  host.querySelectorAll("[data-knowledge-item]").forEach((button) =>
    button.addEventListener("click", () => {
      knowledgeState.activeId = button.dataset.knowledgeItem || "";
      renderKnowledgeList();
      renderKnowledgeMatrix();
    }),
  );
}

function renderMatrixFields() {
  const host = knowledgeQuery("[data-matrix-field-list]");
  if (!host) return;
  host.innerHTML = knowledgeState.matrixFields
    .map(
      (field) => `
    <article class="matrix-field-card" data-field-id="${field.id}">
      <label>
        <span>字段名称</span>
        <input value="${field.name}">
      </label>
      <label>
        <span>判断依据和格式要求</span>
        <textarea>${field.rule}</textarea>
      </label>
      <button class="icon-action-btn danger" type="button" data-knowledge-placeholder-action="delete-field" title="删除字段">×</button>
    </article>
  `,
    )
    .join("");
}

function renderKnowledgeMatrix() {
  const library = activeKnowledgeLibrary();
  const items = activeKnowledgeItems();
  const title = knowledgeQuery("[data-knowledge-current-title]");
  const head = knowledgeQuery("[data-knowledge-matrix-head]");
  const body = knowledgeQuery("[data-knowledge-matrix-body]");
  const status = knowledgeQuery("[data-reading-matrix-status]");
  if (title && library) title.textContent = `${library.name} · 字段设置与矩阵表格`;
  if (status) status.innerHTML = `<span>当前知识库展示 ${items.length} 条占位文献，用于确认三栏结构和矩阵阅读体验。</span>`;
  renderMatrixFields();
  if (!head || !body) return;
  head.innerHTML = `
    <tr>
      <th>名称</th>
      ${knowledgeState.matrixFields.map((field) => `<th>${field.name}</th>`).join("")}
    </tr>
  `;
  body.innerHTML = items
    .map(
      (item) => `
    <tr>
      <td>${item.title}</td>
      ${knowledgeState.matrixFields.map((_, index) => `<td>${item.matrix[index] || "未提取"}</td>`).join("")}
    </tr>
  `,
    )
    .join("");
}

function notifyKnowledgePlaceholder(action) {
  const labels = {
    create: "新建知识库",
    "add-field": "新增字段",
    "recommend-fields": "AI 推荐字段",
    "save-fields": "保存字段",
    "run-matrix": "运行文献矩阵",
    compress: "压缩记忆",
    send: "发送任务",
    "delete-field": "删除字段",
  };
  window.alert(`${labels[action] || "该功能"}暂未实现，当前仅提供知识库界面占位。`);
}

function setupKnowledgePage() {
  if (!document.querySelector("[data-knowledge-page]")) return;
  const sidebarWidth = Number.parseInt(localStorage.getItem(knowledgeStorageKey("sidebarWidth")) || "", 10);
  const chatWidth = Number.parseInt(localStorage.getItem(knowledgeStorageKey("chatWidth")) || "", 10);
  if (sidebarWidth) document.documentElement.style.setProperty("--knowledge-sidebar-width", `${sidebarWidth}px`);
  if (chatWidth) document.documentElement.style.setProperty("--knowledge-chat-width", `${chatWidth}px`);
  knowledgeState.sidebarCollapsed = localStorage.getItem(knowledgeStorageKey("sidebarCollapsed")) === "true";
  knowledgeQuery("[data-toggle-knowledge-sidebar]")?.addEventListener("click", () => {
    knowledgeState.sidebarCollapsed = !knowledgeState.sidebarCollapsed;
    localStorage.setItem(knowledgeStorageKey("sidebarCollapsed"), String(knowledgeState.sidebarCollapsed));
    applyKnowledgeSidebarState();
  });
  knowledgeQuery("[data-add-matrix-field]")?.addEventListener("click", () => notifyKnowledgePlaceholder("add-field"));
  knowledgeQuery("[data-recommend-matrix-fields]")?.addEventListener("click", () => notifyKnowledgePlaceholder("recommend-fields"));
  knowledgeQuery("[data-save-matrix-fields]")?.addEventListener("click", () => notifyKnowledgePlaceholder("save-fields"));
  knowledgeQuery("[data-run-reading-matrix]")?.addEventListener("click", () => notifyKnowledgePlaceholder("run-matrix"));
  knowledgeQuery("[data-knowledge-placeholder-action=\"create\"]")?.addEventListener("click", () => notifyKnowledgePlaceholder("create"));
  knowledgeQuery("[data-knowledge-placeholder-action=\"compress\"]")?.addEventListener("click", () => notifyKnowledgePlaceholder("compress"));
  knowledgeQuery("[data-knowledge-placeholder-action=\"send\"]")?.addEventListener("click", () => notifyKnowledgePlaceholder("send"));
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-knowledge-placeholder-action=\"delete-field\"]");
    if (button) notifyKnowledgePlaceholder("delete-field");
  });
  applyKnowledgeSidebarState();
  setupKnowledgeSplitters();
  renderKnowledgeList();
  renderKnowledgeMatrix();
}

setupKnowledgePage();
