# 需求文档：会话管理、标签维度、结论分析系统

**版本**: 0.5.0  
**日期**: 2026-05-24  
**前置依赖**: req01.md (v0.4.0) 已实现  

---

## 1. 需求背景与目标

### 1.1 核心问题

当前项目（v0.4.0）已具备项目管理、迭代规划、条目追踪、记忆存储能力，但缺少对**工作会话**的显式建模——即一次 AI 持续工作周期内的上下文跟踪、分析复盘、以及按**维度标签**检索积累的知识。

### 1.2 目标

1. **会话建模**: 一个迭代包含多个工作会话（Session），每个会话内 AI 处理若干条目/任务
2. **会话完成分析**: 当会话结束时，系统/项目应自动或辅助生成**分析结论**，按不同维度（标签）归类存储
3. **维度标签**: 定义一套维度标签体系（7 个预设 + AI 可扩展至 ≤30），AI 在任何会话中都可读取这些标签，按需检索对应维度的历史结论
4. **知识复用**: 下一会话开始时，AI 可通过标签搜索此前积累的结论/记忆，形成持续的知识传递

---

## 2. 新增概念与数据模型

### 2.1 概念关系图

```
Project (1) ──< Iteration (N) ──< Session (N) ──< Conclusion (N) ── Tag (N)
   │                │                │
   │                │                └── Items（通过 activity_log 关联）
   │                │
   │                └── Items ── Tag（M:N，通过 memory_tags）
   │
   └── Tags ──< memory_entries（M:N）
```

### 2.2 新增表定义

#### 2.2.1 `sessions` — 工作会话

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    iteration_id TEXT REFERENCES iterations(id),
    title TEXT NOT NULL,
    summary TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_iteration_id ON sessions(iteration_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PK | UUID，会话唯一标识 |
| `project_id` | TEXT FK | 所属项目 |
| `iteration_id` | TEXT FK | 所属迭代（可选） |
| `title` | TEXT NOT NULL | 会话标题 |
| `summary` | TEXT | 会话摘要，结束时由 AI 填写 |
| `status` | TEXT | `active` / `completed` |
| `started_at` | TEXT | 会话开始时间 ISO |
| `completed_at` | TEXT | 会话完成时间 ISO |

**规则**:
- 同一项目同时只能有一个 `active` 会话
- 完成时自动设置 `completed_at = now_iso()`，`status = 'completed'`
- 删除会话时级联删除其 conclusions

#### 2.2.2 `tags` — 维度标签

```sql
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    description TEXT,
    is_preset INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, name)
);
CREATE INDEX IF NOT EXISTS idx_tags_project_id ON tags(project_id);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `project_id` | TEXT FK | 所属项目 |
| `name` | TEXT NOT NULL | 标签名（英文 slug） |
| `description` | TEXT | 标签含义描述 |
| `is_preset` | INTEGER | 1=预设标签，0=AI/用户自定义 |

**约束**:
- `(project_id, name)` 唯一
- 单个项目标签总数 ≤ 30
- 当项目创建时，自动初始化 7 个预设标签

#### 2.2.3 七预设标签

| # | name | 中文名 | description |
|---|------|--------|-------------|
| 1 | `architecture` | 架构与设计 | 系统架构决策、模块划分、设计模式选择 |
| 2 | `implementation` | 实现细节 | 具体代码实现方式、算法选择、编码技巧 |
| 3 | `risk` | 风险与问题 | 已识别风险、遇到的问题、技术债务 |
| 4 | `decision` | 关键决策 | 重要的技术/业务决策及其理由 |
| 5 | `pattern` | 模式与经验 | 可复用的解决方案、最佳实践、踩坑经验 |
| 6 | `integration` | 依赖与集成 | 外部依赖、API 对接、第三方服务集成 |
| 7 | `quality` | 质量与优化 | 代码质量、性能优化、安全加固 |

#### 2.2.4 `conclusions` — 会话分析结论

```sql
CREATE TABLE IF NOT EXISTS conclusions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id),
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    content TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('high', 'medium', 'low')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conclusions_project_id ON conclusions(project_id);
CREATE INDEX IF NOT EXISTS idx_conclusions_session_id ON conclusions(session_id);
CREATE INDEX IF NOT EXISTS idx_conclusions_tag_id ON conclusions(tag_id);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `project_id` | TEXT FK | 所属项目 |
| `session_id` | TEXT FK | 关联会话（CASCADE 删除） |
| `tag_id` | INTEGER FK | 关联标签 |
| `content` | TEXT | 结论内容 |
| `confidence` | TEXT | 可信度：`high` / `medium` / `low` |

