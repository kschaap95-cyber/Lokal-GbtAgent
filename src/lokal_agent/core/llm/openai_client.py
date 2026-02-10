from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

from openai import OpenAI


@dataclass
class LLMResponse:
    text: str
    raw: Any


class OpenAIClient:
    """
    Minimal wrapper around OpenAI Responses API.
    Uses OPENAI_API_KEY from environment automatically.
    """

    def __init__(self, model: str | None = None) -> None:
        self.client = OpenAI()
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.2")

    def respond_text(self, *, developer: str, user: str) -> LLMResponse:
        # Responses API supports either a plain string input or structured message items.
        resp = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "developer", "type": "message", "content": developer},
                {"role": "user", "type": "message", "content": user},
            ],
        )
        return LLMResponse(text=getattr(resp, "output_text", "") or "", raw=resp)

    def compile_plan_to_taskspec_json(self, plan_text: str) -> Dict[str, Any]:
        """
        Hard rule: return JSON-only TaskSpec v1.
        We enforce by parsing JSON. If parsing fails, we raise.
        """
        developer = (
            "You are a strict JSON compiler. Output MUST be valid JSON only (no prose, no markdown). "
            "Return a TaskSpec with this schema:\n"
            "{\n"
            '  "version":"task_spec_v1",\n'
            '  "goal": string,\n'
            '  "steps":[{"id":"S1","task":string,"verify":[string,...]}, ...],\n'
            '  "done_criteria":[string,...]\n'
            "}\n"
            "Rules:\n"
            "- steps must be non-empty\n"
            "- done_criteria must be non-empty\n"
            "- ids must be S1..Sn\n"
        )

        out = self.respond_text(developer=developer, user=plan_text).text.strip()

        # Strict: must start with { and be parseable JSON, no trailing junk.
        if not out.startswith("{"):
            raise ValueError(f"LLM did not return JSON-only. Starts with: {out[:60]!r}")

        try:
            data = json.loads(out)
        except Exception as e:
            raise ValueError(f"Invalid JSON from LLM: {e}\n\nRAW:\n{out[:8000]}")

        # minimal validation
        if data.get("version") != "task_spec_v1":
            raise ValueError("TaskSpec missing version=task_spec_v1")
        if not isinstance(data.get("goal"), str) or not data["goal"].strip():
            raise ValueError("TaskSpec.goal missing/empty")
        steps = data.get("steps")
        if not isinstance(steps, list) or len(steps) == 0:
            raise ValueError("TaskSpec.steps missing/empty")
        done = data.get("done_criteria")
        if not isinstance(done, list) or len(done) == 0:
            raise ValueError("TaskSpec.done_criteria missing/empty")

        return data
