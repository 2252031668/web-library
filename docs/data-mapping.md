# 数据库字段对应说明

本文档说明 Zotero 原生 SQLite、网页后端状态、前端展示字段之间的对应关系。它是后续开发的数据链路约束文件：先明确数据从哪里来、如何解析、如何写回，再讨论是否新增网页语义能力。

## 设计原则

- Zotero 原生 `zotero.sqlite` 是文献数据的唯一来源；网页中的语义字段都是读取后解析得到的派生视图。
- 不修改 Zotero 原生 SQLite 结构，不新增原生表、列或伪字段。
- `#标签`、评分、阅读状态、期刊等级都来自 Zotero 原生标签 `tags.name`，并通过 `itemTags` 关联到条目。
- 前端可以为了展示隐藏前缀，例如 `#多提示词` 显示为 `多提示词`，但写回 Zotero 时必须保存原始语义形式。
- 只读连接模式只读原始 Zotero 目录；本地副本模式只写应用复制出来的 `zotero.sqlite`，不直接修改用户真实 Zotero 源库。
- `app-data/app.sqlite` 只保存网页应用元数据，例如文库配置、列设置、快捷标签、语义规则、同步日志，不代表 Zotero 原生字段。

## Zotero 原生 SQLite 关键表

本项目第一版只记录当前程序实际读取或写入的 Zotero 关键表，不尝试覆盖 Zotero 所有版本的完整 schema。

| 表 | 关键字段 | 内容 | 当前用途 |
| --- | --- | --- | --- |
| `items` | `itemID`, `itemTypeID`, `dateAdded`, `dateModified`, `libraryID`, `key`, `version`, `synced` | Zotero 条目主表，附件和笔记也属于 item | 枚举文献条目、定位写回目标、标记本地副本未同步 |
| `itemTypes` | `itemTypeID`, `typeName` | 条目类型，例如 `journalArticle`, `attachment`, `note` | 过滤附件、笔记、标注等非主文献条目 |
| `fields` | `fieldID`, `fieldName` | Zotero 字段名表，例如 `title`, `date`, `publicationTitle`, `DOI`, `abstractNote`, `extra` | 把字段名映射到 `itemData` |
| `itemData` | `itemID`, `fieldID`, `valueID` | 条目和字段值的关联表 | 读取和写回原生字段 |
| `itemDataValues` | `valueID`, `value` | 字段值文本池 | 保存标题、日期、期刊、摘要、extra 等字段文本 |
| `tags` | `tagID`, `name` | Zotero 原生标签文本 | 所有普通标签和语义标签的真实来源；真实结构没有 `type` 列 |
| `itemTags` | `itemID`, `tagID`, `type` | 条目和标签的关联表 | 给条目添加或移除标签；`type` 属于关联记录，不属于 `tags` 表 |
| `collections` | `collectionID`, `collectionName`, `parentCollectionID`, `libraryID`, `key`, `version`, `synced` | Zotero 文件夹/分类目录 | 读取目录树，创建、重命名、移动本地副本中的文件夹 |
| `collectionItems` | `collectionID`, `itemID`, `orderIndex` | 条目和文件夹的关联表 | 读取和调整条目所在文件夹 |
| `creators` | `creatorID`, `firstName`, `lastName`, `fieldMode` | 作者、机构作者等创作者实体 | 读取作者名称 |
| `creatorTypes` | `creatorTypeID`, `creatorType` | 创作者类型，例如 `author` | 展示作者类型 |
| `itemCreators` | `itemID`, `creatorID`, `creatorTypeID`, `orderIndex` | 条目和创作者的关联表 | 按顺序读取作者列表 |
| `itemAttachments` | `itemID`, `parentItemID`, `linkMode`, `path`, `contentType`, `charsetID` | 附件元数据 | 解析 PDF、HTML、图片、链接、外部文件 |
| `itemNotes` | `itemID`, `parentItemID`, `note`, `title` | Zotero 笔记内容 | 读取条目下的笔记摘要 |
| `deletedItems` | `itemID` | 已删除条目标记 | 标记回收站条目 |

## 后端状态模型

后端从 Zotero SQLite 读出原生数据，再组装为前端状态：