**规则**:
- 一个会话可以有多个结论（每个标签最多一条）
- 相同 `(session_id, tag_id)` 不重复

#### 2.2.5 `memory_tags` — 记忆-标签关联

```sql
CREATE TABLE IF NOT EXISTS memory_tags (
    memory_id INTEGER NOT NULL REFERENCES memory_entries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (memory_id, tag_id)
);
```

新增记忆时可选关联标签，使记忆可按维度搜索。

#### 2.2.6 `merge_log` — 合并操作记录

```sql
CREATE TABLE IF NOT EXISTS merge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL REFERENCES projects(id),
    entity_type TEXT NOT NULL CHECK(entity_type IN ('memory', 'conclusion')),
    kept_id INTEGER NOT NULL,
    removed_id INTEGER NOT NULL,
    kept_content TEXT NOT NULL,
    removed_content TEXT NOT NULL,
    similarity REAL NOT NULL,
    merged_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_merge_log_project_id ON merge_log(project_id);
CREATE INDEX IF NOT EXISTS idx_merge_log_entity_type ON merge_log(entity_type);
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PK | 自增 ID |
| `project_id` | TEXT FK | 所属项目 |
| `entity_type` | TEXT | `memory` 或 `conclusion` |
| `kept_id` | INTEGER | 保留的实体 ID |
| `removed_id` | INTEGER | 被移除/合并的实体 ID |
| `kept_content` | TEXT | 保留实体的内容快照 |
| `removed_content` | TEXT | 被合并实体的内容快照 |
| `similarity` | REAL | 相似度分数 (0.0-1.0) |
| `merged_at` | TEXT | 合并时间 ISO |

用途：
- 审计追踪：记录哪些实体因相似被合并
- 可回查：保留了被移除的内容快照
- 防止重复合并：同一对 (kept_id, removed_id) 不会再次合并

### 2.3 Migration

新增 Schema Version = 2，在 `database.py` 的 `MIGRATIONS` 字典中追加。

---

## 3. MCP 工具定义

### 3.1 会话管理（4 tools）

#### `start_session`
开始一个新的工作会话。

```
参数:
  project_id:   string, 可选（回退活跃项目）
  iteration_id: string, 可选（关联迭代）
  title:        string, 必填
  
返回:
  success: true
  data: { id, project_id, iteration_id, title, status: "active", started_at, ... }
  
规则:
  - 校验项目存在
  - 若 iteration_id 非空，校验迭代存在且属于该项目
  - 同一项目同时只能有一个 active 会话，如有则返回 ACTIVE_SESSION_EXISTS 错误
  - 使用 session_id="default" 统一管理
```

#### `complete_session`
结束一个工作会话。

```
参数:
  session_id: string, 必填
  summary:    string, 必填（AI 填写的会话总结）
  
返回:
  success: true
  data: { id, status: "completed", completed_at, summary }
  
规则:
  - 校验会话存在且 status = active
  - 设置 status = 'completed', completed_at = now_iso(), summary = summary
  - 记录 activity_log(action='complete_session')
```

#### `get_session`
获取单个会话详情。

```
参数:
  session_id: string, 必填
  
返回:
  success: true
  data: { id, project_id, ... , conclusion_count, tag_list }
```

#### `list_sessions`
列出会话列表。

```
参数:
  project_id:   string, 可选
  iteration_id: string, 可选
  status:       string, 可选（active/completed）
  limit:        int,    默认 20
  offset:       int,    默认 0
  
返回:
  success: true
  data: [ { id, title, status, ... } ]
```

### 3.2 标签管理（3 tools）

#### `list_tags`
列出项目的所有标签。

```
参数:
  project_id: string, 可选
  
返回:
  success: true
  data: [ { id, name, description, is_preset } ... ]
  
规则:
  - 返回预设标签在前，自定义标签在后
  - 按 name 字母序排列
```

#### `add_tag`
添加自定义维度标签。

```
参数:
  project_id:  string, 可选
  name:        string, 必填（英文 slug，小写连字符）
  description: string, 可选
  
返回:
  success: true
  data: { id, name, description, is_preset: 0 }
  
规则:
  - 校验 name 不为空，格式为小写字母+连字符
  - 标签总数 ≤ 30，超出返回 TAG_LIMIT_EXCEEDED
  - 标签名不可与已有标签重复
  - 自定义标签 is_preset = 0
```

#### `get_preset_tags`
获取 7 个预设标签（硬编码，无需查库也可返回）。

```
参数: 无

返回:
  success: true
  data: [ { name, description } ... ]  # 7 个预设标签
