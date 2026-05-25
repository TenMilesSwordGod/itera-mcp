from sqlalchemy import select, func, case

from ..database import get_session
from ..utils import make_response, error_response
from ..enums import IterationStatus, ItemType, Priority
from ..models import Project, Iteration, Item, ActivityLog, MemoryEntry
from .projects import _resolve_project_id


def get_active_iteration(project_id: str | None = None, session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    iteration = sess.execute(
        select(Iteration).where(
            Iteration.project_id == project_id,
            Iteration.status == IterationStatus.ACTIVE,
        )
    ).scalar_one_or_none()

    if not iteration:
        return error_response("NOT_FOUND", "No active iteration for this project")

    items = sess.execute(
        select(Item)
        .where(Item.iteration_id == iteration.id, Item.deleted == 0)
        .order_by(Item.priority.desc(), Item.created_at.asc())
    ).scalars().all()

    result = {
        "id": iteration.id,
        "project_id": iteration.project_id,
        "name": iteration.name,
        "goal": iteration.goal,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "status": iteration.status,
        "created_at": iteration.created_at,
        "updated_at": iteration.updated_at,
        "items": [
            {
                "id": item.id,
                "project_id": item.project_id,
                "type": item.type,
                "title": item.title,
                "summary": item.summary,
                "description": item.description,
                "priority": item.priority,
                "status": item.status,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "deleted": item.deleted,
                "completed_at": item.completed_at,
                "iteration_id": item.iteration_id,
                "acceptance_criteria": item.acceptance_criteria,
                "severity": item.severity,
                "steps_to_reproduce": item.steps_to_reproduce,
                "environment": item.environment,
                "verified": item.verified,
            }
            for item in items
        ],
    }
    return make_response(result)


def get_suggestions(project_id: str | None = None, limit: int = 5, session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    priority_order = case(
        (Item.priority == Priority.HIGH, 3),
        (Item.priority == Priority.MEDIUM, 2),
        (Item.priority == Priority.LOW, 1),
        else_=0,
    )
    bug_severity_order = case(
        (Item.type == ItemType.BUG, case(
            (Item.severity == "critical", 3),
            (Item.severity == "major", 2),
            (Item.severity == "minor", 1),
            else_=0,
        )),
        else_=0,
    )

    items = sess.execute(
        select(Item)
        .where(
            Item.project_id == project_id,
            Item.deleted == 0,
            Item.status.notin_(["done", "verified"]),
        )
        .order_by(priority_order.desc(), bug_severity_order.desc(), Item.created_at.asc())
        .limit(limit)
    ).scalars().all()

    return make_response([
        {
            "id": item.id, "project_id": item.project_id, "type": item.type,
            "title": item.title, "summary": item.summary, "description": item.description,
            "priority": item.priority, "status": item.status,
            "created_at": item.created_at, "updated_at": item.updated_at,
            "deleted": item.deleted, "completed_at": item.completed_at,
            "iteration_id": item.iteration_id, "acceptance_criteria": item.acceptance_criteria,
            "severity": item.severity, "steps_to_reproduce": item.steps_to_reproduce,
            "environment": item.environment, "verified": item.verified,
        }
        for item in items
    ])


def get_summary(project_id: str | None = None, session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    total_items = sess.execute(
        select(func.count()).select_from(Item).where(
            Item.project_id == project_id, Item.deleted == 0
        )
    ).scalar()

    todo_count = sess.execute(
        select(func.count()).select_from(Item).where(
            Item.project_id == project_id, Item.deleted == 0,
            Item.status.in_(["backlog", "todo"]),
        )
    ).scalar()

    in_progress_count = sess.execute(
        select(func.count()).select_from(Item).where(
            Item.project_id == project_id, Item.deleted == 0,
            Item.status == "in-progress",
        )
    ).scalar()

    bug_count = sess.execute(
        select(func.count()).select_from(Item).where(
            Item.project_id == project_id, Item.deleted == 0,
            Item.type == ItemType.BUG,
        )
    ).scalar()

    req_count = sess.execute(
        select(func.count()).select_from(Item).where(
            Item.project_id == project_id, Item.deleted == 0,
            Item.type == ItemType.REQUIREMENT,
        )
    ).scalar()

    active_iteration = sess.execute(
        select(Iteration).where(
            Iteration.project_id == project_id,
            Iteration.status == IterationStatus.ACTIVE,
        )
    ).scalar_one_or_none()

    return make_response({
        "project": {
            "id": project.id, "name": project.name, "description": project.description,
            "tech_stack": project.tech_stack, "constraints": project.constraints,
            "active_iteration_id": project.active_iteration_id,
            "created_at": project.created_at, "updated_at": project.updated_at,
        },
        "total_items": total_items,
        "todo_count": todo_count,
        "in_progress_count": in_progress_count,
        "requirement_count": req_count,
        "bug_count": bug_count,
        "active_iteration": {
            "id": active_iteration.id, "name": active_iteration.name,
        } if active_iteration else None,
    })


def get_project_context(project_id: str | None = None, session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    active_iteration = sess.execute(
        select(Iteration).where(
            Iteration.project_id == project_id,
            Iteration.status == IterationStatus.ACTIVE,
        )
    ).scalar_one_or_none()

    recent_activity = sess.execute(
        select(ActivityLog)
        .where(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(10)
    ).scalars().all()

    memories = sess.execute(
        select(MemoryEntry)
        .where(MemoryEntry.project_id == project_id)
        .order_by(MemoryEntry.updated_at.desc())
        .limit(5)
    ).scalars().all()

    todo_items = sess.execute(
        select(Item)
        .where(
            Item.project_id == project_id, Item.deleted == 0,
            Item.status.in_(["backlog", "todo", "in-progress"]),
        )
        .order_by(Item.priority.desc())
        .limit(10)
    ).scalars().all()

    return make_response({
        "project": {
            "id": project.id, "name": project.name, "description": project.description,
            "tech_stack": project.tech_stack, "constraints": project.constraints,
            "active_iteration_id": project.active_iteration_id,
            "created_at": project.created_at, "updated_at": project.updated_at,
        },
        "active_iteration": {
            "id": active_iteration.id, "name": active_iteration.name, "goal": active_iteration.goal,
            "start_date": active_iteration.start_date, "end_date": active_iteration.end_date,
            "status": active_iteration.status,
            "created_at": active_iteration.created_at, "updated_at": active_iteration.updated_at,
        } if active_iteration else None,
        "recent_activity": [
            {
                "id": a.id, "project_id": a.project_id, "timestamp": a.timestamp,
                "session_id": a.session_id, "action": a.action, "summary": a.summary,
                "item_id": a.item_id, "iteration_id": a.iteration_id, "details": a.details,
            }
            for a in recent_activity
        ],
        "key_memories": [
            {
                "id": m.id, "project_id": m.project_id, "type": m.type,
                "content": m.content, "created_at": m.created_at, "updated_at": m.updated_at,
            }
            for m in memories
        ],
        "pending_items": [
            {
                "id": item.id, "project_id": item.project_id, "type": item.type,
                "title": item.title, "summary": item.summary, "description": item.description,
                "priority": item.priority, "status": item.status,
                "created_at": item.created_at, "updated_at": item.updated_at,
                "deleted": item.deleted, "completed_at": item.completed_at,
                "iteration_id": item.iteration_id, "acceptance_criteria": item.acceptance_criteria,
                "severity": item.severity, "steps_to_reproduce": item.steps_to_reproduce,
                "environment": item.environment, "verified": item.verified,
            }
            for item in todo_items
        ],
    })