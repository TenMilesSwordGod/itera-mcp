from loguru import logger
from sqlalchemy import select, func

from ..database import get_session
from ..utils import now_iso, make_response, error_response, model_to_dict
from ..enums import PRESET_TAG_NAMES, PRESET_TAG_DESCRIPTIONS
from ..models import Tag
from .projects import _resolve_project_id
from .guardrails import validate_tag_count, validate_tag_name


def list_tags(project_id: str | None = None, session_id: str = "default") -> dict:
    session = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    rows = (
        session.execute(
            select(Tag)
            .where(Tag.project_id == project_id)
            .order_by(Tag.is_preset.desc(), Tag.name.asc())
        )
        .scalars()
        .all()
    )
    return make_response([model_to_dict(r) for r in rows])


def add_tag(
    project_id: str | None = None,
    name: str = "",
    description: str | None = None,
    session_id: str = "default",
) -> dict:
    session = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    err = validate_tag_name(name)
    if err:
        return err

    existing = session.execute(
        select(Tag).where(Tag.project_id == project_id, Tag.name == name)
    ).scalar_one_or_none()
    if existing:
        return error_response("TAG_EXISTS", f"Tag '{name}' already exists")

    count = session.execute(
        select(func.count()).select_from(Tag).where(Tag.project_id == project_id)
    ).scalar()
    err = validate_tag_count(count)
    if err:
        return err

    now = now_iso()
    tag = Tag(
        project_id=project_id,
        name=name,
        description=description,
        is_preset=0,
        created_at=now,
    )
    session.add(tag)
    session.commit()

    logger.info(f"Added tag '{name}' to project {project_id}")
    return make_response(model_to_dict(tag))


def get_preset_tags() -> dict:
    tags = [
        {"name": n, "description": PRESET_TAG_DESCRIPTIONS.get(n, "")}
        for n in PRESET_TAG_NAMES
    ]
    return make_response(tags)