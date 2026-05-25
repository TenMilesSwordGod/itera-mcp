import json
import pytest
from itera_mcp.tools.projects import find_or_create_project, get_project, update_project, list_projects, set_active_project, _resolve_project_id


def test_find_or_create_project_creates_when_not_exists(temp_db):
    res = find_or_create_project(
        "test-proj", "Test project", ["Python", "SQLite"], ["Use asyncio"]
    )
    assert res["success"] is True
    data = res["data"]
    assert data["name"] == "test-proj"
    assert data["id"] is not None


def test_find_or_create_project_finds_when_exists(temp_db):
    find_or_create_project("test-proj", "desc")
    res = find_or_create_project("test-proj", "other desc")
    assert res["success"] is True
    assert res["data"]["name"] == "test-proj"


def test_get_project_returns_correct_data(temp_db):
    created = find_or_create_project("test-proj", "Test desc")
    proj_id = created["data"]["id"]
    res = get_project(proj_id)
    assert res["success"] is True
    data = res["data"]
    assert data["id"] == proj_id
    assert data["name"] == "test-proj"


def test_get_project_fails_for_nonexistent(temp_db):
    res = get_project("non-existent-id")
    assert res["success"] is False


def test_update_project_updates_fields(temp_db):
    created = find_or_create_project("test-proj", "Old desc")
    proj_id = created["data"]["id"]
    res = update_project(proj_id, description="New desc", tech_stack=["Go"])
    assert res["success"] is True
    data = res["data"]
    assert json.loads(data["tech_stack"]) == ["Go"]
    assert data["description"] == "New desc"


def test_list_projects_returns_all(temp_db):
    find_or_create_project("proj1", "desc1")
    find_or_create_project("proj2", "desc2")
    res = list_projects()
    assert res["success"] is True
    assert len(res["data"]) == 2


def test_set_active_project_works_when_exists(temp_db):
    created = find_or_create_project("test-proj", "desc")
    proj_id = created["data"]["id"]
    res = set_active_project(proj_id, "session-1")
    assert res["success"] is True
    assert res["data"]["project_id"] == proj_id


def test_set_active_project_nonexistent(temp_db):
    res = set_active_project("nonexistent")
    assert res["success"] is False


def test_update_project_nonexistent(temp_db):
    res = update_project("nonexistent", description="x")
    assert res["success"] is False


def test_update_project_name_and_constraints(temp_db):
    created = find_or_create_project("test-proj", "desc")
    proj_id = created["data"]["id"]
    res = update_project(
        proj_id,
        name="new-name",
        constraints=["Use asyncio", "No sync HTTP"],
    )
    assert res["success"] is True
    d = res["data"]
    assert d["name"] == "new-name"
    assert json.loads(d["constraints"]) == ["Use asyncio", "No sync HTTP"]


def test_update_project_no_fields(temp_db):
    created = find_or_create_project("test-proj", "desc")
    proj_id = created["data"]["id"]
    res = update_project(proj_id)
    assert res["success"] is True


def test_resolve_project_id_explicit_project_id(temp_db):
    res = _resolve_project_id("explicit-id", "session-1")
    assert res == "explicit-id"


def test_resolve_project_id_from_active(temp_db):
    import itera_mcp.tools.projects as proj_module
    proj_module._active_projects["session-1"] = "active-proj-id"
    res = _resolve_project_id(None, "session-1")
    assert res == "active-proj-id"


def test_resolve_project_id_no_project_raises(temp_db):
    import itera_mcp.tools.projects as proj_module
    proj_module._active_projects.clear()
    with pytest.raises(ValueError):
        _resolve_project_id(None, None)
