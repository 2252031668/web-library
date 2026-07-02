# 多源异构数据检索功能设计

状态：草案 v3.18
负责人：cjh  
最后更新：2026-06-29

公开功能实现说明见：`docs/多源异构检索功能实现说明.md`。

## 1. 背景与目标

当前项目已经具备 Zotero 本地文库读取、本地副本编辑、标识符导入、引用文本导入、去重和写入 Zotero SQLite 的基础能力。

本功能的目标是补齐前置的“多源异构数据检索”能力：从不同外部数据源检索文献/数据条目，统一清洗、去重、合并、预览，并按照现有文库格式写入本地副本文库。

一句话定位：

> 将外部多源检索结果标准化为项目已有的 `ImportedItem`，再复用现有 `import_metadata_items()` 完成去重和落库。

## 2. 现有基础

当前可复用模块：

- `src/zotero_web_library/metadata_import.py`
  - 已有 `ImportedItem` / `ImportedCreator` 统一导入模型。
  - 已支持 DOI、PMID、arXiv ID、ADS Bibcode、ISBN 标识符识别。
  - 已支持 RIS、BibTeX、CSL JSON、PubMed XML 文本解析。
- `src/zotero_web_library/zotero_adapter.py`
  - 已有 `import_metadata_items()` 统一入库入口。
  - 已有强标识符去重逻辑。
  - 已能写入 Zotero 原生 `items`、`itemData`、`creators`、`tags`、`collectionItems` 等结构。
  - 已能记录 `sync_journal`。
- `src/zotero_web_library/web.py`
  - 已有单条标识符导入接口。
  - 已有引用文本导入接口。
- `src/zotero_web_library/app_store.py`
  - 已有应用侧 SQLite，用于保存文库记录、偏好、快捷标签、同步日志。

## 3. 功能范围

### 3.1 第一阶段 MVP

第一阶段优先实现一个完整闭环：

1. 用户输入关键词或标识符。
2. 后端同时检索多个数据源。
3. 各数据源返回结果统一成候选格式。
4. 后端进行标准化、去重、合并和质量评分。
5. 前端展示候选结果。
6. 用户选择候选条目。
7. 后端将候选转换为 `ImportedItem`。
8. 调用现有 `import_metadata_items()` 写入当前本地副本文库。

第一阶段建议支持的数据源：

- Crossref：论文 DOI、期刊论文、会议论文。
- arXiv：预印本。
- PubMed：生物医学文献。
- bioRxiv / medRxiv：生命科学和医学预印本；DOI 精确查，非 DOI 关键词会扫描近期记录并在本地过滤。
- OpenAlex：跨学科开放学术知识图谱，需要配置 `OPENALEX_API_KEY` 后启用。
- Semantic Scholar：AI/CS 文献和引用信息；可选配置 `SEMANTIC_SCHOLAR_API_KEY` 提升限额。
- DataCite：数据集、软件、报告等 DOI 资源。
- GitHub：公开代码仓库；可选配置 GitHub token 提升限额，入库为软件/代码对象。
- HuggingFace：Hub models 和 datasets；可选配置 HuggingFace token，入库为模型或数据集对象。
- Zenodo：公开 records；覆盖软件、数据集、报告等 DOI 资源，可选配置 Zenodo token。
- OpenLibrary：图书、教材、ISBN 元数据。
- NASA ADS：天文/物理文献和 Bibcode 元数据；需要配置 `ADS_API_TOKEN` 或 `ADS_DEV_KEY` 后启用。
- Local CSV/JSONL：比赛数据、内部数据、离线整理表格；需要配置路径后启用，支持文库级保存 `field_map` 来映射陌生列名。
- HTTP JSON：团队内部 HTTP 检索接口接入模板；需要通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_HTTP_JSON_CONFIG` 配置 `url_template`、`items_path` 和 `field_map` 后启用。
- SQLite：本地只读数据库检索；需要通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_SQLITE_CONFIG` 配置数据库路径、SELECT 查询和 `field_map` 后启用。
- Object Manifest：本地或远程 JSON 对象清单；需要通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_MANIFEST_CONFIG` 配置 `manifest_path` / `manifest_url`、`items_path` 和 `field_map` 后启用。

### 3.2 后续扩展源

后续可按插件方式增加：

- 专用数据库 / 对象存储 SDK：当比赛数据源必须走云厂商 SDK、权限代理或二进制对象索引时，再按插件方式接入；当前先用 SQLite、HTTP JSON 和 Object Manifest 覆盖结构化清单场景。
- RAG / 向量检索：用于全文、网页正文、PDF 片段或实验材料的语义检索；当前第一阶段先做结构化元数据检索和入库闭环。
- 模型服务可选增强：第一阶段已经支持页面级 API 配置。用户可在 `/library/<library_id>/api-config` 填写模型名称、请求地址和 API Key；请求地址可填根地址，例如 `https://ai-pixel.online`，后端会自动补 `/v1/chat/completions`。页面配置优先于环境变量，未保存时继续兼容 `AI_PIXEL_*` 环境变量。

### 3.3 AI 辅助检索闭环

当前实现的 AI 辅助能力不替代真实数据源检索，也不会直接入库：

1. 用户先在 API 配置页保存模型配置。
2. 在多源检索页输入关键词后，可点击“AI 生成检索计划”，生成 3-5 条 query、推荐源和理由。
3. 用户确认后再启动批量检索，真实候选仍来自 Crossref、arXiv、PubMed、GitHub、HuggingFace、Zenodo 等 provider。
4. 检索结果返回后，模型只基于元数据判断候选是否可用，不发送 raw JSON。
5. 候选会得到 `recommend / review / reject`，以及主题相关度、元数据质量、来源证据强度、导入风险、最终推荐置信度、理由和缺失字段。
6. 只有模型判 `recommend`、最终推荐置信度足够、导入风险不高、关键字段不缺时才默认勾选；最终仍由用户点击“导入所选”。

## 4. 总体架构

推荐新增独立检索模块：

```text
src/zotero_web_library/retrieval/
  __init__.py
  models.py
  providers.py
  normalize.py
  merge.py
  cache.py
  crossref.py
  arxiv.py
  pubmed.py
  openalex.py
```

核心原则：

- 数据源 provider 只负责检索和标准化，不直接写 Zotero SQLite。
- 所有外部结果先转换为统一候选模型。
- 只有用户确认导入后，才转换为 `ImportedItem` 并调用现有入库流程。
- Zotero 原生 schema 不扩展；源特有信息进入 `extra` 或应用侧 provenance 表。

## 5. 数据模型设计

### 5.1 检索候选

建议新增候选模型：

```python
@dataclass
class RetrievedCandidate:
    source: str
    external_id: str
    item: ImportedItem
    raw: dict[str, Any]
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    landing_url: str = ""
    pdf_url: str = ""
    also_seen_in: list[str] = field(default_factory=list)
```

字段说明：

- `source`：来源，例如 `crossref`、`arxiv`、`pubmed`。
- `external_id`：来源侧稳定 ID。
- `item`：可入库的统一元数据。
- `raw`：原始响应，方便调试和追溯。
- `confidence`：结果可信度或匹配分。
- `evidence`：命中理由，例如 DOI 命中、标题命中、作者匹配。
- `landing_url`：来源页面。
- `pdf_url`：可选 PDF 地址。
- `also_seen_in`：被其他数据源用强标识符合并命中的来源。

API 输出会额外补充：

- `rank`：当前候选排序序号。
- `confidence_label`：高可信 / 中可信 / 低可信。
- `rank_reasons`：可展示的排序解释，例如强标识符、多源命中、PDF 链接、来源页等。
- `duplicate_hint`：与当前文库已有条目的强标识符匹配提示。
- `existing_matches`：命中的已有条目 key、标题、类型和匹配标识符。
- `similarity_hint`：与当前文库已有条目的弱相似提示。
- `weak_similarity_matches`：标题、年份、第一作者等弱相似证据命中的已有条目。
- `ai_evaluation`：候选可用性判断。模型可用时使用 `ai_rubric_v1`，包含 `decision`、`topic_relevance_score`、`metadata_quality_score`、`source_evidence_score`、`import_risk_score`、`final_confidence_score`、`risk_level`、`reason`、`missing_fields` 和 `auto_select`；未配置模型或模型失败时使用 `metadata_rules_v1` 兜底，并在 `score_source` 标识为规则评分。

AI 评估请求只发送候选元数据：标题、作者、年份、摘要、来源、DOI/PMID/arXiv/ISBN、`source_count`、`multi_source` 和 URL；不发送 provider 的 `raw` 原始响应。

AI 候选评分的详细实现维护在 `docs/ai-candidate-scoring-implementation.md`。

### 5.2 数据源诊断

每个数据源检索后都会进入 `source_stats`，用于前端提示、历史记录和阶段报告：

- `ok`：该源本次是否成功返回。
- `count`：该源返回候选数量。
- `elapsed_ms`：该源本次请求耗时。
- `rate_limit_seconds`：该源当前生效的最小调用间隔。
- `rate_limit_wait_ms`：本次检索因源级节流实际等待的时间。
- `error`：失败时的原始错误摘要。
- `error_kind`：失败类型，例如 `configuration`、`rate_limited`、`timeout`、`network`、`upstream`、`parse`。
- `action`：给用户或汇报人的建议动作，例如稍后重试、配置 API Key、检查网络代理。

外部 HTTP 数据源统一走轻量重试/退避策略：默认对 `429`、`5xx`、网络抖动和超时重试 1 次，可通过 `WEB_LIBRARY_RETRIEVAL_HTTP_RETRIES` 调整，最大 3 次；如果上游返回短 `Retry-After`，优先按该值等待。`401/403` 等权限错误不会重试，直接给出配置或权限诊断。

