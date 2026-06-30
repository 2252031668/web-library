# 多源检索部署与配置指南

负责人：cjh  
更新时间：2026-06-29

## 目标

这份文档用于部署、汇报和交接多源异构数据检索能力。当前实现以结构化元数据检索为主：公共学术 API、文库级本地/内部源配置、候选去重、导入本地副本文库、阶段统计和报告导出。

## 启动服务

```powershell
$env:WEB_LIBRARY_HOST='127.0.0.1'
$env:WEB_LIBRARY_PORT='8686'
$env:WEB_LIBRARY_DEBUG='1'
python -m uv run python -m zotero_web_library.web
```

打开：

```text
http://127.0.0.1:8686/
```

进入任意文库后，点击顶部 `多源检索` 进入独立功能页：

```text
/library/<library_id>/features
```

## 源配置总览

| 源 | 配置方式 | 关键变量 / 入口 | 说明 |
| --- | --- | --- | --- |
| Crossref | 无需配置 | `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_CROSSREF_SECONDS` | 公共接口，批量时建议控制频率。 |
| arXiv | 无需配置 | `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_ARXIV_SECONDS` | 默认限流较慢，适合低频交互和后台批量保护。 |
| PubMed | 无需配置 | `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_PUBMED_SECONDS` | 公共 E-utilities；高频时后续可扩展 NCBI API Key。 |
| bioRxiv / medRxiv | 无需配置 | `WEB_LIBRARY_RETRIEVAL_PREPRINT_DAYS` | DOI 精确查询，关键词检索会扫描近期记录并本地过滤。 |
| OpenAlex | 必填环境变量 | `OPENALEX_API_KEY` | 当前要求配置后启用，避免匿名限额不稳定。 |
| Semantic Scholar | 可选环境变量 | `SEMANTIC_SCHOLAR_API_KEY` | 不配置也可用，配置后限额和稳定性更好。 |
| DataCite | 无需配置 | `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_DATACITE_SECONDS` | 适合数据集、软件、报告 DOI。 |
| OpenLibrary | 无需配置 | `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_OPENLIBRARY_SECONDS` | 适合图书、教材、ISBN 元数据。 |
| NASA ADS | 必填二选一 | `ADS_API_TOKEN` 或 `ADS_DEV_KEY` | 天文/物理 Bibcode 元数据。 |
| Local CSV/JSONL | 文库配置或环境变量 | `/retrieval/local-files`，`WEB_LIBRARY_RETRIEVAL_LOCAL_PATHS` | 读取本地 CSV、JSONL、NDJSON；文库配置可保存 `field_map`。 |
| HTTP JSON | 文库配置或环境变量 | `/retrieval/http-json`，`WEB_LIBRARY_RETRIEVAL_HTTP_JSON_CONFIG` | 接入团队内部 HTTP 检索接口。 |
| SQLite | 文库配置或环境变量 | `/retrieval/sqlite`，`WEB_LIBRARY_RETRIEVAL_SQLITE_CONFIG` | 只读查询本地 SQLite 结构化表。 |
| Object Manifest | 文库配置或环境变量 | `/retrieval/manifest`，`WEB_LIBRARY_RETRIEVAL_MANIFEST_CONFIG` | 读取本地或远程 JSON 对象清单。 |

全局源级限流覆盖：

```text
WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_SECONDS
```

单源覆盖格式：

```text
WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_<SOURCE>_SECONDS
```

例如：

```powershell
$env:WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_OPENALEX_SECONDS='0.5'
$env:WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_ARXIV_SECONDS='3'
```

## 文库级内部源

### Local CSV/JSONL

适合比赛数据、离线整理表和团队内部导出文件。前端可在多源检索面板保存路径和 `field_map`，也可设置：

```powershell
$env:WEB_LIBRARY_RETRIEVAL_LOCAL_PATHS='C:\data\items.csv'
```

支持目录路径，目录内会读取 `.csv`、`.jsonl`、`.ndjson`。如果列名不是内置别名，可在 Local 配置区保存 JSON `field_map`，例如：

