import uuid
import re
from datetime import datetime, timezone


def generate_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_response(data=None) -> dict:
    return {"success": True, "data": data}


def error_response(code: str, message: str) -> dict:
    return {"success": False, "error": {"code": code, "message": message}}


def jaccard_similarity(a: str, b: str) -> float:
    tokens_a = set(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]+', a.lower()))
    tokens_b = set(re.findall(r'[a-zA-Z0-9\u4e00-\u9fff]+', b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def model_to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}