外部源还会经过统一的源级节流预算：每个 provider 可声明默认最小调用间隔，`search_retrieval()`、批量任务和健康检查共用同一套调度状态，避免后台批量任务连续打同一公共 API。可通过 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_SECONDS` 设置全局间隔，也可用 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_<SOURCE>_SECONDS` 覆盖单个源，例如 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_ARXIV_SECONDS`。

`GET /retrieval/sources?check=1` 会对可用源执行轻量健康检查，并把健康结果放入源状态的 `health` 字段。默认打开弹窗时仍只读取静态配置状态，避免频繁消耗外部 API 配额。

源状态还会返回结构化 `setup` 字段，用于前端提示和阶段汇报：

- `config_mode`：`none`、`required_env`、`required_any_env`、`optional_env` 或 `preference_or_env`。
- `config_env` / `alternate_config_env`：需要或可选配置的环境变量，例如 `OPENALEX_API_KEY`、`ADS_API_TOKEN`、`ADS_DEV_KEY`。
- `preference_api`：可通过文库级配置完成接入的源，例如 Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest。
- `rate_limit_env` / `global_rate_limit_env`：源级和全局限流覆盖变量，例如 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_OPENALEX_SECONDS` 和 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_SECONDS`。
- `notes`：面向用户和汇报人的短配置说明。

`/retrieval/sources/report` 会把当前源配置状态导出为 Markdown / CSV / JSON，用于部署检查、阶段汇报和交接。

`/retrieval/readiness` 会把源配置状态和内部源小样本映射预览合并成上线前预检结果。它只对已经配置的 Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest 做样本读取，输出 `ready`、`warning` 或 `blocked`、样本数量、字段覆盖质量和修复建议；用于真实比赛数据源接入后快速判断“能不能检索”和“能不能按现有文库格式落库”。`/retrieval/readiness/report` 会把同一份预检结果导出为 Markdown / CSV / JSON，用于汇报和交接。

Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest 的 readiness 条目会附带 `field_map_suggestion`，汇总从真实小样本推断出的 `field_map`、覆盖质量、样本数、未映射路径数量和 `config_draft` 可用性。文库偏好保存的配置可返回可审阅草稿；环境变量来源的配置只返回映射摘要，避免把带密钥或内部地址的完整配置写进报告。

Local CSV/JSONL 已支持显式保存 `field_map`。保存后，预览、readiness 和正式检索都会按该映射把异构列名转换为现有文库字段；前端 Local 配置区的 `Suggest` 可以从预览样本生成建议，人工确认后保存。

### 5.3 阶段统计

阶段统计由 `retrieval_runs`、`retrieval_candidates` 和 `import_provenance` 聚合生成，不新增 Zotero schema：

- `run_count`：检索批次数。
- `candidate_count`：候选总数。
- `imported_count`：导入记录数。
- `import_rate`：导入记录数 / 候选总数。
- `source_success_rate`：数据源成功次数 / 数据源调用次数。
- `sources`：每个源的调用次数、成功/失败次数、候选数、平均耗时和最近失败建议。
- `rate_limit_wait_avg_ms`：每个源在统计窗口里的平均节流等待时间。
- `observed_rate_limit_seconds`：运行记录里观测到的最近一次源级限流间隔。
- `error_kinds`：限流、超时、配置缺失等错误类型分布。
- `top_queries`：高频检索词。

`/retrieval/tuning` 会基于阶段统计和当前源配置生成限流调优建议；`/retrieval/tuning/report` 可导出 Markdown / CSV / JSON。调优规则保持保守：`rate_limited` 明确建议提高对应 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_<SOURCE>_SECONDS`，`timeout` / `network` / `upstream` 结合失败率建议放慢并复测，`configuration` / `auth` 优先修配置，不把鉴权问题误判为限流问题。

### 5.4 Provider 接口

```python
class MetadataProvider:
    name: str

    def search(self, query: str, limit: int = 10) -> list[RetrievedCandidate]:
        ...

    def resolve(self, identifier: str) -> RetrievedCandidate | None:
        ...
```

接口约束：

- provider 内部可以调用外部 API。
- provider 必须捕获网络/API 错误并返回结构化错误。
- provider 不允许直接写数据库。
- provider 返回结果必须能转换为 `ImportedItem`。

## 6. 检索流程

```text
用户输入 query
  -> retrieval/search API
  -> provider registry 选择数据源
  -> 并发调用 provider.search()
  -> 标准化为 RetrievedCandidate
  -> 记录每个源的耗时、错误类型和建议动作
  -> 按强标识符合并候选
  -> 生成 rank / confidence_label / rank_reasons
  -> 对照当前文库强标识符，生成 duplicate_hint / existing_matches
  -> 对照当前文库标题、年份、第一作者，生成低风险弱相似提示
  -> 写入应用侧 retrieval_runs / retrieval_candidates
  -> 标记已有条目/疑似重复
  -> 返回 run_id 和候选列表
```

候选导入流程：

```text
用户勾选 candidates
  -> retrieval/import API
  -> 前端提交 run_id + candidate_ids
  -> 后端从 retrieval_candidates 取回候选 payload
  -> 转换候选中的 ImportedItem
  -> 调用 ZoteroRepository.import_metadata_items()
  -> 写入 import_provenance
  -> 返回 created / existing / conflict / failed 汇总
```

## 7. 去重与合并规则

### 7.1 强标识符自动去重

可自动判定为同一条目的标识符：

- DOI
- PMID
- PMCID
- arXiv ID
- ADS Bibcode
- ISBN

强标识符相同：

- 检索候选之间可以自动合并。
- 入库时如果已有条目，只复用已有条目，不重复创建。

### 7.2 弱相似只提示

以下信息只能作为“疑似重复”提示，不能自动合并：

- 标题高度相似。
- 第一作者相同。
- 年份相同。
- 来源期刊/会议相似。

原因：避免误合并不同版本、扩展版、预印本和正式发表版。

## 8. 落库规则

外部数据最终必须转换为 `ImportedItem`，再走现有入库入口。

可直接写入 Zotero 原生字段：

- `title`
- `date`
- `publicationTitle`
- `proceedingsTitle`
- `conferenceName`
- `repository`
- `DOI`
- `ISBN`
- `ISSN`
- `url`
- `abstractNote`
- `publisher`
- `place`
- `volume`
- `issue`
- `pages`
- `extra`

不可直接扩展 Zotero schema：

- 不新增 `fields.fieldName`。
- 不新增自定义 Zotero 表。
- 不给 Zotero 原生 `tags` 表增加类型字段。

源特有信息处理方式：

- 重要且可展示的信息：写入 `extra` 的结构化块。
- 调试、溯源、原始响应：写入应用侧 provenance 表。

## 9. 应用侧记录

为了规划、汇报和问题追踪，已在 `app-data/app.sqlite` 增加三类表：

```text
retrieval_runs
retrieval_candidates
import_provenance
```

当前记录：

- 检索时间。
- 操作者，例如 `cjh`。
- 查询词。
- 使用的数据源。
- 每个源返回数量。
- 候选 external id。
- 候选标题、标识符和完整候选 payload。
- 导入状态。
- 最终导入的 Zotero item key。
- 候选来源、标识符和导入结果 payload。

这样前端导入时不需要回传大体积 raw 数据，也能在后续汇报里按检索批次追踪“搜了什么、来自哪些源、最后导入了哪些条目”。

## 10. API 设计草案

### 10.0 API 配置

```http
GET /api/library/<library_id>/api-config
POST /api/library/<library_id>/api-config
POST /api/library/<library_id>/api-config/check
GET /library/<library_id>/api-config
```

配置保存在本机 `app.sqlite` 的 `preferences` 表中，页面默认只返回脱敏状态；`include_secrets=1` 只返回本机保存的 key，不泄露环境变量 key。模型配置字段为 `model`、`base_url` 和 `api_key`，代码/数据源 token 为 `github_token`、`huggingface_token`、`zenodo_token`，全部可选。

### 10.1 多源检索

```http
POST /api/library/<library_id>/retrieval/search
```

请求：

```json
{
  "query": "vision language action robot",
  "sources": ["crossref", "arxiv", "pubmed"],
  "limit": 10,
  "use_ai_evaluation": true
}
```

响应：

```json
{
  "ok": true,
  "query": "vision language action robot",
  "run_id": "run-abc123",
  "candidates": [
    {
      "candidate_id": "cand-def456",
      "source": "crossref",
      "title": "Example paper"
    }
  ],
  "source_stats": {
    "crossref": {"ok": true, "count": 10},
    "arxiv": {"ok": true, "count": 6},
    "pubmed": {"ok": true, "count": 0}
  }
}
```

### 10.2 候选导入

```http
POST /api/library/<library_id>/retrieval/import
```

请求：

```json
{
  "run_id": "run-abc123",
  "candidate_ids": ["cand-def456"],
  "collection_key": "target-collection-key"
}
```

响应复用现有导入 summary，并追加本次导入的证据链摘要：

```json
{
  "ok": true,
  "created_count": 3,
  "existing_count": 1,
  "conflict_count": 0,
  "failed_count": 0,
  "results": [],
  "import_evidence": {
    "status": "recorded",
    "run_id": "run-abc123",
    "run_linked": true,
    "candidate_count": 4,
    "result_count": 4,
    "provenance_recorded_count": 4,
    "item_key_count": 4,
    "statuses": {"created": 3, "existing": 1},
    "sources": ["crossref"],
    "run_report_markdown_endpoint": "/api/library/<library_id>/retrieval/runs/run-abc123/report?format=markdown",
    "summary_report_endpoint": "/api/library/<library_id>/retrieval/summary/report?format=markdown",
    "items": [
      {
        "candidate_id": "cand-def456",
        "source": "crossref",
        "title": "Example paper",
        "status": "created",
        "item_key": "ITEM0001",
        "identifiers": {"doi": "10.1234/example"}
      }
    ]
  }
}
```

兼容说明：为便于测试和旧前端过渡，导入接口仍可接收 `candidates` payload；正式前端优先使用 `run_id` + `candidate_ids`。如果没有 `run_id`，`import_evidence.status` 会标记为 `recorded_without_run`，仍记录候选与导入结果 provenance，但不会生成单次 run 报告入口。

### 10.3 检索批次记录

```http
GET /api/library/<library_id>/retrieval/runs
```

响应：

```json
{
  "ok": true,
  "runs": [
    {
      "run_id": "run-abc123",
      "query": "vision language action robot",
      "sources": ["crossref", "arxiv", "pubmed"],
      "candidate_count": 12,
      "imported_count": 3
    }
  ]
}
```

### 10.3.1 批量检索任务

```http
GET /api/library/<library_id>/retrieval/query-plan?seed_query=robot&sample_size=5&limit=5
GET /api/library/<library_id>/retrieval/query-plan/report?seed_query=robot&sample_size=5&limit=5&format=markdown|csv|json
POST /api/library/<library_id>/retrieval/batches
GET /api/library/<library_id>/retrieval/batches
GET /api/library/<library_id>/retrieval/batches/<job_id>
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=csv&scope=sources
POST /api/library/<library_id>/retrieval/batches/<job_id>/cancel
POST /api/library/<library_id>/retrieval/batches/<job_id>/pause
POST /api/library/<library_id>/retrieval/batches/<job_id>/resume
POST /api/library/<library_id>/retrieval/batches/<job_id>/retry-failed
```