```json
{
  "title": "headline",
  "date": "published_on",
  "doi": "identifier_value",
  "authors": "creator_names",
  "tags": "topic_terms",
  "item_type": "kind",
  "url": "landing"
}
```

保存后 Local preview、readiness 和正式检索都会使用这份映射。前端 `Suggest` 按钮会从当前 preview 样本生成建议，人工确认后再保存。

### HTTP JSON

适合已有内部检索服务。可用前端模板，或设置 JSON 配置：

```json
{
  "label": "Internal API",
  "url_template": "https://example.test/search?q={query}&limit={limit}&page={page}",
  "items_path": "results",
  "max_pages": 2,
  "auth": {"type": "bearer_env", "env": "INTERNAL_API_TOKEN"},
  "field_map": {
    "title": "title",
    "date": "year",
    "doi": "doi",
    "authors": "authors",
    "abstract": "abstract",
    "tags": "keywords",
    "external_id": "id"
  }
}
```

### SQLite

适合本地只读索引库。只允许单条 `SELECT` 或 `WITH` 查询：

```json
{
  "label": "Internal SQLite",
  "path": "C:/data/retrieval.sqlite",
  "query": "SELECT id, title, year, doi, authors, abstract, keywords, url, venue, item_type FROM items WHERE title LIKE :like_query OR abstract LIKE :like_query LIMIT :limit"
}
```

### Object Manifest

适合对象存储导出的 JSON 清单、数据湖目录或比赛平台对象索引：

```json
{
  "label": "Object Manifest",
  "manifest_path": "C:/data/object-manifest.json",
  "items_path": "objects",
  "field_map": {
    "title": "title",
    "date": "year",
    "doi": "doi",
    "authors": "authors",
    "abstract": "abstract",
    "url": "object_url",
    "pdf_url": "pdf_url",
    "tags": "keywords",
    "external_id": "id"
  }
}
```

远程 manifest 可使用：

```json
{
  "manifest_url": "https://example.test/object-manifest.json",
  "auth": {"type": "bearer_env", "env": "MANIFEST_TOKEN"}
}
```

## 配置检查与报告

静态源状态：

```http
GET /api/library/<library_id>/retrieval/sources
```

带轻量健康检查：

```http
GET /api/library/<library_id>/retrieval/sources?check=1
```

导出当前源配置报告：

```http
GET /api/library/<library_id>/retrieval/sources/report?format=markdown
GET /api/library/<library_id>/retrieval/sources/report?format=csv
GET /api/library/<library_id>/retrieval/sources/report?format=json
```

前端多源检索面板里的 `SETUP` 按钮会下载 Markdown 配置报告。

上线前内部源预检：

```http
GET /api/library/<library_id>/retrieval/readiness?query=robot&sample_size=2
GET /api/library/<library_id>/retrieval/readiness/report?query=robot&sample_size=2&format=markdown
GET /api/library/<library_id>/retrieval/query-plan?seed_query=robot&sample_size=5&limit=5
GET /api/library/<library_id>/retrieval/query-plan/report?seed_query=robot&sample_size=5&limit=5&format=markdown
```

Readiness JSON now includes `field_map_suggestion` for configured Local CSV/JSONL, HTTP JSON, SQLite and Object Manifest sources.
The suggestion summarizes inferred `field_map` entries, quality coverage, sample count and whether an editable
`config_draft` is available. Preference-saved configs can return a draft for review; environment-backed configs
return only the mapping summary so reports do not expose secret-bearing config values.
Local CSV/JSONL preference configs can now save the suggested `field_map` with the path list, so offline files can
stay in their original column format while still mapping into the existing library schema.

该接口会汇总静态源状态，并对已经配置的 Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest 做小样本映射预览，返回 `ready`、`warning` 或 `blocked` 状态、样本数量、字段质量和修复建议。前端多源检索面板里的 `READY` 按钮会调用预检接口；如果预检项带可保存 `field_map` 草稿，可在 readiness 卡片直接 `Apply` 回填到对应配置区，人工确认后保存。`RPT` 按钮会下载 Markdown 预检报告；也可以通过 `format=csv|json` 导出表格或原始结构化报告。适合在接入真实比赛数据源后快速确认“配置是否可用、样本能否落到现有文库格式”。

