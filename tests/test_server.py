import asyncio
import json
import pytest
from itera_mcp.server import TOOLS, handle_list_tools, handle_call_tool, TOOL_HANDLERS
from itera_mcp.tools.projects import find_or_create_project


@pytest.fixture
def temp_db_for_server(temp_db):
    yield temp_db


def test_handle_list_tools_returns_all_tools(temp_db_for_server):
    result = asyncio.run(handle_list_tools())
    assert len(result) == len(TOOLS)
    names = [t.name for t in result]
    assert "find_or_create_project" in names
    assert "add_item" in names
    assert "crystallize_context" in names


def test_handle_call_tool_unknown_tool(temp_db_for_server):
    result = asyncio.run(handle_call_tool("nonexistent_tool", {}))
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["success"] is False
    assert data["error"]["code"] == "UNKNOWN_TOOL"


def test_handle_call_tool_success(temp_db_for_server):
    result = asyncio.run(handle_call_tool("list_projects", {}))
    assert len(result) == 1
    data = json.loads(result[0].text)
    assert data["success"] is True


def test_handle_call_tool_success_with_args(temp_db_for_server):
    created = find_or_create_project("test-proj", "desc")
    result = asyncio.run(
        handle_call_tool("get_project", {"project_id": created["data"]["id"]})
    )
    data = json.loads(result[0].text)
    assert data["success"] is True
    assert data["data"]["name"] == "test-proj"


def test_handle_call_tool_invalid_arguments(temp_db_for_server):
    result = asyncio.run(
        handle_call_tool("set_active_project", {"project_id": "nonexistent"})
    )
    data = json.loads(result[0].text)
    assert data["success"] is False


def test_handle_call_tool_internal_error(temp_db_for_server):
    original = TOOL_HANDLERS["get_project"]

    def raise_runtime_error(**kwargs):
        raise RuntimeError("simulated internal error")

    TOOL_HANDLERS["get_project"] = raise_runtime_error

    try:
        result = asyncio.run(handle_call_tool("get_project", {"project_id": "x"}))
        data = json.loads(result[0].text)
        assert data["success"] is False
        assert data["error"]["code"] == "INTERNAL_ERROR"
    finally:
        TOOL_HANDLERS["get_project"] = original


def test_handle_call_tool_value_error(temp_db_for_server):
    original = TOOL_HANDLERS["set_active_project"]

    def raise_value_error(**kwargs):
        raise ValueError("bad argument passed")

    TOOL_HANDLERS["set_active_project"] = raise_value_error

    try:
        result = asyncio.run(handle_call_tool("set_active_project", {"project_id": "x"}))
        data = json.loads(result[0].text)
        assert data["success"] is False
        assert data["error"]["code"] == "INVALID_ARGUMENT"
    finally:
        TOOL_HANDLERS["set_active_project"] = original


def test_run_server_and_main_entry_points():
    from itera_mcp import server as server_module
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        db_path = Path(f.name)
        server_module.init_db(str(db_path))

        async def _test_run_server():
            import itera_mcp.server as sm
            from unittest.mock import AsyncMock, patch

            read_mock = AsyncMock()
            read_mock.receive = AsyncMock(side_effect=EOFError("stop"))

            write_mock = AsyncMock()

            mock_server_cm = AsyncMock()
            mock_server_cm.__aenter__ = AsyncMock(return_value=(read_mock, write_mock))
            mock_server_cm.__aexit__ = AsyncMock(return_value=None)

            with patch.object(sm, "stdio_server", return_value=mock_server_cm):
                await sm.run_server()

        asyncio.run(_test_run_server())
        server_module.close_db()


def test_main_function_wrapper():
    from itera_mcp import server as server_module
    import tempfile
    from pathlib import Path
    from unittest.mock import patch, AsyncMock
    import asyncio

    with tempfile.NamedTemporaryFile(suffix=".db", delete=True) as f:
        db_path = Path(f.name)
        server_module.init_db(str(db_path))

        read_mock = AsyncMock()
        read_mock.receive = AsyncMock(side_effect=EOFError("stop"))
        write_mock = AsyncMock()
        mock_server_cm = AsyncMock()
        mock_server_cm.__aenter__ = AsyncMock(return_value=(read_mock, write_mock))
        mock_server_cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_run(*args):
            server_module.init_db(str(db_path))
            with patch.object(server_module, "stdio_server", return_value=mock_server_cm):
                await server_module.run_server()

        with patch.object(asyncio, "run", side_effect=fake_run):
            server_module.main()

        server_module.close_db()