批量任务接收多行 query 或 query 数组，后台逐条执行现有 `/retrieval/search` 同等逻辑。每个 query 会生成一个普通 `retrieval_run`，因此候选缓存、导入、报告导出和阶段统计都继续复用现有能力。任务本身记录总 query 数、已完成数、失败数、剩余数、预计剩余秒数、候选总数、每个子任务的 `run_id` 和错误信息，前端用这些字段展示后台进度。`/report` 会导出 Markdown / CSV / JSON 批量任务报告：Markdown 先按 source 汇总 `source_evidence`，展示每个来源是否被请求、覆盖 query 数、成功/失败次数、候选数、耗时和最新诊断，再按 query 汇总状态、run_id、候选数、源级候选数、耗时和诊断；`format=csv` 默认导出逐 query 表格，`format=csv&scope=sources` 导出来源级 `source_evidence` 表格，前端批量卡片提供 `SRC CSV` 下载入口；JSON 同步包含 `source_evidence`、`source_errors` 和 `source_error_count`，适合 3 到 5 个真实 query 小批量压测后交给队友复盘。

`/retrieval/query-plan` 会先复用 readiness 的内部源 preview，再从样例 `ImportedItem` 的标题、标签和摘要里提取 3 到 5 条验证 query 草案，返回 `query_text`、来源证据和样例标题。接口支持 `use_ai=1` 和 `sources` 过滤；AI 增强只生成检索计划，不直接入库。`/retrieval/query-plan/report` 可把同一份草案导出为 Markdown / CSV / JSON，保留每条 query 的来源、样本证据和下一步建议。前端主检索区的“AI 生成检索计划”会展示 query、推荐源和理由，人工确认后可按计划启动批量检索。

批量任务操作：

- `cancel`：把仍在排队的 query 标记为 `canceled`，worker 会在每个 query 前检查任务状态；已经开始的当前 query 不做线程级强杀，但不会继续执行后续 query。
- `pause`：把任务标记为 `paused`；已经开始的当前 query 会自然完成，后续 query 不再启动。
- `resume`：把 paused 任务恢复为 `queued` 并继续执行剩余 query。
- `retry-failed`：仅把 `failed` 子任务重置为 `queued` 并重新启动 worker，已完成的 query 和已有 `run_id` 保持不变。

### 10.4 数据源配置状态

```http
GET /api/library/<library_id>/retrieval/sources
GET /api/library/<library_id>/retrieval/sources/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/readiness?query=robot&sample_size=2
GET /api/library/<library_id>/retrieval/readiness/report?query=robot&sample_size=2&format=markdown|csv|json
GET /api/library/<library_id>/retrieval/tuning
GET /api/library/<library_id>/retrieval/tuning/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/onboarding
GET /api/library/<library_id>/retrieval/onboarding/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/onboarding/package
POST /api/library/<library_id>/retrieval/rehearsal/setup?replace_existing=1
POST /api/library/<library_id>/retrieval/rehearsal/validate?replace_existing=1
GET /api/library/<library_id>/retrieval/config-bundle
GET /api/library/<library_id>/retrieval/config-bundle/download
POST /api/library/<library_id>/retrieval/config-bundle
POST /api/library/<library_id>/retrieval/config-bundle?dry_run=1
POST /api/library/<library_id>/retrieval/source-intake
POST /api/library/<library_id>/retrieval/source-intake/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/field-map/targets
POST /api/library/<library_id>/retrieval/field-map/suggest
POST /api/library/<library_id>/retrieval/field-map/report?format=markdown|csv|json
GET /api/library/<library_id>/retrieval/local-files/field-map/suggest?sample_size=3
GET /api/library/<library_id>/retrieval/local-files/field-map/report?sample_size=3&format=markdown|csv|json
GET /api/library/<library_id>/retrieval/http-json/field-map/suggest?query=robot&sample_size=3
GET /api/library/<library_id>/retrieval/http-json/field-map/report?query=robot&sample_size=3&format=markdown|csv|json
GET /api/library/<library_id>/retrieval/sqlite/field-map/suggest?query=robot&sample_size=3
GET /api/library/<library_id>/retrieval/sqlite/field-map/report?query=robot&sample_size=3&format=markdown|csv|json
GET /api/library/<library_id>/retrieval/manifest/field-map/suggest?sample_size=3
GET /api/library/<library_id>/retrieval/manifest/field-map/report?sample_size=3&format=markdown|csv|json
```

ONB 的 `batch_validation` 至少要求 3 条已完成的真实 query 才能进入 `passed`；少于 3 条时返回 `low_sample`，状态卡显示已完成 query / 最低要求 query，避免 1 条样本误判为可交接。

响应：

```json
{
  "ok": true,
  "sources": [
    {"name": "crossref", "label": "Crossref", "available": true, "requires_config": false, "rate_limit_seconds": 0.25},
    {"name": "openalex", "label": "OpenAlex", "available": false, "requires_config": true, "config_key": "OPENALEX_API_KEY", "rate_limit_seconds": 0.2}
  ]
}
```

