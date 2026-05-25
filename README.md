# Itera MCP

为 AI 编程助手（如 OpenCode、Cursor 等）提供多项目需求、Bug、迭代和记忆的结构化管理能力，实现 **"项目→需求→迭代→开发→验证→记忆"** 完整闭环。

## 特性

- **多项目管理**：同时管理多个项目，支持技术栈、约束等元数据
- **条目管理**：需求（requirement）和 Bug 的全生命周期 CRUD，支持软删除
- **迭代管理**：同一项目同时仅一个活跃迭代，支持强制完成
- **状态机**：严格的状态流转校验，需求 `backlog→todo→in-progress→done`，Bug `backlog→todo→in-progress→reproduced→verified→done`
- **查询与报表**：项目统计、加权推荐、上下文获取
- **记忆系统**：事实、决策、踩坑、偏好分类存储；`crystallize_context` 自动抽取会话关键信息
- **SQLite 后端**：零配置，WAL 模式提升并发性能，外键约束保障数据一致性

## 技术栈

- Python 3.10+
- SQLite（标准库 `sqlite3` 模块）
- MCP SDK（`mcp>=1.0.0`）
- Loguru（结构化日志）

## 安装

```bash
# 使用 uv 安装
uv pip install .

# 或直接克隆后安装
git clone <repo-url>
cd itera-mcp
uv sync
```

## 运行

```bash
# 设置数据目录（可选，默认 ~/.itera/）
export ITERA_DATA_DIR=/path/to/your/data

# 启动 MCP Server（通过 stdio 通信）
uv run itera-mcp
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ITERA_DATA_DIR` | `~/.itera` | SQLite 数据库文件所在目录 |

## 工具列表（32 个 MCP 工具）

### 项目管理

| 工具 | 说明 |
|------|------|
| `find_or_create_project` | 按名称查找项目，不存在则创建 |
| `update_project` | 更新项目信息 |
| `get_project` | 获取项目详情 |
| `list_projects` | 列出所有项目 |
| `set_active_project` | 设置当前会话活跃项目 |

### 条目管理

| 工具 | 说明 |
|------|------|
| `add_item` | 创建需求或 Bug |
| `update_item` | 更新条目（部分更新） |
| `list_items` | 列出条目，支持筛选和分页 |
| `get_item` | 获取单个条目 |
| `delete_item` | 软删除条目 |

### 迭代管理

| 工具 | 说明 |
|------|------|
| `create_iteration` | 创建迭代（状态 planning） |
| `add_item_to_iteration` | 将需求加入迭代 |
| `remove_item_from_iteration` | 从迭代中移除需求 |
| `get_iteration` | 获取迭代详情 |
| `list_iterations` | 列出迭代，支持状态筛选 |
| `start_iteration` | 激活迭代（单活跃约束） |
| `complete_iteration` | 完成迭代，支持 force 参数 |

### 状态流转

| 工具 | 说明 |
|------|------|
| `update_item_status` | 通用状态更新（校验转移表） |
| `start_item` | `backlog`/`todo` → `in-progress` |
| `complete_item` | 需求 → `done`，Bug → `verified` |
| `reproduce_bug` | Bug → `reproduced` |
| `verify_bug` | Bug → `verified` |

### 查询与报表

| 工具 | 说明 |
|------|------|
| `get_active_iteration` | 当前活跃迭代及条目列表 |
| `get_suggestions` | 按优先级+严重性加权推荐下一个条目 |
| `get_summary` | 项目统计概览 |
| `get_project_context` | 完整上下文：项目信息、活跃迭代、最近活动、关键记忆 |

### 记忆系统

| 工具 | 说明 |
|------|------|
| `add_memory_entry` | 添加记忆（fact/decision/pitfall/preference） |
| `update_memory_entry` | 编辑或删除记忆 |
| `search_memory` | 关键词搜索记忆 |
| `list_memory` | 列出记忆，支持分页和类型筛选 |
| `crystallize_context` | 会话复盘，抽取关键信息并写入 |
| `get_recent_activity` | 最近活动日志 |

## 状态流转图

```
需求: backlog → todo → in-progress → done

Bug:  backlog → todo → in-progress → reproduced → verified → done
```

## 开发

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest -v

# 运行测试并查看覆盖率
uv run pytest --cov=src/itera_mcp --cov-report=term-missing -v
```

## 后续扩展（v0.6+）

- 需求多迭代关联（多对多）
- 条目依赖关系
- 自定义标签
- Git 分支自动关联
- HTTP/SSE 传输模式
- 技能模板（轻量替代 Hermes 技能系统）
