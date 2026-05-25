from sqlalchemy import (
    Column,
    Text,
    Integer,
    Float,
    ForeignKey,
    Index,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session as OrmSession, sessionmaker
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    tech_stack = Column(Text)
    constraints = Column(Text)
    active_iteration_id = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    iterations = relationship("Iteration", back_populates="project")
    items = relationship("Item", back_populates="project")
    memory_entries = relationship("MemoryEntry", back_populates="project")
    sessions = relationship("Session", back_populates="project")
    tags = relationship("Tag", back_populates="project")


class Iteration(Base):
    __tablename__ = "iterations"

    id = Column(Text, primary_key=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    name = Column(Text, nullable=False)
    goal = Column(Text)
    start_date = Column(Text)
    end_date = Column(Text)
    status = Column(Text, nullable=False, default="planning")
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    project = relationship("Project", back_populates="iterations")
    items = relationship("Item", back_populates="iteration")
    sessions = relationship("Session", back_populates="iteration")

    __table_args__ = (
        Index("idx_iterations_project_id", "project_id"),
    )


class Item(Base):
    __tablename__ = "items"

    id = Column(Text, primary_key=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    type = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    description = Column(Text)
    priority = Column(Text, nullable=False, default="medium")
    status = Column(Text, nullable=False, default="backlog")
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)
    deleted = Column(Integer, nullable=False, default=0)
    completed_at = Column(Text)
    iteration_id = Column(Text, ForeignKey("iterations.id"))
    acceptance_criteria = Column(Text)
    severity = Column(Text)
    steps_to_reproduce = Column(Text)
    environment = Column(Text)
    verified = Column(Integer, default=0)

    project = relationship("Project", back_populates="items")
    iteration = relationship("Iteration", back_populates="items")

    __table_args__ = (
        Index("idx_items_project_id", "project_id"),
        Index("idx_items_type", "type"),
        Index("idx_items_status", "status"),
        Index("idx_items_iteration_id", "iteration_id"),
        Index("idx_items_deleted", "deleted"),
    )


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    type = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    project = relationship("Project", back_populates="memory_entries")

    __table_args__ = (
        Index("idx_memory_project_id", "project_id"),
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    timestamp = Column(Text, nullable=False)
    session_id = Column(Text)
    action = Column(Text, nullable=False)
    summary = Column(Text)
    item_id = Column(Text)
    iteration_id = Column(Text)
    details = Column(Text)

    __table_args__ = (
        Index("idx_activity_project_id", "project_id"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Text, primary_key=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    iteration_id = Column(Text, ForeignKey("iterations.id"))
    title = Column(Text, nullable=False)
    summary = Column(Text)
    status = Column(Text, nullable=False, default="active")
    started_at = Column(Text, nullable=False)
    completed_at = Column(Text)
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    project = relationship("Project", back_populates="sessions")
    iteration = relationship("Iteration", back_populates="sessions")
    conclusions = relationship("Conclusion", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sessions_project_id", "project_id"),
        Index("idx_sessions_iteration_id", "iteration_id"),
        Index("idx_sessions_status", "status"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    is_preset = Column(Integer, nullable=False, default=0)
    created_at = Column(Text, nullable=False)

    project = relationship("Project", back_populates="tags")

    __table_args__ = (
        Index("idx_tags_project_id", "project_id"),
    )


class Conclusion(Base):
    __tablename__ = "conclusions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    session_id = Column(Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id"), nullable=False)
    content = Column(Text, nullable=False)
    confidence = Column(Text, nullable=False, default="medium")
    created_at = Column(Text, nullable=False)
    updated_at = Column(Text, nullable=False)

    session = relationship("Session", back_populates="conclusions")

    __table_args__ = (
        Index("idx_conclusions_project_id", "project_id"),
        Index("idx_conclusions_session_id", "session_id"),
        Index("idx_conclusions_tag_id", "tag_id"),
    )


class MemoryTag(Base):
    __tablename__ = "memory_tags"

    memory_id = Column(Integer, ForeignKey("memory_entries.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class MergeLog(Base):
    __tablename__ = "merge_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Text, ForeignKey("projects.id"), nullable=False)
    entity_type = Column(Text, nullable=False)
    kept_id = Column(Integer, nullable=False)
    removed_id = Column(Integer, nullable=False)
    kept_content = Column(Text, nullable=False)
    removed_content = Column(Text, nullable=False)
    similarity = Column(Float, nullable=False)
    merged_at = Column(Text, nullable=False)

    __table_args__ = (
        Index("idx_merge_log_project_id", "project_id"),
        Index("idx_merge_log_entity_type", "entity_type"),
    )


_engine = None
_SessionFactory = None


def _get_engine(db_path: str):
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
            echo=False,
        )
    return _engine


def init_engine(db_path: str) -> None:
    engine = _get_engine(db_path)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()
    Base.metadata.create_all(engine)


def get_session(db_path: str) -> OrmSession:
    global _SessionFactory
    engine = _get_engine(db_path)
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine, autoflush=False)
    return _SessionFactory()


def get_engine_for_path(db_path: str):
    return _get_engine(db_path)


def close_engine() -> None:
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _SessionFactory = None