`/retrieval/query-plan` 会复用 readiness 的内部源 preview 样例，从已保存的 Local CSV/JSONL、HTTP JSON、SQLite 和 Object Manifest 配置里提取标题、标签和摘要关键词，生成 3 到 5 条小批量验证 query 草案。`/retrieval/query-plan/report` 可导出 Markdown / CSV / JSON，保留每条 query 的来源、样本证据和建议动作。前端批量检索面板的 `PLAN` 按钮会把 `query_text` 填入批量 query 文本框，`PLAN RPT` 会下载 Markdown 草案报告，用户确认后再点击 `Start batch`；该接口不写入配置，也不替代正式检索。

批量检索报告：

```http
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=markdown
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=csv
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=csv&scope=sources
GET /api/library/<library_id>/retrieval/batches/<job_id>/report?format=json
```

批量任务卡片里的 `Report` 按钮会下载 Markdown 报告，`SRC CSV` 会下载来源级表格。报告先按 source 汇总 `source_evidence`，展示每个来源是否被请求、覆盖了多少 query、成功/失败次数、候选数、耗时和最新诊断；再按 query 汇总状态、关联 `run_id`、候选数、源级候选数、耗时和诊断。`format=csv` 默认仍导出逐 query 表格；`format=csv&scope=sources` 导出来源级 `source_evidence` 表格。JSON 报告同步包含 `source_evidence`、`source_errors` 和 `source_error_count`，适合把 3 到 5 个真实 query 的小批量压测结果交给队友复盘。

候选导入后，`POST /api/library/<library_id>/retrieval/import` 会在原有导入 summary 外返回 `import_evidence`。它记录本次候选数、导入结果数、provenance 记录数、item key 数、status 分布、来源列表、样例 item 明细，以及 `run_report_markdown_endpoint` 和 `summary_report_endpoint`。前端导入成功提示会显示“溯源记录 x/y 条”，导入后可直接打开 run 报告或阶段 summary 报告，证明“搜到的候选已经按现有文库格式落库并留下溯源”。

小批量真实检索后的限流调优：

```http
GET /api/library/<library_id>/retrieval/tuning
GET /api/library/<library_id>/retrieval/tuning/report?format=markdown
GET /api/library/<library_id>/retrieval/tuning/report?format=csv
GET /api/library/<library_id>/retrieval/tuning/report?format=json
```