```

### 3.3 结论管理（4 tools）

#### `add_conclusion`
手动添加一条分析结论。

```
参数:
  project_id: string, 可选
  session_id: string, 必填
  tag_name:   string, 必填（标签名）
  content:    string, 必填
  confidence: string, 可选（high/medium/low，默认 medium）

返回:
  success: true
  data: { id, tag_id, content, ... }
  
规则:
  - 校验 session 存在且属于同一项目
  - 校验 tag_name 存在于该项目的 tags 中
  - 相同 (session_id, tag_name) 的结论如已存在则更新 content（upsert）
```

#### `search_conclusions`
按标签维度搜索结论。

```
参数:
  project_id: string, 可选
  tag_names:  string[], 可选（多标签 OR 搜索）
  session_id: string,   可选（限定会话）
  confidence: string,   可选（high/medium/low）
  query:      string,   可选（全文关键词）
  limit:      int,      默认 20
  offset:     int,      默认 0

返回:
  success: true
  data: [ { id, tag_name, tag_description, content, confidence, session_title, ... } ]
  
规则:
  - tag_names 为空时返回所有标签的结论
  - query 不为空时对 content 做 LIKE 匹配
```

#### `get_session_conclusions`
获取某个会话的所有结论（按标签分组）。

```
参数:
  session_id: string, 必填

返回:
  success: true
  data: [ { tag_name, conclusions: [{ id, content, confidence }] } ... ]
  
规则:
  - 按标签分组返回
  - 包含该会话中缺失维度的标签提示（哪些预设标签没有结论）
```

#### `get_conclusion`
获取单个结论详情。

```
参数:
  conclusion_id: int, 必填

返回:
  success: true
  data: { id, project_id, session_id, tag_name, content, ... }
```

### 3.4 分析工具（1 tool）

#### `analyze_session`
对已完成的会话进行分析，生成按维度标签归类的结论。
**这是 AI 使用的核心工具**。

```
参数:
  session_id:      string, 必填
  session_summary: string, 必填（AI 总结的会话内容）
  conclusions:     array,  可选
    [ { tag_name: string, content: string, confidence: string } ... ]
  
返回:
  success: true
  data: { session_id, conclusions_added: int, missing_tags: [string] }
  
AI 工作流:
  1. 调用 complete_session 结束会话
  2. AI 反思会话内容，按各维度标签产出结论
  3. 调用 analyze_session 传入结论数组
  4. 系统批量存储到 conclusions 表
  5. 系统检测哪些预设标签缺少结论，返回 missing_tags 提示 AI 补充
  
规则:
  - 校验 session 状态为 completed
  - 批量 upsert conclusions（同 tag_name 去重）
  - 对传入的每个 tag_name 做校验（必须存在于项目 tags 中）
  - 返回 missing_tags：预设标签中未被分析的维度列表
```

### 3.5 增强现有工具

#### `add_memory_entry` (增强)
在原参数基础上增加：

```
新增参数:
  tag_names:     string[], 可选（关联标签名列表）
  merge_similar: bool,     默认 true（自动检测并合并相似记忆）

规则:
  - 校验每个 tag_name 存在于项目 tags 中
  - 写入 memory_tags 关联表
  - 若 merge_similar=true，写入前检测相似记忆（同 project + type）：
    1. 对所有同类记忆计算关键词 Jaccard 相似度
    2. 相似度 ≥ SIMILARITY_THRESHOLD (0.6) → 合并：
       - 保留内容较长/较完整的记忆
       - 将新内容追加到保留的记忆中（分隔符 "\n\n---\n\n"）
       - 删除被合并的记忆
       - 记录到 merge_log
       - 返回 { ..., merged_from: old_id }
    3. 无相似记忆 → 正常新增
  - merge_similar=false 时跳过检测，强制新增
```

#### `search_memory` (增强)

#### `add_conclusion` (增强)
手动添加分析结论时也支持相似合并。

```
新增参数:
  merge_similar: bool, 默认 true

规则（merge_similar=true 时）:
  - 写入前检测同 (project_id, tag_id) 下相似结论
  - 相似结论合并策略：
    1. 保留最新的结论
    2. 若新内容包含旧结论未涵盖的信息，追加到保留结论
    3. confidence 取两者中的较高值
    4. 记录 merge_log
  - 跨会话合并：高相似度的结论在不同会话间也会触发合并
```

#### `analyze_session` (增强)
批量写入结论时，每条结论也遵循 merge_similar 逻辑。
在原参数基础上增加：

```
新增参数:
  tag_names: string[], 可选

