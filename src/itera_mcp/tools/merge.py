from loguru import logger
from sqlalchemy import select

from ..database import get_session
from ..utils import now_iso, make_response, error_response, jaccard_similarity
from ..models import MemoryEntry, Conclusion, Tag, MergeLog
from .projects import _resolve_project_id


def find_similar_items(
    project_id: str | None = None,
    entity_type: str | None = None,
    tag_name: str | None = None,
    threshold: float = 0.6,
    limit: int = 20,
    session_id: str = "default",
) -> dict:
    sess = get_session()
    project_id = _resolve_project_id(project_id, session_id)

    results = []

    if not entity_type or entity_type == "memory":
        all_mems = sess.execute(
            select(MemoryEntry).where(MemoryEntry.project_id == project_id)
        ).scalars().all()
        for i in range(len(all_mems)):
            for j in range(i + 1, len(all_mems)):
                if all_mems[i].type != all_mems[j].type:
                    continue
                sim = jaccard_similarity(all_mems[i].content, all_mems[j].content)
                if sim >= threshold:
                    a, b = all_mems[i], all_mems[j]
                    keep = "keep_a" if len(a.content) >= len(b.content) else "keep_b"
                    results.append({
                        "type": "memory",
                        "item_a": {"id": a.id, "content_snippet": a.content[:100], "created_at": a.created_at},
                        "item_b": {"id": b.id, "content_snippet": b.content[:100], "created_at": b.created_at},
                        "similarity": round(sim, 3),
                        "suggestion": keep,
                    })

    if not entity_type or entity_type == "conclusion":
        if tag_name:
            tag = sess.execute(
                select(Tag).where(Tag.project_id == project_id, Tag.name == tag_name)
            ).scalar_one_or_none()
            if tag:
                all_concs = sess.execute(
                    select(Conclusion).where(
                        Conclusion.project_id == project_id, Conclusion.tag_id == tag.id
                    )
                ).scalars().all()
                for i in range(len(all_concs)):
                    for j in range(i + 1, len(all_concs)):
                        sim = jaccard_similarity(all_concs[i].content, all_concs[j].content)
                        if sim >= threshold:
                            a, b = all_concs[i], all_concs[j]
                            keep = "keep_a" if len(a.content) >= len(b.content) else "keep_b"
                            results.append({
                                "type": "conclusion",
                                "item_a": {"id": a.id, "content_snippet": a.content[:100], "created_at": a.created_at},
                                "item_b": {"id": b.id, "content_snippet": b.content[:100], "created_at": b.created_at},
                                "similarity": round(sim, 3),
                                "suggestion": keep,
                            })
        else:
            all_tags = sess.execute(
                select(Tag).where(Tag.project_id == project_id)
            ).scalars().all()
            for tag in all_tags:
                tag_concs = sess.execute(
                    select(Conclusion).where(
                        Conclusion.project_id == project_id, Conclusion.tag_id == tag.id
                    )
                ).scalars().all()
                for i in range(len(tag_concs)):
                    for j in range(i + 1, len(tag_concs)):
                        sim = jaccard_similarity(tag_concs[i].content, tag_concs[j].content)
                        if sim >= threshold:
                            a, b = tag_concs[i], tag_concs[j]
                            keep = "keep_a" if len(a.content) >= len(b.content) else "keep_b"
                            results.append({
                                "type": "conclusion",
                                "item_a": {"id": a.id, "content_snippet": a.content[:100], "created_at": a.created_at},
                                "item_b": {"id": b.id, "content_snippet": b.content[:100], "created_at": b.created_at},
                                "similarity": round(sim, 3),
                                "suggestion": keep,
                            })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return make_response(results[:limit])


def merge_items(
    entity_type: str = "",
    keep_id: int = 0,
    remove_id: int = 0,
    keep_content: str | None = None,
) -> dict:
    if keep_id == remove_id:
        return error_response("SAME_ENTITY", "Cannot merge an entity with itself")

    sess = get_session()

    if entity_type == "memory":
        keep = sess.get(MemoryEntry, keep_id)
        remove = sess.get(MemoryEntry, remove_id)
    elif entity_type == "conclusion":
        keep = sess.get(Conclusion, keep_id)
        remove = sess.get(Conclusion, remove_id)
    else:
        return error_response("INVALID_TYPE", "entity_type must be 'memory' or 'conclusion'")

    if not keep or not remove:
        return error_response("NOT_FOUND", "One or both entities not found")

    if keep.project_id != remove.project_id:
        return error_response("PROJECT_MISMATCH", "Entities must be in the same project")

    kept_snapshot = keep.content
    removed_snapshot = remove.content
    similarity = jaccard_similarity(keep.content, remove.content)

    if keep_content is not None:
        keep.content = keep_content
    else:
        keep.content = keep.content + "\n\n---\n\n" + remove.content

    keep.updated_at = now_iso()
    sess.delete(remove)
    sess.commit()

    log = MergeLog(
        project_id=keep.project_id,
        entity_type=entity_type,
        kept_id=keep_id,
        removed_id=remove_id,
        kept_content=kept_snapshot,
        removed_content=removed_snapshot,
        similarity=similarity,
        merged_at=now_iso(),
    )
    sess.add(log)
    sess.commit()

    logger.info(f"Merged {entity_type}: kept #{keep_id}, removed #{remove_id}, similarity={similarity:.3f}")
    snippet = keep.content[:200] + ("..." if len(keep.content) > 200 else "")
    return make_response({
        "kept": {"id": keep_id, "content": snippet},
        "removed": {"id": remove_id},
        "merged_at": now_iso(),
    })