该接口会基于最近检索运行的 `source_stats` 和当前源配置，汇总每个源的失败率、错误类型、候选数、平均耗时、平均节流等待、当前限流和建议限流。`rate_limited` 会建议调大对应 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_<SOURCE>_SECONDS`；`configuration` / `auth` 会提示先修配置；`timeout` / `network` / `upstream` 会结合失败率建议放慢并复测。前端多源检索面板里的 `TUNE` 按钮会下载 Markdown 调优报告。

接入验收报告：

```http
GET /api/library/<library_id>/retrieval/onboarding
GET /api/library/<library_id>/retrieval/onboarding/report?format=markdown
GET /api/library/<library_id>/retrieval/onboarding/report?format=csv
GET /api/library/<library_id>/retrieval/onboarding/report?format=json
GET /api/library/<library_id>/retrieval/onboarding/package
POST /api/library/<library_id>/retrieval/rehearsal/setup?replace_existing=1
POST /api/library/<library_id>/retrieval/rehearsal/validate?replace_existing=1
```

ONB 的批量验证至少需要 3 条已完成的真实 query 才能进入 `passed`；少于 3 条时会返回 `low_sample`，前端验收卡会显示已完成 query / 最低要求 query。

如果还没有拿到真实比赛数据源，可以先点击前端 `DEMO KIT`，或调用 `/retrieval/rehearsal/setup?replace_existing=1`。它会在 `WEB_LIBRARY_DATA_DIR/retrieval-rehearsal/<library_id>/` 下生成一组公开虚构的 CSV、SQLite 和 Object Manifest 源，并保存到当前文库的 Local CSV/JSONL、SQLite、Object Manifest 配置中。默认 API 不会覆盖已有内部源配置；只有传 `replace_existing=1` 时才会替换这三类演练配置。需要一键演示完整闭环时，点击前端 `DEMO RUN`，或调用 `/retrieval/rehearsal/validate?replace_existing=1`；该接口会生成/配置演练源，以 `robot catalyst` 生成 query-plan 草案，再按 PLAN query 跑批量验证，并返回 Query plan、READY、Batch report、Source CSV、ONB report 和 ONB ZIP 入口。响应里的 `seed_queries` 保留演练包种子 query，`queries` 是实际执行的 PLAN query；`validation_summary` 会汇总 READY 状态、batch 完成 query、候选数、ONB 状态和 artifact 数，`validation_gates` 会逐项列出演练源配置、READY、Batch、ONB 的状态、证据和下载入口，可直接放进阶段汇报或交接说明。

ONB 还会输出 `acceptance_gates`，把源预检、query-plan 覆盖、批量验证、调优信号、配置包和交接材料拆成逐项 gate。每个 gate 都有 `status`、`evidence`、`message`、`action_endpoint` 和 `artifacts`；前端状态卡可直接下载 gate 关联的 READY/PLAN/TUNE/ONB/CFG/Batch report/Source CSV，并显示 PLAN coverage 和 config evidence。Markdown 报告和 CSV 明细也会保留这些证据，便于汇报时解释“哪一项已经能交接，哪一项还要补真实 query 或修配置”。如果最近 batch 没覆盖当前 PLAN 草案 query，ONB 会返回 `query_gap`，提示先按 PLAN/Use queries 重跑小批量验证。

新建 batch 会记录当时脱敏源配置的指纹，ONB 会把该指纹和当前配置指纹比较，输出 `config_context_status=matched|mismatch|unknown`。旧 batch 没有上下文时显示 `unknown`；如果最新 batch 是旧配置下跑出的结果，ONB 会返回 `config_drift`，需要保存当前源配置后重新跑 3 到 5 条 query 的小批量验证。

ONB 的 `batch_validation.remediation` 会把下一步动作结构化为 `action`、`label`、`method`、`endpoint`，必要时还会带上建议补跑的 `queries` 或 `sources`。`GET` 动作通常是下载最新 Batch report 或 Source CSV；`POST` 动作是建议执行的补救操作，例如 retry failed queries、按当前配置重跑 `/retrieval/batches`，或只补当前 PLAN / Source intake 缺失的 query/source 覆盖。前端 gate 和报告会显示 method，方便汇报时区分“已有证据可下载”和“还需要补跑验证”；当 endpoint 通过 `/retrieval/` 白名单且 method 为 `POST` 时，前端会显示人工点击的补跑按钮，点击后创建建议 batch 或调用 `retry-failed`，并刷新 batch/ONB 证据。

ONB 还会输出 `import_readiness` gate：它从最近 batch 的 cached candidates 抽样，调用现有候选转 `ImportedItem` 逻辑做 dry-run 检查，不写入 Zotero SQLite。报告会记录 sampled candidates 中有多少能进入现有入库模型、多少缺 title、多少存在转换错误；如果全部样本都无法转换，ONB 会标为 blocked。这个 gate 用来证明“真实源不仅能检索出候选，而且候选能按现有文库格式存起来”。

`/retrieval/onboarding/package` 会生成一份 ZIP 交接包，包含 README、manifest、ONB Markdown/CSV/JSON、Source setup Markdown/CSV/JSON、PLAN Markdown/CSV/JSON、READY Markdown/CSV/JSON、已配置内部源 field-map Markdown/CSV/JSON、TUNE Markdown/CSV/JSON、脱敏 CFG JSON，以及最近批量任务的 Markdown/CSV/JSON 和 Source CSV。`manifest.json` 会记录 gate 状态、source_setup 摘要、query-plan 摘要、field_map_reports 摘要、包内 payload 文件清单、字节数和 SHA256，方便交给队友或仓库作者后做内容核验。前端 `ONB ZIP` 按钮或 handoff gate 的 `ONB package` artifact 可直接下载，适合留档复盘。

该接口会把源配置状态、readiness 预检、tuning 调优信号、最近批量任务验证、配置包脱敏状态和下一步建议汇总成一份验收材料。前端 `ONB CHECK` 会直接显示接入验收状态卡，并把 `batch_validation.source_evidence` 展示成每个来源的 q / ok / fail / hits / elapsed 摘要；如果存在最近批量任务，卡片会直接提供 `Batch report` 和 `Source CSV` 下载入口。`ONB` 按钮默认下载 Markdown 报告，适合在保存真实内部源配置后向队友或仓库作者说明“哪些源已配置、样例能否落到文库格式、最近批量 query 是否跑过、配置包是否可交接”。ONB 的 `batch_validation` 会列出最近批量任务数量、完成 query、失败 query、候选数、最新批量任务报告端点、最新来源级 CSV 端点、当前配置指纹状态，并对已配置内部源计算 `validated_sources` / `missing_sources` 覆盖情况；ONB Markdown / CSV 明细表会把每个最近批量任务的来源级 CSV 作为 `batch_evidence` 行留存，也会用 `batch_context` 行留存配置指纹匹配状态。它还会聚合 batch item 的源级 `source_stats`，给出 `missing`、`active`、`failed_queries`、`source_errors`、`incomplete`、`source_gap`、`config_drift`、`no_candidates` 或 `passed` 状态和处理建议。

字段映射建议：

```http
GET /api/library/<library_id>/retrieval/model-status
GET /api/library/<library_id>/retrieval/model-status?check=1
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
POST /api/library/<library_id>/retrieval/source-intake
POST /api/library/<library_id>/retrieval/source-intake/report?format=markdown|csv|json
```

Optional AI Pixel enhancement is available only for the generic `POST /retrieval/field-map/suggest` lab path.
Set `AI_PIXEL_BASE_URL=https://ai-pixel.online` and `AI_PIXEL_API_KEY` in the local environment, then send
`use_ai=true`. The backend still runs the rule-based mapper first, sends only sample paths/values to the model,
and accepts only model-returned paths that already exist in the provided columns or JSON samples.
`/retrieval/query-plan` and `/retrieval/query-plan/report` also accept `use_ai=1`. The backend still builds the
rule-based PLAN first, then allows AI Pixel to add short validation queries only when they overlap the seed/query/evidence
terms and do not contain URLs or credential-like text. If you use the Batch panel `AI` toggle beside `PLAN`, keep the
same toggle enabled for `ONB CHECK`, `ONB` and `ONB ZIP` so batch validation is checked against the same AI-enhanced PLAN.
`ONB CHECK`, `ONB` and `ONB ZIP` also pass the current Batch retrieval textarea as newline-separated `required_queries`;
when present, ONB validates coverage against those reviewed queries instead of regenerating PLAN. This is the preferred
handoff path after the user edits PLAN text or uses AI-assisted PLAN.
The frontend reads `model-status` before enabling the Field map lab `AI` switch, so demos can show whether the local
environment is ready without exposing the API key.
The Field map lab `Check` button calls `model-status?check=1` on demand. That endpoint sends one tiny chat-completions
request to AI Pixel and returns only `health.ok`, `elapsed_ms`, `error_kind`, and a short error/message summary; it does
not return the API key or model request payload.