规则:
  - tag_names 不为空时，只返回关联了指定标签的记忆
  - 通过 JOIN memory_tags 实现
```

### 3.6 去重与合并工具（2 tools）

#### `find_similar_items`
检测项目中相似/重复的记忆或结论，返回建议合并的配对列表。
**AI 应当在每个会话结束时调用此工具清理重复数据**。

```
参数:
  project_id:  string, 可选
  entity_type: string, 可选（"memory" / "conclusion"，不传则查两者）
  tag_name:    string, 可选（限定标签维度，仅 conclusions）
  threshold:   float,  默认 0.6（相似度阈值）
  limit:       int,    默认 20

返回:
  success: true
  data: [
    {
      type: "memory" | "conclusion",
      item_a: { id, content_snippet, created_at },
      item_b: { id, content_snippet, created_at },
      similarity: 0.78,
      suggestion: "keep_b"  # 建议保留哪个
    }, ...
  ]

相似度计算:
  - 分词：提取 ≥3 字符的单词/中文词组，去停用词
  - Jaccard = |A_words ∩ B_words| / |A_words ∪ B_words|
  - 仅比较同 project + 同 type/memory_type + 同 tag（conclusions）
```

#### `merge_items`
手动将两个相似实体合并为一个。

```
参数:
  entity_type: string, 必填（"memory" / "conclusion"）
  keep_id:     int,    必填（保留的实体 ID）
  remove_id:   int,    必填（被合并的实体 ID）
  keep_content: string,  可选（合并后的最终内容，不传则自动拼接）

返回:
  success: true
  data: { kept: { id, content }, removed: { id }, merged_at }

规则:
  - 校验两个实体存在于同一 project
  - 同类型实体间才可合并
  - 合并操作记录到 merge_log
  - 删除 remove_id 指向的实体
  - 若 keep_id 是结论且 remove_id 也是结论，两者的 session 关联需手动处理
  - 不可合并同一实体
```

---

## 4. 业务规则

### 4.1 会话规则

| 规则 | 说明 |
|------|------|
| 单活跃会话 | 同一项目同时只能有一个 `active` 会话 |
| 完成不可逆 | 会话一旦 `completed`，不可重新激活 |
| 摘要必填 | 完成会话时 `summary` 不能为空 |
| 关联迭代 | 会话可关联迭代，但非强制 |

### 4.2 标签规则

| 规则 | 说明 |
|------|------|
| 7 预设 | 项目创建时自动初始化 7 个预设标签 |
| 上限 30 | 单个项目标签总数（预设+自定义）≤ 30 |
| 不可删除预设 | 预设标签不可删除 |
| 命名规范 | 标签名：小写字母 + 连字符（slug 格式） |
| 项目隔离 | 标签是项目级别的，不同项目的标签独立 |

### 4.3 结论规则

| 规则 | 说明 |
|------|------|
| 会话-标签唯一 | 同一会话下，对同一标签只能有一条结论（upsert） |
| CASCADE 删除 | 删除会话时级联删除其所有结论 |
| 可信度 | 结论附可信度：high（已验证）、medium（推断）、low（猜测） |

### 4.4 去重与合并规则

| 规则 | 说明 |
|------|------|
| 相似度阈值 | Jaccard 相似度 ≥ 0.6 即视为可合并 |
| 同类型约束 | 仅同类型实体间合并（memory↔memory, conclusion↔conclusion） |
| 同标签约束 | conclusions 仅在同 tag 维度下比较相似度 |
| 保留策略 | 优先保留内容更完整（更长）或更新时间更新的实体 |
| 内容拼接 | 合并后以 "\n\n---\n\n" 分隔新旧内容，保留完整信息 |
| 审计记录 | 每次合并写入 merge_log，记录 kept/removed 的快照 |
| 不可逆 | 合并操作不可自动撤销（可通过 merge_log 手动恢复） |
| 自动/手动 | 写入时自动合并（merge_similar=true）+ 手动批量合并（merge_items） |

**相似度计算示例**:

```
记忆 A: "采用 JWT token 进行用户认证"
记忆 B: "用户认证使用 JWT token 方案实现"

A_words: {"采用", "JWT", "token", "进行", "用户", "认证"}
B_words: {"用户", "认证", "使用", "JWT", "token", "方案", "实现"}

交集: {"JWT", "token", "用户", "认证"} = 4
并集: {"采用", "JWT", "token", "进行", "用户", "认证", "使用", "方案", "实现"} = 9

Jaccard = 4/9 ≈ 0.44 → < 0.6 → 不合并（虽然是同一主题，但表述差异大）

