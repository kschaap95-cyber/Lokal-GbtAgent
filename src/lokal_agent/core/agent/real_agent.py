from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from lokal_agent.core.config import AppConfig, ensure_dirs
from lokal_agent.core.indexing.indexer import ProjectIndex, build_index
from lokal_agent.core.agent.protocol import FinalReport, ArtifactOut


@dataclass
class AgentResult:
    report: FinalReport
    report_path: str


class RealLocalAgent:
    """
    "Echter" Agent (ohne Cloud-LLM): indexiert das Projekt und erzeugt einen strukturierten Report.
    Später ersetzen wir die Report-Generierung durch ein LLM-Backend – die Schnittstelle bleibt.
    """

    def run(self, cfg: AppConfig, project_path: str, start_message: str, run_id: int | None = None) -> AgentResult:
        ensure_dirs(cfg)

        idx = build_index(project_path)

        report_md = self._render_report(idx, start_message)
        name = f"run_{run_id or 'na'}_report.md"
        out_path = (cfg.reports_dir / name).resolve()
        out_path.write_text(report_md, encoding="utf-8")

        summary = self._render_summary(idx, start_message)

        final = FinalReport(
            summary=summary,
            artifacts=[ArtifactOut(path=str(out_path), description="Projekt-Analyse Report (Markdown)")],
            next_steps=[
                "LLM-Backend anbinden (OpenAI/Local) und Agent als Tool-User laufen lassen",
                "Index erweitern: große Repos chunking + Embeddings (optional)",
                "API-Mode asynchron: POST /runs -> run_id, GET /runs/{id}, GET /runs/{id}/messages",
            ],
            done=True,
        )
        return AgentResult(report=final, report_path=str(out_path))

    def _render_summary(self, idx: ProjectIndex, start_message: str) -> str:
        return (
            f"Projektindex erstellt: {idx.file_count} Dateien, {idx.total_bytes} Bytes.\n"
            f"Root: {idx.root}\n"
            f"Auftrag: {start_message}\n"
            f"Wichtige Dateien: {', '.join([f.path for f in idx.important]) or '(keine)'}"
        )

    def _render_report(self, idx: ProjectIndex, start_message: str) -> str:
        imp = "\n".join([f"- `{f.path}` ({f.size} bytes)" for f in idx.important]) or "- (keine)"
        sections: List[str] = []

        sections.append("# Lokal-GbtAgent Report")
        sections.append("")
        sections.append("## Auftrag")
        sections.append(start_message.strip() or "(leer)")
        sections.append("")
        sections.append("## Projekt-Überblick")
        sections.append(f"- Root: `{idx.root}`")
        sections.append(f"- Dateien (gezählt/gescannt): **{idx.file_count}**")
        sections.append(f"- Gesamtgröße (gezählt/gescannt): **{idx.total_bytes}** bytes")
        sections.append("")
        sections.append("## Wichtige Dateien (heuristisch)")
        sections.append(imp)
        sections.append("")
        sections.append("## Tree Preview (Ausschnitt)")
        sections.append("```")
        sections.append(idx.tree_preview or "")
        sections.append("```")
        sections.append("")

        sections.append("## Snippets (Ausschnitt)")
        for f in idx.important:
            if not f.snippet:
                continue
            sections.append(f"### {f.path}")
            sections.append("```")
            sections.append(f.snippet)
            sections.append("```")
            sections.append("")

        sections.append("## Einschätzung / Nächste Schritte")
        sections.append("- Projektindex ist vorhanden; als nächstes binden wir ein LLM-Backend an, das auf Basis dieses Index eine planvolle Task-Ausführung macht.")
        sections.append("- Danach: Completion-Erkennung über FINAL_REPORT-Protokoll + Report-Artefakte.")
        sections.append("")

        return "\n".join(sections)