`/retrieval/source-intake/report` exports the same source-intake classification as Markdown, CSV or JSON. Use it before
saving a real source config when you need a handoff artifact that explains the detected signals, likely source type,
field-map draft, config draft, intake-level validation query drafts and next actions. The frontend `Source intake`
panel exposes this as `RPT`.

`/retrieval/field-map/report` exports the same Field map lab suggestion as Markdown, CSV or JSON. Use it when you need
evidence for how external columns or JSON paths map into the existing library format, including confidence, coverage,
unmapped paths, optional AI status and the generated `config_draft`. The frontend `Field map lab` exposes this as `RPT`.
Each saved internal source also has a source-specific `/field-map/report` endpoint beside its `/field-map/suggest`
endpoint. Those reports sample the configured source itself, so use them after saving Local CSV/JSONL, HTTP JSON,
SQLite or Object Manifest config when the handoff needs proof from the real source instead of a pasted lab sample.

拿到真实比赛数据源后，第一步可以先在多源检索面板的 `Source intake` 粘贴路径、URL、SQL、CSV 表头或 JSON 样例，或调用 `/retrieval/source-intake`。它会推荐最可能的源类型、下一步配置端点、必填配置项、后续 batch 应使用的 `target_source`，并在样例足够时生成可带到 Field map lab 的 `field_map_lab` 草案；该接口不保存任何配置。粘贴已存在的本地 CSV/JSONL/NDJSON 文件或目录时，接口会读取少量样例行；粘贴 SQLite 路径时，接口会只读读取 schema 和样例行，并生成带真实 `path` / `query` 的 `config_draft`；粘贴 Object Manifest JSON 路径时，接口会读取少量对象记录、推断 `items_path`，并生成带真实 `manifest_path` 的 `config_draft`。HTTP URL 默认只做类型识别；勾选前端 `Sample URL` 或调用接口时传 `sample_url=true` 后，才会请求一次远程 JSON 样本，并生成带 `url_template`、推断 `items_path` 和 `field_map` 的 HTTP JSON `config_draft`。有样本时，响应还会输出 `validation_queries`，从样本标题、标签/关键词和摘要提取 1 到 5 条验证 query 草案，并输出 `validation_plan`，列出保存配置、READY 预检、目标源小批量验证、ONB/ONB ZIP 证据下载这些 gate 和 artifact；文库级 API 会读取当前 `/retrieval/sources` 状态，保存前 `save_config` 是 pending，保存后会变成 passed，同时读取目标源最近的 batch validation summary，并把本次 `validation_queries` 作为 `required_queries` 校验 draft coverage。最近 batch 已完成 3 条以上目标源 query、覆盖当前草案 query、候选数非零且无失败时，Source intake 会把 `validation_plan.status` 和 batch gate 推进为 `passed`，并在 artifact 中附上最近 batch report / source CSV；如果最近 batch 没有覆盖当前草案 query，则会显示 `query_gap`；如果最近 batch 是旧配置下跑出的结果，则会显示 `config_drift` 和 `config_context_status=mismatch`，提示先按当前配置重跑；如果证据不足，则会显示 `low_sample`、`source_gap`、`source_errors`、`no_candidates` 等状态。前端分型结果卡会直接显示这份验收计划、最近 batch evidence、draft coverage 和 config evidence。`Use queries` 会把这些 query 直接填入批量检索框，并按 `target_source.name` 默认只选中目标源作为批量 source；目标源仍不可用时，普通检索和批量检索都会被前端拦截，提示先保存配置或刷新 source 状态。正式验收仍以保存配置后的 `PLAN` / Batch / ONB 为准。前端 `Use in lab` 用于把草案带到 Field map lab 继续调字段；`Use config` 用于直接回填到目标源配置区，回填后仍需人工点击对应配置区的 `Save`。