---

记忆 A: "Redis 缓存层使用连接池，最大连接数 100"
记忆 B: "Redis 连接池最大 100 连接"

A_words: {"Redis", "缓存层", "使用", "连接池", "最大", "连接数", "100"}
B_words: {"Redis", "连接池", "最大", "100", "连接"}

交集: {"Redis", "连接池", "最大", "100"} = 4
并集: {"Redis", "缓存层", "使用", "连接池", "最大", "连接数", "100", "连接"} = 8

Jaccard = 4/8 = 0.5 → < 0.6 → 不合并

---

记忆 A: "CSS 模块使用 CSS Modules 方案，避免全局样式污染"
记忆 B: "采用 CSS Modules 避免样式全局污染问题"

A_words: {"CSS", "模块", "使用", "Modules", "方案", "避免", "全局", "样式污染"}
B_words: {"采用", "CSS", "Modules", "避免", "样式", "全局污染", "问题"}

交集: {"CSS", "Modules", "避免"} = 3
并集: {"CSS", "模块", "使用", "Modules", "方案", "避免", "全局", "样式污染", 
        "采用", "样式", "全局污染", "问题"} = 12

→ 中文 + 英文混合场景下分词颗粒度不够
→ 建议 AI 写入时保持术语一致性，如 "CSS Modules" 统一为一个词
```

#### 核心设计原则

合并的目标是**减少碎片化**，而非**丢失信息**：

1. **宁可少合，不可误合**：阈值设在 0.6 偏保守，避免将不同含义的内容合并
2. **保留全部信息**：合并后新旧内容用分隔符保留，不丢失任何原始信息
3. **AI 最终决策**：`find_similar_items` 只提供建议，由 AI 决定是否执行 `merge_items`
4. **可审计**：merge_log 保留完整快照，任何合并都可追溯到原始内容

### 4.5 AI 开发行为约束 (AI Guardrails)

以下规则在 AI 使用 Itera MCP 进行开发工作时**必须遵守**。违反规则的调用应被工具层拒绝。

#### 4.5.1 会话边界约束

| 规则 | 说明 | 违规处理 |
|------|------|----------|
| 单会话活跃 | 同一项目同时只能有一个 `active` 会话，创建新会话前必须 `complete_session` | 返回 `ACTIVE_SESSION_EXISTS` |
| 会话必分析 | 完成会话时必须提供 `summary`，且 `summary` 不可为空或仅占位符 | 返回 `MISSING_SUMMARY` |
| 会话内闭环 | 会话内创建/修改的条目、记忆，应在该会话分析中体现 | 系统通过 `missing_tags` 提示 |
| 禁止跨会话修改 | 不允许修改其他已完成会话的 `summary` 或状态 | 返回 `SESSION_IMMUTABLE` |

#### 4.5.2 知识操作约束

| 规则 | 说明 | 违规处理 |
|------|------|----------|
| 结论不可删除 | 已存储的 conclusion 不可被 AI 删除（仅 `merge_items` 可移除已合并的重复项） | 不提供 `delete_conclusion` 工具 |
| 记忆不可删除 | `memory_entries` 不可直接删除（`update_memory_entry(content="")` 可标记删除，但需给出理由） | 返回 `DELETE_FORBIDDEN` |
| 只读历史 | 搜索/读取其他会话的结论只能作为参考，不可改写或覆盖 | — |
| 置信度必标 | 每条 conclusion 必须标注 `confidence`（high/medium/low），不可全部默认为 medium | analyze_session 对未标 confidence 的缺省为 low |
| 事实与观点分离 | `fact` 类型记忆仅存储可验证的事实；推测/判断用 `decision` 或 `preference` | 写入时校验 |

#### 4.5.3 标签使用约束

| 规则 | 说明 | 违规处理 |
|------|------|----------|
| 预定义优先 | AI 应优先使用 7 个预设标签归类结论；仅当预设标签完全不适用时才创建自定义标签 | — |
| 标签总量 ≤30 | 单项目标签总数（预设+自定义）硬上限 30 | 返回 `TAG_LIMIT_EXCEEDED` |
| 禁止删除预设 | 7 个预设标签不可删除 | 返回 `PRESET_TAG_IMMUTABLE` |
| 标签语义校验 | 自定义标签名必须是英文 slug 格式，且在预设标签中不重复含义（如不能创建 "arch" 替代 "architecture"） | 返回 `TAG_NAME_INVALID` |
| 跨会话标签一致 | 同一项目后续会话应复用已有标签，不应为相同概念创建新标签名 | AI 自觉遵守，`add_tag` 查重 |

#### 4.5.4 条目与迭代约束

| 规则 | 说明 | 违规处理 |
|------|------|----------|
| 条目归属校验 | 条目的 `iteration_id` 必须属于同一项目 | 返回 `PROJECT_MISMATCH` |
| Bug 不关联迭代 | Bug 类型的条目不应强制绑定迭代（可通过不传 `iteration_id` 实现） | — |
| 需求必关联迭代 | Requirement 类型的条目必须关联 `iteration_id` | 返回 `MISSING_FIELD` |
| 迭代完成门槛 | `complete_iteration` 前检查是否有未完成的条目（非 done 状态），除非 `force=true` | 返回 `INCOMPLETE_ITEMS` |
| 状态转移合规 | 条目状态变更必须遵循需求/Bug 的合法转移路径 | 返回 `INVALID_TRANSITION` |

#### 4.5.5 操作频率与规模约束

| 规则 | 说明 | 违规处理 |
|------|------|----------|
| 单次分析上限 | `analyze_session` 单次传入的 conclusions 不超过 10 条 | 返回 `TOO_MANY_CONCLUSIONS` |
| 列表分页上限 | `list_items`/`list_sessions`/`list_memory` 的 `limit` 不得超过 100 | 自动截断为 100 |
| 搜索返回上限 | `search_conclusions`/`search_memory` 默认返回 20 条，上限 50 | 自动截断为 50 |
| 标签创建频率 | 单次会话内新增自定义标签不超过 3 个 | 返回 `TOO_MANY_TAGS` |

#### 4.5.6 错误处理与回退

| 规则 | 说明 |
|------|------|
| 静默失败禁止 | 任何工具返回 `success: false` 时，AI **必须**向用户报告错误码和消息，不可静默忽略 |
| 不猜测参数 | 当不确定参数值（如 `type`/`priority`/`tag_name`）时，应先查询而非猜测 |
| 幂等性感知 | 重复调用 `start_item`（已 in-progress）或 `complete_session`（已 completed）是幂等错误，AI 应识别并告知用户 |
| 回退链完整 | 如某操作失败，AI 应说明已执行了哪些步骤及当前状态，引导用户决定继续或回退 |

#### 4.5.7 AI 提示词注入

以上规则应在系统提示词中以简洁形式注入，确保 AI 在每次调用时遵守：

```
# 开发约束 (Guardrails)