前端用这个接口展示每个源的可用状态，并禁用缺少配置的源，避免用户误选后才发现失败。
加上 `?check=1` 后会执行实时健康检查；前端用“检查数据源健康”按钮触发，不在每次打开弹窗时自动请求。
`/retrieval/readiness` 用于上线前内部源统一预检，前端 `READY` 按钮触发。它会汇总 `sources`，并把 Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest 的预览质量放入 `previews`，便于一次看到配置缺口、样本映射质量和修复建议。`/retrieval/readiness/report` 复用同一份结果输出 Markdown / CSV / JSON，前端 `RPT` 按钮默认下载 Markdown。
HTTP JSON、SQLite、Object Manifest 和 Local CSV/JSONL 预检项都会带 `field_map_suggestion`，前端 readiness 卡片显示 `map N` 和草稿状态；有可保存草稿时可直接 `Apply` 回填到对应配置区，人工确认后再保存。CSV/JSON 报告输出映射建议状态；Markdown 报告在建议栏附带 `field_map N fields; draft yes/no`。
Local CSV/JSONL 前端配置区会保存路径和 `field_map`，Local preview 文件头显示 `map N / config`，并可通过 `Suggest` 从当前样本回填建议映射。
`/retrieval/tuning` 用于小批量真实检索后复盘各源稳定性，前端 `TUNE` 按钮默认下载 Markdown 调优报告。它会输出每个源的失败率、错误类型、平均耗时、平均节流等待、当前限流和建议限流，适合决定是否调整全局或单源 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_*` 变量。
`/retrieval/onboarding` 用于把源状态、readiness、query-plan、tuning、最近批量任务验证、候选入库模型检查和配置包脱敏状态合并成接入验收结果。前端 `ONB CHECK` 会调用该接口并显示接入验收状态卡，同时把 `batch_validation.source_evidence` 展示成每个来源的 q / ok / fail / hits / elapsed 摘要，并显示 PLAN coverage 和 import ready；如果存在最近批量任务，状态卡可直接下载最新批量 Markdown 报告和来源级 CSV。`/retrieval/onboarding/report` 支持 Markdown / CSV / JSON，前端 `ONB` 按钮默认下载 Markdown，适合阶段汇报时证明“配置能预检、能采样、候选能转换成现有文库入库模型、能交接”。报告里的 `batch_validation` 会汇总最近批量任务数量、完成 query、失败 query、候选数、最新批量任务报告端点和最新来源级 CSV 端点，并把每个最近批量任务的来源级 CSV 写入 `batch_evidence` 明细行；它还会复用当前 `/retrieval/query-plan` 草案作为 `required_queries`，输出 `covered_queries` / `missing_queries`，并对已配置内部源计算 `validated_sources` / `missing_sources` 覆盖情况，聚合 batch item 的源级 `source_stats`，输出 `missing`、`active`、`failed_queries`、`source_errors`、`incomplete`、`query_gap`、`source_gap`、`no_candidates` 或 `passed` 状态和处理建议。`import_readiness` 会从最近 batch 的 cached candidates 抽样，不写库地调用现有 `ImportedItem` 转换逻辑，统计可入库候选数、缺 title 数和转换错误数；全部候选无法转换时 ONB 会阻断，避免只证明“搜得到”但不能“按现有文库格式存”。
ONB 的 `batch_validation` 还会比对最新 batch 创建时记录的脱敏源配置指纹与当前配置指纹，输出 `config_context_status=matched|mismatch|unknown`。新 batch 会随任务保存 `web-library.retrieval-batch-context/v1` 上下文；旧 batch 没有上下文时显示 `unknown` 但不阻断验收；如果最新 batch 指纹与当前配置不一致，则返回 `config_drift`，提示先用当前配置重跑小批量验证，避免配置变更后继续引用旧 batch 证据。
ONB 同步输出 `acceptance_gates`：`source_readiness`、`batch_validation`、`tuning_signal`、`import_readiness`、`config_bundle` 和 `handoff_artifacts`。每个 gate 都带 `status`、`evidence`、`message`、`action_endpoint` 和 `artifacts`，前端状态卡可直接下载 READY/PLAN/TUNE/ONB/CFG/Batch report/Source CSV，Markdown 和 CSV 明细会保留这些证据，方便把阶段验收拆成可汇报、可追责、可补跑的清单。
`/retrieval/onboarding/package` 会把 README、ONB、Source setup、PLAN、READY、TUNE、已配置内部源的 field-map 报告、脱敏 CFG、最近批量报告和 Source CSV 打成 ZIP 交接包，并附带 `manifest.json` 记录 gate 状态、source_setup 摘要、query-plan 摘要、field_map_reports 摘要、包内 payload 文件清单、字节数和 SHA256；前端 `ONB ZIP` 可一键下载，用于给队友或仓库作者交接和核验。
`/retrieval/rehearsal/setup` 用于在没有真实比赛数据源时生成演练数据源。它会在应用数据目录下创建 CSV、SQLite 和 Object Manifest 三种公开虚构元数据源，并通过配置包导入逻辑保存为当前文库的内部源配置；默认不覆盖已有配置，传 `replace_existing=1` 后才替换 Local CSV/JSONL、SQLite 和 Object Manifest。前端 `DEMO KIT` 按钮会调用该接口并把 query 切到 `robot catalyst`，便于立即跑 READY、批量验证和 ONB ZIP。`/retrieval/rehearsal/validate` 是一键演练验收入口，会生成/配置同一套演练源，以 `robot catalyst` 生成 query-plan 草案，再按 PLAN query 启动批量验证，并返回 Query plan、READY、Batch report、Source CSV、ONB report 和 ONB ZIP artifact endpoint；响应还会输出 `seed_queries`、实际 `queries`、`validation_summary` 和 `validation_gates`，把演练源配置、READY、PLAN query batch、ONB 交接材料拆成可汇报的状态、证据和 artifact。前端 `DEMO RUN` 按钮调用它，适合阶段汇报或给仓库作者演示接入闭环。
`/retrieval/config-bundle` 用于导出或导入文库级内部源配置包。配置包覆盖 Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest，默认把直接写在配置中的 token、Authorization、secret、password 等值替换为 `__REDACTED__`，但保留 `${ENV:...}` 或环境变量名引用。前端 `CFG` 按钮下载脱敏 JSON；多源检索面板的配置包导入区可粘贴 JSON，先 dry-run 查看 `would_apply` / `skipped`，并可把 dry-run 或 import 结果下载为 CSV 留档，再确认导入。导入时包含 `__REDACTED__`、缺少必填项或带有不支持 `field_map` target 的源会被跳过，避免把占位符或坏映射写入配置；其他有效源仍会继续预演或导入，dry-run 不会写入文库级配置。
`/retrieval/source-intake` 用于真实比赛数据源拿到后的第一步分型。调用方可提交路径、URL、SQL、CSV 表头或 JSON 样例；后端会输出最可能的源类型、候选类型分数、检测到的信号、下一步配置端点、必填配置项、后续 batch 应使用的 `target_source`，以及可直接带到 Field map lab 的 `field_map_lab` 草案。如果输入中包含列名或 JSON 样本，响应会复用字段映射建议器生成 `field_map_suggestion`，但不会保存任何配置。如果提交的是已存在的本地 CSV/JSONL/NDJSON 文件或目录，接口会读取少量样例行；如果提交的是 SQLite 路径，接口会只读打开数据库、选择第一个业务表或视图读取列名和少量样例，并在 `config_draft` 中带上真实 `path` 与自动生成的 `query`；如果提交的是本地 Object Manifest JSON 文件，接口会读取少量对象记录、推断 `items_path`，并生成带真实 `manifest_path` 的草案。对 HTTP URL，默认只识别为 HTTP JSON 候选源；只有请求带 `sample_url=true` 或前端勾选 `Sample URL` 时，才会发起一次轻量 JSON 采样，并把样本、推断出的 `items_path` 和 `url_template` 写入 HTTP JSON `config_draft`。采样成功后，Source intake 还会从样本标题、标签/关键词和摘要生成 `validation_queries` 草案，并输出 `validation_plan`，把保存配置、READY 预检、目标源小批量验证、ONB/ONB ZIP 证据下载拆成 gate 和 artifact 清单；文库级 API 会复用当前 `/retrieval/sources` 状态，把目标源已保存/未保存/不可用反映到 `save_config`、`readiness` 和 `batch_validation` gate，同时读取目标源最近的 batch validation summary，把 `passed`、`low_sample`、`source_gap`、`source_errors`、`config_drift`、`no_candidates` 等状态折叠进 `validation_plan.batch_validation` 和 batch gate。Source intake 会把本次 `validation_queries` 作为 `required_queries` 传给 batch summary，若最近 batch 没有覆盖这些草案 query，会返回 `query_gap`，避免旧 batch 证据误判新真实源已验收；若最近 batch 是旧配置指纹下产生的，会返回 `config_drift`，并在分型卡、gate evidence 和报告里显示 `config_context_status`，提示先按当前配置重跑小批量验证。前端分型结果卡会直接显示 target source、最低 query 数、最近 batch evidence、draft coverage、config evidence、gate 和 artifact；如果已有 3 条以上目标源验证 query、当前草案 query 覆盖、候选数/源覆盖通过，Source intake 会自动显示 `passed` 并附上最近 batch report / source CSV artifact。采样失败只返回 `sampling_error`，不写入配置。`/retrieval/source-intake/report` 可把同一份分型结果导出为 Markdown / CSV / JSON，保留识别信号、候选源类型、目标 batch source、字段映射草案、验证 query 草案、验收计划、最近 batch 证据、draft query 覆盖度、配置指纹状态和下一步动作。前端 `Source intake` 面板调用该接口，`RPT` 下载分型报告，`Use in lab` 会把结果填入 Field map lab 便于二次调整，`Use config` 会把 `config_draft` 直接回填到对应源配置区，`Use queries` 会把 `validation_queries.query_text` 填入批量检索框，并按 `target_source.name` 默认只选中目标源作为批量 source；如果目标源尚不可用，前端会拦截普通检索和批量检索，提示先保存配置或刷新 source 状态，人工确认并保存配置后再启动批量验证。正式验收仍以保存配置后的 `/retrieval/query-plan`、Batch 和 ONB 为准。
`/retrieval/field-map/targets` 和 `/retrieval/field-map/suggest` 用于陌生结构化源接入前的字段映射建议。调用方可提交 CSV/SQL 列名或 JSON 样例，后端按现有 Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest 的统一别名规则生成 `field_map`、质量覆盖情况和 `config_draft`，再由人工确认后保存配置；若尚未提供完整连接配置，会按 `source_type` 生成带占位连接参数的 starter 草案。前端多源检索面板提供 `Field map lab`，可先选择源类型、粘贴列名或 JSON 样例、生成草案并 `Apply draft` 到对应配置区；它会先读取 `/retrieval/model-status`，已配置 `AI_PIXEL_API_KEY` 时才启用 `AI` 开关。打开 `AI` 后会发送 `use_ai=true`，让 AI Pixel 在规则建议基础上补齐较难判断的字段，后端只接受样例里真实存在的路径。HTTP JSON / SQLite / Object Manifest 已保存配置后，还可以调用各自的 `/field-map/suggest` 端点从真实源读取 1 到 3 条样本并生成可保存草案；若配置来自环境变量，响应只返回 `field_map` 和质量信息，不回传完整配置草案，避免泄露密钥或内部地址。

本地 CSV / JSONL 源通过文库级 `/retrieval/local-files` 或 `WEB_LIBRARY_RETRIEVAL_LOCAL_PATHS` 配置，支持文件路径或目录路径；目录下会读取 `.csv`、`.jsonl`、`.ndjson` 文件。多个路径可用系统路径分隔符或换行分隔。常见字段名会自动映射到现有文库格式，例如 `title`、`authors`、`year`、`doi`、`abstract`、`keywords`、`item_type`、`url`、`venue`。

也可以通过前端“Local CSV/JSONL 路径”配置文库级本地源路径，并在同一区域保存 `field_map`。文库级配置存入应用侧 `preferences` 表，优先级高于环境变量；清空后该文库不再启用本地源。

```http
GET /api/library/<library_id>/retrieval/local-files
POST /api/library/<library_id>/retrieval/local-files
GET /api/library/<library_id>/retrieval/local-files/preview?sample_size=2
GET /api/library/<library_id>/retrieval/local-files/field-map/suggest?sample_size=3
```

`local-files/preview` 会读取当前文库生效的本地 CSV/JSONL 路径和 `field_map`，返回文件名、列名、源列到 Zotero 字段的映射、样例行映射后的 `ImportedItem` 结构。这个接口用于导入前检查表头质量，避免本地异构数据源字段映射错误后才发现。

预览结果还会返回字段覆盖率质量提示：

- 文件级 `quality`：统计标题、强标识符、年份/日期、作者/创建者在已扫描行中的覆盖率、缺失行数、质量状态和修复建议。
- 样例行级 `quality`：标出该行缺少哪些关键字段，例如缺标题、缺 DOI/arXiv/PMID/PMCID/ADS Bibcode/ISBN、缺年份或缺作者。
- 前端会在 Local CSV/JSONL 预览卡片中展示 coverage、recommendations 和行级 issues，导入前即可判断是否需要先清洗源文件。

字段映射建议接口适合在还没有保存完整源配置时使用：

```http
GET /api/library/<library_id>/retrieval/field-map/targets
POST /api/library/<library_id>/retrieval/field-map/suggest
POST /api/library/<library_id>/retrieval/field-map/report?format=markdown|csv|json
```

`targets` 返回当前可写入 `field_map` 的目标字段和别名。Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest 的文库级配置保存和配置包导入都会校验 `field_map` target：直接保存接口遇到未知 target 会返回 400；配置包导入会把坏源写入 `skipped` 并继续处理其他有效源，避免把拼错字段静默写入配置。`model-status` 返回 AI Pixel base URL、模型名、配置状态和环境变量名，不返回 API key；调用 `model-status?check=1` 时才发起一次轻量模型连通性检查，并在 `health` 中返回 `ok`、`elapsed_ms`、`error_kind` 和错误摘要，便于演示前确认 `https://ai-pixel.online` 端点可用。`suggest` 接收 `columns`、`sample` 或 `samples`，也可带上未保存的 `config`；响应会返回建议 `field_map`、每个目标字段的置信度/原因、未映射源路径、标题/强标识符/日期/作者覆盖质量，以及合并建议后的 `config_draft`。如果传入 `use_ai=true` 且已配置 `AI_PIXEL_API_KEY`，响应还会带 `ai_enhancement`，记录模型是否配置、实际应用了几个字段、哪些模型路径被拒绝。该接口不写入配置，适合把真实比赛数据源样例先转成配置草案，再通过 Local CSV/JSONL、HTTP JSON、SQLite 或 Object Manifest 配置接口保存。Local CSV/JSONL 已保存路径后，也可以调用 `/local-files/field-map/suggest` 从当前文件样本生成同格式建议。
`/retrieval/field-map/report` 使用同一份请求生成 Markdown / CSV / JSON 字段映射报告，保留目标字段、源路径、置信度、质量覆盖、未映射源字段、AI 增强状态和 `config_draft`；前端 `Field map lab` 的 `RPT` 按钮用于下载该报告，适合把外部字段如何落到现有文库格式作为汇报附件。
已保存 Local CSV/JSONL、HTTP JSON、SQLite 或 Object Manifest 配置后，对应 source-specific `/field-map/report` 会从真实源采样并导出同格式报告；前端各配置区 `Suggest` 旁的 `RPT` 用于下载真实源采样证据。环境变量来源的配置仍会隐藏完整 `config_draft`，只保留映射摘要和质量判断。

### 10.5 HTTP JSON 内部源配置

HTTP JSON 源用于接入团队内部搜索服务、比赛数据服务或已有数据库的 HTTP 包装接口。它不要求服务端遵循某个固定第三方协议，只要求返回 JSON，并通过配置声明“结果数组在哪里、哪些字段映射到现有文库字段”。

```http
GET /api/library/<library_id>/retrieval/http-json
POST /api/library/<library_id>/retrieval/http-json
GET /api/library/<library_id>/retrieval/http-json/templates
GET /api/library/<library_id>/retrieval/http-json/preview?query=robot&sample_size=2
GET /api/library/<library_id>/retrieval/http-json/field-map/suggest?query=robot&sample_size=3
```

文库级配置存入应用侧 `preferences` 表，优先级高于环境变量 `WEB_LIBRARY_RETRIEVAL_HTTP_JSON_CONFIG`；清空后该文库不再启用 HTTP JSON 源。

配置示例：

