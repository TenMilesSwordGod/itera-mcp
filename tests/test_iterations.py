from itera_mcp.tools.projects import find_or_create_project
from itera_mcp.tools.items import add_item
from itera_mcp.tools.iterations import (
    create_iteration,
    add_item_to_iteration,
    remove_item_from_iteration,
    get_iteration,
    list_iterations,
    start_iteration,
    complete_iteration,
)


def test_create_iteration_sets_planning_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    res = create_iteration(proj["data"]["id"], "Sprint 1", "Deliver feature X")
    assert res["success"] is True
    data = res["data"]
    assert data["status"] == "planning"
    assert data["name"] == "Sprint 1"


def test_get_iteration_returns_correct_data(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    created = create_iteration(proj["data"]["id"], "Sprint 1")
    res = get_iteration(created["data"]["id"])
    assert res["success"] is True
    assert res["data"]["name"] == "Sprint 1"


def test_list_iterations_filters_by_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    create_iteration(proj_id, "Sprint 1")
    create_iteration(proj_id, "Sprint 2")

    res = list_iterations(proj_id, status="planning")
    assert res["success"] is True
    assert len(res["data"]) == 2


def test_add_item_to_iteration_validates_type(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    req = add_item(
        proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id
    )
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="minor")

    res = add_item_to_iteration(iter_id, bug["data"]["id"])
    assert res["success"] is False
    assert "Only requirements" in res["error"]["message"]

    res2 = add_item_to_iteration(iter_id, req["data"]["id"])
    assert res2["success"] is True


def test_remove_item_from_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    req = add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id)
    res = remove_item_from_iteration(iter_id, req["data"]["id"])
    assert res["success"] is True
    assert res["data"]["removed"] is True


def test_start_iteration_enforces_single_active(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    i1 = create_iteration(proj_id, "Sprint 1")
    i2 = create_iteration(proj_id, "Sprint 2")

    res = start_iteration(i1["data"]["id"])
    assert res["success"] is True
    assert res["data"]["status"] == "active"

    res2 = start_iteration(i2["data"]["id"])
    assert res2["success"] is False
    assert "ACTIVE_ITERATION_EXISTS" in res2["error"]["code"]


def test_complete_iteration_checks_incomplete_items(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_id)
    start_iteration(iter_id)

    res = complete_iteration(iter_id)
    assert res["success"] is False
    assert "INCOMPLETE_ITEMS" in res["error"]["code"]

    res2 = complete_iteration(iter_id, force=True)
    assert res2["success"] is True
    assert res2["data"]["status"] == "completed"


def test_create_iteration_nonexistent_project(temp_db):
    res = create_iteration("nonexistent", "Sprint 1")
    assert res["success"] is False
    assert res["error"]["code"] == "NOT_FOUND"


def test_start_iteration_nonexistent(temp_db):
    res = start_iteration("nonexistent")
    assert res["success"] is False


def test_start_iteration_already_active(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]
    start_iteration(iter_id)
    res = start_iteration(iter_id)
    assert res["success"] is True


def test_start_completed_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]
    complete_iteration(iter_id, force=True)
    res = start_iteration(iter_id)
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_STATUS"


def test_complete_iteration_already_completed(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]
    complete_iteration(iter_id, force=True)
    res = complete_iteration(iter_id)
    assert res["success"] is True


def test_complete_iteration_nonexistent(temp_db):
    res = complete_iteration("nonexistent")
    assert res["success"] is False


def test_add_item_to_iteration_nonexistent_iteration(temp_db):
    res = add_item_to_iteration("nonexistent", "item-1")
    assert res["success"] is False


def test_add_item_to_iteration_nonexistent_item(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    iter_ = create_iteration(proj["data"]["id"], "Sprint 1")
    res = add_item_to_iteration(iter_["data"]["id"], "nonexistent")
    assert res["success"] is False


def test_add_item_to_iteration_project_mismatch(temp_db):
    p1 = find_or_create_project("proj1", "desc")
    p2 = find_or_create_project("proj2", "desc")
    iter_ = create_iteration(p1["data"]["id"], "Sprint 1")
    iter2 = create_iteration(p2["data"]["id"], "Sprint 2")
    req = add_item(p2["data"]["id"], "requirement", "R1", "s", iteration_id=iter2["data"]["id"])
    res = add_item_to_iteration(iter_["data"]["id"], req["data"]["id"])
    assert res["success"] is False
    assert res["error"]["code"] == "PROJECT_MISMATCH"


def test_remove_item_from_iteration_nonexistent(temp_db):
    res = remove_item_from_iteration("nonexistent", "item-1")
    assert res["success"] is False


def test_get_iteration_nonexistent(temp_db):
    res = get_iteration("nonexistent")
    assert res["success"] is False