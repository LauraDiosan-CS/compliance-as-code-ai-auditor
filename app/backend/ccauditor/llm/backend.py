"""LLM backends.

The production backend shells out to the Claude Code CLI in headless mode
(``claude -p --output-format json``), which authenticates with the developer's
Claude subscription: no API key is needed. Every call is isolated from the
user's Claude Code environment (no tools, no MCP servers, no settings/CLAUDE.md,
no session persistence, cwd in an empty temp dir) so it is fast, cheap and
reproducible.

``FakeBackend`` provides deterministic responses for tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Raised when the backend cannot produce a valid JSON object."""


# ------------------------------------------------------------------ usage accounting


@dataclass
class Usage:
    calls: int = 0  # real (non-cached) model calls
    cache_hits: int = 0
    failures: int = 0
    input_tokens: int = 0  # includes cache creation / cache read tokens
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0  # summed wall-clock of real calls
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, *, calls: int = 0, cache_hits: int = 0, failures: int = 0, input_tokens: int = 0,
            output_tokens: int = 0, cost_usd: float = 0.0, latency_s: float = 0.0) -> None:
        with self._lock:
            self.calls += calls
            self.cache_hits += cache_hits
            self.failures += failures
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cost_usd += cost_usd
            self.latency_s += latency_s

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "calls": self.calls,
                "cache_hits": self.cache_hits,
                "failures": self.failures,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cost_usd": round(self.cost_usd, 6),
                "latency_s": round(self.latency_s, 3),
            }


def usage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in after.items():
        b = before.get(k, 0)
        out[k] = round(v - b, 6) if isinstance(v, float) else v - b
    return out


@runtime_checkable
class LLMBackend(Protocol):
    name: str
    model: str | None
    concurrency: int
    usage: Usage

    def complete_json(self, system: str, prompt: str, schema: dict | None = None,
                      model: str | None = None) -> dict: ...


# ------------------------------------------------------------------ JSON helpers


def _strip_fences(text: str) -> str:
    t = text.strip()
    if "```" in t:
        # prefer the content of the first fenced block that contains a '{'
        parts = t.split("```")
        for i in range(1, len(parts), 2):
            block = parts[i]
            if block[:10].lower().startswith("json"):
                block = block[4:]
            if "{" in block:
                return block.strip()
    return t


def _balanced_objects(text: str):
    """Yield every top-level balanced {...} substring (string/escape aware)."""
    i = 0
    n = len(text)
    while i < n:
        start = text.find("{", i)
        if start < 0:
            return
        depth = 0
        in_str = False
        esc = False
        for j in range(start, n):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    yield text[start: j + 1]
                    i = j + 1
                    break
        else:
            return  # unbalanced till the end


def extract_json(text: str) -> dict:
    """Robustly extract the first JSON object from model output.

    Handles code fences, leading/trailing prose, and nested braces inside strings.
    Raises ValueError if no JSON object can be parsed.
    """
    if text is None:
        raise ValueError("empty response")
    if isinstance(text, dict):
        return text
    t = text.strip()
    if not t:
        raise ValueError("empty response")
    for candidate in (t, _strip_fences(t)):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            pass
    for src in (_strip_fences(t), t):
        for chunk in _balanced_objects(src):
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                # tolerate trailing commas, a frequent LLM slip
                try:
                    obj = json.loads(re.sub(r",\s*([}\]])", r"\1", chunk))
                except json.JSONDecodeError:
                    continue
            if isinstance(obj, dict):
                return obj
    raise ValueError(f"no JSON object found in response: {t[:200]!r}")


_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_schema(obj: dict, schema: dict | None) -> list[str]:
    """Light validation: required keys, top-level types and enums. Returns a list of problems."""
    if not schema:
        return []
    problems: list[str] = []
    props = schema.get("properties", {}) or {}
    for key in schema.get("required", []) or []:
        if key not in obj:
            problems.append(f"missing required key '{key}'")
    for key, spec in props.items():
        if key not in obj or not isinstance(spec, dict):
            continue
        val = obj[key]
        typ = spec.get("type")
        if isinstance(typ, str) and typ in _JSON_TYPES:
            ok = isinstance(val, _JSON_TYPES[typ]) and not (typ in ("number", "integer") and isinstance(val, bool))
            if not ok and not (val is None and not (key in (schema.get("required") or []))):
                problems.append(f"key '{key}' should be {typ}")
        if "enum" in spec and val not in spec["enum"]:
            problems.append(f"key '{key}' must be one of {spec['enum']}")
    return problems


