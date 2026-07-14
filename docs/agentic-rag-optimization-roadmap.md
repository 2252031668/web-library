# Agentic RAG 优化路线图

状态：执行中  
建立日期：2026-07-14  
适用范围：知识库问答、统一检索、文献矩阵、综述写作及其共享证据链

## 一、项目所处阶段

当前项目的主要产品功能和端到端入口已经基本齐全：

- Zotero 文库接入、本地副本和只读访问。
- 文献、附件、PDF 阅读、标注和元数据管理。
- 多源外部检索、候选筛选和导入。
- 知识库管理、RAG 索引和知识库作用域。
- metadata、BM25 keyword、semantic 和 hybrid 检索。
- 带工具调用、证据引用、会话记忆和作用域快照的知识库 Agent 对话。
- 文献矩阵字段管理、AI 推荐、批量运行、进度展示和结果持久化。
- 综述写作工作台、大纲、文献映射和正文生成。

因此，项目已经进入“从功能完整走向质量成熟”的阶段，而不是继续堆叠页面和功能入口。

需要明确的是，“功能存在”不等于“能力成熟”。当前主要差距集中在：

1. 已有一套最小离线回归基线，但现阶段暂不继续扩建评测指标体系。
2. Hybrid Retrieval 仍是轻量实现，结构化分块、查询分解、融合排序和 rerank 能力有限。
3. Agent 已具备 ReAct 式动态工具调用，但还没有显式的计划、证据状态、缺口检测和独立验证闭环。
4. 文献矩阵仍是独立的 PDF 到 JSON 抽取流程，尚未复用 RAG 检索，也没有单元格级证据链。
5. 矩阵、问答和写作尚未完全共享同一套 claim-evidence 数据模型。
6. 图表、表格、公式、引用网络和外部检索回退仍属于后续增强能力。

## 二、当前能力盘点

| 能力 | 当前状态 | 主要缺口 |
|---|---|---|
| 文库与附件 | 基本完整 | 大规模文库性能和更多附件格式仍需验证 |
| 多源检索与导入 | 已形成完整工作流 | 与知识库 Agent 的自动补充检索尚未打通 |
| 知识库作用域 | 已实现并由后端强制 | 需要持续增加越权和删除场景测试 |
| Keyword Retrieval | 已实现 SQLite FTS5/BM25 | 缺少查询改写、结构化过滤和结果多样性控制 |
| Semantic Retrieval | 已实现 Embedding provider 和 SQLite 向量检索 | 大规模向量检索、模型版本迁移和 provider 健康管理仍需加强 |
| Hybrid Retrieval | 已实现多查询标准 RRF、可选 reranker、coverage、多样性和故障降级 | 后续根据实际运行反馈调整规则和参数 |
| Agentic Chat | 已实现工具调用、多轮会话、证据累积和引用 | 缺少显式规划、证据充分性判断、claim verifier 和自适应预算 |
| 会话持久化 | 已保存并支持重新进入页面恢复 | 后续需要多会话列表、重命名、删除和长期记忆压缩 |
| 文献矩阵 | 已支持字段、批处理、进度和本地存储 | 当前直接读取 PDF，缺少 RAG、sources、confidence、单元格重跑和人工复核状态 |
| 综述写作 | 已具备完整工作台 | 需要统一矩阵和 RAG 的底层证据引用，减少不可追溯生成 |
| 可观测性 | 已有 tool trace、usage 和 warnings | 统一 trace id、阶段耗时和结构化错误分类推迟到后续阶段 |
| 自动化测试 | 已覆盖主要后端、前端契约和 20 条最小离线回归 | 现阶段只维护已有回归资产，不继续扩建评测平台 |

## 三、什么叫“真正的 Agency”

本项目不把“模型会调用工具”直接等同于完整 Agency。

目标中的 Agent 应当具备以下闭环能力：

```text
理解用户目标
  -> 判断任务类型与成功条件
  -> 分解子问题并生成检索计划
  -> 选择并执行受控工具
  -> 更新证据状态
  -> 识别缺失、冲突或低质量证据
  -> 改写查询、切换检索策略或深读上下文
  -> 验证每个事实主张与引用的对应关系
  -> 在证据充分时回答，在证据不足时说明缺口
  -> 保存可恢复、可审计的任务状态
```

