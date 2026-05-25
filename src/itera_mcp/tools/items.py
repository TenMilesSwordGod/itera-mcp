import json
from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import generate_id, now_iso, make_response, error_response, model_to_dict
from ..enums import ItemType, Priority, Severity
from ..models import Project, Iteration, Item
from .memory import log_activity
from .projects import _resolve_project_id


def add_item(
    project_id: str | None = None,
    type: str = "",
    title: str = "",
    summary: str = "",
    description: str | None = None,
    priority: str = "medium",
    iteration_id: str | None = None,
    acceptance_criteria: list[str] | None = None,
    severity: str | None = None,
    steps_to_reproduce: str | None = None,
    environment: str | None = None,
    session_id: str = "default",
) -> dict:
    session = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    if type not in (ItemType.REQUIREMENT, ItemType.BUG):
        return error_response("INVALID_TYPE", "type must be 'requirement' or 'bug'")

    if priority not in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
        return error_response("INVALID_PRIORITY", "priority must be 'high', 'medium', or 'low'")

    project = session.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    if type == ItemType.REQUIREMENT:
        if not iteration_id:
            return error_response("MISSING_FIELD", "iteration_id is required for requirements")
        iteration = session.get(Iteration, iteration_id)
        if not iteration:
            return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")
        if iteration.project_id != project_id:
            return error_response(
                "PROJECT_MISMATCH", "Iteration does not belong to the specified project"
            )

    if type == ItemType.BUG and severity and severity not in (Severity.CRITICAL, Severity.MAJOR, Severity.MINOR):
        return error_response("INVALID_SEVERITY", "severity must be 'critical', 'major', or 'minor'")

    item_id = generate_id()
    now = now_iso()
    acceptance_json = json.dumps(acceptance_criteria or [], ensure_ascii=False)

    item = Item(
        id=item_id,
        project_id=project_id,
        type=type,
        title=title,
        summary=summary,
        description=description or "",
        priority=priority,
        status="backlog",
        created_at=now,
        updated_at=now,
        iteration_id=iteration_id,
        acceptance_criteria=acceptance_json,
        severity=severity,
        steps_to_reproduce=steps_to_reproduce or "",
        environment=environment or "",
    )
    session.add(item)
    session.commit()

    result = model_to_dict(item)
    log_activity(item.project_id, "add_item", f"Created {item.type}: {item.title}", item_id=item.id)
    logger.info(f"Created item: {title} ({item_id})")
    return make_response(result)


def update_item(
    id: str,
    title: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    iteration_id: str | None = None,
    acceptance_criteria: list[str] | None = None,
    severity: str | None = None,
    steps_to_reproduce: str | None = None,
    environment: str | None = None,
    verified: int | None = None,
) -> dict:
    session = get_session()
    item = session.get(Item, id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {id} not found")

    if priority is not None:
        if priority not in (Priority.HIGH, Priority.MEDIUM, Priority.LOW):
            return error_response("INVALID_PRIORITY", "priority must be 'high', 'medium', or 'low'")
        item.priority = priority
    if title is not None:
        item.title = title
    if summary is not None:
        item.summary = summary
    if description is not None:
        item.description = description
    if status is not None:
        item.status = status
    if iteration_id is not None:
        if iteration_id:
            iteration = session.get(Iteration, iteration_id)
            if not iteration:
                return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")
            if iteration.project_id != item.project_id:
                return error_response(
                    "PROJECT_MISMATCH", "Iteration does not belong to the item's project"
                )
        item.iteration_id = iteration_id if iteration_id else None
    if acceptance_criteria is not None:
        item.acceptance_criteria = json.dumps(acceptance_criteria, ensure_ascii=False)
    if severity is not None:
        if severity not in (Severity.CRITICAL, Severity.MAJOR, Severity.MINOR):
            return error_response("INVALID_SEVERITY", "severity must be 'critical', 'major', or 'minor'")
        item.severity = severity
    if steps_to_reproduce is not None:
        item.steps_to_reproduce = steps_to_reproduce
    if environment is not None:
        item.environment = environment
    if verified is not None:
        item.verified = verified

    item.updated_at = now_iso()
    session.commit()

    log_activity(item.project_id, "update_item", f"Updated item: {item.title}", item_id=item.id)
    result = model_to_dict(item)
    return make_response(result)


def list_items(
    project_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    iteration_id: str | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    session_id: str = "default",
) -> dict:
    session = get_session()
    project_id = _resolve_project_id(project_id, session_id)
    stmt = select(Item).where(Item.project_id == project_id)

    if not include_deleted:
        stmt = stmt.where(Item.deleted == 0)
    if type:
        stmt = stmt.where(Item.type == type)
    if status:
        stmt = stmt.where(Item.status == status)
    if priority:
        stmt = stmt.where(Item.priority == priority)
    if iteration_id is not None:
        stmt = stmt.where(Item.iteration_id == iteration_id)

    stmt = stmt.order_by(Item.created_at.desc()).limit(limit).offset(offset)
    rows = session.execute(stmt).scalars().all()
    return make_response([model_to_dict(r) for r in rows])


def get_item(id: str) -> dict:
    session = get_session()
    item = session.get(Item, id)
    if not item:
        return error_response("NOT_FOUND", f"Item {id} not found")
    return make_response(model_to_dict(item))


def delete_item(id: str) -> dict:
    session = get_session()
    item = session.get(Item, id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {id} not found")
    item.deleted = 1
    item.updated_at = now_iso()
    session.commit()
    log_activity(item.project_id, "delete_item", f"Deleted item: {item.title}", item_id=item.id)
    logger.info(f"Soft-deleted item: {id}")
    return make_response({"id": id, "deleted": True})