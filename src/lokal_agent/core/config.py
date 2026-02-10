from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path = Path("data")
    db_path: Path = Path("data") / "lokal_agent.db"
    runs_dir: Path = Path("data") / "runs"
    reports_dir: Path = Path("data") / "reports"

    # Agent behavior
    max_steps: int = 6


def ensure_dirs(cfg: AppConfig) -> None:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.runs_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