Agency 的核心不是工具数量，而是 Agent 能否根据环境反馈改变计划、从失败中恢复、验证结果并在正确时机停止。

## 四、总体实施原则

后续开发统一遵循以下原则：

1. **回归资产保留但不阻塞开发**：维护已有测试和 Iteration 0.1 基线，暂不继续建设评测平台。
2. **证据优先**：所有事实型输出都应能回到 item、chunk、页码、图表、笔记或矩阵单元格来源。
3. **作用域由后端控制**：模型和前端不能扩大知识库或会话快照的检索范围。
4. **优雅降级**：语义检索、reranker 或外部服务故障时，保留仍可用的本地能力并返回结构化 warning。
5. **状态可观察**：计划、工具调用、证据、失败、预算和停止原因都应可以审计。
6. **先单 Agent，后多 Agent**：先把一个 Agent 的计划、执行和验证闭环做扎实，再根据实际运行瓶颈决定是否拆分角色。
7. **先解决质量瓶颈，再替换基础设施**：SQLite 尚能满足规模时，不因为技术潮流提前迁移向量数据库。
8. **每阶段做行为验收**：以功能契约、回归测试和故障降级是否成立判断阶段结果。

## 五、分阶段路线

### Phase 0：已保留的最小回归基础（暂停扩建）

状态：已完成 Iteration 0.1；按当前开发决策，Iteration 0.2–0.4 不再作为前置阶段。

已保留的资产：

- [x] `evals/agentic_rag/` 下的 case schema、20 条最小烟雾问题和合成语料。
- [x] 可重复运行的离线入口与 JSON/Markdown baseline 报告。
- [x] 由基线发现并修复的 FTS5 连字符查询回归测试。

后续只维护这些已有资产，不继续建设 Retrieval/回答/Agency 指标、模型辅助评估、统一 trace 平台或 CI 质量阈值。开发顺序直接进入 Phase 1。

### Phase 1：检索质量升级

目标：让 Agent 得到更完整、更相关且覆盖合理的证据集合。

状态：已完成；完整回归为 285 passed。

#### 工作项

- [x] 基于 MinerU Markdown 标题层级实现结构化 chunk。
- [x] 引入 parent-child chunk：小块用于召回，父级上下文用于回答。
- [x] 为表格、图注、References、摘要、方法和实验结果标记明确的 chunk 类型。
- [x] 实现任务类型识别：factual、summary、comparative、matrix、writing、scope。
- [x] 实现中英文查询规范化、关键词扩展和多查询改写。
- [x] 对复杂问题生成多个子查询，并保存 query lineage。
- [x] 将当前轻量加权融合升级为规范的 Reciprocal Rank Fusion。
- [x] 增加可选 cross-encoder reranker，并保持失败可降级。
- [x] 增加 MMR 或等价多样性策略，避免结果全部来自同一论文或相邻 chunk。
- [x] 比较类任务增加 per-item coverage 约束。
- [x] 增加 metadata filters：年份、作者、venue、item_key、chunk_type。
- [x] 对 Embedding 模型、维度和内容版本建立明确的索引版本和迁移策略。
- [x] 当前继续使用 SQLite；只有确认扫描成为实际瓶颈后才接入 FAISS/HNSW 或外部 vector store。

#### 验收标准

- 结构化 chunk 能保留标题路径和明确类型，命中子块后可读取其父级章节上下文。
- 比较类问题的候选结果在作用域允许时覆盖多篇论文，不会被单篇论文垄断。
- Reranker 或 Embedding 服务失败时，系统仍能用本地检索完成请求。
- 检索日志可以解释每条结果来自哪个 query、检索器和排序阶段。

### Phase 1.5：Agentic RAG Skill 与运行时契约统一

目标：让 Skill、工具 schema、Evidence Pack 和知识库 Function Calling Agent 使用同一套 Phase 1 能力与证据规则，为 Phase 2 状态机建立稳定的行为基线。

状态：已完成；Skill 结构校验通过，完整回归为 291 passed。

#### 工作项

