import json
import sys
from typing import Any

from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .database import init_db, close_db
from .utils import error_response
from .tools.projects import (
    find_or_create_project,
    update_project,
    get_project,
    list_projects,
    set_active_project,
)
from .tools.items import add_item, update_item, list_items, get_item, delete_item
from .tools.iterations import (
    create_iteration,
    add_item_to_iteration,
    remove_item_from_iteration,
    get_iteration,
    list_iterations,
    start_iteration,
    complete_iteration,
)
from .tools.status import (
    update_item_status,
    start_item,
    complete_item,
    reproduce_bug,
    verify_bug,
)
from .tools.queries import (
    get_active_iteration,
    get_suggestions,
    get_summary,
    get_project_context,
)
from .tools.memory import (
    add_memory_entry,
    update_memory_entry,
    search_memory,
    list_memory,
    crystallize_context,
    get_recent_activity,
)
from .tools.sessions import start_session, complete_session, get_session_, list_sessions
from .tools.tags import list_tags, add_tag, get_preset_tags
from .tools.conclusions import (
    add_conclusion,
    search_conclusions,
    get_session_conclusions,
    get_conclusion,
    analyze_session,
)
from .tools.merge import find_similar_items, merge_items

logger.remove()
logger.add(sys.stderr, level="INFO")

server = Server("itera-mcp")