## 会话纪律
- 每次开始工作必须先 start_session，结束必须 complete_session + analyze_session
- 不跨会话修改知识：conclusions 和 memories 一旦写入即不可删除

## 标签纪律
- 优先使用 7 个预设标签；自定义标签每会话最多新增 3 个
- 标签名用英文 slug，不与预设标签含义重复

## 操作纪律
- 任何工具返回错误必须报告用户，不可忽略
- 不确定参数值时先查询（list_tags/list_items/search_conclusions）而非猜测
- 结论必须标注 confidence（high/medium/low），事实与观点分离
- analyze_session 单次 ≤10 条结论

## 条目纪律
- Requirement 必须关联 iteration，Bug 不强制关联
- 状态转移走合法路径（backlog→todo→in-progress→done/reproduced→verified→done）
- 迭代完成前检查未完成条目
```

---

## 5. AI 使用工作流

### 5.1 完整工作流

```
┌─────────────────────────────────────────────────────────────┐
│                     迭代 Session 工作流                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【Session N 开始】                                           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. start_session(title="实现用户认证模块")              │  │
│  │ 2. list_tags() → 获取 7 个维度标签                      │  │
│  │ 3. search_conclusions(tag_names=["architecture",      │  │
│  │       "risk", "decision"]) → 读取历史结论               │  │
│  │ 4. AI 工作: add_item / update_item / add_memory      │  │
│  │ 5. complete_session(summary="...")                    │  │
│  │ 6. AI 反思 → 按维度产出结论:                             │  │
│  │    - architecture: "采用 JWT + refresh token 方案"     │  │
│  │    - risk: "发现 CSRF 防护缺失，待修复"                  │  │
│  │    - decision: "选择 bcrypt 而非 argon2（兼容性考虑）"    │  │
│  │    - pattern: "中间件链模式处理认证流程"                  │  │
│  │ 7. analyze_session(conclusions=[...])                 │  │
│  │    → 返回 missing_tags: ["integration","quality"]      │  │
│  │ 8. AI 补充缺失维度后再次调用 analyze_session             │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                 │
│  【Session N+1 开始】                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. start_session(title="实现权限控制模块")              │  │
│  │ 2. list_tags()                                         │  │
│  │ 3. search_conclusions(                                │  │
│  │       tag_names=["architecture", "risk"])              │  │
│  │    → 读取到: "采用 JWT + refresh token 方案"            │  │
│  │    → 读取到: "CSRF 防护缺失，待修复"                      │  │
│  │ 4. AI 基于历史结论继续工作...                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 AI 使用指南（写入系统提示词）

