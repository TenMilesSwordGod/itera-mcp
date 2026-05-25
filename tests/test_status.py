from itera_mcp.tools.projects import find_or_create_project
from itera_mcp.tools.items import add_item, delete_item
from itera_mcp.tools.iterations import create_iteration
from itera_mcp.tools.status import (
    start_item,
    complete_item,
    reproduce_bug,
    verify_bug,
    update_item_status,
)


def test_start_item_transitions_to_in_progress(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(
        proj_id, "requirement", "Req 1", "summary",
        iteration_id=iter_["data"]["id"],
    )
    req_id = req["data"]["id"]

    res = start_item(req_id)
    assert res["success"] is True
    assert res["data"]["status"] == "in-progress"


def test_complete_requirement_to_done(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(
        proj_id, "requirement", "Req 1", "summary",
        iteration_id=iter_["data"]["id"],
    )
    req_id = req["data"]["id"]
    start_item(req_id)

    res = complete_item(req_id)
    assert res["success"] is True
    assert res["data"]["status"] == "done"
    assert res["data"]["completed_at"] is not None


def test_bug_lifecycle_reproduce_verify(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="major")
    bug_id = bug["data"]["id"]

    start_item(bug_id)

    res = reproduce_bug(bug_id)
    assert res["success"] is True
    assert res["data"]["status"] == "reproduced"

    res2 = verify_bug(bug_id)
    assert res2["success"] is True
    assert res2["data"]["status"] == "verified"
    assert res2["data"]["verified"] == 1


def test_update_item_status_validates_transition(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(
        proj_id, "requirement", "Req 1", "summary",
        iteration_id=iter_["data"]["id"],
    )
    req_id = req["data"]["id"]

    res = update_item_status(req_id, "done")
    assert res["success"] is False
    assert "INVALID_TRANSITION" in res["error"]["code"]

    update_item_status(req_id, "todo")
    update_item_status(req_id, "in-progress")
    res3 = update_item_status(req_id, "done")
    assert res3["success"] is True
    assert res3["data"]["status"] == "done"


def test_start_item_nonexistent(temp_db):
    res = start_item("nonexistent")
    assert res["success"] is False


def test_start_item_invalid_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_["data"]["id"])
    req_id = req["data"]["id"]
    update_item_status(req_id, "todo")
    update_item_status(req_id, "in-progress")

    res = start_item(req_id)
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_STATUS"


def test_complete_item_nonexistent(temp_db):
    res = complete_item("nonexistent")
    assert res["success"] is False


def test_complete_item_invalid_status_requirement(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(proj_id, "requirement", "Req 1", "summary", iteration_id=iter_["data"]["id"])
    res = complete_item(req["data"]["id"])
    assert res["success"] is False


def test_reproduce_bug_nonexistent(temp_db):
    res = reproduce_bug("nonexistent")
    assert res["success"] is False


def test_reproduce_bug_invalid_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="major")
    res = reproduce_bug(bug["data"]["id"])
    assert res["success"] is False


def test_verify_bug_nonexistent(temp_db):
    res = verify_bug("nonexistent")
    assert res["success"] is False


def test_verify_bug_invalid_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="major")
    res = verify_bug(bug["data"]["id"])
    assert res["success"] is False


def test_complete_bug_invalid_status(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="major")
    res = complete_item(bug["data"]["id"])
    assert res["success"] is False


def test_complete_item_bug_full_lifecycle(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug 1", "summary", severity="major")
    bug_id = bug["data"]["id"]

    start_item(bug_id)
    reproduce_bug(bug_id)
    complete_item(bug_id)


def test_update_item_status_on_deleted_item(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    req = add_item(proj_id, "requirement", "Req", "s", iteration_id=iter_["data"]["id"])
    delete_item(req["data"]["id"])

    res = update_item_status(req["data"]["id"], "todo")
    assert res["success"] is False