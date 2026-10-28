"""Comment / docstring / TODO masking for deterministic checks.

Text inside comments, docstrings and TODO-style notes is not implemented behaviour: a commented-out
``# logger.info(...)`` or ``// TODO: label AI replies`` must not satisfy a "present" check, and a docstring
saying a feature is *not* supported must not trip an "absent" check. ``mask_non_code`` replaces such
spans with spaces, preserving newlines so line numbers (and evidence chunk mapping) stay valid.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import PurePosixPath

# extension -> (line comment markers, block comment pairs, string delimiters)
_C_LIKE = (("//",), (("/*", "*/"),), ('"', "'", "`"))
_HASH = (("#",), (), ('"', "'"))
_HCL = (("#", "//"), (("/*", "*/"),), ('"',))
_SQL = (("--",), (("/*", "*/"),), ("'", '"'))
_MARKUP = ((), (("<!--", "-->"),), ())

SYNTAX: dict[str, tuple] = {
    **{e: _C_LIKE for e in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".java", ".kt", ".go", ".rs", ".cs",
                             ".c", ".cc", ".cpp", ".h", ".hpp", ".swift", ".scala", ".php", ".vue", ".svelte")},
    **{e: _HASH for e in (".rb", ".sh", ".bash", ".r", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
                           ".properties", ".rego", ".env", ".tfvars")},
    **{e: _HCL for e in (".tf", ".hcl")},
    ".sql": _SQL,
    **{e: _MARKUP for e in (".md", ".html", ".htm", ".xml", ".rst", ".adoc")},
}
_NAMES = {"dockerfile": _HASH, "makefile": _HASH, ".gitignore": _HASH}

TODO_LINE = re.compile(r"\b(TODO|FIXME|TBD|XXX|HACK)\b")


def _blank(s: str) -> str:
    return re.sub(r"[^\n]", " ", s)


def _mask_python(text: str) -> str | None:
    """Blank comments and docstrings (string statements) using the tokenizer. None if it cannot tokenize."""
    lines = text.splitlines(keepends=True)
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    prev_sig = tokenize.NEWLINE
    for tok in toks:
        if tok.type == tokenize.COMMENT:
            spans.append((tok.start, tok.end))
        elif tok.type == tokenize.STRING and prev_sig in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
            spans.append((tok.start, tok.end))  # bare string statement = docstring
        if tok.type not in (tokenize.COMMENT, tokenize.NL):
            prev_sig = tok.type if tok.type in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT) else tokenize.OP
    if not spans:
        return text
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))
    chars = list(text)
    for (sr, sc), (er, ec) in spans:
        a = offsets[sr - 1] + sc
        b = offsets[er - 1] + ec
        for i in range(a, min(b, len(chars))):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def _mask_generic(text: str, line_markers: tuple, blocks: tuple, quotes: tuple) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in quotes:  # string literal: copy verbatim (strings are code, e.g. log messages)
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\\":
                    j += 1
                elif text[j] == "\n" and c != "`":
                    break
                j += 1
            out.append(text[i:j + 1])
            i = j + 1
            continue
        hit = False
        for a, b in blocks:
            if text.startswith(a, i):
                j = text.find(b, i + len(a))
                j = n if j < 0 else j + len(b)
                out.append(_blank(text[i:j]))
                i, hit = j, True
                break
        if hit:
            continue
        for m in line_markers:
            # '#' only starts a comment at line start or after whitespace (avoids URLs/anchors, '#!' etc.)
            if text.startswith(m, i) and (m != "#" or i == 0 or text[i - 1] in " \t\n"):
                j = text.find("\n", i)
                j = n if j < 0 else j
                out.append(_blank(text[i:j]))
                i, hit = j, True
                break
        if hit:
            continue
        out.append(c)
        i += 1
    return "".join(out)


def mask_todo_lines(text: str) -> str:
    """Blank whole lines that are TODO / FIXME / TBD notes (plans are not evidence)."""
    return "".join(_blank(ln) if TODO_LINE.search(ln) else ln for ln in text.splitlines(keepends=True))


def mask_non_code(path: str, text: str) -> str:
    """Return ``text`` with comments, docstrings and TODO lines replaced by spaces (same length/lines)."""
    p = PurePosixPath(path)
    ext = p.suffix.lower()
    masked: str | None = None
    if ext == ".py":
        masked = _mask_python(text)
        if masked is None:
            masked = _mask_generic(text, ("#",), (), ('"', "'"))
    else:
        syntax = SYNTAX.get(ext) or _NAMES.get(p.name.lower())
        masked = _mask_generic(text, *syntax) if syntax else text
    return mask_todo_lines(masked)


# "feature flag that is switched off": `override_allowed = False`, `human_review_enabled: false`
DISABLED_FLAG = re.compile(
    r"\b\w*(allowed|enabled|enable|active|supported|on)\b[\"']?\s*[:=]\s*[\"']?(false|0|none|null|nil|off|no|disabled)\b",
    re.IGNORECASE,
)


def is_disabled_flag_line(line: str) -> bool:
    return bool(DISABLED_FLAG.search(line))


_COMMENT_MARK = re.compile(r"^\s*(#+|//+|/\*+|\*+|<!--|--|\"\"\"|''')\s*")
_CODE_LIKE = re.compile(
    r"^(?:[A-Za-z_$][\w.$]*(?:\[[^\]]*\])?\s*\(.*\)\s*;?\s*$"     # call: logger.info(...)
    r"|[A-Za-z_$][\w.$\[\]'\"]*\s*[-+*/]?=\s*\S"                   # assignment: x = ...
    r"|(?:import|from|def|class|return|if|elif|for|while|const|let|var|await|function|async|raise)\b"
    r"|.*[;{]\s*$)"
)


def comment_kind(line: str) -> str:
    """Classify a comment / docstring line: 'todo', 'code' (commented-out code) or 'prose' (explanation)."""
    if TODO_LINE.search(line):
        return "todo"
    body = _COMMENT_MARK.sub("", line, count=1).strip()
    body = re.sub(r"\s*(\*/|-->|\"\"\"|''')\s*$", "", body)
    return "code" if body and _CODE_LIKE.match(body) else "prose"
