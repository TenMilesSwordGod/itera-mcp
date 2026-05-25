from itera_mcp.tools.projects import find_or_create_project
from itera_mcp.tools.items import add_item, get_item, update_item, list_items, delete_item
from itera_mcp.tools.iterations import create_iteration


def test_add_invalid_priority(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    res = add_item(proj_id, "bug", "t", "s", priority="urgent")
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_PRIORITY"


def test_add_requirement_item_requires_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    res = add_item(
        project_id=proj_id,
        type="requirement",
        title="Test requirement",
        summary="Short summary",
        description="Some longer description",
        priority="high",
    )
    assert res["success"] is False
    assert "iteration_id is required" in res["error"]["message"]


def test_add_valid_requirement_creates(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    iter_id = iter_["data"]["id"]

    res = add_item(
        project_id=proj_id,
        type="requirement",
        title="Add pagination",
        summary="Implement pagination for list items",
        description="Longer text here",
        priority="high",
        iteration_id=iter_id,
        acceptance_criteria=["page param works", "limit works"],
    )
    assert res["success"] is True
    data = res["data"]
    assert data["title"] == "Add pagination"
    assert data["type"] == "requirement"


def test_add_bug_with_severity_creates(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    res = add_item(
        project_id=proj_id,
        type="bug",
        title="Crash on null",
        summary="Null pointer when title empty",
        severity="major",
        environment="Linux Python 3.11",
    )
    assert res["success"] is True
    assert res["data"]["severity"] == "major"


def test_get_item_returns_correct_data(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")

    created = add_item(
        project_id=proj_id,
        type="requirement",
        title="Test",
        summary="summary",
        iteration_id=iter_["data"]["id"],
    )
    item_id = created["data"]["id"]

    res = get_item(item_id)
    assert res["success"] is True
    assert res["data"]["id"] == item_id


def test_update_item_modifies_fields(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")

    created = add_item(
        project_id=proj_id,
        type="requirement",
        title="Old title",
        summary="old summary",
        iteration_id=iter_["data"]["id"],
    )
    item_id = created["data"]["id"]

    res = update_item(item_id, title="New title", priority="low")
    assert res["success"] is True
    data = res["data"]
    assert data["title"] == "New title"
    assert data["priority"] == "low"


def test_list_items_filters_by_type(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")

    add_item(proj_id, "requirement", "Req 1", "sum1", iteration_id=iter_["data"]["id"])
    add_item(proj_id, "bug", "Bug 1", "sum2", severity="minor")

    res = list_items(proj_id, type="requirement")
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["type"] == "requirement"


def test_delete_item_soft_deletes(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    created = add_item(
        proj_id, "requirement", "To delete", "summary", iteration_id=iter_["data"]["id"]
    )

    res = delete_item(created["data"]["id"])
    assert res["success"] is True

    res2 = list_items(proj_id, include_deleted=False)
    assert len(res2["data"]) == 0

    res3 = list_items(proj_id, include_deleted=True)
    assert len(res3["data"]) == 1


def test_add_item_validates_type_and_priority(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    res = add_item(project_id=proj_id, type="invalid", title="t", summary="s")
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_TYPE"


def test_add_item_nonexistent_project(temp_db):
    res = add_item(project_id="nonexistent", type="bug", title="t", summary="s")
    assert res["success"] is False
    assert res["error"]["code"] == "NOT_FOUND"


def test_add_item_invalid_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    res = add_item(proj_id, "requirement", "t", "s", iteration_id="nonexistent")
    assert res["success"] is False
    assert res["error"]["code"] == "NOT_FOUND"


def test_add_item_iteration_project_mismatch(temp_db):
    p1 = find_or_create_project("proj1", "desc")
    p2 = find_or_create_project("proj2", "desc")
    iter_ = create_iteration(p1["data"]["id"], "Sprint 1")
    res = add_item(p2["data"]["id"], "requirement", "t", "s", iteration_id=iter_["data"]["id"])
    assert res["success"] is False
    assert res["error"]["code"] == "PROJECT_MISMATCH"


def test_update_item_nonexistent(temp_db):
    res = update_item("nonexistent", title="x")
    assert res["success"] is False
    assert res["error"]["code"] == "NOT_FOUND"


def test_update_item_invalid_priority(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    created = add_item(proj_id, "requirement", "t", "s", iteration_id=iter_["data"]["id"])
    res = update_item(created["data"]["id"], priority="urgent")
    assert res["success"] is False


def test_update_item_invalid_severity(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "t", "s", severity="minor")
    res = update_item(bug["data"]["id"], severity="catastrophic")
    assert res["success"] is False


def test_update_item_no_fields(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    created = add_item(proj_id, "requirement", "t", "s", iteration_id=iter_["data"]["id"])
    res = update_item(created["data"]["id"])
    assert res["success"] is True


def test_list_items_filters_by_status_and_priority(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    add_item(proj_id, "requirement", "high", "s", priority="high", iteration_id=iter_["data"]["id"])
    add_item(proj_id, "requirement", "low", "s", priority="low", iteration_id=iter_["data"]["id"])

    res = list_items(proj_id, priority="high")
    assert len(res["data"]) == 1

    res2 = list_items(proj_id, status="backlog")
    assert len(res2["data"]) == 2


def test_get_item_nonexistent(temp_db):
    res = get_item("nonexistent")
    assert res["success"] is False


def test_delete_item_already_deleted(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    created = add_item(proj_id, "requirement", "t", "s", iteration_id=iter_["data"]["id"])
    delete_item(created["data"]["id"])
    res = delete_item(created["data"]["id"])
    assert res["success"] is False


def test_list_items_pagination(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    for i in range(5):
        add_item(proj_id, "requirement", f"Req {i}", f"s{i}", iteration_id=iter_["data"]["id"])

    res = list_items(proj_id, limit=2, offset=0)
    assert len(res["data"]) == 2
    res2 = list_items(proj_id, limit=2, offset=3)
    assert len(res2["data"]) == 2


def test_list_items_by_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter_ = create_iteration(proj_id, "Sprint 1")
    add_item(proj_id, "requirement", "R1", "s1", iteration_id=iter_["data"]["id"])
    add_item(proj_id, "bug", "B1", "s2")

    res = list_items(proj_id, iteration_id=iter_["data"]["id"])
    assert len(res["data"]) == 1
    assert res["data"][0]["type"] == "requirement"


def test_update_item_all_fields(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    bug = add_item(proj_id, "bug", "Bug", "summary", severity="minor")
    bug_id = bug["data"]["id"]

    res = update_item(
        bug_id,
        title="New title",
        summary="new summary",
        description="desc",
        priority="high",
        status="in-progress",
        severity="critical",
        steps_to_reproduce="step1",
        environment="Linux",
        verified=1,
    )
    assert res["success"] is True
    d = res["data"]
    assert d["title"] == "New title"
    assert d["summary"] == "new summary"
    assert d["priority"] == "high"
    assert d["severity"] == "critical"
    assert d["steps_to_reproduce"] == "step1"
    assert d["environment"] == "Linux"
    assert d["verified"] == 1


def test_update_item_acceptance_criteria_and_iteration(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    iter1 = create_iteration(proj_id, "Sprint 1")
    iter2 = create_iteration(proj_id, "Sprint 2")
    req = add_item(proj_id, "requirement", "Req", "summary", iteration_id=iter1["data"]["id"])

    res = update_item(
        req["data"]["id"],
        iteration_id=iter2["data"]["id"],
        acceptance_criteria=["criterion 1", "criterion 2"],
    )
    assert res["success"] is True


def test_add_item_invalid_bug_severity(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    res = add_item(proj_id, "bug", "t", "s", severity="catastrophic")
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_SEVERITY"