Source intake 的 `validation_plan.batch_validation.remediation` 复用 ONB 的补救动作，因此分型报告会明确写出下一步是下载现有证据，还是补跑目标源 batch、补齐 draft query 覆盖、按当前配置重跑，或先处理来源级错误。字段本身不自动修改配置；当前端看到安全的 `POST` remediation 且已有建议 query 时，会显示补跑按钮，由 cjh 或协作者人工点击后再启动 batch，避免分型分析阶段静默发起检索。

拿到陌生 CSV/SQL 列名或 JSON 样例后，也可以直接在 `Field map lab` 粘贴样例，或调用通用 `field-map/suggest` 生成 `field_map` 建议和 `config_draft`。请求可包含 `columns`、`sample` / `samples` 和未保存的 `config`；如果还没有完整连接配置，后端会按 `source_type` 返回带占位 URL / SQLite 路径 / Manifest 路径的 starter `config_draft`，再由人工补齐。响应会返回建议目标字段、置信度、未映射路径，以及标题、强标识符、年份、作者覆盖质量。该接口不写入配置，适合人工确认后再保存 Local CSV/JSONL、HTTP JSON、SQLite 或 Object Manifest 配置。保存配置时，`field_map` target 必须来自 `field-map/targets`；拼错或未知 target 会返回 400。配置包导入也会按源校验 target，但坏源会进入 `skipped`，避免静默丢字段且不阻断其他有效源。