| 状态字段 | 来源 | 读取规则 |
| --- | --- | --- |
| `items[*].item_id` | `items.itemID` | 后端内部定位用，不作为用户可编辑字段 |
| `items[*].key` | `items.key` | Zotero 条目稳定 key，前端 API 使用它定位条目 |
| `items[*].type` | `itemTypes.typeName` | 主条目类型；附件、笔记、annotation 不进入主表格 |
| `items[*].title` | `fields.fieldName = 'title'` 对应值 | 没有标题时显示 `未命名文献` |
| `items[*].fields` | `itemData -> fields -> itemDataValues` | 保留 Zotero 原生字段名和值 |
| `items[*].creators` | `itemCreators -> creators -> creatorTypes` | 按 `orderIndex` 读取作者或机构作者 |
| `items[*].year` | `fields.date` | 取日期文本前 4 位 |
| `items[*].venue` | `publicationTitle`, `proceedingsTitle`, `conferenceName`, `repository` | 按此优先级取第一个非空值 |
| `items[*].tags` | `itemTags -> tags.name` | 保留 Zotero 原始标签文本列表 |
| `items[*].semantic` | `parse_tags(items[*].tags)` | 从原始标签派生语义桶 |
| `items[*].collections` | `collectionItems -> collections` | 条目所在文件夹列表 |
| `items[*].attachments` | `itemAttachments` 加 `items.key` 和附件标题 | 解析附件路径、类型和是否可打开 |
| `items[*].notes` | `itemNotes` | 读取条目下 Zotero 笔记 |
| `items[*].deleted` | `deletedItems` | 判断是否在回收站 |
| `tag_shortcuts` | `app-data/app.sqlite.tag_shortcuts` | 文库级快捷标签清单，只是 UI 辅助，不是 Zotero 标签字段 |
| `semantic_counts` | 所有 `items[*].semantic` | 前端筛选区计数 |

## 字段映射总表

| 网页字段 | 前端显示 | Zotero 来源 | 写回规则 |
| --- | --- | --- | --- |
| 标题 | `item.title` | `fields.title` 对应 `itemDataValues.value` | 只允许写 Zotero 已存在字段名，通过 `itemData/itemDataValues` 更新值；禁止新增 `fields.fieldName` |
| 作者 | `creators_display`, `creators_full_display` | `creators`, `itemCreators`, `creatorTypes` | 当前不写回 |
| 年份 | `item.year` | `fields.date` | 当前由 `date` 派生；若编辑日期，写回 `date` 原生字段 |
| 来源 | `item.venue` | `publicationTitle` 等字段优先级派生 | 当前可通过原生字段编辑入口写 `publicationTitle` 等字段 |
| 摘要 | `item.fields.abstractNote` | `fields.abstractNote` | 当前可写回 `abstractNote` 原生字段；禁止新增字段名 |
| Extra | `item.fields.extra` | `fields.extra` | 当前可写回 `extra` 原生字段；派生规则见下文；禁止新增字段名 |
| 原始标签 | `item.tags` | `tags.name` + `itemTags` | 添加标签时先确保 `tags.name` 存在，再写入 `itemTags` 关联 |
| `#标签` | `item.semantic.nested`，显示时去掉 `#` | `tags.name` 中以 `#` 开头且未被特殊语义规则截获的标签 | 写回时必须使用带 `#` 的 `tags.name` |
| 评分 | `item.semantic.rating` | 星级标签或 `#Rating/N` 标签 | 设置评分时移除当前条目旧评分标签，再添加新的评分标签 |
| 阅读 | `item.semantic.reading_status` | `/done`, `/reading`, `read`, `unread` 等标签 | 设置阅读状态时移除当前条目旧阅读状态标签，再添加目标标签；未读可表示为无阅读标签 |
| 期刊等级 | `item.semantic.venue_rank` | `CCF-A`, `JCR Q1`, `中科院1区`, `SCI` 等标签 | 当前只解析展示，不单独写回 |
| 普通标签 | `item.semantic.plain` | 未被语义规则分类的 `tags.name` | 当前不提供专门写回入口 |
| 文件夹 | `item.collections` | `collections` + `collectionItems` | 通过插入或删除 `collectionItems` 调整归属 |
| 附件 | `item.attachments` | `itemAttachments` 加 `storage/` 文件 | 当前只读和打开，不写回 |
| 笔记 | `item.notes` | `itemNotes.note` | 当前只读 |

