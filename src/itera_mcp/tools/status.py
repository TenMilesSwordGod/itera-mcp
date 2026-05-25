from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import now_iso, make_response, error_response, model_to_dict
from ..enums import ItemType
from ..models import Item
from .memory import log_activity

REQUIREMENT_TRANSITIONS: dict[str, list[str]] = {
    "backlog": ["todo"],
    "todo": ["in-progress"],
    "in-progress": ["done"],
    "done": [],
}

BUG_TRANSITIONS: dict[str, list[str]] = {
    "backlog": ["todo"],
    "todo": ["in-progress"],
    "in-progress": ["reproduced"],
    "reproduced": ["verified"],
    "verified": ["done"],
    "done": [],
}


def _validate_transition(item_type: str, current: str, target: str) -> dict | None:
    transitions = REQUIREMENT_TRANSITIONS if item_type == ItemType.REQUIREMENT else BUG_TRANSITIONS
    allowed = transitions.get(current, [])
    if target not in allowed:
        return error_response(
            "INVALID_TRANSITION",
            f"Cannot transition {item_type} from '{current}' to '{target}'. "
            f"Allowed: {allowed}",
        )
    return None


def update_item_status(id: str, status: str) -> dict:
    sess = get_session()
    item = sess.get(Item, id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {id} not found")

    err = _validate_transition(item.type, item.status, status)
    if err:
        return err

    now = now_iso()
    item.status = status
    item.updated_at = now
    if status == "done":
        item.completed_at = now

    sess.commit()

    log_activity(item.project_id, "update_item_status", f"Status: {item.status}", item_id=id)
    logger.info(f"Updated item {id} status: {item.status} -> {status}")
    return make_response(model_to_dict(item))


def start_item(id: str) -> dict:
    sess = get_session()
    item = sess.get(Item, id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {id} not found")

    if item.status not in ("backlog", "todo"):
        return error_response(
            "INVALID_STATUS",
            f"Cannot start item in '{item.status}' status. Must be 'backlog' or 'todo'.",
        )

    item.status = "in-progress"
    item.updated_at = now_iso()
    sess.commit()

    log_activity(item.project_id, "start_item", f"Started: {item.title}", item_id=id)
    logger.info(f"Started item {id}: {item.status}")
    return make_response(model_to_dict(item))


def complete_item(id: str) -> dict:
    sess = get_session()
    item = sess.get(Item, id)
    if not item or item.deleted:
        return error_response("NOT_FOUND", f"Item {id} not found")

    if item.type == ItemType.REQUIREMENT:
        if item.status != "in-progress":
            return error_response(
                "INVALID_STATUS",
                f"Cannot complete requirement in '{item.status}' status.",
            )
        return update_item_status(id, "done")
    else:
        if item.status != "reproduced":
            return error_response(
                "INVALID_STATUS",
                f"Cannot complete bug in '{item.status}' status. Use verify_bug first.",
            )
        item.status = "verified"
        item.verified = 1
        item.updated_at = now_iso()
        sess.commit()
        log_activity(item.project_id, "complete_item", f"Completed bug: {item.title}", item_id=id)
        return make_response(model_to_dict(item))


def reproduce_bug(id: str) -> dict:
    sess = get_session()
    item = sess.execute(
        select(Item).where(Item.id == id, Item.deleted == 0, Item.type == ItemType.BUG)
    ).scalar_one_or_none()
    if not item:
        return error_response("NOT_FOUND", f"Bug {id} not found")

    if item.status != "in-progress":
        return error_response(
            "INVALID_STATUS",
            f"Cannot reproduce bug in '{item.status}' status.",
        )

    return update_item_status(id, "reproduced")


def verify_bug(id: str) -> dict:
    sess = get_session()
    item = sess.execute(
        select(Item).where(Item.id == id, Item.deleted == 0, Item.type == ItemType.BUG)
    ).scalar_one_or_none()
    if not item:
        return error_response("NOT_FOUND", f"Bug {id} not found")

    if item.status != "reproduced":
        return error_response(
            "INVALID_STATUS",
            f"Cannot verify bug in '{item.status}' status.",
        )

    item.status = "verified"
    item.verified = 1
    item.updated_at = now_iso()
    sess.commit()

    log_activity(item.project_id, "verify_bug", f"Verified bug: {item.title}", item_id=id)
    return make_response(model_to_dict(item))