如果 Local CSV/JSONL / HTTP JSON / SQLite / Object Manifest 已经保存了最小配置，优先使用前端配置区的 `Suggest` 按钮或对应 source-specific API。它会从真实源读取小样本、自动推断 `field_map`；HTTP JSON / Object Manifest 还会推断 `items_path`。文库级配置会返回可审阅的配置草案；来自环境变量的配置不会回传完整 `config_draft`，只返回映射建议和质量信息，避免泄露密钥。HTTP JSON、SQLite 和 Object Manifest 在前端保存配置成功后会自动刷新一次 preview，便于立刻发现鉴权、查询、`items_path` 或字段映射问题。

文库级检索源配置包：

```http
GET /api/library/<library_id>/retrieval/config-bundle
GET /api/library/<library_id>/retrieval/config-bundle/download
POST /api/library/<library_id>/retrieval/config-bundle
POST /api/library/<library_id>/retrieval/config-bundle?dry_run=1
```

该配置包用于和仓库作者或队友交接 Local CSV/JSONL、HTTP JSON、SQLite、Object Manifest 的文库级配置。默认下载内容会把直接写在配置里的 token、Authorization、password、secret 等值替换为 `__REDACTED__`，但保留 `${ENV:...}` 或环境变量名引用。前端 `CFG` 按钮下载默认脱敏包；多源检索面板里的配置包导入区支持粘贴 JSON 后先 dry-run，再确认真实导入。dry-run 或真实导入后，结果卡片里的 `CSV` 按钮会下载 `retrieval-config-bundle-dry-run.csv` 或 `retrieval-config-bundle-import-result.csv`，保留每个源的 `would_apply` / `applied` / `skipped` 清单。导入时如果某个源仍包含 `__REDACTED__`、缺少必填项或带有不支持的 `field_map` target，该源会被写入 `skipped`，其他有效源仍会继续预演或导入。

正式导入前建议先用 `dry_run=1` 预演。dry-run 会按源解析配置包、执行脱敏占位符跳过、必填字段校验和 `field_map` target 校验，并返回 `applied` / `skipped` 清单；`applied` 里的 `action` 为 `would_apply`，不会写入任何文库级 preferences。确认源清单、环境变量名、本机路径和 skipped 原因无误后，先下载 dry-run CSV 留档，再去掉 `dry_run` 做真实导入。

## 模型服务可选增强

当前第一阶段不依赖模型 API；未配置 key 时，所有结构化检索、字段映射建议和导入闭环仍可运行。模型服务当前只作为 Field map lab 的可选增强，用于陌生列名/JSON 路径较难靠规则判断时辅助生成 `field_map`：

```powershell
$env:AI_PIXEL_BASE_URL='https://ai-pixel.online'
$env:AI_PIXEL_API_KEY='不要写入仓库，放本机环境变量或部署密钥'
```

模型 key 不写入代码、文档样例真实值、测试 fixture 或 git 提交。后端只把样例路径和值片段发给模型，并校验模型返回路径必须存在于请求样例中。配置好 `AI_PIXEL_API_KEY` 后，可以在 Field map lab 点 `Check` 或调用 `/retrieval/model-status?check=1` 做一次连通性检查；这个检查不会自动轮询，也不会回传密钥。结构化数据源检索跑稳以后，再决定是否把模型服务继续接到“检索前 query 改写”或“候选入库前字段清洗”。