TOOLS = [
    Tool(
        name="find_or_create_project",
        description="Find a project by name, or create it if it doesn't exist",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name"},
                "description": {"type": "string", "description": "Project description"},
                "tech_stack": {"type": "array", "items": {"type": "string"}, "description": "Tech stack as list of strings"},
                "constraints": {"type": "array", "items": {"type": "string"}, "description": "Project constraints as list of strings"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="update_project",
        description="Update an existing project's information",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "name": {"type": "string", "description": "New project name"},
                "description": {"type": "string", "description": "New description"},
                "tech_stack": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="get_project",
        description="Get project details by ID",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="list_projects",
        description="List all projects",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="set_active_project",
        description="Set the active project for the current session",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": ["project_id"],
        },
    ),
    Tool(
        name="add_item",
        description="Create a new item (requirement or bug)",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "type": {"type": "string", "enum": ["requirement", "bug"]},
                "title": {"type": "string", "description": "Title, max 200 chars"},
                "summary": {"type": "string", "description": "Short summary, max 80 chars"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "iteration_id": {"type": "string", "description": "Required for requirements"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                "steps_to_reproduce": {"type": "string"},
                "environment": {"type": "string"},
            },
            "required": ["type", "title", "summary"],
        },
    ),
    Tool(
        name="update_item",
        description="Update an existing item (partial update)",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Item ID"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "status": {"type": "string"},
                "iteration_id": {"type": "string"},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                "steps_to_reproduce": {"type": "string"},
                "environment": {"type": "string"},
                "verified": {"type": "integer", "enum": [0, 1]},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="list_items",
        description="List items with filtering and pagination",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "type": {"type": "string", "enum": ["requirement", "bug"]},
                "status": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "iteration_id": {"type": "string"},
                "include_deleted": {"type": "boolean"},
                "limit": {"type": "integer", "default": 50},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
    ),
    Tool(
        name="get_item",
        description="Get a single item by ID",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="delete_item",
        description="Soft-delete an item (sets deleted=1)",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="create_iteration",
        description="Create a new iteration (status: planning)",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string"},
                "goal": {"type": "string"},
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="add_item_to_iteration",
        description="Add a requirement to an iteration",
        inputSchema={
            "type": "object",
            "properties": {
                "iteration_id": {"type": "string"},
                "item_id": {"type": "string"},
            },
            "required": ["iteration_id", "item_id"],
        },
    ),
    Tool(
        name="remove_item_from_iteration",
        description="Remove a requirement from an iteration",
        inputSchema={
            "type": "object",
            "properties": {
                "iteration_id": {"type": "string"},
                "item_id": {"type": "string"},
            },
            "required": ["iteration_id", "item_id"],
        },
    ),
    Tool(
        name="get_iteration",
        description="Get iteration details by ID",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="list_iterations",
        description="List iterations with optional status filter and pagination",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "status": {"type": "string", "enum": ["planning", "active", "completed"]},
                "limit": {"type": "integer", "default": 50},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
    ),
    Tool(
        name="start_iteration",
        description="Activate an iteration (only one active per project)",
        inputSchema={
            "type": "object",
            "properties": {"iteration_id": {"type": "string"}},
            "required": ["iteration_id"],
        },
    ),
    Tool(
        name="complete_iteration",
        description="Complete an iteration, optionally forcing if items remain",
        inputSchema={
            "type": "object",
            "properties": {
                "iteration_id": {"type": "string"},
                "force": {"type": "boolean", "default": False},
            },
            "required": ["iteration_id"],
        },
    ),
    Tool(
        name="update_item_status",
        description="Update item status with transition validation",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["id", "status"],
        },
    ),
    Tool(
        name="start_item",
        description="Move item to in-progress (from backlog/todo)",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="complete_item",
        description="Complete a requirement (→done) or bug (→verified)",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="reproduce_bug",
        description="Mark a bug as reproduced",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="verify_bug",
        description="Mark a bug as verified",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    ),
    Tool(
        name="get_active_iteration",
        description="Get the currently active iteration with its items",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": [],
        },
    ),
    Tool(
        name="get_suggestions",
        description="Get recommended next items by priority and severity",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": [],
        },
    ),
    Tool(
        name="get_summary",
        description="Get project statistics overview",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": [],
        },
    ),
    Tool(
        name="get_project_context",
        description="Get full project context: info, active iteration, recent activity, key memories",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": [],
        },
    ),
    Tool(
        name="add_memory_entry",
        description="Add a memory entry (fact/decision/pitfall/preference) with optional tags and merge",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "type": {"type": "string", "enum": ["fact", "decision", "pitfall", "preference"]},
                "content": {"type": "string"},
                "tag_names": {"type": "array", "items": {"type": "string"}, "description": "Dimension tags to associate"},
                "merge_similar": {"type": "boolean", "default": True, "description": "Auto-merge with similar existing memory"},
            },
            "required": ["type", "content"],
        },
    ),
    Tool(
        name="update_memory_entry",
        description="Update or delete a memory entry (empty content = delete)",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "content": {"type": "string"},
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="search_memory",
        description="Search memory entries by keyword and optional tag filter",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "query": {"type": "string"},
                "type": {"type": "string", "enum": ["fact", "decision", "pitfall", "preference"]},
                "tag_names": {"type": "array", "items": {"type": "string"}, "description": "Filter by dimension tags"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="list_memory",
        description="List memory entries with optional type filter and pagination",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "type": {"type": "string", "enum": ["fact", "decision", "pitfall", "preference"]},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
    ),
    Tool(
        name="crystallize_context",
        description="Extract and store key memories from a session summary",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_summary": {"type": "string"},
            },
            "required": ["session_summary"],
        },
    ),
    Tool(
        name="get_recent_activity",
        description="Get recent activity log entries",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "limit": {"type": "integer", "default": 15},
            },
            "required": [],
        },
    ),
    Tool(
        name="start_session",
        description="Start a new work session",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "iteration_id": {"type": "string", "description": "Iteration ID (optional)"},
                "title": {"type": "string", "description": "Session title"},
            },
            "required": ["title"],
        },
    ),
    Tool(
        name="complete_session",
        description="Complete a work session",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "summary": {"type": "string", "description": "Session summary"},
            },
            "required": ["session_id", "summary"],
        },
    ),
    Tool(
        name="get_session",
        description="Get session details",
        inputSchema={
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    ),
    Tool(
        name="list_sessions",
        description="List sessions with filters and pagination",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "iteration_id": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "completed"]},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
    ),
    Tool(
        name="list_tags",
        description="List all dimension tags for a project",
        inputSchema={
            "type": "object",
            "properties": {"project_id": {"type": "string"}},
            "required": [],
        },
    ),
    Tool(
        name="add_tag",
        description="Add a custom dimension tag",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string", "description": "Tag name (lowercase slug)"},
                "description": {"type": "string", "description": "Tag description"},
            },
            "required": ["name"],
        },
    ),
    Tool(
        name="get_preset_tags",
        description="Get the 7 preset dimension tags",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="add_conclusion",
        description="Add an analysis conclusion for a session",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "session_id": {"type": "string"},
                "tag_name": {"type": "string", "description": "Tag name"},
                "content": {"type": "string", "description": "Conclusion content"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium"},
                "merge_similar": {"type": "boolean", "default": True},
            },
            "required": ["session_id", "tag_name", "content"],
        },
    ),
    Tool(
        name="search_conclusions",
        description="Search conclusions by tag, query, confidence, or session",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "tag_names": {"type": "array", "items": {"type": "string"}},
                "session_id": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
                "offset": {"type": "integer", "default": 0},
            },
            "required": [],
        },
    ),
    Tool(
        name="get_session_conclusions",
        description="Get all conclusions for a session grouped by tag",
        inputSchema={
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    ),
    Tool(
        name="get_conclusion",
        description="Get a single conclusion by ID",
        inputSchema={
            "type": "object",
            "properties": {"conclusion_id": {"type": "integer"}},
            "required": ["conclusion_id"],
        },
    ),
    Tool(
        name="analyze_session",
        description="Analyze a completed session and store tagged conclusions",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "session_summary": {"type": "string"},
                "conclusions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tag_name": {"type": "string"},
                            "content": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["high", "medium", "low"], "default": "medium"},
                        },
                    },
                },
            },
            "required": ["session_id", "session_summary"],
        },
    ),
    Tool(
        name="find_similar_items",
        description="Find similar/duplicate memories or conclusions for dedup",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["memory", "conclusion"]},
                "tag_name": {"type": "string"},
                "threshold": {"type": "number", "default": 0.6},
                "limit": {"type": "integer", "default": 20},
            },
            "required": [],
        },
    ),
    Tool(
        name="merge_items",
        description="Merge two similar entities into one",
        inputSchema={
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": ["memory", "conclusion"]},
                "keep_id": {"type": "integer"},
                "remove_id": {"type": "integer"},
                "keep_content": {"type": "string", "description": "Final merged content (optional, auto-concatenates if not set)"},
            },
            "required": ["entity_type", "keep_id", "remove_id"],
        },
    ),
]