```json
{
  "label": "Internal API",
  "url_template": "https://example.test/search?q={query}&limit={limit}&page={page}",
  "items_path": "results",
  "next_url_path": "links.next",
  "max_pages": 3,
  "auth": {
    "type": "bearer_env",
    "env": "INTERNAL_API_TOKEN"
  },
  "headers": {"X-Team": "${ENV:INTERNAL_TEAM}"},
  "field_map": {
    "title": "title",
    "date": "year",
    "doi": "doi",
    "abstract": "abstract",
    "authors": "authors",
    "url": "url",
    "venue": "venue",
    "item_type": "item_type",
    "tags": "keywords",
    "external_id": "id",
    "pdf_url": "pdf_url"
  }
}
```

`url_template` 支持占位符：

- `{query}`：URL 编码后的检索词。
- `{raw_query}`：未编码检索词。
- `{limit}`：每源返回数量上限。
- `{page}`：当前页号，默认从 1 开始，可通过 `page_start` 调整。
- `{offset}`：当前偏移量，按 `page_index * limit` 计算。

`items_path` 支持点路径，例如 `results.items`。如果不配置，后端会尝试 `items`、`results`、`data`、`docs`、`records`、`response.docs`。`field_map` 支持常见嵌套路径，例如 `metadata.title`、`links.pdf`。

分页策略：

- 默认只请求第一页。
- 配置 `max_pages` 后最多请求 10 页，避免配置错误导致无限请求。
- 如果 `url_template` 包含 `{page}` 或 `{offset}`，后端会按模板连续翻页，直到候选数达到 `limit`、结果为空或达到 `max_pages`。
- 如果响应里有下一页 URL，可用 `next_url_path` 指定路径，例如 `links.next`；相对 URL 会按当前请求地址自动补全。

鉴权策略：

- 推荐把密钥放在运行环境变量里，不直接写入文库配置。
- `auth.type = "bearer_env"` 会读取 `auth.env` 指定的环境变量，并生成 `Authorization: Bearer <token>`。
- `auth.type = "header_env"` 会读取 `auth.env` 指定的环境变量，并写入 `auth.header` 指定的 header，默认是 `X-API-Key`。
- 普通 `headers` 也支持 `${ENV:NAME}` 占位符，例如 `"X-Team": "${ENV:INTERNAL_TEAM}"`。
- 如果缺少鉴权环境变量，`/retrieval/sources` 会把 `httpjson` 标为不可用，并提示缺失的环境变量名。

`http-json/preview` 会使用当前配置发起一次小样本检索，把样例结果映射为 `ImportedItem`，并返回标题、强标识符、年份/日期、作者覆盖率和行级质量问题。这个接口用于正式批量检索前验证字段映射和鉴权是否可用。前端保存 HTTP JSON 配置成功后会自动触发一次 preview，让用户立即看到字段覆盖质量或鉴权/解析错误。

`http-json/templates` 返回可编辑配置模板，前端可一键套用后再保存。当前内置：

- `basic-rest`：无鉴权的基础关键词检索接口。
- `bearer-page`：使用环境变量 Bearer token 且按 `{page}` 翻页的接口。
- `api-key-cursor`：使用环境变量 API key header 且按 `next_url_path` 游标翻页的接口。

当前第一阶段的 HTTP JSON 源仍属于结构化元数据检索：它把外部 API 结果标准化为 `ImportedItem` 并写入文库。它不是 RAG。RAG 更适合后续检索全文、PDF 段落、网页正文或实验材料时使用。

### 10.6 SQLite 只读数据库源配置

SQLite 源用于接入比赛数据、小型内部索引库或离线清洗后的结构化数据表。它只读打开数据库文件，只允许单条 `SELECT` 或 `WITH` 查询，不作为写库入口。

```http
GET /api/library/<library_id>/retrieval/sqlite
POST /api/library/<library_id>/retrieval/sqlite
GET /api/library/<library_id>/retrieval/sqlite/templates
GET /api/library/<library_id>/retrieval/sqlite/preview?query=robot&sample_size=2
GET /api/library/<library_id>/retrieval/sqlite/field-map/suggest?query=robot&sample_size=3
```

配置示例：

```json
{
  "label": "Internal SQLite",
  "path": "C:/data/retrieval.sqlite",
  "query": "SELECT id, title, year, doi, authors, abstract, keywords, url, venue, item_type FROM items WHERE title LIKE :like_query OR abstract LIKE :like_query LIMIT :limit",
  "field_map": {
    "title": "title",
    "date": "year",
    "doi": "doi",
    "abstract": "abstract",
    "authors": "authors",
    "url": "url",
    "venue": "venue",
    "item_type": "item_type",
    "tags": "keywords",
    "external_id": "id"
  }
}
```

查询参数约定：

- `:query`：原始检索词。
- `:like_query`：自动补 `%` 的 LIKE 检索词。
- `:limit`：每源返回数量上限。

`sqlite/preview` 与 HTTP JSON 预览一致，会返回样例 `ImportedItem`、字段覆盖率和行级质量问题，用于正式检索前验证 SQL 与字段映射。前端保存 SQLite 配置成功后会自动触发一次 preview，让用户立即看到查询、字段映射和样例质量是否可用。

### 10.7 Object Manifest 对象清单源配置

Object Manifest 源用于接入对象存储导出的 JSON 清单、数据湖目录文件、比赛平台导出的对象索引或团队维护的远程 manifest。它不直接扫描对象存储 bucket，也不下载全文对象；第一阶段只读取“清单里的结构化元数据”，把每条对象记录映射为 `ImportedItem`。

```http
GET /api/library/<library_id>/retrieval/manifest
POST /api/library/<library_id>/retrieval/manifest
GET /api/library/<library_id>/retrieval/manifest/templates
GET /api/library/<library_id>/retrieval/manifest/preview?query=robot&sample_size=2
GET /api/library/<library_id>/retrieval/manifest/field-map/suggest?sample_size=3
```

配置示例：

```json
{
  "label": "Object Manifest",
  "manifest_path": "C:/data/object-manifest.json",
  "items_path": "objects",
  "field_map": {
    "title": "title",
    "date": "year",
    "doi": "doi",
    "abstract": "abstract",
    "authors": "authors",
    "url": "object_url",
    "pdf_url": "pdf_url",
    "venue": "venue",
    "item_type": "item_type",
    "tags": "keywords",
    "external_id": "id"
  }
}
```

也可以使用远程清单：

```json
{
  "label": "Remote Object Manifest",
  "manifest_url": "https://example.test/object-manifest.json",
  "items_path": "objects",
  "auth": {"type": "bearer_env", "env": "MANIFEST_TOKEN"},
  "field_map": {
    "title": "title",
    "doi": "doi",
    "url": "object_url",
    "pdf_url": "pdf_url"
  }
}
```

内置模板：

- `local-json`：本地 JSON 清单文件，默认读取 `items` 数组。
- `remote-json`：远程 JSON 清单 URL，可通过环境变量 Bearer Token 鉴权。

前端保存 Object Manifest 配置成功后会自动触发一次 preview，让用户立即看到 `items_path`、字段映射和对象记录质量是否可用。Object Manifest 与 HTTP JSON / SQLite 一样属于结构化元数据检索，不是 RAG。它解决的是“对象在哪里、对象元数据如何落到文库字段”的问题；如果后续要检索对象正文、PDF 片段或实验材料内容，再补 RAG / 向量检索。

### 10.8 检索报告导出

```http
GET /api/library/<library_id>/retrieval/runs/<run_id>/report
```

支持 `format=markdown|csv|json`，默认返回 Markdown 文件下载，包含：

- 检索批次、查询词、操作者和时间。
- 数据源统计。
- 候选列表。
- 导入状态和 Zotero item key。

数据源统计会包含成功/失败、候选数量、耗时、错误类型和建议动作。
用途是阶段汇报、人工核对和问题追踪。

### 10.8 阶段统计
```http
GET /api/library/<library_id>/retrieval/summary
```

响应会聚合最近检索批次，返回检索批次数、候选总数、导入数、导入率、源成功率、各源平均耗时和错误类型分布。前端用它展示“阶段统计”看板，方便负责人 cjh 做阶段汇报。

阶段统计也支持下载报告：

```http
GET /api/library/<library_id>/retrieval/summary/report?format=markdown|csv|json
```

默认返回 Markdown，另支持 CSV 表格和 JSON 原始统计，便于汇报材料、表格分析和后续自动评估。

## 11. 前端设计草案

优先复用现有“添加条目”弹窗，增加一个 tab：

- 标识符导入
- 引用文本导入
- 多源检索

多源检索界面需要：

- 关键词输入框。
- 数据源勾选。
- 每源结果数量和错误提示。
- 每源耗时、限流、超时和建议动作提示。
- 阶段统计看板，包括检索批次、候选数、导入数、导入率、源成功率和各源平均耗时。
- 批量检索任务入口：多行 query、后台执行、进度条、每个 query 的 run_id 和失败提示。
- 候选结果表格。
- 候选详情预览。
- DOI / arXiv / PMID / ISBN 徽标。
- 来源徽标。
- 疑似重复提示。
- 批量勾选导入。

## 12. 迭代计划

### 里程碑 1：后端检索闭环

- 新增 retrieval 模块。
- 接入 Crossref search。
- 接入 arXiv search。
- 返回统一候选列表。
- 增加基础测试。

### 里程碑 2：候选导入闭环

- 候选转换为 `ImportedItem`。
- 新增 retrieval import API。
- 复用现有去重和入库。
- 返回导入 summary。

### 里程碑 3：前端多源检索入口

- 在添加条目弹窗增加“多源检索”。
- 展示候选列表。
- 支持批量选择导入。
- 展示导入结果。

### 里程碑 4：溯源与汇报能力

- 增加 retrieval run 记录。
- 增加 retrieval candidate 服务端缓存。
- 增加 import provenance 记录。
- 增加 source stats。
- 新增 retrieval runs 查询 API。
- 前端展示最近检索记录和导入统计。
- 支持导出检索/导入报告。

### 里程碑 5：扩展数据源

- PubMed 关键词检索。
- bioRxiv / medRxiv 预印本 DOI 检索和近期记录过滤。
- OpenAlex 关键词检索。
- Semantic Scholar 关键词检索。
- DataCite DOI 资源检索。
- OpenLibrary 图书/ISBN 资源检索。
- NASA ADS Bibcode 资源检索。
- 本地 CSV / JSONL 检索。

## 13. 测试计划

必须覆盖：