## 上线前检查

1. 打开 `/retrieval/sources`，确认公共源可用、必配源有清晰缺口。
2. 没有真实比赛数据源时，先点 `DEMO RUN` 或调用 `/retrieval/rehearsal/validate?replace_existing=1`，确认演练源、READY、PLAN query 批量验证和 ONB ZIP 闭环可用。
3. 拿到真实源路径、URL、SQL、CSV 表头或 JSON 样例时，先在 `Source intake` 做源类型分型；本地 CSV/JSONL/NDJSON、SQLite 或 Object Manifest JSON 路径会先被采样；HTTP JSON URL 需要确认可请求后勾选 `Sample URL` 或传 `sample_url=true` 才会远程采样；采样结果里的 `validation_queries` 可以作为后续批量验证的起点，点击 `Use queries` 可填入批量检索框并默认只选中目标源；再用 `Use config` 回填到对应配置区或用 `Use in lab` 带到 `Field map lab` 继续调 `field_map`；若目标源仍显示不可用，先保存配置或刷新 source 状态，前端不会启动这类无效检索；手写 `field_map` target 时先对照 `/retrieval/field-map/targets`。
4. 对 Local CSV/JSONL，保存路径后打开 preview，点击 `Suggest` 自动采样生成 `field_map` 草案，确认后保存。
5. 能保存最小连接配置的内部源，先保存 HTTP JSON / SQLite / Object Manifest 配置；保存成功后前端会自动刷新 preview，再点击对应配置区的 `Suggest` 自动采样生成 `field_map` 草案。
6. 对需要的内部源保存配置后，点击 `READY` 或调用 `/retrieval/readiness` 做统一预检。
7. 对预检里出现 `warning`、`poor` 或 `error` 的内部源，再使用对应 `Preview` 按钮复查字段映射细节。
8. 使用 `?check=1` 做一次轻量健康检查，不要在高频场景自动轮询公共 API。
9. 用 `/retrieval/query-plan` 或前端 `PLAN` 从真实源样本生成 3 到 5 条小批量验证 query 草案，人工确认后可下载 `/retrieval/query-plan/report` 留档。
10. 用 3 到 5 个真实 query 做小批量检索，下载批量任务 `Report`，检查 `source_stats` 中的 `elapsed_ms`、`error_kind`、`rate_limit_wait_ms`；少于 3 条完成 query 时 ONB 会标为 `low_sample`。
11. 下载 `/retrieval/tuning/report` 或点击 `TUNE`，根据报告调整 `WEB_LIBRARY_RETRIEVAL_RATE_LIMIT_SECONDS` 或单源限流变量。
12. 复测同一组 query，确认 `rate_limited`、`timeout` 和平均耗时是否下降到可接受范围。
13. 点击 `ONB CHECK` 查看接入验收状态卡，可直接下载最新批量 `Batch report` 和 `Source CSV`，再点击 `ONB` 下载接入验收报告，确认 readiness、query-plan、tuning、批量验证和配置包状态都能解释清楚。
14. 点击 `CFG` 下载脱敏配置包，确认里面没有真实 API key；队友粘贴到配置包导入区后先 `Dry run`，确认 `would_apply` / `skipped` 清单并下载结果 CSV，再 `Import`。
15. 下载 readiness 预检报告、query-plan 报告、源配置报告、阶段统计报告、tuning 调优报告、接入验收报告、ONB ZIP 和脱敏配置包，作为阶段汇报附件。

## 当前边界

当前第一阶段不做全文 RAG，也不要求模型 API。HTTP JSON、SQLite 和 Object Manifest 都是结构化元数据接入：它们把外部记录标准化为 `ImportedItem`，再复用现有导入和去重流程。若后续要检索 PDF 片段、网页正文或实验材料内容，再补向量索引和 RAG 检索；若要做查询改写、候选重排或更深的字段清洗，再扩展模型服务接入点。
