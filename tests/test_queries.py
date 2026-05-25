from itera_mcp.tools.projects import find_or_create_project
from itera_mcp.tools.items import add_item
from itera_mcp.tools.iterations import create_iteration, start_iteration
from itera_mcp.tools.queries import (
    get_active_iteration,
    get_suggestions,
    get_summary,
    get_project_context,
)


def test_get_active_iteration_returns_items(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id)
    add_item(proj_id, "requirement", "Req 2", "summary", priority="high", iteration_id=iter_id)
    start_iteration(iter_id)

    res = get_active_iteration(proj_id)
    assert res["success"] is True
    assert "items" in res["data"]
    assert len(res["data"]["items"]) == 2


def test_get_suggestions_returns_prioritized(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    add_item(proj_id, "requirement", "Low req", "summary", priority="low", iteration_id=iter_id)
    add_item(proj_id, "requirement", "High req", "summary", priority="high", iteration_id=iter_id)
    add_item(proj_id, "bug", "Critical bug", "summary", severity="critical")

    res = get_suggestions(proj_id, limit=3)
    assert res["success"] is True
    assert len(res["data"]) <= 3
    assert res["data"][0]["priority"] == "high"


def test_get_summary_counts_correctly(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id)
    add_item(proj_id, "bug", "Bug 1", "summary", severity="minor")

    res = get_summary(proj_id)
    assert res["success"] is True
    assert res["data"]["total_items"] == 2
    assert res["data"]["requirement_count"] == 1
    assert res["data"]["bug_count"] == 1
    assert res["data"]["todo_count"] == 2


def test_get_project_context_includes_all_sections(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id)

    res = get_project_context(proj_id)
    assert res["success"] is True
    assert "project" in res["data"]
    assert "pending_items" in res["data"]
    assert "key_memories" in res["data"]
    assert "recent_activity" in res["data"]


def test_get_active_iteration_no_active(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    res = get_active_iteration(proj_id)
    assert res["success"] is False


def test_get_summary_nonexistent(temp_db):
    res = get_summary("nonexistent")
    assert res["success"] is False


def test_get_project_context_nonexistent(temp_db):
    res = get_project_context("nonexistent")
    assert res["success"] is False