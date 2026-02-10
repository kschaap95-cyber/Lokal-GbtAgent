from __future__ import annotations

import json
import re
from typing import Optional, List

from pydantic import BaseModel, Field


FINAL_MARKER = "FINAL_REPORT"


class ArtifactOut(BaseModel):
    path: str
    description: str


class FinalReport(BaseModel):
    type: str = Field(default="final", pattern=r"^final$")
    summary: str
    artifacts: List[ArtifactOut] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    done: bool = True


_FINAL_BLOCK_RE = re.compile(
    r"FINAL_REPORT\s*```json\s*(\{.*?\})\s*```",
    flags=re.DOTALL | re.IGNORECASE,
)


def try_extract_final_report(text: str) -> Optional[FinalReport]:
    m = _FINAL_BLOCK_RE.search(text)
    if not m:
        return None

    raw = m.group(1)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None

    try:
        return FinalReport.model_validate(obj)
    except Exception:
        return None