- provider 返回结果能转换为 `ImportedItem`。
- Crossref / arXiv 示例响应解析正确。
- 本地 CSV / JSONL 行能按现有文库字段映射为候选条目。
- 本地 CSV / JSONL 字段映射预览能展示列名、目标字段、样例 `ImportedItem`。
- 本地 CSV + JSONL 样例目录能完成“配置路径 -> 检索 -> candidate_id 导入 -> 写入本地副本文库 -> provenance 记录”的闭环验证。
- HTTP JSON 配置能把内部接口响应按 `items_path` 和 `field_map` 映射为候选条目，并支持内置配置模板、模板分页、响应 `next` 链接分页、环境变量鉴权和映射预览。
- SQLite 配置能把本地只读数据库查询结果按 `field_map` 映射为候选条目，并支持模板、预览和正式检索。
- Object Manifest 配置能把本地或远程 JSON 对象清单按 `items_path` 和 `field_map` 映射为候选条目，并支持本地/远程模板、预览和正式检索。
- `/retrieval/readiness` 能汇总内部源配置状态和样本映射质量，返回 `ready` / `warning` / `blocked`、样本数量和修复建议。
- `/retrieval/readiness/report` 能把预检结果导出为 Markdown / CSV / JSON。
- readiness 已能为 Local CSV/JSONL / HTTP JSON / SQLite / Object Manifest 输出 `field_map_suggestion`，文库级配置返回可保存草稿，环境变量配置只返回映射摘要。
- 多源候选按 DOI / arXiv ID 合并。
- 已有条目不会重复创建。
- 弱相似只提示，不自动合并。
- 部分源失败时，其他源结果仍能返回。
- 批量导入 summary 正确。
- 检索后生成 run_id 和 candidate_id。
- 使用 run_id + candidate_ids 能从服务端缓存导入候选。
- 导入后能在 retrieval runs 中统计候选数和导入数。
- 批量检索任务能去重 query、后台逐条生成 retrieval run，并记录 completed/failed/candidate 进度。
- 批量检索任务支持取消 queued query、暂停/恢复剩余 query，并支持只重试 failed query。
- 批量检索任务输出 `remaining_queries`、`average_seconds_per_completed_query` 和 `eta_seconds`，用于前端展示预计剩余时间。
- 前端保留最近检索记录入口，便于人工核对和阶段汇报。
- API 输出候选 rank、可信度标签和排序解释。
- API 输出当前文库已有条目的强标识符匹配提示。
- API 输出当前文库已有条目的低风险弱相似提示。
- API 输出每个外部源的 `elapsed_ms`、`error_kind` 和 `action`，用于健康检查、限流提示和阶段报告。
- API 输出阶段统计汇总，用于汇报多源检索进展和数据源稳定性。
- API 可导出阶段统计 Markdown / CSV / JSON 报告。
- 外部 HTTP 数据源遇到 `429`、`5xx`、超时或网络抖动时会执行轻量重试和短退避。
- API 输出源级节流预算和本次节流等待时间，用于解释批量检索速度和公共 API 保护策略。
- API 可基于阶段统计生成源级限流调优建议，并导出 Markdown / CSV / JSON。
- API 可生成多源接入验收报告，合并 readiness、tuning、配置包脱敏状态和下一步建议。
- API 可导出/导入文库级检索源配置包，默认脱敏直接密钥，并支持 dry-run 预演导入结果，便于和作者或队友交接。
- API 可基于列名或 JSON 样例生成 `field_map` 建议和配置草案，降低陌生异构源接入成本。
- Local CSV/JSONL 预览输出字段覆盖率和行级质量问题，用于导入前发现异构字段缺失。

## 14. 风险与约束

- 外部 API 可能限流或不可用，需要超时和降级。
- 不同数据源字段质量不一致，需要保留 raw 和 provenance。
- 预印本与正式发表版本可能存在 DOI/arXiv 双版本关系，不能粗暴合并。
- Zotero schema 不应被扩展，避免破坏兼容性。
- 只读文库不能写入；导入必须要求本地副本模式。

## 15. 汇报模板

每次阶段汇报可以按这个结构写：

```text
本阶段目标：

已完成：
- 

当前效果：
- 

关键技术点：
- 

遇到的问题：
- 

下一步计划：
- 
```

## 16. 当前推荐下一步

第一阶段当前已完成：

- 新增 `src/zotero_web_library/retrieval/` 模块。
- 新增统一候选模型 `RetrievedCandidate`。
- 接入 Crossref 关键词检索 provider。
- 接入 arXiv 关键词检索 provider。
- 接入 PubMed 关键词检索 provider。
- 接入 bioRxiv / medRxiv 预印本 provider，支持 DOI 精确查询和近期记录关键词过滤。
- 接入 OpenAlex 关键词检索 provider；未配置 `OPENALEX_API_KEY` 时返回清晰错误，不影响其他源检索。
- 接入 Semantic Scholar 关键词检索 provider；无 `SEMANTIC_SCHOLAR_API_KEY` 时仍可用，配置后提升限额稳定性。
- 接入 DataCite 关键词检索 provider，覆盖数据集、软件、报告等 DOI 资源。
- 接入 OpenLibrary 关键词检索 provider，覆盖图书、教材和 ISBN 元数据。
- 接入 NASA ADS 关键词检索 provider；未配置 `ADS_API_TOKEN` 或 `ADS_DEV_KEY` 时返回清晰配置状态，不影响其他源检索。
- 接入 Local CSV/JSONL provider；配置 `WEB_LIBRARY_RETRIEVAL_LOCAL_PATHS` 后可检索比赛数据、内部数据和离线整理表格。
- 接入 HTTP JSON provider；通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_HTTP_JSON_CONFIG` 配置内部检索接口后可检索团队自有结构化数据源，并支持内置模板、`max_pages`、`page` / `offset` 模板分页、`next_url_path` 响应分页、环境变量鉴权和小样本映射预览。
- 接入 SQLite provider；通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_SQLITE_CONFIG` 配置本地数据库路径、只读 SELECT 查询和字段映射后，可检索本地数据库型比赛数据。
- 接入 Object Manifest provider；通过文库偏好或 `WEB_LIBRARY_RETRIEVAL_MANIFEST_CONFIG` 配置本地/远程 JSON 对象清单后，可检索对象存储清单型比赛数据。
- 新增候选强标识符合并逻辑。
- 新增 `/api/library/<library_id>/retrieval/search` API。
- 新增 `/api/library/<library_id>/retrieval/import` API。
- 新增 `/api/library/<library_id>/retrieval/runs` API。
- 新增 `/api/library/<library_id>/retrieval/sources` API，展示源配置状态。
- 新增 `/api/library/<library_id>/retrieval/runs/<run_id>/report` API，导出 Markdown / CSV / JSON 检索报告。
- 新增 `retrieval_runs`、`retrieval_candidates`、`import_provenance` 应用侧记录。
- 前端导入已优先提交 `run_id` + `candidate_ids`，避免回传候选 raw 数据。
- 前端多源检索面板已展示数据源可用状态、最近检索记录、候选数、已导入数和各源返回统计，并支持下载 Markdown / CSV / JSON 检索报告。
- 前端候选列表已展示排序序号、可信度标签和排序解释。
- 前端候选列表已展示与当前文库已有条目的强标识符匹配提示。
- 前端候选列表已展示与当前文库已有条目的弱相似提示；该提示不触发自动合并。
- 候选导入复用现有 `ZoteroRepository.import_metadata_items()`，不重复实现写库逻辑。
- 新增后端测试覆盖 provider 解析、候选合并、API 调用、候选导入、候选缓存导入、溯源统计和只读文库写入保护。
- 前端“添加条目”弹窗已增加“多源检索”模式。
- 前端已支持 Crossref / arXiv / PubMed / bioRxiv / medRxiv / Semantic Scholar / DataCite / OpenLibrary / NASA ADS / Local CSV/JSONL / HTTP JSON / SQLite / Object Manifest / OpenAlex 源选择、候选展示、手动勾选和导入所选；OpenAlex、bioRxiv、medRxiv、OpenLibrary、NASA ADS、Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest 不默认勾选，Semantic Scholar 和 DataCite 默认勾选。

