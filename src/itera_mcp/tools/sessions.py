from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import generate_id, now_iso, make_response, error_response, model_to_dict
from ..enums import SessionStatus
from ..models import Project, Iteration, Session
from .projects import _resolve_project_id
from .memory import log_activity
from .guardrails import (
    validate_active_session_exists,
    validate_session_immutable,
    validate_summary_not_empty,
    validate_list_limit,
)


def start_session(
    project_id: str | None = None,
    iteration_id: str | None = None,
    title: str = "",
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    if not title.strip():
        return error_response("MISSING_FIELD", "title is required")

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    if iteration_id:
        iteration = sess.get(Iteration, iteration_id)
        if not iteration:
            return error_response("NOT_FOUND", f"Iteration {iteration_id} not found")
        if iteration.project_id != project_id:
            return error_response("PROJECT_MISMATCH", "Iteration does not belong to this project")

    active_count = sess.execute(
        select(Session).where(
            Session.project_id == project_id, Session.status == SessionStatus.ACTIVE
        )
    ).scalars().all()
    err = validate_active_session_exists(len(list(active_count)))
    if err:
        return err

    sid = generate_id()
    now = now_iso()
    s = Session(
        id=sid,
        project_id=project_id,
        iteration_id=iteration_id,
        title=title,
        status=SessionStatus.ACTIVE,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    sess.add(s)
    sess.commit()

    log_activity(project_id, "start_session", f"Started session: {title}", session_id=sid)
    logger.info(f"Started session: {title} ({sid})")
    return make_response(model_to_dict(s))


def complete_session(
    session_id: str = "",
    summary: str = "",
) -> dict:
    sess = get_session()

    s = sess.get(Session, session_id)
    if not s:
        return error_response("NOT_FOUND", f"Session {session_id} not found")

    err = validate_session_immutable(s.status)
    if err:
        return err
    err = validate_summary_not_empty(summary)
    if err:
        return err

    now = now_iso()
    s.status = SessionStatus.COMPLETED
    s.summary = summary
    s.completed_at = now
    s.updated_at = now
    sess.commit()

    log_activity(s.project_id, "complete_session", f"Completed session: {s.title}", session_id=session_id)
    logger.info(f"Completed session: {session_id}")
    return make_response(model_to_dict(s))


def get_session_(session_id: str = "") -> dict:
    sess = get_session()
    s = sess.get(Session, session_id)
    if not s:
        return error_response("NOT_FOUND", f"Session {session_id} not found")

    from ..models import Conclusion
    conclusion_count = sess.execute(
        select(Conclusion).where(Conclusion.session_id == session_id)
    ).scalars().all()

    data = model_to_dict(s)
    data["conclusion_count"] = len(list(conclusion_count))
    return make_response(data)


def list_sessions(
    project_id: str | None = None,
    iteration_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    limit = validate_list_limit(limit)
    stmt = select(Session).where(Session.project_id == project_id)
    if iteration_id is not None:
        stmt = stmt.where(Session.iteration_id == iteration_id)
    if status:
        stmt = stmt.where(Session.status == status)

    stmt = stmt.order_by(Session.created_at.desc()).limit(limit).offset(offset)
    rows = sess.execute(stmt).scalars().all()
    return make_response([model_to_dict(r) for r in rows])