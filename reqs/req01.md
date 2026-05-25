收到，技术栈明确：**Python 开发，SQLite 作为数据库后端**。已更新需求文档相关章节（非功能需求、技术栈等），完整文档如下：

---

# Itera MCP 工具需求文档

**版本**：0.4.0  
**技术栈**：Python 3.10+，SQLite（内嵌，通过 `sqlite3` 模块访问）  
**目标**：为 AI 编程助手（如 OpenCode）提供多项目需求、Bug、迭代和记忆的管理能力，实现“项目→需求→迭代→开发→验证→记忆”闭环。

---

## 1. 项目背景

在真实开发中，一个 AI 编程助手需要同时参与多个项目，每个项目有自己的上下文、约束、迭代节奏和记忆。Itera 将这些信息结构化存储在 MCP Server 的 SQLite 数据库中，AI 可根据当前项目名称自动匹配或创建项目，高效获取上下文，减少 token 消耗，并通过记忆系统消除会话失忆问题。

---

## 2. 核心概念

| 术语 | 定义 |
|------|------|
| **Project** | 一个软件项目，拥有独立的条目集合、迭代和配置。Server 中可管理多个项目。 |
| **Item** | 工作单元，分为需求（requirement）或 Bug（bug） |
| **Iteration** | 一个开发周期，归属于某个项目，包含一组需求条目 |
| **Status** | 条目的生命周期状态 |
| **Summary** | 条目的超短摘要（≤80 字符），帮助 AI 用最少 token 快速扫描 |
| **Memory** | AI 可检索的结构化记忆，包括项目事实、用户偏好、决策、踩坑记录和活动日志 |

---

## 3. 系统架构

### 3.1 Server 与数据存储

- Itera 是一个 **Python MCP Server**，通过标准输入/输出（stdio）与 AI 助手通信。
- 所有数据存储在单个 SQLite 数据库文件中，文件路径由环境变量 `ITERA_DATA_DIR` 指定（默认 `~/.itera/itera.db`）。若目录不存在，Server 启动时自动创建。
- Server 启动时连接数据库，自动执行迁移（基于 `PRAGMA user_version`），确保表结构最新。
- 数据库使用 WAL 模式（`PRAGMA journal_mode=WAL;`）提高并发读写性能，启用外键约束（`PRAGMA foreign_keys=ON;`）。

### 3.2 数据库表结构

#### 3.2.1 项目表 `projects`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | UUID |
| `name` | TEXT NOT NULL UNIQUE | 项目名称 |
| `description` | TEXT | 项目描述 |
| `tech_stack` | TEXT | JSON 数组，如 `["Go","PostgreSQL"]` |
| `constraints` | TEXT | JSON 数组，如 `["使用函数式组件"]` |
| `active_iteration_id` | TEXT | 当前活跃迭代 ID，可空 |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |

#### 3.2.2 条目表 `items`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | UUID |
| `project_id` | TEXT NOT NULL REFERENCES projects(id) | 所属项目 |
| `type` | TEXT NOT NULL | `requirement` 或 `bug` |
| `title` | TEXT NOT NULL | ≤200 字符 |
| `summary` | TEXT NOT NULL | ≤80 字符，极简摘要 |
| `description` | TEXT | Markdown 描述 |
| `priority` | TEXT NOT NULL DEFAULT 'medium' | `high`/`medium`/`low` |
| `status` | TEXT NOT NULL DEFAULT 'backlog' | 状态 |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |
| `deleted` | INTEGER NOT NULL DEFAULT 0 | 软删除标记 |
| `completed_at` | TEXT | 完成时间 |
| `iteration_id` | TEXT REFERENCES iterations(id) | 需求关联的迭代 |
| `acceptance_criteria` | TEXT | JSON 数组，需求专用 |
| `severity` | TEXT | Bug 专用：`critical`/`major`/`minor` |
| `steps_to_reproduce` | TEXT | Bug 专用 |
| `environment` | TEXT | Bug 专用 |
| `verified` | INTEGER DEFAULT 0 | Bug 专用，0/1 |