- [x] 更新 `skills/agentic-rag/SKILL.md` 的触发描述、任务分类、检索闭环、证据充分性和停止规则。
- [x] 更新 tool contract，加入 filters、parent context、query lineage、ranking stages 和结构化 warnings。
- [x] 更新 retrieval policy，明确比较任务 coverage、结构化 chunk 选择、失败降级和避免重复检索。
- [x] 更新 citation contract，明确父级上下文、表格/图注文本和未实现多模态能力的引用边界。
- [x] 让 `/rag/chat` 的 Function Calling Agent 实际加载主 Skill 与 references，而不是只依赖重复维护的硬编码 prompt。
- [x] 保持 Codex SDK 的 `SkillInput` 路径与 Function Calling Agent 指向同一 Skill 目录。
- [x] 校验 `agents/openai.yaml` 与更新后的 Skill 一致。
- [x] 增加 Skill 加载、prompt 注入、工具契约和能力边界回归测试。

#### 验收标准

- 知识库聊天的 system prompt 中存在实际 Skill 内容及必要 references，且缺失文件时有明确错误。
- Agent 能从工具说明中获知 filters 和 parent context，但不能通过 filters 扩大后端作用域。
- Skill 明确区分检索分数与事实置信度，并能处理 semantic/reranker 降级 warning。
- Skill 不会声称当前已具备 `read_matrix`、图片理解或尚未实现的 Phase 2 状态机能力。
- Skill 目录通过结构校验，相关专项测试和完整回归通过。

### Phase 2：显式 Agency 控制器

目标：从隐式 ReAct 提示词升级为可验证、可恢复的 Agent 状态机。

#### 工作项

- [ ] 定义 `TaskPlan`：目标、任务类型、子问题、期望证据类型、预算和完成条件。
- [ ] 定义 `EvidenceState`：已覆盖主张、待确认主张、冲突证据和证据缺口。
- [ ] 将 Agent 主循环显式拆为 plan、retrieve、inspect、read、verify、answer/abstain 状态。
- [ ] 增加 evidence sufficiency judge，不只依赖生成模型一句“证据足够”。
- [ ] 增加 claim-evidence verifier，逐条核对最终回答中的事实主张和 citation。
- [ ] 发现证据缺口时，允许 Agent 改写 query、切换 mode、补读 chunk 或列出 scope 文献。
- [ ] 工具失败时根据错误类别决定重试、降级、换工具或停止。
- [ ] 使用自适应预算：简单问题快速回答，复杂比较任务允许更多检索步骤。
- [ ] 保存停止原因：completed、insufficient_evidence、budget_exceeded、provider_unavailable、user_action_required。
- [ ] 防止重复调用相同工具参数，建立 invocation cache 或重复检测。
- [ ] 把计划摘要、证据覆盖和验证结果加入可折叠前端 trace。

#### 验收标准

- Agent 能在测试中识别缺失证据并主动换查询或深读，而不是直接编造。
- 已覆盖的工具失败场景能够按错误类型恢复、降级或明确停止。
- 最终回答中的事实型 claim 可以逐条映射到有效 citation。
- Agent 能解释为什么停止检索，以及是完成还是证据不足。
- 工具调用数量和 token 消耗相对任务复杂度合理，不靠固定轮数硬撑。

### Phase 3：统一文献矩阵、问答与写作证据链

目标：让矩阵不再是孤立的 PDF 摘要生成器，而成为可追溯的研究数据层。

#### 工作项

- [ ] 文献矩阵改用统一 `retrieve` + `read_chunk_context` 工具链。
- [ ] 一个矩阵字段对应一个明确的抽取任务和成功条件。
- [ ] 每个单元格保存 answer、sources、confidence、tool_trace、status 和 error。
- [ ] 增加 `needs_review`、`insufficient_evidence` 和 `conflicting_evidence` 状态。
- [ ] 支持单元格重跑、整篇重跑、覆盖现有结果和只补空值。
- [ ] 支持用户编辑结果，同时保留模型版本和原始生成记录。
- [ ] 支持点开单元格查看引用 chunk、章节、页码和摘录。
- [ ] 为知识库 Agent 增加只读 `read_matrix` / `compare_matrix` 工具。
- [ ] 写作 Agent 使用矩阵结论时继续保留下层 chunk citation。
- [ ] 统一矩阵 JSON 文件和设计文档中 `rag_matrix_*` 表的长期存储方案，避免两套真值并存。
- [ ] 将当前仅提取 PDF 前 12 页、最多 12000 字的限制替换为按字段检索相关章节。