```
# 会话工作流程

当开始一个新会话时:
1. 调用 start_session 开始新会话
2. 调用 list_tags 了解可用的维度标签
3. 调用 search_conclusions 按你需要关注的维度（如 risk, decision）获取历史结论
4. 在会话中完成工作（创建/更新条目、记录记忆等）
5. 完成所有任务后:
   a. 调用 complete_session 结束会话并提交总结
   b. 反思会话内容，按每个维度标签提取关键结论
   c. 调用 analyze_session 将结论存储到系统
   d. 检查返回的 missing_tags，补充缺失维度的结论

# 维度标签说明

每次会话都应尝试覆盖以下维度产出结论:
- architecture: 架构决策、模块设计
- implementation: 实现细节、编码方式
- risk: 风险识别、已知问题、技术债务
- decision: 重要决策及理由
- pattern: 可复用方案、最佳实践
- integration: 外部依赖、API对接
- quality: 质量改进、性能优化

即使某维度在当前会话中没有新发现，也应说明"无新增，延续之前结论"。

# 去重与知识整理

每个会话结束后，应清理重复知识:

1. 调用 find_similar_items(threshold=0.6) 检测相似记忆和结论
2. 对返回的相似配对逐一判断：
   a. 确认为重复 → 调用 merge_items 合并
   b. 相似但不同主题 → 修正内容使区分更明确
   c. 不确定 → 保留原样（宁可少合）
3. 合并后的知识更精炼，后续会话搜索效率更高

注意:
- 合并会保留所有原始信息（用分隔符拼接）
- 可在 merge_log 中查看历史合并记录
- merge_similar 默认开启，写入时自动检测
```

---

## 6. 非功能性需求

### 6.1 性能

| 指标 | 要求 |
|------|------|
| 会话 CRUD | < 10ms |
| 标签列表 | < 5ms（约 30 条内） |
| 结论搜索 | < 20ms（≤ 1000 条） |
| 分析写入 | < 50ms（批量 upsert ≤ 10 条） |

### 6.2 约束

| 约束 | 值 |
|------|-----|
| 标签上限 | 30 个/项目 |
| 预设标签数 | 7 个 |
| 单项目活跃会话 | 1 个 |
| 结论内容长度 | ≤ 10000 字符 |

### 6.3 兼容性

- Python 3.10+
- SQLite WAL 模式
- 与现有 v0.4.0 schema 完全兼容（通过迁移升级）
- 现有的 31 个 MCP 工具不受影响

---

## 7. Schema 迁移

在 `database.py` 的 `MIGRATIONS` 字典中新增版本 2：

```python
SCHEMA_VERSION = 2

MIGRATIONS = {
    2: """
        CREATE TABLE IF NOT EXISTS sessions (...);
        CREATE TABLE IF NOT EXISTS tags (...);
        CREATE TABLE IF NOT EXISTS conclusions (...);
        CREATE TABLE IF NOT EXISTS memory_tags (...);
        
        -- 为已有项目初始化7个预设标签
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'architecture', '架构与设计：系统架构决策、模块划分、设计模式选择', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'implementation', '实现细节：具体代码实现方式、算法选择、编码技巧', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'risk', '风险与问题：已识别风险、遇到的问题、技术债务', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'decision', '关键决策：重要的技术/业务决策及其理由', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'pattern', '模式与经验：可复用的解决方案、最佳实践、踩坑经验', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'integration', '依赖与集成：外部依赖、API对接、第三方服务集成', 1, datetime('now')
        FROM projects;
        
        INSERT OR IGNORE INTO tags (project_id, name, description, is_preset, created_at)
        SELECT id, 'quality', '质量与优化：代码质量、性能优化、安全加固', 1, datetime('now')
        FROM projects;

        CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_iteration_id ON sessions(iteration_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_tags_project_id ON tags(project_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_project_id ON conclusions(project_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_session_id ON conclusions(session_id);
        CREATE INDEX IF NOT EXISTS idx_conclusions_tag_id ON conclusions(tag_id);
    """,
    1: """... (现有 migration，不变) ..."""
}
```

---

## 8. 新增枚举