**索引**：`project_id`，`type`，`status`，`iteration_id`，`deleted`。

#### 3.2.3 迭代表 `iterations`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | TEXT PRIMARY KEY | UUID |
| `project_id` | TEXT NOT NULL REFERENCES projects(id) | 所属项目 |
| `name` | TEXT NOT NULL | 迭代名称 |
| `goal` | TEXT | 迭代目标 |
| `start_date` | TEXT | YYYY-MM-DD |
| `end_date` | TEXT | YYYY-MM-DD |
| `status` | TEXT NOT NULL DEFAULT 'planning' | `planning`/`active`/`completed` |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |

#### 3.2.4 记忆表 `memory_entries`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `project_id` | TEXT NOT NULL REFERENCES projects(id) | 所属项目 |
| `type` | TEXT NOT NULL | `fact`/`decision`/`pitfall`/`preference` |
| `content` | TEXT NOT NULL | 记忆内容 |
| `created_at` | TEXT NOT NULL | ISO 8601 UTC |
| `updated_at` | TEXT NOT NULL | ISO 8601 UTC |

#### 3.2.5 活动日志 `activity_log`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | |
| `project_id` | TEXT NOT NULL REFERENCES projects(id) | |
| `timestamp` | TEXT NOT NULL | ISO 8601 UTC |
| `session_id` | TEXT | 会话标识 |
| `action` | TEXT NOT NULL | 操作类型 |
| `summary` | TEXT | 摘要 |
| `item_id` | TEXT | 关联条目 |
| `iteration_id` | TEXT | 关联迭代 |
| `details` | TEXT | JSON 格式额外信息 |

---

## 4. 功能需求

### 4.1 项目管理

| MCP 工具 | 功能 | 参数 |
|---------|------|------|
| `find_or_create_project` | 按名称查找项目，不存在则创建 | `name`（必填），`description`，`tech_stack`，`constraints` |
| `update_project` | 更新项目信息 | `project_id`，可更新字段同上 |
| `get_project` | 获取项目详情 | `project_id` |
| `list_projects` | 列出所有项目 | 无 |
| `set_active_project` | 设置当前会话的活跃项目 | `project_id` |

**规则**：
- 若工具未指定 `project_id`，则使用当前活跃项目；若均未指定，返回错误。
- 首次使用时，AI 调用 `find_or_create_project` 完成项目初始化。

---

### 4.2 条目管理

**状态流转**：同 v0.3.0（需求：`backlog→todo→in-progress→done`；Bug：`backlog→todo→in-progress→reproduced→verified→done`）

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `add_item` | 创建条目 | `type`，`title`，`summary`，`description`，`priority`，`iteration_id`（需求必填），Bug 专用字段 |
| `update_item` | 更新条目（部分更新） | `id`，可更新字段 |
| `list_items` | 列出条目，支持筛选、分页 | `project_id`，`type`，`status`，`priority`，`iteration_id`，`include_deleted`，`limit`/`offset` |
| `get_item` | 获取单个条目 | `id` |
| `delete_item` | 软删除（设 `deleted=1`） | `id` |

**约束**：
- 需求必须关联 `iteration_id`，且迭代属于同一项目。
- Bug 不关联迭代。
- 不允许修改 `type`。

---

### 4.3 迭代管理

| 工具 | 功能 |
|------|------|
| `create_iteration` | 创建迭代，状态为 `planning` |
| `add_item_to_iteration` | 将需求加入迭代（校验类型） |
| `remove_item_from_iteration` | 移除需求 |
| `get_iteration` | 查看迭代详情 |
| `list_iterations` | 列出迭代，支持状态筛选和分页 |
| `start_iteration` | 激活迭代（单活跃约束） |
| `complete_iteration` | 完成迭代，支持 `force` 参数 |

**规则**：
- 同一项目同时只能有一个 `active` 迭代。
- 需求可属于多个迭代（通过修改 `iteration_id` 实现，暂时仅支持单一关联，多迭代支持见后续扩展）。

