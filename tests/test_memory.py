from itera_mcp.tools.projects import find_or_create_project
from itera_mcp.tools.memory import (
    add_memory_entry,
    update_memory_entry,
    search_memory,
    list_memory,
    crystallize_context,
    get_recent_activity,
    log_activity,
)


def test_add_memory_entry_creates_record(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    res = add_memory_entry(proj_id, "fact", "This project uses SQLite")
    assert res["success"] is True
    assert res["data"]["type"] == "fact"
    assert res["data"]["content"] == "This project uses SQLite"
    assert res["data"]["id"] is not None


def test_update_memory_entry_modifies_or_deletes(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    created = add_memory_entry(proj_id, "decision", "Use Python")

    res = update_memory_entry(created["data"]["id"], "Use Python 3.11+")
    assert res["success"] is True
    assert res["data"]["content"] == "Use Python 3.11+"

    res2 = update_memory_entry(created["data"]["id"], "")
    assert res2["success"] is True
    assert res2["data"]["deleted"] is True


def test_search_memory_finds_by_keyword(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    add_memory_entry(proj_id, "fact", "SQLite is the database")
    add_memory_entry(proj_id, "pitfall", "Be careful with transactions")
    add_memory_entry(proj_id, "preference", "Use async everywhere")

    res = search_memory(proj_id, "SQLite")
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert "SQLite" in res["data"][0]["content"]


def test_search_memory_filters_by_type(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    add_memory_entry(proj_id, "fact", "SQLite is the database")
    add_memory_entry(proj_id, "pitfall", "SQLite has limits")

    res = search_memory(proj_id, "SQLite", type="pitfall")
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["type"] == "pitfall"


def test_list_memory_with_pagination(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    for i in range(5):
        add_memory_entry(proj_id, "fact", f"Fact {i}")

    res = list_memory(proj_id, limit=3)
    assert res["success"] is True
    assert len(res["data"]) == 3

    res2 = list_memory(proj_id, limit=5, offset=3)
    assert res2["success"] is True
    assert len(res2["data"]) == 2


def test_crystallize_context_extracts_entries(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    summary = "我们决定使用SQLite作为数据库。发现Python异步需要特别处理。偏好使用uv管理依赖。"
    res = crystallize_context(proj_id, summary)
    assert res["success"] is True
    assert res["data"]["entries_added"] > 0


def test_get_recent_activity_returns_entries(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]

    log_activity(proj_id, "create", "Created something", item_id="item-1")
    log_activity(proj_id, "update", "Updated something")

    res = get_recent_activity(proj_id)
    assert res["success"] is True
    assert len(res["data"]) == 2


def test_add_memory_invalid_type(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    res = add_memory_entry(proj_id, "invalid_type", "content")
    assert res["success"] is False
    assert res["error"]["code"] == "INVALID_TYPE"


def test_add_memory_nonexistent_project(temp_db):
    res = add_memory_entry("nonexistent", "fact", "content")
    assert res["success"] is False


def test_update_memory_nonexistent(temp_db):
    res = update_memory_entry(99999, "content")
    assert res["success"] is False


def test_crystallize_nonexistent_project(temp_db):
    res = crystallize_context("nonexistent", "summary")
    assert res["success"] is False


def test_crystallize_fallback_when_no_keywords(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    summary = "This is a random summary with no matching keywords at all"
    res = crystallize_context(proj_id, summary)
    assert res["success"] is True
    assert res["data"]["entries_added"] == 1
    assert res["data"]["entries"][0]["type"] == "fact"


def test_log_activity(temp_db):
    proj = find_or_create_project("test-proj", "desc")
    proj_id = proj["data"]["id"]
    from itera_mcp.tools.memory import log_activity

    log_activity(proj_id, "create_item", "Created a requirement", item_id="item-1", details={"key": "val"})
    res = get_recent_activity(proj_id)
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["action"] == "create_item"