```python
# enums.py 新增

class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# 预设标签名（常量，非数据库枚举字段）
PRESET_TAG_NAMES = [
    "architecture",
    "implementation", 
    "risk",
    "decision",
    "pattern",
    "integration",
    "quality",
]

MAX_TAGS_PER_PROJECT = 30

# 去重相似度阈值
SIMILARITY_THRESHOLD = 0.6  # Jaccard 相似度 ≥ 0.6 触发合并
```

---

## 9. SQLAlchemy 新增 Models

```python
# models.py 新增

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Text, primary_key=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    iteration_id = Column(Text, ForeignKey("iterations.id"))
    title = Column(Text, nullable=False)
    summary = Column(Text)
    status = Column(Text, nullable=False, default="active")
    started_at = Column(Text, nullable=False)
    completed_at = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)
    
    project = relationship("Project")
    iteration = relationship("Iteration")
    conclusions = relationship("Conclusion", back_populates="session", cascade="all, delete-orphan")


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    is_preset = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False)


class Conclusion(Base):
    __tablename__ = "conclusions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    session_id = Column(Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    content = Column(Text, nullable=False)
    confidence = Column(Text, nullable=False, default="medium")
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)
    
    session = relationship("Session", back_populates="conclusions")


class MemoryTag(Base):
    __tablename__ = "memory_tags"
    memory_id = Column(Integer, ForeignKey("memory_entries.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class MergeLog(Base):
    __tablename__ = "merge_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    entity_type = Column(Text, nullable=False)
    kept_id = Column(Integer, nullable=False)
    removed_id = Column(Integer, nullable=False)
    kept_content = Column(Text, nullable=False)
    removed_content = Column(Text, nullable=False)
    similarity = Column(Float, nullable=False)
    merged_at = Column(Text, nullable=False)
```

---

## 10. 实现计划

### 10.1 新增文件

| 文件 | 内容 |
|------|------|
| `tools/sessions.py` | 会话 CRUD 工具（4 tools） |
| `tools/tags.py` | 标签管理工具（3 tools） |
| `tools/conclusions.py` | 结论管理 + 分析工具（5 tools） |
| `tools/merge.py` | 去重与合并工具（2 tools） |
| `tools/guardrails.py` | AI 行为约束校验器（供所有工具调用） |

### 10.2 修改文件

| 文件 | 变更 |
|------|------|
| `enums.py` | 新增 SessionStatus, Confidence, PRESET_TAG_NAMES |
| `models.py` | 新增 Session, Tag, Conclusion, MemoryTag 模型 |
| `database.py` | SCHEMA_VERSION=2, 新增 migration v2 |
| `tools/memory.py` | add_memory_entry/search_memory 增加 tag_names 参数 |
| `server.py` | 注册新增 11 个 MCP tools（总计扩至 42 tools） |
| `__init__.py` | 导出新增工具 |

### 10.3 新增测试

| 文件 | 覆盖 |
|------|------|
| `tests/test_sessions.py` | 会话 CRUD、单活跃约束、完成流程 |
| `tests/test_tags.py` | 标签 CRUD、上限、预设标签初始化 |
| `tests/test_conclusions.py` | 结论 CRUD、搜索、分析工作流 |
| `tests/test_merge.py` | 相似检测、merge_items、merge_log |
| `tests/test_guardrails.py` | 约束校验：标签上限、操作频率、跨会话修改拒绝 |

### 10.4 实施顺序

```
 1. enums.py         — 新增枚举和常量
 2. database.py      — migration v2
 3. models.py        — 新增 ORM 模型
 4. tools/guardrails.py — 行为约束校验器（被所有工具调用）
 5. tools/tags.py    — 标签管理（含上限、预设保护）
 6. tools/sessions.py — 会话管理（含 SESSION_IMMUTABLE 校验）
 7. tools/conclusions.py — 结论与分析（含 merge_similar、频率限制）
 8. tools/merge.py   — 去重与合并
 9. tools/memory.py  — 增强 memory 支持 tag + merge_similar
10. server.py        — 注册所有新工具（总计 44 tools）
11. tests/           — 测试全覆盖
```

---

## 11. 附录：标签扩展策略（未来）

当前 v0.5.0 定义 7 个预设标签，AI 可自定义扩展至 30 个。未来版本可考虑：

- **AI 自动建议标签**: analyze_session 时如发现内容不适合现有标签，AI 建议新标签名
- **标签合并**: 当两个标签内容高度重叠时，提示合并
- **会话默认标签集**: 不同迭代类型可配置默认关注哪些标签
- **标签使用统计**: 追踪各标签使用频率，淘汰低频自定义标签