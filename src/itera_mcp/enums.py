from enum import StrEnum


class ItemType(StrEnum):
    REQUIREMENT = "requirement"
    BUG = "bug"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class MemoryType(StrEnum):
    FACT = "fact"
    DECISION = "decision"
    PITFALL = "pitfall"
    PREFERENCE = "preference"


class IterationStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


PRESET_TAG_NAMES = [
    "architecture",
    "implementation",
    "risk",
    "decision",
    "pattern",
    "integration",
    "quality",
]

PRESET_TAG_DESCRIPTIONS: dict[str, str] = {
    "architecture": "架构与设计：系统架构决策、模块划分、设计模式选择",
    "implementation": "实现细节：具体代码实现方式、算法选择、编码技巧",
    "risk": "风险与问题：已识别风险、遇到的问题、技术债务",
    "decision": "关键决策：重要的技术/业务决策及其理由",
    "pattern": "模式与经验：可复用的解决方案、最佳实践、踩坑经验",
    "integration": "依赖与集成：外部依赖、API 对接、第三方服务集成",
    "quality": "质量与优化：代码质量、性能优化、安全加固",
}

MAX_TAGS_PER_PROJECT = 30
MAX_CUSTOM_TAGS_PER_SESSION = 3
SIMILARITY_THRESHOLD = 0.6