---

### 4.4 状态流转快捷操作

| 工具 | 功能 |
|------|------|
| `start_item` | `backlog`/`todo` → `in-progress` |
| `complete_item` | 需求 → `done`，Bug → `verified` + `verified=1` |
| `reproduce_bug` | Bug → `reproduced` |
| `verify_bug` | Bug → `verified` |
| `update_item_status` | 通用状态更新（校验转移表） |

---

### 4.5 查询与报表

| 工具 | 功能 |
|------|------|
| `get_active_iteration` | 当前活跃迭代及需求列表 |
| `get_suggestions` | 按优先级+严重性加权推荐下一个需求 |
| `get_summary` | 项目统计、约束、待办数、Bug 数 |
| `get_project_context` | 完整上下文：项目信息、约束、活跃迭代、最近活动、关键记忆（最新 5 条） |

---

### 4.6 记忆系统

#### 4.6.1 设计原则

- 分层存储：事实、决策、踩坑、偏好分别存储（`type` 字段），支持按类检索。
- 默认返回最近 20 条，避免 Token 膨胀。
- 会话结束时调用 `crystallize_context` 自动抽取关键信息并写入记忆。

#### 4.6.2 工具

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| `add_memory_entry` | 添加一条记忆 | `type`，`content` |
| `update_memory_entry` | 编辑/删除记忆（通过 ID） | `id`，`content`（空则删除） |
| `search_memory` | 关键词搜索记忆 | `query`，`type`（可选） |
| `list_memory` | 列出记忆，支持分页和类型筛选 | `type`，`limit`/`offset` |
| `crystallize_context` | 会话复盘，抽取事实/决策/偏好写入 | `session_summary` |
| `get_recent_activity` | 最近 N 条活动日志 | `limit`（默认 15） |

**`crystallize_context` 内部实现**：
1. 接收 `session_summary`。
2. 调用 LLM（需集成，或暂用规则抽取）提取关键信息，返回结构化结果。
3. 将抽取的每一条写入 `memory_entries`，同时将本次会话摘要写入 `activity_log`。

#### 4.6.3 活动日志

所有状态变更、CRUD 操作自动记录至 `activity_log`，记录由工具函数内部自动完成，无独立写入 API（除 `crystallize_context` 外）。

---

## 5. 非功能性需求

- **开发语言**：Python 3.10+，使用标准库 `sqlite3` 模块操作数据库。
- **依赖**：最小外部依赖（MCP SDK 如 `mcp` 包，UUID 生成等）。
- **数据库**：SQLite，WAL 模式，外键约束开启；支持通过 `ITERA_DATA_DIR` 自定义路径。
- **性能**：条目数 < 10,000 时，所有查询 < 50ms。
- **迁移**：Server 启动时检查 `PRAGMA user_version`，按版本号执行 SQL 迁移脚本。
- **错误处理**：统一返回 JSON `{"success": bool, "data": ..., "error": {"code": ..., "message": ...}}`。
- **日志**：Server 端输出简洁日志到 stderr，方便调试。

---

## 6. 后续扩展（v0.6+）

- 需求多迭代关联（多对多）。
- 条目依赖关系。
- 自定义标签。
- Git 分支自动关联。
- HTTP/SSE 传输模式。
- 技能模板（轻量替代 Hermes 技能系统）。

---

## 7. 里程碑

| 里程碑 | 内容 |
|--------|------|
| M1 | Python 项目骨架、SQLite 初始化、项目管理功能 |
| M2 | 条目 CRUD（含软删除、摘要） |
| M3 | 迭代管理（含单活跃约束） |
| M4 | 状态机与快捷操作 |
| M5 | 查询报表与上下文工具 |
| M6 | 记忆系统（记忆条目、活动日志、crystallize） |
| M7 | 测试覆盖、文档、发布到 PyPI |

---

以上需求文档已明确技术栈为 **Python + SQLite**，所有存储均在 SQLite 中，可立即作为开发蓝图使用。如需进一步调整，请随时告知。