- 新增数据源诊断字段：耗时、错误类型、建议动作。
- 新增数据源结构化配置指南 `setup`：返回配置模式、环境变量、文库级配置入口、源级/全局限流变量和简短说明。
- 新增 `/api/library/<library_id>/retrieval/sources/report` 源配置报告导出 API，支持 Markdown / CSV / JSON。
- 新增 `/api/library/<library_id>/retrieval/readiness` 上线前预检 API，汇总内部源样本映射质量、样本数量和修复建议。
- 新增 `/api/library/<library_id>/retrieval/readiness/report` 预检报告导出 API，支持 Markdown / CSV / JSON。
- 新增 `/retrieval/sources?check=1` 轻量健康检查；前端用按钮手动触发，避免自动消耗 API 配额。
- 前端已显示每个源的耗时、失败类型、限流/超时建议、配置方式提示，并支持手动健康检查、READY 预检、字段映射草稿回填、RPT 预检报告下载和源配置报告下载。
- 新增 `docs/retrieval-deployment.md`，记录部署启动、源配置、限流变量、内部源配置示例、配置检查和上线前检查清单。
- 新增 `/api/library/<library_id>/retrieval/summary` 阶段统计 API。
- 前端已展示阶段统计看板：检索批次、候选数、导入数、导入率、源成功率和各源平均耗时。
- 新增 `/api/library/<library_id>/retrieval/summary/report` 阶段统计报告导出 API，支持 Markdown / CSV / JSON。
- 前端阶段统计看板已支持下载 Markdown / CSV / JSON 阶段报告。
- 新增 `/api/library/<library_id>/retrieval/tuning` 限流调优建议 API，基于失败率、错误类型、平均耗时、平均节流等待和当前源配置生成建议动作。
- 新增 `/api/library/<library_id>/retrieval/tuning/report` 限流调优报告导出 API，支持 Markdown / CSV / JSON。
- 前端多源检索面板已增加 `TUNE` 下载入口，用于小批量真实检索后复盘各源节流配置。
- 新增 `/api/library/<library_id>/retrieval/onboarding` 和 `/retrieval/onboarding/report` 接入验收报告 API，汇总源状态、readiness、query-plan、tuning、最近批量验证、候选 `import_readiness`、配置包脱敏状态和建议动作；`batch_validation` 已输出结构化状态、query-plan 草案覆盖度、已配置内部源覆盖情况和处理建议。
- 前端多源检索面板已增加 `ONB CHECK` 状态卡和 `ONB` 下载入口；状态卡会直接展示来源级 `source_evidence`，并可直接下载最新批量报告和来源级 CSV，用于阶段汇报验收材料。
- ONB 已增加 `acceptance_gates`，把源预检、批量验证、调优信号、配置包和交接材料拆成逐项状态、证据、建议和 artifact 下载入口，并在前端状态卡、Markdown、CSV 中留档。
- ONB 已增加 `package` 交接包导出，打包 README、manifest、ONB/Source setup/PLAN/READY/TUNE 报告、已配置内部源 field-map 报告、脱敏 CFG、最近批量报告和来源级 CSV；manifest 会记录 source setup、query-plan、field-map 报告摘要、字节数和 SHA256，前端提供 `ONB ZIP` 一键下载。
- 新增 `/api/library/<library_id>/retrieval/rehearsal/setup` 演练数据源生成 API，并在前端提供 `DEMO KIT` 按钮，可生成 CSV、SQLite、Object Manifest 三类异构源并保存配置，用于没有真实比赛源时演示完整 READY / Batch / ONB ZIP 闭环。
- 新增 `/api/library/<library_id>/retrieval/rehearsal/validate` 一键演练验收 API，并在前端提供 `DEMO RUN` 按钮，可生成演练源、以 `robot catalyst` 生成 PLAN 草案、启动 3 条 PLAN query 批量验证，并返回 Query plan、READY、Batch report、Source CSV、ONB report 和 ONB ZIP artifact endpoint；响应新增 `seed_queries`、实际 `queries`、`validation_summary` / `validation_gates`，用于直接汇报演练源配置、READY、Batch 和 ONB 交接 gate。
- 新增 `/api/library/<library_id>/retrieval/config-bundle` 文库级检索源配置包导出/导入 API，支持默认脱敏、跳过脱敏占位符导入，以及 `dry_run=1` 预演导入结果。
- 前端多源检索面板已增加 `CFG` 下载入口和配置包导入区，可先 dry-run 预演、下载结果 CSV，再真实导入，用于交接脱敏配置包。
- 新增 `/api/library/<library_id>/retrieval/source-intake` 和 `/retrieval/source-intake/report` 真实源接入分型 API，并在前端提供 `Source intake` 面板，可根据路径、URL、SQL、CSV 表头或 JSON 样例推荐 Local CSV/JSONL、HTTP JSON、SQLite 或 Object Manifest，下载分型报告，并把字段映射草案带到 Field map lab 或直接回填到目标源配置区；已存在的本地 CSV/JSONL/NDJSON、SQLite 或 Object Manifest JSON 路径会被小样本采样，用于直接生成真实路径配置草案；HTTP URL 需显式 `sample_url=true` 或勾选 `Sample URL` 后才会请求远程 JSON 样本，并生成 HTTP JSON `config_draft`；响应会输出结构化 `target_source` 作为后续批量验证的目标源，并输出 `validation_plan` 作为保存配置、READY、Batch、ONB 和 ONB ZIP 的验收清单；文库级 Source intake 还会读取目标源最近的 batch validation summary，把 `passed`、`low_sample`、`query_gap`、`source_gap`、`source_errors` 等状态、draft query 覆盖度和最近 batch report artifact 写回验收计划；有样本时同步输出 `validation_queries` 草案，`Use queries` 可一键填入批量检索框并默认只选中目标源，目标源不可用时会拦截检索并提示保存配置或刷新状态，方便保存配置后跑小批量验证。
- 新增 `/api/library/<library_id>/retrieval/field-map/targets`、`/retrieval/field-map/suggest` 和 `/retrieval/field-map/report`，可根据列名或 JSON 样例生成 Local CSV/JSONL / HTTP JSON / SQLite / Object Manifest 通用 `field_map` 建议、配置草案和可下载字段映射报告。
- 前端多源检索面板已增加 `Field map lab`，支持在保存真实源前用列名或 JSON 样例生成 `field_map` 和 starter `config_draft`，并把草案回填到对应配置区。
- Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest 保存配置和配置包导入时都会校验 `field_map` target；直接保存未知 target 会返回 400，配置包导入则把坏源放入 `skipped` 并继续处理其他有效源。
- 新增 `/api/library/<library_id>/retrieval/model-status` 和 Field map lab 的 `AI` 开关；前端会先显示 AI Pixel 是否已配置，配置 `AI_PIXEL_API_KEY` 后，通用字段映射建议可用 `use_ai=true` 调用 AI Pixel 补齐字段映射，模型输出会被样例路径白名单校验；Field map lab 的 `Check` 按钮会显式调用 `model-status?check=1` 做一次不泄露 key 的模型端点连通性检查。
- 新增 `/retrieval/local-files/field-map/suggest`、`/retrieval/http-json/field-map/suggest`、`/retrieval/sqlite/field-map/suggest` 和 `/retrieval/manifest/field-map/suggest`，可对已保存的真实源自动采样并生成 `field_map` 配置草案。
- 新增四类已配置源的 `/field-map/report` 下载接口，前端在各源配置区 `Suggest` 旁提供 `RPT`，可把真实采样得到的字段映射建议导出为 Markdown / CSV / JSON。
- 新增外部 HTTP 源轻量重试/退避机制，覆盖 `429`、`5xx`、超时和网络抖动；权限错误不重试。
- 新增外部源级调用节流预算，默认覆盖 Crossref / arXiv / PubMed / bioRxiv / medRxiv / OpenAlex / Semantic Scholar / DataCite / OpenLibrary / NASA ADS，可通过环境变量全局或按源覆盖。
- 新增 Local CSV/JSONL 前端路径和 `field_map` 配置，保存后即时刷新本地源可用状态，并让预览和正式检索使用同一份映射。
- 新增 `/api/library/<library_id>/retrieval/local-files/preview` 字段映射预览 API。
- 前端 Local CSV/JSONL 配置区已展示字段映射预览，可查看源列、目标字段、样例条目类型、标题、标识符、作者和标签。
- 前端 Local CSV/JSONL 预览已展示标题、强标识符、年份/日期、作者/创建者覆盖率，以及样例行缺字段问题；`Suggest` 可从当前样本生成本地 `field_map` 草案。
- 新增 `/api/library/<library_id>/retrieval/http-json` 文库级 HTTP JSON 配置 API。
- 前端已支持保存/清空 HTTP JSON 配置，并在配置可用后即时启用 `httpjson` 源。
- 新增 `/api/library/<library_id>/retrieval/http-json/templates` 模板 API。
- 前端 HTTP JSON 配置区已支持一键套用基础 REST、Bearer 分页和 API key 游标模板。
- 新增 `/api/library/<library_id>/retrieval/http-json/preview` 小样本映射预览 API。
- 前端 HTTP JSON 配置区已支持预览样例结果、字段覆盖率和行级质量问题，保存配置成功后会自动刷新 preview。
- 前端 HTTP JSON 配置区已支持 `Suggest`，可从已配置 HTTP JSON 源采样生成 `field_map` 草案。
- 新增 `/api/library/<library_id>/retrieval/sqlite`、`/retrieval/sqlite/templates` 和 `/retrieval/sqlite/preview` API。
- 前端 SQLite 配置区已支持模板套用、保存/清空、样例预览和启用 `sqlite` 源，保存配置成功后会自动刷新 preview。
- 前端 SQLite 配置区已支持 `Suggest`，可从只读查询结果采样生成 `field_map` 草案。
- 新增 `/api/library/<library_id>/retrieval/manifest`、`/retrieval/manifest/templates` 和 `/retrieval/manifest/preview` API。
- 前端 Object Manifest 配置区已支持模板套用、保存/清空、样例预览和启用 `manifest` 源，保存配置成功后会自动刷新 preview。
- 前端 Object Manifest 配置区已支持 `Suggest`，可从对象清单采样生成 `field_map` 草案。
- 新增批量检索任务 API：`POST/GET /api/library/<library_id>/retrieval/batches` 和 `GET /api/library/<library_id>/retrieval/batches/<job_id>`。
- 新增 `retrieval_batch_jobs`、`retrieval_batch_items` 应用侧记录，保存后台任务状态、query 进度、候选数、失败数和关联 `run_id`。
- 前端多源检索面板已支持多行 query 批量提交、最近批量任务展示、进度条和短轮询刷新。
- 前端批量任务卡片已支持暂停、恢复、取消运行中/排队任务，以及对失败 query 发起重试，并展示剩余 query 和 ETA。
- 新增 `/api/library/<library_id>/retrieval/query-plan` 和 `/retrieval/query-plan/report`，可从已配置内部源 preview 样例中生成 3 到 5 条小批量验证 query 草案，并导出 Markdown / CSV / JSON；前端批量检索面板 `PLAN` 按钮可一键填入批量 query 文本框，`PLAN RPT` 可直接下载草案报告，ONB ZIP 会把 PLAN 报告一并打包。
- 新增 `/api/library/<library_id>/retrieval/batches/<job_id>/report` 批量任务报告导出 API，支持 Markdown / CSV / JSON；Markdown 报告已包含来源级 Source summary，JSON 报告已包含 `source_evidence` / `source_errors`，`format=csv&scope=sources` 可下载来源级表格，前端批量任务卡片可直接下载 Markdown 报告和来源级 CSV。
- 新增本地异构样例数据集 `tests/fixtures/retrieval_sources/`，包含 CSV 内部登记表和 JSONL 外部导出记录。
- 新增端到端测试覆盖 Local CSV/JSONL 从前端配置接口、真实 provider 检索、候选缓存、按 candidate_id 导入、本地 Zotero 写入、run 统计和 `import_provenance` 记录。
- 新增测试覆盖 HTTP JSON provider 映射、配置模板、模板分页、next 链接分页、环境变量鉴权、映射预览、源配置状态和文库级配置后检索闭环。
- 新增测试覆盖 SQLite provider 映射、配置模板、文库级配置、预览和正式检索闭环。
- 新增测试覆盖 Object Manifest provider 映射、配置模板、源配置状态、文库级配置、预览和正式检索闭环。
- 新增测试覆盖字段映射建议器的嵌套 JSON 样例、列名建议、目标字段清单、API 配置草案，以及 HTTP JSON / SQLite / Object Manifest 已配置源自动采样建议。
- 新增测试覆盖接入验收报告的 readiness / tuning / 配置包汇总、Markdown 下载和 CSV 下载。

建议下一步优先实现：

