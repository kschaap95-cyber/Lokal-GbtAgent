from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from lokal_agent.core.llm.openai_client import OpenAIClient


def compile_plan_to_taskspec(plan_text: str, out_path: Path) -> Dict[str, Any]:
    client = OpenAIClient()
    spec = client.compile_plan_to_taskspec_json(plan_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    return spec
