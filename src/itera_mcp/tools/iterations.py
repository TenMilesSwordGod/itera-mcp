from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import generate_id, now_iso, make_response, error_response, model_to_dict
from ..enums import ItemType, IterationStatus
from ..models import Project, Iteration, Item
from .memory import log_activity
from .projects import _resolve_project_id


def create_iteration(
    project_id: str | None = None,
    name: str = "",
    goal: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    iteration_id = generate_id()
    now = now_iso()

    iteration = Iteration(
        id=iteration_id,
        project_id=project_id,
        name=name,
        goal=goal or "",
        start_date=start_date,
        end_date=end_date,
        status="planning",
        created_at=now,
        updated_at=now,
    )
    sess.add(iteration)
    sess.commit()

    logger.info(f"Created iteration: {name} ({iteration_id})")
    return make_response(model_to_dict(iteration))


def add_item_to_iteration(iteration_id: str, item_id: str) -> dict:
    sess = get_session()

    iteration = sess.get(Iteration, iteration_id)
    if not iteration:
        return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")

    item = sess.get(Item, item_id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {item_id} not found")
    if item.type != ItemType.REQUIREMENT:
        return error_response("INVALID_TYPE", "Only requirements can be added to iterations")
    if item.project_id != iteration.project_id:
        return error_response(
            "PROJECT_MISMATCH", "Item and iteration belong to different projects"
        )

    item.iteration_id = iteration_id
    item.updated_at = now_iso()
    sess.commit()

    log_activity(
        iteration.project_id,
        "add_item_to_iteration",
        f"Added item {item_id} to iteration {iteration_id}",
        item_id=item_id,
        iteration_id=iteration_id,
    )
    return make_response({"iteration_id": iteration_id, "item_id": item_id})


def remove_item_from_iteration(iteration_id: str, item_id: str) -> dict:
    sess = get_session()

    item = sess.execute(
        select(Item).where(
            Item.id == item_id,
            Item.iteration_id == iteration_id,
            Item.deleted == 0,
        )
    ).scalar_one_or_none()
    if not item:
        return error_response("NOT_FOUND", f"Item {item_id} not in iteration {iteration_id}")

    project_id = item.project_id
    item.iteration_id = None
    item.updated_at = now_iso()
    sess.commit()

    log_activity(
        project_id,
        "remove_item_from_iteration",
        f"Removed item {item_id} from iteration {iteration_id}",
        item_id=item_id,
        iteration_id=iteration_id,
    )
    return make_response({"iteration_id": iteration_id, "item_id": item_id, "removed": True})


def get_iteration(id: str) -> dict:
    sess = get_session()
    iteration = sess.get(Iteration, id)
    if not iteration:
        return error_response("NOT_FOUND", f"Iteration {id} not found")
    return make_response(model_to_dict(iteration))


def list_iterations(
    project_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    stmt = select(Iteration).where(Iteration.project_id == project_id)
    if status:
        stmt = stmt.where(Iteration.status == status)
    stmt = stmt.order_by(Iteration.created_at.desc()).limit(limit).offset(offset)
    rows = sess.execute(stmt).scalars().all()
    return make_response([model_to_dict(r) for r in rows])


def start_iteration(iteration_id: str) -> dict:
    sess = get_session()

    iteration = sess.get(Iteration, iteration_id)
    if not iteration:
        return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")

    if iteration.status == IterationStatus.ACTIVE:
        return make_response(model_to_dict(iteration))

    if iteration.status == IterationStatus.COMPLETED:
        return error_response("INVALID_STATUS", "Cannot start a completed iteration")

    project = sess.get(Project, iteration.project_id)
    if project.active_iteration_id and project.active_iteration_id != iteration_id:
        return error_response(
            "ACTIVE_ITERATION_EXISTS",
            f"Project already has an active iteration: {project.active_iteration_id}. Complete it first.",
        )

    now = now_iso()
    iteration.status = IterationStatus.ACTIVE
    iteration.updated_at = now
    project.active_iteration_id = iteration_id
    project.updated_at = now
    sess.commit()

    log_activity(
        project.id,
        "start_iteration",
        f"Started iteration: {iteration.name}",
        iteration_id=iteration_id,
    )
    logger.info(f"Started iteration: {iteration_id}")
    return make_response(model_to_dict(iteration))


def complete_iteration(iteration_id: str, force: bool = False) -> dict:
    sess = get_session()

    iteration = sess.get(Iteration, iteration_id)
    if not iteration:
        return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")

    if iteration.status == IterationStatus.COMPLETED:
        return make_response(model_to_dict(iteration))

    project = sess.get(Project, iteration.project_id)

    if not force:
        incomplete = sess.execute(
            select(Item).where(
                Item.iteration_id == iteration_id,
                Item.deleted == 0,
                Item.status != "done",
            )
        ).scalars().all()
        if len(incomplete) > 0:
            return error_response(
                "INCOMPLETE_ITEMS",
                f"Iteration has {len(incomplete)} incomplete items. Use force=true to override.",
            )

    now = now_iso()
    iteration.status = IterationStatus.COMPLETED
    iteration.updated_at = now
    project.active_iteration_id = None
    project.updated_at = now
    sess.commit()

    log_activity(
        project.id,
        "complete_iteration",
        f"Completed iteration: {iteration.name}",
        iteration_id=iteration_id,
    )
    logger.info(f"Completed iteration: {iteration_id}")
    return make_response(model_to_dict(iteration))