#### 验收标准

- 任意矩阵单元格都能回到至少一条实际证据，或明确标记证据不足。
- RAG 对话可以读取矩阵结果，但不能绕过其底层证据。
- 写作输出中的矩阵结论可以继续追溯到论文 chunk。
- 单篇失败不会导致整个矩阵任务失败，任务支持停止和恢复。

### Phase 4：高级研究能力

目标：覆盖真实科研工作中仅靠纯文本 chunk 无法处理的任务。

#### 工作项

- [ ] 实现表格、图注、图片和公式的结构化索引。
- [ ] 增加 `figure_read` / `table_read` 工具和多模态证据类型。
- [ ] 解析 References，并构建本地条目匹配和引用图谱。
- [ ] 支持根据引用关系发现基础工作、对比工作和证据冲突。
- [ ] 当知识库证据不足时，经用户授权调用现有多源外部检索流程。
- [ ] 外部结果必须先进入候选审核或受控临时证据区，不能直接混入本地知识库真值。
- [ ] 为长任务增加 durable job、checkpoint、pause/resume 和取消能力。
- [ ] 建立三层记忆：短期对话、任务摘要、用户偏好；论文事实不能写入无来源的偏好记忆。
- [ ] 支持研究任务 DAG，例如“发现文献 -> 导入 -> 解析 -> 索引 -> 对比 -> 矩阵 -> 写作”。

#### 验收标准

- 图表和表格问题返回可追溯的多模态来源。
- 外部补充检索只能在明确授权和受控作用域下发生。
- 长任务在进程中断后可以从 checkpoint 恢复。
- 会话压缩不会改变知识库作用域或丢失关键来源。

### Phase 5：规模化与条件式多 Agent

目标：只在单 Agent 闭环稳定且确认存在实际瓶颈后，解决吞吐、成本和复杂任务并行问题。

#### 工作项

- [ ] 根据 Phase 1–4 的运行反馈识别是否真的存在角色拆分收益。
- [ ] 评估 planner、researcher、verifier 分工，而不是默认引入多 Agent。
- [ ] 对独立子问题并行检索，但统一共享受控 scope 和 evidence registry。
- [ ] 增加模型路由：轻模型做分类/改写，强模型做复杂规划和最终综合。
- [ ] 增加检索、Embedding、rerank 和验证缓存。
- [ ] 建立并发、速率限制、成本配额和任务优先级。
- [ ] 对大规模文库引入独立向量索引和增量重建机制。

#### 验收标准

- 多 Agent 或模型路由必须解决已经确认的成功率、延迟或成本问题。
- 并行执行不会造成跨知识库越权、证据重复污染或不可解释的最终结论。
- 如果没有量化收益，继续保留更简单的单 Agent 架构。

## 六、推荐执行顺序

后续严格按以下顺序推进：

1. Phase 1：结构化 chunk、查询分解、RRF、reranker 和 coverage。
2. Phase 1.5：统一 Skill、工具契约和 Function Calling 运行时注入。
3. Phase 2：TaskPlan、EvidenceState、证据缺口检测和 claim verifier。
4. Phase 3：矩阵接入 RAG，并统一问答、矩阵和写作证据链。
5. Phase 4：图表、引用图谱、外部检索回退、长任务和分层记忆。
6. Phase 5：仅在已确认有收益时再做多 Agent、模型路由和规模化基础设施。

Iteration 0.1 作为已有回归资产继续保留；不要在 SQLite 尚未成为性能瓶颈时优先迁移向量数据库。

## 七、当前执行迭代

### Iteration 0.1：评测契约

状态：已完成。确定性 `retrieve` 基线为 20/20 通过；报告保存在 `evals/agentic_rag/reports/`。首次运行发现并修复了 FTS5 对 `long-horizon`、`self-generated` 等连字符查询的解析错误。

- [x] 定义 eval case JSON schema。
- [x] 建立 20 条最小烟雾问题集。
- [x] 实现离线运行入口，保存 answer、sources、tool_trace、usage 和 latency。
- [x] 输出第一份 baseline JSON/Markdown 报告。

### Iteration 1.1：结构化与 parent-child chunk

