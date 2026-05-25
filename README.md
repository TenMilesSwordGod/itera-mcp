# Itera MCP

为 AI 编程助手（如 **OpenCode**、Claude Code、Cursor 等）提供多项目需求、Bug、迭代、会话、记忆和结论的结构化管理能力，实现 **"项目→迭代→会话→开发→分析→去重"** 完整闭环。

## 特性

- **多项目管理** — 同时管理多个项目，支持技术栈、约束等元数据
- **条目管理** — 需求（requirement）和 Bug 的全生命周期 CRUD，支持软删除
- **迭代管理** — 同一项目同时仅一个活跃迭代，支持强制完成
- **状态机** — 严格的状态流转校验，需求 `backlog→todo→in-progress→done`，Bug `backlog→todo→in-progress→reproduced→verified→done`
- **会话建模** — 每次开发会话的 start/complete 生命周期，自动关联迭代
- **标签系统** — 7 个预设维度标签（architecture / implementation / risk / decision / pattern / integration / quality），上限 30 个/项目
- **知识积累** — 事实（fact）、决策（decision）、踩坑（pitfall）、偏好（preference）四类记忆
- **会话分析** — `analyze_session` 按 7 个维度自动生成结论，自动检测遗漏标签
- **相似去重** — Jaccard 相似度算法自动识别并合并相似记忆和结论
- **查询与报表** — 项目统计、加权推荐、上下文获取
- **SQLite 后端** — 零配置，WAL 模式，SQLAlchemy ORM

## 技术栈

| 组件 | 说明 |
|------|------|
| Python | 3.10+ |
| 数据库 | SQLite（SQLAlchemy ORM） |
| MCP 协议 | `mcp>=1.0.0`，stdio 传输 |
| 日志 | Loguru |
| 代码质量 | Ruff |

## 安装

```bash
git clone https://github.com/TenMilesSwordGod/itera-mcp.git
cd itera-mcp
uv sync
```

## 在 OpenCode 中配置

将以下配置加入 OpenCode 的 MCP 配置文件：

### 方式一：OpenCode UI 配置

1. 打开 OpenCode → 设置 → MCP Servers
2. 点击 "Add MCP Server"
3. 填写：
   - **Name**: `itera-mcp`
   - **Command**: `uv`
   - **Arguments**: `--directory /absolute/path/to/itera-mcp run itera-mcp`

### 方式二：直接编辑配置文件

OpenCode MCP 配置文件通常位于：

| 系统 | 路径 |
|------|------|
| macOS | `~/.opencode/mcp.json` 或 `~/.config/opencode/mcp.json` |
| Linux | `~/.config/opencode/mcp.json` |
| Windows | `%APPDATA%\opencode\mcp.json` |

```json
{
  "mcpServers": {
    "itera-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/vncuser/workdir/liheng/itera-mcp",
        "run",
        "itera-mcp"
      ],
      "env": {
        "ITERA_DATA_DIR": "/home/vncuser/.itera"
      }
    }
  }
}
```

### 在 Claude Code / Cursor 中配置

Claude Code（`~/.claude/mcp.json`）或 Cursor（`~/.cursor/mcp.json`）中配置格式相同：

```json
{
  "mcpServers": {
    "itera-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/itera-mcp",
        "run",
        "itera-mcp"
      ],
      "env": {
        "ITERA_DATA_DIR": "~/.itera"
      }
    }
  }
}
```

### 验证安装

配置完成后重启 OpenCode，在对话中输入：

```
请用 itera-mcp 工具列出所有项目
```

如果看到工具调用成功返回，说明配置正确。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ITERA_DATA_DIR` | `~/.itera` | SQLite 数据库文件所在目录 |

## 工作流快速开始

详细工作流请参考 [workflow.md](workflow.md)，核心流程：

```
1. find_or_create_project("my-project")
2. create_iteration("Sprint 1", goal="...")
3. start_iteration(iteration_id)
4. add_item("requirement", title="...", iteration_id=...)
5. start_session(title="实现 XXX", iteration_id=...)
6. start_item(id) → update_item → add_memory_entry → ...
7. complete_session(summary="...")
8. analyze_session(conclusions=[...])
9. find_similar_items → merge_items (去重)
10. complete_iteration(iteration_id)
```

## 工具列表（42 个 MCP 工具）

### 项目管理 (5)

| 工具 | 说明 |
|------|------|
| `find_or_create_project` | 按名称查找项目，不存在则创建 |
| `update_project` | 更新项目信息（名称、描述、技术栈、约束） |
| `get_project` | 获取项目详情 |
| `list_projects` | 列出所有项目 |
| `set_active_project` | 设置当前会话的活跃项目 |

### 条目管理 (5)

| 工具 | 说明 |
|------|------|
| `add_item` | 创建需求或 Bug，支持优先级、严重性、验收标准等 |
| `update_item` | 更新条目（部分更新） |
| `list_items` | 列出条目，支持状态/类型筛选和分页 |
| `get_item` | 获取单个条目详情 |
| `delete_item` | 软删除条目 |

### 迭代管理 (7)

| 工具 | 说明 |
|------|------|
| `create_iteration` | 创建迭代（初始状态 planning） |
| `add_item_to_iteration` | 将需求加入迭代 |
| `remove_item_from_iteration` | 从迭代中移除需求 |
| `get_iteration` | 获取迭代详情 |
| `list_iterations` | 列出迭代，支持状态筛选 |
| `start_iteration` | 激活迭代（单活跃约束，自动设置 project.active_iteration_id） |
| `complete_iteration` | 完成迭代，支持 `force=true` 跳过未完成条目检查 |

### 状态流转 (5)

| 工具 | 说明 |
|------|------|
| `update_item_status` | 通用状态更新（校验状态转移表） |
| `start_item` | `backlog`/`todo` → `in-progress` |
| `complete_item` | 需求 → `done`，Bug → `verified` |
| `reproduce_bug` | Bug → `reproduced` |
| `verify_bug` | Bug → `verified` |

### 状态流转图

```
需求: backlog → todo → in-progress → done