# ------------------------------------------------------------------ disk cache


def _cache_enabled_by_env() -> bool:
    return os.environ.get("CCAUDITOR_NO_CACHE", "").strip().lower() not in ("1", "true", "yes")


class DiskCache:
    def __init__(self, root: str | Path | None = None):
        base = root or os.environ.get("CCAUDITOR_CACHE_DIR") or (Path.home() / ".cache" / "ccauditor")
        self.root = Path(base) / "llm"

    @staticmethod
    def key(model: str | None, system: str, prompt: str, schema: dict | None) -> str:
        h = hashlib.sha256()
        for part in (model or "", system, prompt, json.dumps(schema, sort_keys=True) if schema else ""):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        p = self._path(key)
        try:
            return json.loads(p.read_text("utf-8"))["response"]
        except (OSError, ValueError, KeyError):
            return None

    def put(self, key: str, response: dict, meta: dict | None = None) -> None:
        p = self._path(key)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps({"response": response, "meta": meta or {}}), "utf-8")
            tmp.replace(p)
        except OSError:
            pass


# ------------------------------------------------------------------ Claude Code backend


NUDGE = (
    "\n\nIMPORTANT: your previous answer could not be parsed ({error}). "
    "Return ONLY one valid JSON object, no prose, no markdown fences."
)


class ClaudeCodeBackend:
    """LLM backend that calls the Claude Code CLI headlessly (subscription auth, no API key).

    Flags used (all verified on the installed CLI):
      -p --output-format json         single JSON result envelope
      --model <alias>                 e.g. sonnet / haiku / opus
      --system-prompt <text>          replaces the Claude Code system prompt entirely
      --tools ""                      no built-in tools -> single-turn, no side effects
      --strict-mcp-config             ignore the user's MCP servers
      --setting-sources ""            ignore user/project/local settings, hooks, plugins
      --disable-slash-commands        no skills/commands loaded
      --no-session-persistence        nothing written to ~/.claude sessions
      --json-schema <schema>          (when use_json_schema) server-validated structured output
    The process runs with cwd = empty temp dir so no CLAUDE.md is discovered.
    The user prompt is passed on stdin (no argv length limit).
    """

    name = "claude"

    def __init__(self, model: str = "sonnet", timeout: float = 180, max_retries: int = 2,
                 concurrency: int = 4, use_cache: bool | None = None, use_json_schema: bool = True,
                 executable: str | None = None, cache_dir: str | Path | None = None):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.concurrency = max(1, int(concurrency))
        self.use_json_schema = use_json_schema
        self.executable = executable or shutil.which("claude") or "claude"
        self.use_cache = _cache_enabled_by_env() if use_cache is None else use_cache
        self.cache = DiskCache(cache_dir) if self.use_cache else None
        self.usage = Usage()
        self._sem = threading.Semaphore(self.concurrency)
        self._workdir = tempfile.mkdtemp(prefix="ccauditor-llm-")

    # -- low level -----------------------------------------------------------
    def _build_cmd(self, system: str, model: str, schema: dict | None) -> list[str]:
        cmd = [
            self.executable, "-p",
            "--output-format", "json",
            "--model", model,
            "--system-prompt", system,
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        if schema and self.use_json_schema:
            cmd += ["--json-schema", json.dumps(schema)]
        return cmd

    def _invoke(self, system: str, prompt: str, model: str, schema: dict | None) -> tuple[dict, str]:
        """Run one CLI call. Returns (envelope, text_result)."""
        cmd = self._build_cmd(system, model, schema)
        env = dict(os.environ)
        env.pop("CLAUDECODE", None)  # allow running from inside a Claude Code session
        t0 = time.perf_counter()
        with self._sem:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                  timeout=self.timeout, cwd=self._workdir, env=env)
        dt = time.perf_counter() - t0
        try:
            env_obj = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.usage.add(failures=1, latency_s=dt)
            raise LLMError(f"claude CLI returned non-JSON (rc={proc.returncode}): "
                           f"{(proc.stdout or proc.stderr)[:300]}")
        u = env_obj.get("usage") or {}
        self.usage.add(
            calls=1,
            input_tokens=int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
            + int(u.get("cache_read_input_tokens", 0)),
            output_tokens=int(u.get("output_tokens", 0)),
            cost_usd=float(env_obj.get("total_cost_usd") or 0.0),
            latency_s=dt,
        )
        if env_obj.get("is_error") or proc.returncode != 0:
            raise LLMError(f"claude CLI error: {str(env_obj.get('result') or env_obj.get('subtype'))[:300]}")
        return env_obj, env_obj.get("result") or ""

    # -- public --------------------------------------------------------------
    def complete_json(self, system: str, prompt: str, schema: dict | None = None,
                      model: str | None = None) -> dict:
        model = model or self.model
        key = DiskCache.key(model, system, prompt, schema) if self.cache else None
        if key:
            hit = self.cache.get(key)
            if hit is not None:
                self.usage.add(cache_hits=1)
                return hit
        last_err: Exception | None = None
        cur_prompt = prompt
        for _attempt in range(self.max_retries + 1):
            try:
                env_obj, text = self._invoke(system, cur_prompt, model, schema)
            except subprocess.TimeoutExpired as e:
                self.usage.add(failures=1, latency_s=self.timeout)
                last_err = e
                continue
            except LLMError as e:
                last_err = e
                time.sleep(1.0)
                continue
            try:
                so = env_obj.get("structured_output")
                obj = so if isinstance(so, dict) else extract_json(text)
                problems = validate_schema(obj, schema)
                if problems:
                    raise ValueError("; ".join(problems))
            except ValueError as e:
                last_err = e
                cur_prompt = prompt + NUDGE.format(error=str(e)[:200])
                continue
            if key:
                self.cache.put(key, obj, {"model": model})
            return obj
        raise LLMError(f"LLM failed after {self.max_retries + 1} attempts: {last_err}")