## 标签语义规则

标签解析只读取 Zotero 原生 `tags.name`。分类顺序会影响结果：一个标签命中特殊语义后，不再进入普通 `#标签` 或普通标签。

| 语义桶 | 当前规则 | 示例 | 展示/写回约束 |
| --- | --- | --- | --- |
| `rating` | 星级标签，或 `#Rating/1` 到 `#Rating/5` | `★★★★★`, `#Rating/3` | 前端评分控件写回星级标签；评分不是独立数据库字段 |
| `venue_rank` | `CCF-A/B/C`, `JCR Q1-Q4`, `中科院一二三四区`, `SCI`, `EI`, `北核`, `CSCD`，可带 `#Venue/` 前缀 | `CCF-A`, `JCR Q1`, `#Venue/SCI` | 当前只解析展示 |
| `reading_status` | `/done`, `/reading`, `done`, `read`, `unread`, `reading`, `未读`, `已读`, `待读` | `/done`, `/reading` | 前端统一展示为未读、在读、已读 |
| `nested` | 以 `#` 开头，且未被评分或期刊等级等规则截获 | `#多提示词`, `#VLA/端到端` | 前端显示时用 `displayHashTag()` 去掉 `#`；写回时用 `normalizeHashTag()` 补回 `#` |
| `plain` | 未被以上规则分类的标签 | `Computer Vision`, `普通标签` | 作为普通 Zotero 标签展示 |

## 快捷标签规则

快捷标签是网页应用自己的文库级 UI 辅助清单，不是 Zotero 原生字段。

- 存储位置是 `app-data/app.sqlite` 的 `tag_shortcuts` 表。
- 建库或首次加载时可用全库已有 `semantic.nested` 初始化一次。
- 新增快捷标签只加入快捷标签清单，不自动写入任何条目。
- 点击快捷标签给当前条目添加标签时，真实写入 Zotero 的仍然是 `tags.name = '#xxx'` 和 `itemTags` 关联。
- 删除快捷标签只删除 `tag_shortcuts` 记录，不删除 Zotero `tags.name`，也不删除任何条目的 `itemTags` 关联。

## Extra 与中文增强字段规则

本节是第一版已确定协议，用来约束后续开发方向；它不表示当前代码已经全部实现，但后续实现应以这里的协议为准。

| 网页增强字段 | Zotero 来源 | 第一版解析规则 | 写回约束 |
| --- | --- | --- | --- |
| 用户备注 | `fields.extra` | 只识别 `[remark]... [remarkend]` 成对块 | 写回时只更新对应块内容，不新增 Zotero 字段，不重写其他原文 |
| 中文标题 | `fields.extra` | 只识别 `[title_zh]... [title_zhend]` 成对块 | 写回时只更新对应块内容，不新增 Zotero 字段，不重写其他原文 |
| 中文摘要 | `fields.abstractNote` | 只识别 `[abstract_zh]... [abstract_zhend]` 成对块 | 写回时只更新对应块内容，不新增 Zotero 字段，不重写其他原文 |
| TLDR | `fields.extra` | 待讨论，可参考 `TLDR:` 标记 | 未定 |
| 项目链接/代码链接 | `fields.extra` 或 `fields.url` | 待讨论，可从 URL、备注正文或专门标记中提取 | 未定 |
| arXiv ID | `fields.extra`, `DOI`, `url` 或原始字段 | 待讨论，可能出现在备注正文中 | 未定 |

示例：

```text
[remark]李飞飞团队 rekep-robot.github.io arXiv:2409.01652 [cs] TLDR: This work introduces Relational Keypoint Constraints (ReKep), a visually-grounded representation for constraints in robotic manipulation that can employ a hierarchical optimization procedure to solve for robot actions with a perception-action loop at a real-time frequency.[remarkend]
[title_zh]ReKep：机器人操作中关系关键点约束的时空推理[title_zhend]
```

第一版解释：

