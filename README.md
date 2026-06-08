# Web Library

这是一个面向 Zotero 本地文库的网页端浏览与编辑工具。

项目与 Guangming AI Workbench 分离维护，重点是把本地 Zotero 文库以三栏高密度界面呈现出来，并在不破坏原始数据结构的前提下，提供标签语义解析、结构化字段提取、本地副本编辑等能力。

## 当前功能

- 三栏 Zotero 风格界面：左侧文件夹树与筛选，中间条目表，右侧条目详情。
- 支持文件夹树浏览，以及评分、类型、`#标签`、期刊/会议等级、阅读状态、普通标签筛选。
- 表格字段列可配置，可调整列顺序、列宽，并保留用户设置。
- 支持条目多选；切换筛选条件或文件夹后，已勾选状态仍会保留。
- 标题列支持中文条目类型徽标，类型 key 以 Zotero 官方类型定义为准。
- 支持条目前端语义标签解析：
  - `#标签`
  - 阅读状态
  - 评分
  - 期刊/会议等级
- 支持文库级共享快捷标签，用于快速给条目设置 `#标签`。
- 支持结构化字段提取与写回：
  - `remark`
  - `title_zh`
  - `abstract_zh`
- 支持在表格单元格内直接编辑结构化字段，也支持在详情区统一编辑。
- 支持 PDF、HTML、笔记、图片、链接等附件徽标展示。
- 详情区笔记支持摘要折叠与展开。
- 支持只读连接真实 Zotero 数据目录。
- 支持建立可编辑的本地副本，所有写操作只落到副本。

## 最近界面能力

- 前端已按 Zotero 官方类型 key 做归一化，并提供中文类型徽标和独立类型筛选。
- 快捷标签改为文库级共享清单；删除快捷标签只影响快捷表，不影响已有条目标签。
- `remark`、`title_zh`、`abstract_zh` 已接入结构化解析与结构化写回。
- 已加入多选复选框和批量操作工具栏占位，便于后续扩展批量功能。

## 数据源模式

### 只读连接

直接读取指定的 Zotero 数据目录，例如：

```text
C:\Users\<你自己的用户名>\Zotero
```

这种模式不会写入原始 `zotero.sqlite`、`storage/` 或 Zotero 目录中的任何文件。

### 本地副本

程序会把 `zotero.sqlite` 和 `storage/` 复制到应用自己的数据目录里，后续编辑都只作用在这个副本上。

项目明确不支持直接写用户真实 Zotero 源库。Zotero 的本地 SQLite 可以读取，但直接修改原始库风险太高。

## 数据规则

- Zotero 原生 `zotero.sqlite` 是文献信息的唯一真实来源。
- `#标签`、评分、阅读状态、期刊/会议等级都来自 Zotero 原生 `tags.name`。
- 不新增 Zotero 原生表或字段，不修改 Zotero 原生 schema。
- 应用自己的元数据，例如快捷标签、列设置、界面偏好等，存放在 `app-data/app.sqlite`。

更详细的字段来源、解析规则和写回约束见：
[docs/data-mapping.md](/C:/Users/27216/Desktop/project/web-library/docs/data-mapping.md)

## 环境要求

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

仓库中的 `.python-version` 已固定为 `3.12`。

## 启动方式

```powershell
uv sync
uv run python -m zotero_web_library.web
```

启动后访问：

```text
http://127.0.0.1:5088
```

## 测试

```powershell
uv run pytest
```

## 应用数据目录

默认情况下，应用会把元数据和本地副本保存在：

```text
./app-data/
  app.sqlite
  libraries/
    <library-id>/
      zotero.sqlite
      storage/
      source.json
```

`app-data/` 已加入 Git 忽略，因为其中可能包含私人 Zotero 数据和复制出的附件文件。

## 使用注意

- 不要提交 `app-data/`。
- 不要提交复制出来的 Zotero 数据库或附件文件。
- 浏览真实 Zotero 文库时，优先使用只读连接模式。
- 需要实验性编辑时，使用本地副本模式，不要直接碰源库。
