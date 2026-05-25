import json
from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import generate_id, now_iso, make_response, error_response, model_to_dict
from ..models import Project

_active_projects: dict[str, str] = {}


def set_active_project(project_id: str, session_id: str = "default") -> dict:
    sess = get_session()
    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")
    _active_projects[session_id] = project_id
    return make_response({"project_id": project_id, "name": project.name})


def _resolve_project_id(project_id: str | None, session_id: str | None) -> str:
    if project_id:
        return project_id
    if session_id and session_id in _active_projects:
        return _active_projects[session_id]
    raise ValueError("No project_id specified and no active project set")


def find_or_create_project(
    name: str,
    description: str | None = None,
    tech_stack: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict:
    sess = get_session()
    project = sess.execute(
        select(Project).where(Project.name == name)
    ).scalar_one_or_none()
    if project:
        return make_response(model_to_dict(project))

    project_id = generate_id()
    now = now_iso()
    tech_stack_json = json.dumps(tech_stack or [], ensure_ascii=False)
    constraints_json = json.dumps(constraints or [], ensure_ascii=False)

    project = Project(
        id=project_id,
        name=name,
        description=description or "",
        tech_stack=tech_stack_json,
        constraints=constraints_json,
        created_at=now,
        updated_at=now,
    )
    sess.add(project)
    sess.commit()

    logger.info(f"Created project: {name} ({project_id})")
    return make_response(model_to_dict(project))


def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    tech_stack: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict:
    sess = get_session()
    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if tech_stack is not None:
        project.tech_stack = json.dumps(tech_stack, ensure_ascii=False)
    if constraints is not None:
        project.constraints = json.dumps(constraints, ensure_ascii=False)

    projects_changed = name is not None or description is not None or tech_stack is not None or constraints is not None
    if not projects_changed:
        return make_response(model_to_dict(project))

    project.updated_at = now_iso()
    sess.commit()

    return make_response(model_to_dict(project))


def get_project(project_id: str) -> dict:
    sess = get_session()
    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")
    return make_response(model_to_dict(project))


def list_projects() -> dict:
    sess = get_session()
    rows = sess.execute(
        select(Project).order_by(Project.created_at.desc())
    ).scalars().all()
    return make_response([model_to_dict(r) for r in rows])