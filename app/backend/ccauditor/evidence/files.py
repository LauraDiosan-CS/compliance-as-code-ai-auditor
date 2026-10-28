"""Safe repository walking, file classification and reading helpers."""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from ccauditor.models import EvidenceKind

MAX_FILE_BYTES = 1_000_000

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build",
    ".next", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".vscode",
    ".terraform", "site-packages", "coverage", ".cache",
}

BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tar",
    ".tgz", ".bz2", ".xz", ".7z", ".jar", ".war", ".class", ".so", ".dylib", ".dll", ".exe",
    ".bin", ".o", ".a", ".pyc", ".pyo", ".whl", ".pkl", ".pickle", ".pt", ".pth", ".onnx",
    ".h5", ".npy", ".npz", ".parquet", ".db", ".sqlite", ".woff", ".woff2", ".ttf", ".otf",
    ".eot", ".mp3", ".mp4", ".mov", ".avi", ".wav", ".lock", ".safetensors", ".ckpt",
}

CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".java", ".kt", ".go", ".rs", ".rb",
    ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".swift", ".scala", ".sh", ".bash",
    ".sql", ".r", ".ipynb", ".vue", ".svelte", ".rego",
}
CONFIG_EXTS = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml"}
IAC_EXTS = {".tf", ".tfvars", ".hcl", ".bicep"}
DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(2048)
    except OSError:
        return True


def iter_repo_files(repo_root: str | Path, exclude: list[str] | None = None) -> Iterator[Path]:
    """Yield text files under repo_root (absolute paths), skipping vendored/build dirs, binaries, >1MB."""
    root = Path(repo_root).resolve()
    exclude = exclude or []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, pat) for pat in exclude):
                continue
            try:
                if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            if is_binary(p):
                continue
            yield p


def read_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _is_k8s_manifest(text: str) -> bool:
    return "apiVersion:" in text and "kind:" in text


def classify(rel_path: str, text: str | None = None) -> EvidenceKind | None:
    """Classify a repo-relative path into an EvidenceKind (None = ignore)."""
    p = PurePosixPath(rel_path)
    name = p.name
    lname = name.lower()
    parts = [x.lower() for x in p.parts[:-1]]
    suffix = p.suffix.lower()

    # model cards / datasheets first (they are often markdown)
    if (
        lname.startswith(("model_card", "modelcard", "datasheet", "data_card", "datacard"))
        or lname.endswith(".modelcard.md")
        or lname.startswith("model-card")
        or lname.startswith("data-card")
    ):
        return EvidenceKind.MODEL_CARD

    # logs
    if suffix == ".log" or (parts and parts[0] in ("logs", "log")) or (
        suffix == ".jsonl" and any(x in ("logs", "log", "audit") for x in parts)
    ):
        return EvidenceKind.LOG

    # infrastructure as code
    if suffix in IAC_EXTS:
        return EvidenceKind.IAC
    if lname.startswith(("docker-compose", "compose.")) and suffix in (".yml", ".yaml"):
        return EvidenceKind.IAC
    if any(x in ("helm", "charts", "k8s", "kubernetes", "manifests", "terraform") for x in parts):
        if suffix in (".yaml", ".yml", ".tpl", ".json"):
            return EvidenceKind.IAC
    if lname in ("chart.yaml", "values.yaml", "kustomization.yaml"):
        return EvidenceKind.IAC
    if suffix in (".yaml", ".yml") and text is not None and _is_k8s_manifest(text):
        return EvidenceKind.IAC

    # docs
    if lname.startswith("readme") or (parts and parts[0] in ("docs", "doc", "adr", "adrs")):
        if suffix in DOC_EXTS or suffix == "":
            return EvidenceKind.DOC
    if suffix in DOC_EXTS or lname in ("license", "changelog", "contributing"):
        return EvidenceKind.DOC

    # config
    if lname == "dockerfile" or lname.startswith("dockerfile.") or lname.endswith(".dockerfile"):
        return EvidenceKind.CONFIG
    if lname.startswith(".env") and lname != ".env":  # .env.example, .env.sample (never real .env)
        return EvidenceKind.CONFIG
    if suffix in CONFIG_EXTS or lname in ("makefile", ".gitignore", ".dockerignore", "procfile"):
        return EvidenceKind.CONFIG

    if suffix in CODE_EXTS:
        return EvidenceKind.CODE
    return None


def read_lines(repo_root: str | Path, path: str, start: int, end: int) -> str:
    """Return lines [start, end] (1-based, inclusive) of a repo file; refuses paths escaping the repo."""
    root = Path(repo_root).resolve()
    target = (root / path).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"path escapes repository: {path}")
    lines = read_text(target).splitlines()
    start = max(1, start)
    return "\n".join(lines[start - 1 : max(start - 1, end)])
