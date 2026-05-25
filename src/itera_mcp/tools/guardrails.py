from ..enums import (
    MAX_TAGS_PER_PROJECT,
    MAX_CUSTOM_TAGS_PER_SESSION,
    PRESET_TAG_NAMES,
)
from ..utils import error_response


def validate_tag_count(project_tag_count: int) -> dict | None:
    if project_tag_count >= MAX_TAGS_PER_PROJECT:
        return error_response("TAG_LIMIT_EXCEEDED", f"Project has reached max {MAX_TAGS_PER_PROJECT} tags")


def validate_custom_tags_per_session(new_custom_count: int, existing_custom_count: int) -> dict | None:
    if new_custom_count > MAX_CUSTOM_TAGS_PER_SESSION:
        return error_response("TOO_MANY_TAGS", f"Max {MAX_CUSTOM_TAGS_PER_SESSION} custom tags per session")


def validate_preset_tag_immutable(tag_name: str) -> dict | None:
    if tag_name in PRESET_TAG_NAMES:
        return error_response("PRESET_TAG_IMMUTABLE", f"Preset tag '{tag_name}' cannot be deleted")


def validate_session_immutable(status: str) -> dict | None:
    if status == "completed":
        return error_response("SESSION_IMMUTABLE", "Cannot modify a completed session")


def validate_active_session_exists(active_count: int) -> dict | None:
    if active_count > 0:
        return error_response("ACTIVE_SESSION_EXISTS", "Project already has an active session")


def validate_summary_not_empty(summary: str | None) -> dict | None:
    if not summary or not summary.strip():
        return error_response("MISSING_SUMMARY", "Summary cannot be empty")


def validate_conclusion_count(count: int) -> dict | None:
    if count > 10:
        return error_response("TOO_MANY_CONCLUSIONS", "Max 10 conclusions per analyze_session call")


def validate_search_limit(limit: int, max_limit: int = 50) -> int:
    return min(limit, max_limit)


def validate_list_limit(limit: int, max_limit: int = 100) -> int:
    return min(limit, max_limit)


def validate_tag_name(name: str) -> dict | None:
    if not name or not name.strip():
        return error_response("TAG_NAME_INVALID", "Tag name cannot be empty")
    for ch in name:
        if not (ch.islower() or ch == "-" or ch.isdigit()):
            return error_response("TAG_NAME_INVALID", f"Tag name must be lowercase slug: '{name}'")
    return None