- `[remark]... [remarkend]` 内部文本是用户备注。
- `[title_zh]... [title_zhend]` 内部文本是中文标题。
- `[abstract_zh]... [abstract_zhend]` 内部文本是中文摘要。
- 备注内部的 `TLDR:`、项目链接、arXiv ID 暂不强拆为稳定字段，后续讨论后再定。

协议细则：

- 标记必须成对出现，只有开始标记或只有结束标记时，不参与结构化提取。
- 每种块默认只识别第一个有效块；重复块先视为异常原文，后续是否合并另行讨论。
- 块内容允许多行；提取时保留内部换行。
- 提取后的结构化值默认去掉首尾空白，但不改正文中的中间内容。

解析失败处理：

- 如果字段中没有合法成对标记，则该增强字段解析结果为空，不猜测、不回退到旧的 `remark:` / `titleTranslation:` 前缀规则。
- 如果标记嵌套、交叉或重复异常，当前阶段视为未成功结构化，保留原文，等待人工修正。
- 解析失败不会覆盖原始 `extra` 或 `abstractNote` 文本，也不会自动清洗原文。

写回原文保留策略：

- 写回备注、中文标题、中文摘要时，只替换对应的成对块内容。
- 未识别的其他文本、其他块、普通备注内容、换行和顺序应尽量原样保留。
- 如果目标块不存在，后续实现时应以“追加标准块”的方式写入，而不是重写整个 `extra` 或 `abstractNote`。
- 不允许为了这些增强字段新增 Zotero 原生字段名，也不允许新增 `fields.fieldName` 记录。

## CRUD 规则

| 操作 | 规则 |
| --- | --- |
| 读取文库 | 通过 `items` 枚举主条目，联表读取字段、标签、作者、文件夹、附件、笔记 |
| 添加标签 | 对用户输入先执行标签规范化；`#标签` 真实保存为带 `#` 的 `tags.name`；再写 `itemTags` |
| 删除条目标签 | 删除当前条目对应的 `itemTags` 关联，不删除 `tags.name` 全局记录 |
| 设置评分 | 删除当前条目已解析为评分的标签，再添加目标评分标签 |
| 设置阅读状态 | 删除当前条目已解析为阅读状态的标签，再添加目标阅读标签；未读可以不写标签 |
| 编辑原生字段 | 只允许写 Zotero 已存在字段名；通过 `itemData/itemDataValues` 保存值；如果 `fields.fieldName` 不存在则报错，不允许新增 |
| 调整文件夹 | 添加或删除 `collectionItems` 关联，不改变条目本身字段 |
| 删除快捷标签 | 只删除 `app-data/app.sqlite.tag_shortcuts`，不影响 Zotero 原生标签 |
| 只读连接模式 | 禁止写 Zotero 源目录 |
| 本地副本模式 | 只写复制到 `app-data/libraries/<library-id>/` 下的副本 |

## 禁止事项

- 不得把 `#标签` 设计成 Zotero 新字段。
- 不得给 Zotero 原生 `tags` 表添加 `type` 列；真实标签文本只依赖 `tags.name`。
- 不得为了评分、阅读、期刊等级新增 Zotero 表或列。
- 不得直接写用户真实 Zotero 源库。
- 不得让快捷标签删除操作影响条目已有标签。
- 不得把 zotero-style 的实现规则不加讨论地照搬进本项目。

## zotero-style 参考边界

zotero-style 6.0.8 可以作为交互和语义设计参考，尤其是：

- `#Tags`：匹配以 `#` 开头的 Zotero 标签，展示时隐藏 `#`。
- Nested Tags：把带层级含义的标签用于更清晰的组织。
- Publication Tags：将期刊/会议等级作为可展示标签。

本项目不直接依赖 zotero-style，也不照搬其完整数据集、偏好存储或 Zotero 插件内部 API。所有规则必须先落到本文档，再进入代码实现。

## 待讨论字段

后续可以继续讨论是否从 Zotero 原生字段中派生以下网页增强字段：

- 中文标题。
- 中文摘要。
- 用户备注。
- TLDR。
- 项目主页。
- 代码链接。
- arXiv ID。
- DOI 规范化。
- 期刊等级归一化。
- 阅读进度。
- 附件质量或缺失状态。
