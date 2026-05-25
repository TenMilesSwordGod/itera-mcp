from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import now_iso, make_response, error_response, jaccard_similarity, model_to_dict
from ..enums import Confidence, PRESET_TAG_NAMES
from ..models import Session, Tag, Conclusion
from .projects import _resolve_project_id
from .memory import log_activity
from .guardrails import validate_conclusion_count, validate_search_limit


def add_conclusion(
    project_id: str | None = None,
    session_id: str = "",
    tag_name: str = "",
    content: str = "",
    confidence: str = "medium",
    merge_similar: bool = True,
    s_id: str = "default",
) -> dict:
    sess = get_session()
    if project_id:
        project_id = _resolve_project_id(project_id, s_id)

    s = sess.get(Session, session_id)
    if not s:
        return error_response("NOT_FOUND", f"Session {session_id} not found")
    project_id = s.project_id

    tag = sess.execute(
        select(Tag).where(Tag.project_id == project_id, Tag.name == tag_name)
    ).scalar_one_or_none()
    if not tag:
        return error_response("TAG_NOT_FOUND", f"Tag '{tag_name}' not found in project")

    if confidence not in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW):
        return error_response("INVALID_CONFIDENCE", "confidence must be 'high', 'medium', or 'low'")

    if not content.strip():
        return error_response("MISSING_FIELD", "content is required")

    now = now_iso()

    existing = sess.execute(
        select(Conclusion).where(
            Conclusion.session_id == session_id, Conclusion.tag_id == tag.id
        )
    ).scalar_one_or_none()

    if existing:
        existing.content = content
        existing.confidence = confidence
        existing.updated_at = now
        sess.commit()
        return make_response(model_to_dict(existing))

    if merge_similar:
        similar = sess.execute(
            select(Conclusion).where(
                Conclusion.project_id == project_id,
                Conclusion.tag_id == tag.id,
            )
        ).scalars().all()
        for sim in similar:
            if jaccard_similarity(content, sim.content) >= 0.6:
                sim.content = sim.content + "\n\n---\n\n" + content
                sim.confidence = max(confidence, sim.confidence)
                sim.updated_at = now
                sess.commit()
                logger.info(f"Merged conclusion into #{sim.id} (similar content)")
                data = model_to_dict(sim)
                data["merged_from"] = "existing"
                return make_response(data)

    c = Conclusion(
        project_id=project_id,
        session_id=session_id,
        tag_id=tag.id,
        content=content,
        confidence=confidence,
        created_at=now,
        updated_at=now,
    )
    sess.add(c)
    sess.commit()

    log_activity(project_id, "add_conclusion", f"Added conclusion for tag '{tag_name}'", session_id=session_id)
    logger.info(f"Added conclusion for tag '{tag_name}' in session {session_id}")
    return make_response(model_to_dict(c))


def search_conclusions(
    project_id: str | None = None,
    tag_names: list[str] | None = None,
    session_id: str | None = None,
    confidence: str | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
    s_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, s_id)

    limit = validate_search_limit(limit)
    stmt = select(Conclusion).where(Conclusion.project_id == project_id)

    if session_id:
        stmt = stmt.where(Conclusion.session_id == session_id)
    if confidence:
        stmt = stmt.where(Conclusion.confidence == confidence)

    if tag_names:
        tag_ids_subq = select(Tag.id).where(
            Tag.project_id == project_id, Tag.name.in_(tag_names)
        ).subquery()
        stmt = stmt.where(Conclusion.tag_id.in_(tag_ids_subq))

    rows = sess.execute(stmt).scalars().all()

    if query:
        rows = [r for r in rows if query.lower() in r.content.lower()]

    results = []
    for r in rows[offset : offset + limit]:
        tag = sess.get(Tag, r.tag_id)
        item_session = sess.get(Session, r.session_id)
        d = model_to_dict(r)
        d["tag_name"] = tag.name if tag else str(r.tag_id)
        d["tag_description"] = tag.description if tag else ""
        d["session_title"] = item_session.title if item_session else r.session_id
        results.append(d)

    return make_response(results)


def get_session_conclusions(session_id: str = "") -> dict:
    sess = get_session()
    s = sess.get(Session, session_id)
    if not s:
        return error_response("NOT_FOUND", f"Session {session_id} not found")

    rows = sess.execute(
        select(Conclusion).where(Conclusion.session_id == session_id)
    ).scalars().all()

    grouped: dict[str, list] = {}
    seen_tags: set[str] = set()
    for r in rows:
        tag = sess.get(Tag, r.tag_id)
        tag_name = tag.name if tag else str(r.tag_id)
        seen_tags.add(tag_name)
        if tag_name not in grouped:
            grouped[tag_name] = []
        grouped[tag_name].append({"id": r.id, "content": r.content, "confidence": r.confidence})

    result_list = [{"tag_name": k, "conclusions": v} for k, v in grouped.items()]
    missing_tags = [t for t in PRESET_TAG_NAMES if t not in seen_tags]

    return make_response(
        {"session_id": session_id, "conclusions": result_list, "missing_tags": missing_tags}
    )


def get_conclusion(conclusion_id: int = 0) -> dict:
    sess = get_session()
    c = sess.get(Conclusion, conclusion_id)
    if not c:
        return error_response("NOT_FOUND", f"Conclusion {conclusion_id} not found")

    tag = sess.get(Tag, c.tag_id)
    data = model_to_dict(c)
    data["tag_name"] = tag.name if tag else str(c.tag_id)
    return make_response(data)


def analyze_session(
    session_id: str = "",
    session_summary: str = "",
    conclusions: list[dict] | None = None,
) -> dict:
    sess = get_session()

    s = sess.get(Session, session_id)
    if not s:
        return error_response("NOT_FOUND", f"Session {session_id} not found")
    if s.status != "completed":
        return error_response("INVALID_STATUS", "Session must be completed before analysis")

    conclusions = conclusions or []
    err = validate_conclusion_count(len(conclusions))
    if err:
        return err

    added = 0
    seen_tags: set[str] = set()
    now = now_iso()

    for entry in conclusions:
        tag_name = entry.get("tag_name", "")
        content = entry.get("content", "")
        confidence = entry.get("confidence", "medium")

        if not tag_name or not content:
            continue

        tag = sess.execute(
            select(Tag).where(Tag.project_id == s.project_id, Tag.name == tag_name)
        ).scalar_one_or_none()
        if not tag:
            continue

        seen_tags.add(tag_name)

        existing = sess.execute(
            select(Conclusion).where(
                Conclusion.session_id == session_id, Conclusion.tag_id == tag.id
            )
        ).scalar_one_or_none()

        if existing:
            existing.content = content
            existing.confidence = confidence
            existing.updated_at = now
        else:
            c = Conclusion(
                project_id=s.project_id,
                session_id=session_id,
                tag_id=tag.id,
                content=content,
                confidence=confidence,
                created_at=now,
                updated_at=now,
            )
            sess.add(c)
        added += 1

    sess.commit()

    all_tags = sess.execute(
        select(Tag.name).where(Tag.project_id == s.project_id, Tag.is_preset == 1)
    ).scalars().all()
    missing_tags = [t for t in all_tags if t not in seen_tags]

    log_activity(
        s.project_id,
        "analyze_session",
        f"Analyzed session {session_id}: {added} conclusions",
        session_id=session_id,
    )
    logger.info(f"Analyzed session {session_id}: {added} conclusions, missing: {missing_tags}")
    return make_response(
        {"session_id": session_id, "conclusions_added": added, "missing_tags": missing_tags}
    )