TOOL_HANDLERS: dict[str, Any] = {
    "find_or_create_project": find_or_create_project,
    "update_project": update_project,
    "get_project": get_project,
    "list_projects": list_projects,
    "set_active_project": set_active_project,
    "add_item": add_item,
    "update_item": update_item,
    "list_items": list_items,
    "get_item": get_item,
    "delete_item": delete_item,
    "create_iteration": create_iteration,
    "add_item_to_iteration": add_item_to_iteration,
    "remove_item_from_iteration": remove_item_from_iteration,
    "get_iteration": get_iteration,
    "list_iterations": list_iterations,
    "start_iteration": start_iteration,
    "complete_iteration": complete_iteration,
    "update_item_status": update_item_status,
    "start_item": start_item,
    "complete_item": complete_item,
    "reproduce_bug": reproduce_bug,
    "verify_bug": verify_bug,
    "get_active_iteration": get_active_iteration,
    "get_suggestions": get_suggestions,
    "get_summary": get_summary,
    "get_project_context": get_project_context,
    "add_memory_entry": add_memory_entry,
    "update_memory_entry": update_memory_entry,
    "search_memory": search_memory,
    "list_memory": list_memory,
    "crystallize_context": crystallize_context,
    "get_recent_activity": get_recent_activity,
    "start_session": start_session,
    "complete_session": complete_session,
    "get_session": get_session_,
    "list_sessions": list_sessions,
    "list_tags": list_tags,
    "add_tag": add_tag,
    "get_preset_tags": get_preset_tags,
    "add_conclusion": add_conclusion,
    "search_conclusions": search_conclusions,
    "get_session_conclusions": get_session_conclusions,
    "get_conclusion": get_conclusion,
    "analyze_session": analyze_session,
    "find_similar_items": find_similar_items,
    "merge_items": merge_items,
}


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            result = error_response("UNKNOWN_TOOL", f"Unknown tool: {name}")
        else:
            result = handler(**arguments)

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except ValueError as e:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    error_response("INVALID_ARGUMENT", str(e)), ensure_ascii=False
                ),
            )
        ]
    except Exception as e:
        logger.exception(f"Error calling tool {name}")
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    error_response("INTERNAL_ERROR", str(e)), ensure_ascii=False
                ),
            )
        ]


async def run_server():
    init_db()
    logger.info("Itera MCP Server starting")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import asyncio
    try:
        asyncio.run(run_server())
    finally:
        close_db()