状态：已完成。

- [x] 保留 MinerU Markdown 完整标题路径。
- [x] 识别摘要、方法、实验结果、表格、图注和参考文献 chunk。
- [x] 小 chunk 用于召回，父级章节上下文用于回答和深读。

### Iteration 1.2：查询规划与 RRF

状态：已完成。

- [x] 识别任务类型并规范化中英文查询。
- [x] 为复杂问题生成带 lineage 的子查询。
- [x] 使用标准 Reciprocal Rank Fusion 融合各查询和检索器结果。

### Iteration 1.3：过滤、覆盖与多样性

状态：已完成。

- [x] 增加年份、作者、venue、item_key 和 chunk_type filters。
- [x] 增加 MMR 或等价多样性选择。
- [x] 为 comparative 任务增加 per-item coverage。

### Iteration 1.4：可选 reranker 与索引版本

状态：已完成。

- [x] 增加可选 cross-encoder reranker，并保证失败可降级。
- [x] 明确 chunk、Embedding 内容版本和重建迁移规则。
- [x] 仅在 SQLite 成为实际瓶颈后再评估独立向量索引。

### Phase 1 阶段评审

```text
阶段：Phase 1
版本/提交：当前 codex/agentic-rag-optimization 工作树
完成日期：2026-07-14
完成工作项：Iteration 1.1–1.4 全部工作项
未完成工作项：无；独立向量索引按条件延后，不属于当前缺口
回归测试：285 passed
行为验收：结构化父子 chunk、query lineage、标准 RRF、过滤、覆盖、多样性、reranker 降级和索引版本均有专项测试
发现的新风险：查询分类与改写目前是确定性规则；reranker 质量取决于用户配置的外部模型
是否达到进入下一阶段的门槛：是
下一步：Phase 1.5，统一 Skill、工具契约和运行时注入
```

### Phase 1.5 阶段评审

```text
阶段：Phase 1.5
版本/提交：当前 codex/agentic-rag-optimization 工作树
完成日期：2026-07-14
完成工作项：Skill 主规则、三个 references、openai.yaml、共享路径加载器、Function Calling prompt 注入和回归测试
未完成工作项：无
回归测试：Skill 专项 20 passed；完整回归 291 passed
行为验收：Skill bundle 实际进入 /rag/chat system prompt；Codex SDK 与 Function Calling 共用同一 Skill 路径；缺文件明确失败
发现的新风险：Function Calling 会在每次新会话请求读取 Skill 文件；未来打包部署时必须一并分发 skills/agentic-rag 目录
是否达到进入下一阶段的门槛：是
下一步：Phase 2，显式 TaskPlan、EvidenceState 和 Agent 状态机
```

## 八、阶段评审模板

每个阶段完成时，在本文件中追加一次评审记录：

```text
阶段：Phase N
版本/提交：
完成日期：
完成工作项：
未完成工作项：
回归测试：
行为验收：
发现的新风险：
是否达到进入下一阶段的门槛：是 / 否
下一步：
```

## 九、近期已完成的可靠性改进

- [x] `hybrid` 在 Embedding provider 查询失败时降级保留 metadata + keyword 结果。
- [x] 语义分支失败返回 `semantic_search_failed` warning，不再让整个 `search_evidence` 变成 `tool_failed`。
- [x] 补充 MinerU 轮询使用的 `import time`。
- [x] 知识库页面记住最近选择的知识库。
- [x] 重新进入知识库页面时，从后端恢复最近会话、sources 和 tool trace。
- [x] 增加相关后端、前端契约和检索降级回归测试。

## 十、相关文档

- `docs/agentic-rag-design.md`：整体目标架构和数据流。
- `docs/agentic-rag-function-calling-design.md`：当前 ReAct 工具循环、会话和 API 契约。
- `docs/rag-knowledge-base-schema.md`：RAG、知识库、矩阵和会话数据结构设计。
- `docs/semantic-search.md`：Embedding、semantic 和 hybrid 检索实现。
- `docs/openai-codex-agentic-rag-plan.md`：早期 Codex runtime 接入计划。

本文件是后续 Agentic RAG 优化的主执行路线；其他设计文档负责解释具体模块，本文件负责约束实施顺序和阶段验收。