1. 没有真实比赛数据源时，先点击 `DEMO RUN` 或调用 `/retrieval/rehearsal/validate?replace_existing=1`，用生成的 CSV / SQLite / Object Manifest 演练源一键跑通 READY、3 条 PLAN query 批量验证和 ONB ZIP；只想生成演练源时再用 `DEMO KIT` / `/retrieval/rehearsal/setup?replace_existing=1`。
2. 拿到真实比赛数据源后，先把路径、URL、SQL、CSV 表头或 JSON 样例贴到 `Source intake`，判断它属于 Local CSV/JSONL、HTTP JSON、SQLite 还是 Object Manifest，并用 `RPT` 下载分型报告；如果是本机 CSV/JSONL/NDJSON、SQLite 或 Object Manifest JSON 路径，先让 Source intake 采样并生成字段映射、配置草案和 `validation_queries`；如果是 HTTP JSON URL，确认可访问后勾选 `Sample URL` 做一次显式采样；再用 `Use config` 回填到目标源配置区，用 `Use queries` 把验证 query 填入批量检索框并默认只选中目标源；若目标源仍不可用，前端会阻止启动检索，先保存最小配置或刷新 source 状态后再跑小批量验证。
3. 对 Local CSV/JSONL，先保存路径、打开 preview，或从 `Source intake` / `Suggest` 生成本地 `field_map` 草案，人工确认后保存。
4. 对 HTTP JSON / SQLite / Object Manifest，保存最小连接配置后点击对应配置区的 `Suggest` 从真实样本生成 `field_map` 草案。
5. 用真实比赛数据源跑 `/retrieval/readiness`，验证各内部源配置模板，并补齐具体鉴权变量名、游标分页、SQL 查询和字段映射细节。
6. 调用 `/retrieval/query-plan` 或点击 `PLAN` 生成 3 到 5 条小批量验证 query 草案，人工确认后跑批量检索；需要交接时可下载 `/retrieval/query-plan/report`。
7. 调用 `/retrieval/onboarding` 或点击 `ONB CHECK` 查看接入验收状态，再下载 `/retrieval/onboarding/report` 或点击 `ONB`，把 readiness、query-plan、tuning、批量验证和配置包状态作为阶段验收材料。
8. 用真实检索压测结果生成 `/retrieval/tuning/report`，根据报告调整各源默认节流预算，并把最终推荐值写入 `docs/retrieval-deployment.md`。
9. 如果真实对象存储不能导出 JSON 清单，再补云厂商 SDK 或权限代理型 provider；否则优先沉淀比赛专用模板。
10. 为新增源继续复用现有 provider 状态、节流预算、错误诊断、源配置报告和阶段统计。

这个切片已经可以向团队展示“多源检索从前端到后端可用，并能导入本地副本文库，而且每次检索和导入都有应用侧记录”，同时还没有过早陷入复杂 UI 和数据源数量竞赛。
## v3.16 update: AI-assisted PLAN

- `/retrieval/query-plan` and `/retrieval/query-plan/report` now accept `use_ai=1`.
- The backend still builds deterministic rule queries first. When `AI_PIXEL_API_KEY` is configured, AI Pixel may add short validation queries, but accepted AI queries must overlap the seed/query/evidence terms and must not contain URLs or credential-like text.
- The response includes `ai_enhancement` with requested/configured/status/suggested/accepted/applied/rejected counts, without returning the API key or model payload.
- ONB, ONB report and ONB ZIP accept the same `use_ai=1` flag so batch validation can be checked against the same AI-enhanced PLAN that filled the batch query box.
- ONB, ONB report and ONB ZIP also accept `required_queries` as newline-separated reviewed batch queries. When present, batch coverage is checked against that explicit list instead of a freshly regenerated PLAN, so AI or human query edits do not cause validation drift.
- New batch jobs store a redacted retrieval-config fingerprint in `retrieval_batch_context`; ONB surfaces `config_context_status` and returns `config_drift` when the latest batch was produced under an older source configuration.
- `batch_validation` now includes structured `remediation` hints with `action`, `label`, `method`, `endpoint`, and optional `queries` / `sources`, so ONB and Source intake can distinguish "download evidence" from POST actions such as retrying failed queries, rerunning the current-config batch, or filling missing query/source coverage. The frontend renders safe POST remediation as an explicit button that creates the suggested batch or calls `retry-failed`, then refreshes batch/ONB evidence.
- The frontend Batch retrieval panel has an `AI` toggle beside `PLAN`; it is disabled until `AI_PIXEL_API_KEY` is configured and `model-status` reports the model as available.

## v3.17 update: 字段保真、候选去重和真实案例

本次优化解决三个汇报重点：

- 入库前字段补全：候选条目的顶层 `title`、`abstract`、`landing_url`、`identifiers`、`creators` 会回填到统一 `ImportedItem`，避免前端候选里看得到、入库后丢失。
- Zotero 写入前兜底：如果来源只给了 `identifiers`，系统会把 DOI / ISBN 写入 Zotero 原生字段，把 PMID / PMCID / arXiv / ADS Bibcode 写入 `extra`。
- 候选去重和多源命中：先按 DOI / PMID / PMCID / arXiv / ADS Bibcode / ISBN 合并；没有强标识符时，有作者信息则按“规范化标题 + 年份 + 第一作者”合并，缺作者时才退回“规范化标题 + 年份”。合并后的候选会输出 `sources`、`source_count`、`multi_source` 和 `also_seen_in`，前端显示“多源命中”。
- 候选操作简化：候选结果区支持“全选候选”和“清空选择”，检索结果多时可以先批量选择，再逐条取消不需要入库的条目。

### 检索后实际保存的位置

检索后不会马上写入 Zotero 文库。系统先保存检索批次和候选，用户勾选后才导入。

应用侧证据链库：

```text
app-data/app.sqlite
  retrieval_runs        检索批次：query、sources、source_stats、operator、created_at
  retrieval_candidates  候选快照：candidate_id、run_id、source、external_id、title、identifiers_json、payload_json
  import_provenance     导入证据：run_id、candidate_id、item_key、status、source、identifiers_json、operator
```

Zotero 文库库：

```text
app-data/libraries/<library_id>/zotero.sqlite
  items            条目主体
  itemData         title、DOI、date、abstractNote、publicationTitle、url、extra 等字段
  creators         作者
  itemCreators     条目和作者关系
  tags / itemTags  标签
  collectionItems  导入到哪个文库文件夹
```

### 真实例子 1：论文 / PubMed

检索关键词：

```text
speculative decoding
```

候选快照示例：

```json
{
  "source": "pubmed",
  "external_id": "42241253",
  "title": "SJD++: Improved Speculative Jacobi Decoding for Training-free Acceleration of Discrete Auto-regressive Text-to-Image Generation.",
  "identifiers": {
    "pmid": "42241253",
    "doi": "10.1109/tpami.2026.3700227"
  }
}
```

导入 Zotero 后保存成：

```json
{
  "item_type": "journalArticle",
  "fields": {
    "title": "SJD++: Improved Speculative Jacobi Decoding for Training-free Acceleration of Discrete Auto-regressive Text-to-Image Generation.",
    "DOI": "10.1109/tpami.2026.3700227",
    "date": "2026",
    "publicationTitle": "IEEE transactions on pattern analysis and machine intelligence",
    "url": "https://pubmed.ncbi.nlm.nih.gov/42241253/",
    "extra": "PMID: 42241253"
  },
  "creators": [
    {"first_name": "Yao", "last_name": "Teng", "creator_type": "author"},
    {"first_name": "Zhihuan", "last_name": "Jiang", "creator_type": "author"}
  ],
  "identifiers": {
    "pmid": "42241253",
    "doi": "10.1109/tpami.2026.3700227"
  }
}
```

证据链记录会保存：

```json
{
  "run_id": "run-3iqqgl4wmwy0",
  "candidate_id": "cand-r5spyhh1rqzc",
  "item_key": "KBRBYCK1",
  "status": "created",
  "source": "pubmed",
  "operator": "cjh"
}
```

### 真实例子 2：数据 / 软件 / DataCite

候选快照示例：

```json
{
  "source": "datacite",
  "external_id": "10.48448/w24j-c646",
  "title": "Decoding Speculative Decoding",
  "identifiers": {
    "doi": "10.48448/w24j-c646"
  }
}
```

导入 Zotero 后保存成：

```json
{
  "item_type": "document",
  "fields": {
    "title": "Decoding Speculative Decoding",
    "DOI": "10.48448/w24j-c646",
    "date": "2025",
    "publisher": "Underline Science Inc.",
    "url": "https://underline.io/lecture/116280-decoding-speculative-decoding",
    "extra": "DataCite ID: 10.48448/w24j-c646\nDataCite Resource Type: Audiovisual\nDataCite Resource Type Detail: Conference talk"
  },
  "tags": [
    "Artificial Intelligence",
    "Computational Linguistics",
    "Natural Language Processing"
  ],
  "identifiers": {
    "doi": "10.48448/w24j-c646"
  }
}
```

这个例子体现了异构性：它不是传统论文，但仍然能按 Zotero 文库格式保存为可检索条目，来源类型细节放进 `extra`。

### 真实例子 3：本地 / Manifest 多源命中

如果同一个对象同时存在于本地 CSV 和 Object Manifest，例如：

```json
{
  "title": "AI4S Catalyst Benchmark Dataset",
  "date": "2026",
  "creators": [{"name": "Ada Lovelace"}],
  "source": "localfile"
}
```

以及：

```json
{
  "title": "AI4S Catalyst Benchmark Dataset",
  "date": "2026",
  "creators": [{"name": "Ada Lovelace"}],
  "source": "manifest",
  "url": "https://example.test/dataset"
}
```

没有 DOI 时，因为两个来源的规范化标题、年份和第一作者一致，系统会合并为一条候选：

```json
{
  "title": "AI4S Catalyst Benchmark Dataset",
  "sources": ["localfile", "manifest"],
  "source_count": 2,
  "multi_source": true,
  "also_seen_in": ["manifest"],
  "landing_url": "https://example.test/dataset"
}
```

前端显示为“多源 localfile / manifest”和“多源命中 2”。导入后仍然落到统一 `ImportedItem`，再由 `import_metadata_items()` 写入 Zotero。

## v3.18 update: AI 辅助检索和代码/数据源扩展

- 新增独立 API 配置页 `/library/<library_id>/api-config`，侧边栏用“配”进入；模型配置只填模型名称、请求地址和 API Key，代码/数据源 token 为 GitHub、HuggingFace、Zenodo 三项可选配置。
- 新增 `GET/POST /api/library/<library_id>/api-config` 和 `/api-config/check`，配置保存在本机 `app.sqlite` 的 `preferences`，默认脱敏显示，页面配置优先于环境变量。
- 新增 GitHub、HuggingFace、Zenodo provider：分别映射为代码仓库、模型/数据集、软件/数据/报告 DOI 资源，并接入源状态、限流、错误诊断、多源候选合并和证据链。
- `/retrieval/query-plan` 支持 `sources` 过滤和页面级模型配置；前端主检索区新增“AI 生成检索计划”，展示 query、推荐源和理由，用户确认后再启动批量检索。
- `/retrieval/search` 默认开启 AI 候选可用性判断；模型未配置时返回 `not_configured` 且检索不失败。
- AI 评估只发送候选元数据，不发送 raw JSON；候选新增 `ai_evaluation`，严格推荐项才会 `auto_select=true`，最终仍需用户点击“导入所选”。
