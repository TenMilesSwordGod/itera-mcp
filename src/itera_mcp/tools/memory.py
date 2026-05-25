import json
from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import now_iso, make_response, error_response, jaccard_similarity
from ..enums import MemoryType, SIMILARITY_THRESHOLD
from ..models import Project, MemoryEntry, ActivityLog, Tag, MemoryTag
from .projects import _resolve_project_id


def add_memory_entry(
    project_id: str | None = None,
    type: str = "",
    content: str = "",
    tag_names: list[str] | None = None,
    merge_similar: bool = True,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    if type not in (MemoryType.FACT, MemoryType.DECISION, MemoryType.PITFALL, MemoryType.PREFERENCE):
        return error_response(
            "INVALID_TYPE",
            "type must be 'fact', 'decision', 'pitfall', or 'preference'",
        )

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    tag_ids = []
    if tag_names:
        for tn in tag_names:
            t = sess.execute(
                select(Tag).where(Tag.project_id == project_id, Tag.name == tn)
            ).scalar_one_or_none()
            if not t:
                return error_response("TAG_NOT_FOUND", f"Tag '{tn}' not found in project")
            tag_ids.append(t.id)

    if merge_similar:
        existing_rows = sess.execute(
            select(MemoryEntry).where(
                MemoryEntry.project_id == project_id, MemoryEntry.type == type
            )
        ).scalars().all()
        for existing in existing_rows:
            if jaccard_similarity(content, existing.content) >= SIMILARITY_THRESHOLD:
                merged_content = existing.content + "\n\n---\n\n" + content
                existing.content = merged_content
                existing.updated_at = now_iso()
                sess.commit()
                logger.info(f"Merged memory into #{existing.id} (similar content)")
                return make_response({
                    "id": existing.id,
                    "content": merged_content,
                    "merged_from": existing.id,
                })

    now = now_iso()
    entry = MemoryEntry(
        project_id=project_id,
        type=type,
        content=content,
        created_at=now,
        updated_at=now,
    )
    sess.add(entry)
    sess.flush()

    for tid in tag_ids:
        existing_mt = sess.get(MemoryTag, (entry.id, tid))
        if not existing_mt:
            sess.add(MemoryTag(memory_id=entry.id, tag_id=tid))
    sess.commit()

    result = {
        "id": entry.id,
        "project_id": entry.project_id,
        "type": entry.type,
        "content": entry.content,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }
    return make_response(result)


def update_memory_entry(id: int, content: str | None = None) -> dict:
    sess = get_session()
    entry = sess.get(MemoryEntry, id)
    if not entry:
        return error_response("NOT_FOUND", f"Memory entry {id} not found")

    if content is None or content == "":
        sess.delete(entry)
        sess.commit()
        return make_response({"id": id, "deleted": True})

    entry.content = content
    entry.updated_at = now_iso()
    sess.commit()

    return make_response({
        "id": entry.id,
        "project_id": entry.project_id,
        "type": entry.type,
        "content": entry.content,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    })


def search_memory(
    project_id: str | None = None,
    query: str = "",
    type: str | None = None,
    tag_names: list[str] | None = None,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    if tag_names:
        tag_ids_subq = select(Tag.id).where(
            Tag.project_id == project_id, Tag.name.in_(tag_names)
        ).subquery()
        stmt = (
            select(MemoryEntry)
            .join(MemoryTag, MemoryEntry.id == MemoryTag.memory_id, isouter=False)
            .where(MemoryEntry.project_id == project_id)
            .where(MemoryTag.tag_id.in_(tag_ids_subq))
            .where(MemoryEntry.content.ilike(f"%{query}%"))
        )
        if type:
            stmt = stmt.where(MemoryEntry.type == type)
        stmt = stmt.order_by(MemoryEntry.updated_at.desc()).limit(20)
        rows = sess.execute(stmt.distinct()).scalars().all()
        return make_response([
            {"id": r.id, "project_id": r.project_id, "type": r.type,
             "content": r.content, "created_at": r.created_at, "updated_at": r.updated_at}
            for r in rows
        ])

    stmt = (
        select(MemoryEntry)
        .where(MemoryEntry.project_id == project_id)
        .where(MemoryEntry.content.ilike(f"%{query}%"))
    )
    if type:
        stmt = stmt.where(MemoryEntry.type == type)
    stmt = stmt.order_by(MemoryEntry.updated_at.desc()).limit(20)
    rows = sess.execute(stmt).scalars().all()
    return make_response([
        {"id": r.id, "project_id": r.project_id, "type": r.type,
         "content": r.content, "created_at": r.created_at, "updated_at": r.updated_at}
        for r in rows
    ])


def list_memory(
    project_id: str | None = None,
    type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    stmt = select(MemoryEntry).where(MemoryEntry.project_id == project_id)
    if type:
        stmt = stmt.where(MemoryEntry.type == type)
    stmt = stmt.order_by(MemoryEntry.updated_at.desc()).limit(limit).offset(offset)
    rows = sess.execute(stmt).scalars().all()
    return make_response([
        {"id": r.id, "project_id": r.project_id, "type": r.type,
         "content": r.content, "created_at": r.created_at, "updated_at": r.updated_at}
        for r in rows
    ])


def crystallize_context(project_id: str | None = None, session_summary: str = "", session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    project = sess.get(Project, project_id)
    if not project:
        return error_response("NOT_FOUND", f"Project {project_id} not found")

    now = now_iso()
    entries_added = []

    extracted = _extract_memories(session_summary)

    for entry in extracted:
        mem = MemoryEntry(
            project_id=project_id,
            type=entry["type"],
            content=entry["content"],
            created_at=now,
            updated_at=now,
        )
        sess.add(mem)
        entries_added.append(entry)

    log = ActivityLog(
        project_id=project_id,
        timestamp=now,
        action="crystallize",
        summary=session_summary[:200],
        details=json.dumps(entries_added, ensure_ascii=False),
    )
    sess.add(log)
    sess.commit()

    logger.info(f"Crystallized {len(entries_added)} memories for project {project_id}")
    return make_response({"entries_added": len(entries_added), "entries": entries_added})


def _extract_memories(session_summary: str) -> list[dict]:
    entries = []

    keywords_map = {
        "fact": {"发现", "确认", "事实", "已知", "note", "fact"},
        "decision": {"决定", "选择", "采用", "决策", "decision", "choose"},
        "pitfall": {"踩坑", "错误", "失败", "问题", "教训", "bug", "error", "陷阱"},
        "preference": {"偏好", "喜欢", "希望", "习惯", "prefer", "style"},
    }

    lines = session_summary.replace("。", "。\n").replace(".", ".\n").replace(";", ";\n").split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 8:
            continue

        detected_type = None
        for mem_type, keywords in keywords_map.items():
            if any(kw in line.lower() for kw in keywords):
                detected_type = mem_type
                break

        if detected_type:
            entries.append({"type": detected_type, "content": line})

    if not entries:
        entries.append({"type": "fact", "content": session_summary[:200]})

    return entries


def get_recent_activity(project_id: str | None = None, limit: int = 15, session_id: str = "default") -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)
    stmt = (
        select(ActivityLog)
        .where(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
    )
    rows = sess.execute(stmt).scalars().all()
    return make_response([
        {
            "id": r.id,
            "project_id": r.project_id,
            "timestamp": r.timestamp,
            "session_id": r.session_id,
            "action": r.action,
            "summary": r.summary,
            "item_id": r.item_id,
            "iteration_id": r.iteration_id,
            "details": r.details,
        }
        for r in rows
    ])


def log_activity(
    project_id: str,
    action: str,
    summary: str | None = None,
    item_id: str | None = None,
    iteration_id: str | None = None,
    details: dict | None = None,
    session_id: str | None = None,
) -> None:
    sess = get_session()
    log = ActivityLog(
        project_id=project_id,
        timestamp=now_iso(),
        session_id=session_id,
        action=action,
        summary=summary,
        item_id=item_id,
        iteration_id=iteration_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )
    sess.add(log)
    sess.commit()