# ------------------------------------------------------------------ Fake backend


Responder = Callable[[str, str], dict]


class FakeBackend:
    """Deterministic backend for tests.

    ``responder`` is either a dict (returned for every call) or a callable
    ``(system, prompt) -> dict``. Callables may also accept a third ``schema`` arg.
    All calls are recorded in ``self.calls`` as (system, prompt, schema, model).
    """

    name = "fake"

    def __init__(self, responder: Responder | dict | None = None, model: str | None = "fake",
                 concurrency: int = 4):
        self.responder = responder if responder is not None else {}
        self.model = model
        self.concurrency = concurrency
        self.usage = Usage()
        self.calls: list[tuple[str, str, dict | None, str | None]] = []
        self._lock = threading.Lock()

    def complete_json(self, system: str, prompt: str, schema: dict | None = None,
                      model: str | None = None) -> dict:
        with self._lock:
            self.calls.append((system, prompt, schema, model))
        if callable(self.responder):
            try:
                out = self.responder(system, prompt, schema)  # type: ignore[call-arg]
            except TypeError:
                out = self.responder(system, prompt)
        else:
            out = self.responder
        if isinstance(out, str):
            out = extract_json(out)
        self.usage.add(calls=1, input_tokens=(len(system) + len(prompt)) // 4,
                       output_tokens=len(json.dumps(out)) // 4)
        return json.loads(json.dumps(out))  # defensive deep copy


# ------------------------------------------------------------------ factory


def get_backend(name: str | None = None, model: str | None = None, **kwargs: Any) -> LLMBackend:
    """Return a backend by name: "claude" (default if the CLI is on PATH) or "fake"."""
    name = (name or os.environ.get("CCAUDITOR_BACKEND") or "").strip().lower()
    if not name:
        name = "claude" if shutil.which("claude") else "fake"
    if name in ("claude", "claude-code", "claude_code"):
        return ClaudeCodeBackend(model=model or os.environ.get("CCAUDITOR_MODEL") or "sonnet", **kwargs)
    if name == "fake":
        return FakeBackend(kwargs.get("responder"), model=model or "fake")
    raise ValueError(f"unknown LLM backend {name!r} (expected 'claude' or 'fake')")
