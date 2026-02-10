from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlmodel import SQLModel, Session, create_engine, select

from lokal_agent.core.config import AppConfig, ensure_dirs
from lokal_agent.core.storage.models import Project, Run, Message, Artifact


def make_engine(cfg: AppConfig):
    ensure_dirs(cfg)
    db_url = f"sqlite:///{cfg.db_path.as_posix()}"
    return create_engine(db_url, echo=False)


def init_db(cfg: AppConfig) -> None:
    engine = make_engine(cfg)
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope(cfg: AppConfig):
    engine = make_engine(cfg)
    with Session(engine) as session:
        yield session


def upsert_project(cfg: AppConfig, path: str, name: Optional[str] = None) -> Project:
    p = Path(path)
    if name is None:
        name = p.name

    with session_scope(cfg) as s:
        existing = s.exec(select(Project).where(Project.path == path)).first()
        if existing:
            existing.name = name
            existing.last_used_at = datetime.utcnow()
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing

        proj = Project(name=name, path=path, last_used_at=datetime.utcnow())
        s.add(proj)
        s.commit()
        s.refresh(proj)
        return proj


def create_run(cfg: AppConfig, project_id: int, start_message: str) -> Run:
    with session_scope(cfg) as s:
        run = Run(project_id=project_id, status="QUEUED", start_message=start_message)
        s.add(run)
        s.commit()
        s.refresh(run)
        return run


def set_run_status(cfg: AppConfig, run_id: int, status: str, error: Optional[str] = None) -> None:
    with session_scope(cfg) as s:
        run = s.get(Run, run_id)
        if not run:
            return
        run.status = status
        run.error = error
        if status in ("COMPLETED", "FAILED"):
            run.finished_at = datetime.utcnow()
        s.add(run)
        s.commit()


def add_message(cfg: AppConfig, run_id: int, role: str, content: str) -> None:
    with session_scope(cfg) as s:
        m = Message(run_id=run_id, role=role, content=content)
        s.add(m)
        s.commit()


def list_messages(cfg: AppConfig, run_id: int) -> list[Message]:
    with session_scope(cfg) as s:
        msgs = list(s.exec(select(Message).where(Message.run_id == run_id).order_by(Message.ts)))
        return msgs


def add_artifact(cfg: AppConfig, run_id: int, path: str, type_: str, description: str) -> None:
    with session_scope(cfg) as s:
        a = Artifact(run_id=run_id, path=path, type=type_, description=description)
        s.add(a)
        s.commit()


def get_run(cfg: AppConfig, run_id: int) -> Optional[Run]:
    with session_scope(cfg) as s:
        return s.get(Run, run_id)


def list_runs(cfg: AppConfig, limit: int = 30) -> list[Run]:
    with session_scope(cfg) as s:
        runs = list(s.exec(select(Run).order_by(Run.created_at.desc()).limit(limit)))
        return runs

def list_projects(cfg: AppConfig, limit: int = 20) -> list[Project]:
    with session_scope(cfg) as s:
        q = select(Project).order_by(Project.last_used_at.desc().nullslast(), Project.created_at.desc()).limit(limit)
        return list(s.exec(q))


def get_project_by_id(cfg: AppConfig, project_id: int) -> Optional[Project]:
    with session_scope(cfg) as s:
        return s.get(Project, project_id)

def list_projects(cfg: AppConfig, limit: int = 20) -> list[Project]:
    with session_scope(cfg) as s:
        q = select(Project).order_by(Project.last_used_at.desc().nullslast(), Project.created_at.desc()).limit(limit)
        return list(s.exec(q))


def get_project_by_id(cfg: AppConfig, project_id: int) -> Optional[Project]:
    with session_scope(cfg) as s:
        return s.get(Project, project_id)
