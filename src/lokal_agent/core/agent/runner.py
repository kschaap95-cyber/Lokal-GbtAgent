from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lokal_agent.core.config import AppConfig
from lokal_agent.core.agent.protocol import FinalReport
from lokal_agent.core.agent.real_agent import RealLocalAgent


# Optional: DB hooks (duck-typing; läuft auch ohne diese Funktionen)
def _db_try_add_message(cfg: AppConfig, run_id: int, role: str, content: str) -> None:
    try:
        from lokal_agent.core.storage import db as storage_db  # type: ignore
    except Exception:
        return

    # common names we may have
    for fn_name in ("add_message", "create_message", "insert_message"):
        fn = getattr(storage_db, fn_name, None)
        if callable(fn):
            try:
                fn(cfg, run_id, role, content)
            except Exception:
                pass
            return


def _db_try_set_run_status(cfg: AppConfig, run_id: int, status: str) -> None:
    try:
        from lokal_agent.core.storage import db as storage_db  # type: ignore
    except Exception:
        return

    for fn_name in ("set_run_status", "update_run_status"):
        fn = getattr(storage_db, fn_name, None)
        if callable(fn):
            try:
                fn(cfg, run_id, status)
            except Exception:
                pass
            return


class DummyAgent:
    """Legacy placeholder (kept for compatibility)."""
    pass


def run_agent(cfg: AppConfig, _agent: object, run_id: int, project_path: str, start_message: str) -> FinalReport:
    _db_try_set_run_status(cfg, run_id, "RUNNING")
    _db_try_add_message(cfg, run_id, "user", start_message)

    # Real agent execution
    real = RealLocalAgent()
    _db_try_add_message(cfg, run_id, "assistant", "Indexiere Projekt und erstelle Report…")
    result = real.run(cfg, project_path=project_path, start_message=start_message, run_id=run_id)

    _db_try_add_message(cfg, run_id, "assistant", f"Report erstellt: {result.report_path}")
    _db_try_set_run_status(cfg, run_id, "COMPLETED")
    return result.report
