from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


DEFAULT_EXCLUDE_DIRS = {
    ".git", ".hg", ".svn",
    ".venv", "venv", "__pycache__",
    ".mypy_cache", ".pytest_cache",
    "node_modules",
    "dist", "build",
    ".idea", ".vscode",
    "data",  # our own runtime data
}


DEFAULT_TEXT_EXTS = {
    ".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".json",
    ".ini", ".cfg", ".env", ".gitignore",
    ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
    ".sql", ".sh", ".ps1",
}


@dataclass
class IndexedFile:
    path: str
    size: int
    snippet: str = ""


@dataclass
class ProjectIndex:
    root: str
    file_count: int
    total_bytes: int
    important: List[IndexedFile]
    tree_preview: str


def _is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in DEFAULT_TEXT_EXTS:
        return True
    # fallback: small files without extension (e.g. LICENSE)
    return path.suffix == "" and path.stat().st_size < 200_000


def _safe_read_text(path: Path, max_chars: int) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    data = data.replace("\r\n", "\n")
    if len(data) > max_chars:
        data = data[:max_chars] + "\n…(truncated)…"
    return data


def _walk_files(root: Path, exclude_dirs: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # prune dirs
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            yield Path(dirpath) / fn


def build_index(
    project_root: str,
    *,
    max_files: int = 2000,
    max_total_bytes: int = 20_000_000,
    max_snippet_chars: int = 3000,
    important_limit: int = 12,
    exclude_dirs: Optional[set[str]] = None,
) -> ProjectIndex:
    root = Path(project_root).resolve()
    exclude = exclude_dirs or set(DEFAULT_EXCLUDE_DIRS)

    file_count = 0
    total_bytes = 0
    files: List[Path] = []

    for p in _walk_files(root, exclude):
        try:
            size = p.stat().st_size
        except Exception:
            continue

        file_count += 1
        total_bytes += size
        files.append(p)

        if file_count >= max_files or total_bytes >= max_total_bytes:
            break

    # choose "important" files heuristically
    preferred_names = [
        "README.md", "README.txt", "pyproject.toml", "requirements.txt",
        "package.json", "Dockerfile", "docker-compose.yml",
        ".env", ".env.example",
        "main.py", "app.py",
    ]
    important_paths: List[Path] = []

    # 1) exact preferred names near root
    for name in preferred_names:
        cand = root / name
        if cand.exists() and cand.is_file():
            important_paths.append(cand)

    # 2) top-level python files (limited)
    for p in sorted(root.glob("*.py"))[:6]:
        if p not in important_paths:
            important_paths.append(p)

    # 3) fallback: smallest few text files (often configs)
    text_files = [p for p in files if p.is_file() and _is_probably_text(p)]
    text_files.sort(key=lambda x: x.stat().st_size if x.exists() else 10**12)
    for p in text_files:
        if len(important_paths) >= important_limit:
            break
        if p not in important_paths:
            important_paths.append(p)

    important: List[IndexedFile] = []
    for p in important_paths[:important_limit]:
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        snippet = _safe_read_text(p, max_snippet_chars) if _is_probably_text(p) else ""
        important.append(IndexedFile(path=str(p.relative_to(root)), size=size, snippet=snippet))

    tree_preview = _make_tree_preview(root, files, max_lines=120)

    return ProjectIndex(
        root=str(root),
        file_count=file_count,
        total_bytes=total_bytes,
        important=important,
        tree_preview=tree_preview,
    )


def _make_tree_preview(root: Path, files: List[Path], max_lines: int = 120) -> str:
    rels = []
    for p in files:
        try:
            rels.append(str(p.relative_to(root)))
        except Exception:
            continue
    rels.sort()
    lines = rels[:max_lines]
    if len(rels) > max_lines:
        lines.append(f"... ({len(rels) - max_lines} more)")
    return "\n".join(lines)