Bug:  backlog → todo → in-progress → reproduced → verified → done
```

### 查询与报表 (4)

| 工具 | 说明 |
|------|------|
| `get_active_iteration` | 当前活跃迭代及条目列表 |
| `get_suggestions` | 按优先级+严重性加权推荐下一个任务 |
| `get_summary` | 项目统计概览（需求/Bug 数量、完成率） |
| `get_project_context` | 完整上下文快照：项目 + 活跃迭代 + 最近活动 + 关键记忆 + 待办条目 |

### 记忆系统 (6)

| 工具 | 说明 |
|------|------|
| `add_memory_entry` | 添加记忆（fact/decision/pitfall/preference），支持 `merge_similar=true` 自动合并 |
| `update_memory_entry` | 编辑记忆内容；传空 content 则删除 |
| `search_memory` | 关键词+标签组合搜索记忆 |
| `list_memory` | 列出记忆，支持分页和类型筛选 |
| `crystallize_context` | 会话复盘，自动从摘要中抽取 fact/decision/pitfall/preference |
| `get_recent_activity` | 最近活动日志 |

### 会话管理 (4)

| 工具 | 说明 |
|------|------|
| `start_session` | 开始一个新的工作会话，关联迭代 |
| `complete_session` | 完成会话，写入总结 |
| `get_session` | 获取会话详情，含关联结论列表 |
| `list_sessions` | 列出项目会话，支持状态筛选 |

### 标签管理 (3)

| 工具 | 说明 |
|------|------|
| `list_tags` | 列出项目的所有标签 |
| `add_tag` | 添加自定义标签（上限 30 个，不允许删除预设标签） |
| `get_preset_tags` | 获取 7 个预设维度标签定义 |

**7 个预设标签**：`architecture`、`implementation`、`risk`、`decision`、`pattern`、`integration`、`quality`

### 结论管理 (5)

| 工具 | 说明 |
|------|------|
| `add_conclusion` | 添加/更新结论（同一标签同一会话 upsert），需标注可信度 high/medium/low |
| `search_conclusions` | 搜索结论，支持标签+关键词+可信度组合筛选 |
| `get_session_conclusions` | 获取某次会话的所有结论 |
| `get_conclusion` | 获取单条结论详情 |
| `analyze_session` | **核心分析工具**：输入会话总结，按 7 个维度自动生成结论，返回 missing_tags 提示遗漏维度 |

### 去重管理 (2)

| 工具 | 说明 |
|------|------|
| `find_similar_items` | Jaccard 相似度算法查找相似记忆/结论（可设 threshold） |
| `merge_items` | 合并两条记忆或结论（keep_id 保留，remove_id 删除） |

## AI 行为约束

本 MCP 工具内置以下约束规则，确保 AI 使用规范：

| 类别 | 规则 |
|------|------|
| **会话** | 每个项目只能有一个活跃会话；必须先完成分析再开新会话 |
| **标签** | 上限 30 个；7 个预设标签不可删除；自定义标签用小写连字符格式 |
| **记忆** | 事实与观点分离；自动合并相似条目（`merge_similar=true`） |
| **结论** | 必须标注可信度（high/medium/low）；每个标签每个会话 upsert 操作 |
| **条目** | 需求条目需要 `iteration_id`；Bug 可跳过；按状态流转路径操作 |
| **分析** | 每次 `analyze_session` 最多 10 条结论；力求覆盖全部 7 个预设标签 |
| **去重** | 每个会话结束后运行 `find_similar_items`；谨慎合并，保留信息 |
| **错误处理** | 不可忽略 `success: false` 响应，必须向用户报告 |

## 开发

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest -v

# 运行测试并查看覆盖率
uv run pytest --cov=src/itera_mcp --cov-report=term-missing -v

# 运行 Ruff 代码检查
uv run ruff check src tests
```

## 项目结构

```
itera-mcp/
├── main.py                    # 入口
├── pyproject.toml             # 项目配置
├── workflow.md                # 详细工作流文档（中文）
├── reqs/                      # 需求文档和报告
│   ├── req02.md
│   └── req03-code-quality.md
├── src/itera_mcp/
│   ├── server.py              # MCP Server 主程序（42 工具注册和路由）
│   ├── database.py            # 数据库初始化和迁移（SQLite WAL + SQLAlchemy）
│   ├── models.py              # SQLAlchemy ORM 模型
│   ├── enums.py               # 枚举定义
│   ├── utils.py               # 共享工具函数
│   └── tools/
│       ├── projects.py        # 项目管理
│       ├── items.py           # 条目 CRUD
│       ├── iterations.py      # 迭代管理
│       ├── status.py          # 状态流转
│       ├── queries.py         # 查询和报表
│       ├── memory.py          # 记忆系统
│       ├── sessions.py        # 会话管理
│       ├── tags.py            # 标签管理
│       ├── conclusions.py     # 结论管理和分析
│       ├── merge.py           # 相似去重
│       └── guardrails.py      # AI 行为约束验证
└── tests/
    ├── conftest.py
    ├── test_database.py
    ├── test_items.py
    ├── test_queries.py
    └── test_status.py
```

## 后续扩展

- [ ] 需求多迭代关联（多对多）
- [ ] 条目依赖关系
- [ ] Git 分支自动关联
- [ ] HTTP/SSE 传输模式
- [ ] 技能模板
- [ ] Web 管理界面