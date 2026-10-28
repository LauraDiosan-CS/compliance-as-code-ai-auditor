import json
import subprocess

import pytest

from ccauditor.llm.backend import (
    ClaudeCodeBackend,
    DiskCache,
    FakeBackend,
    LLMError,
    extract_json,
    get_backend,
    validate_schema,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('```\n{"a": {"b": [1, 2]}}\n```\nDone.', {"a": {"b": [1, 2]}}),
        ('Sure! Here is the verdict:\n{"status": "compliant", "note": "uses {braces} and \\"quotes\\""}\nThanks',
         {"status": "compliant", "note": 'uses {braces} and "quotes"'}),
        ('prefix {not json} then {"ok": true}', {"ok": True}),
        ('{"a": [1, 2,], "b": 3,}', {"a": [1, 2], "b": 3}),
    ],
)
def test_extract_json_robust(text, expected):
    assert extract_json(text) == expected


@pytest.mark.parametrize("bad", ["", "no json here", "[1, 2, 3]", '{"unterminated": '])
def test_extract_json_failure(bad):
    with pytest.raises(ValueError):
        extract_json(bad)


def test_validate_schema():
    schema = {"type": "object", "properties": {"status": {"type": "string", "enum": ["a", "b"]},
                                               "confidence": {"type": "number"}},
              "required": ["status", "confidence"]}
    assert validate_schema({"status": "a", "confidence": 0.5}, schema) == []
    assert validate_schema({"status": "c", "confidence": 1}, schema)
    assert validate_schema({"status": "a"}, schema)
    assert validate_schema({"status": "a", "confidence": "high"}, schema)
    assert validate_schema({"x": 1}, None) == []


def test_fake_backend_dict_and_callable():
    fb = FakeBackend({"x": 1})
    assert fb.complete_json("s", "p") == {"x": 1}
    fb2 = FakeBackend(lambda system, prompt: {"echo": prompt})
    assert fb2.complete_json("s", "hello") == {"echo": "hello"}
    assert fb2.usage.calls == 1 and len(fb2.calls) == 1


def test_get_backend():
    assert get_backend("fake").name == "fake"
    b = get_backend("claude", "haiku")
    assert isinstance(b, ClaudeCodeBackend) and b.model == "haiku"
    with pytest.raises(ValueError):
        get_backend("nope")


def _envelope(result: str, structured=None, is_error=False):
    d = {"type": "result", "is_error": is_error, "result": result, "total_cost_usd": 0.001,
         "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0,
                   "output_tokens": 20}}
    if structured is not None:
        d["structured_output"] = structured
    return json.dumps(d)


class _FakeRun:
    """Replaces subprocess.run; returns queued stdout values and records commands."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.cmds = []
        self.inputs = []

    def __call__(self, cmd, input=None, **kw):  # noqa: A002
        self.cmds.append(cmd)
        self.inputs.append(input)
        out = self.outputs.pop(0)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


def test_claude_backend_retries_with_nudge_and_accounts_usage(monkeypatch, tmp_path):
    fake = _FakeRun([_envelope("I think it is compliant."), _envelope('```json\n{"status": "compliant"}\n```')])
    monkeypatch.setattr(subprocess, "run", fake)
    b = ClaudeCodeBackend(model="haiku", use_cache=False, use_json_schema=False)
    out = b.complete_json("sys", "prompt", {"type": "object", "properties": {"status": {"type": "string"}},
                                            "required": ["status"]})
    assert out == {"status": "compliant"}
    assert len(fake.cmds) == 2
    assert "Return ONLY one valid JSON object" in fake.inputs[1]
    cmd = fake.cmds[0]
    for flag in ("-p", "--output-format", "--system-prompt", "--tools", "--strict-mcp-config",
                 "--setting-sources", "--no-session-persistence", "--disable-slash-commands"):
        assert flag in cmd
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert b.usage.calls == 2 and b.usage.input_tokens == 220 and b.usage.output_tokens == 40
    assert b.usage.cost_usd == pytest.approx(0.002)


def test_claude_backend_structured_output_and_cache(monkeypatch, tmp_path):
    fake = _FakeRun([_envelope("", structured={"status": "partial"})])
    monkeypatch.setattr(subprocess, "run", fake)
    schema = {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}
    b = ClaudeCodeBackend(model="haiku", use_cache=True, cache_dir=tmp_path)
    assert b.complete_json("s", "p", schema) == {"status": "partial"}
    assert "--json-schema" in fake.cmds[0]
    # second identical call is served from disk cache (no subprocess output queued -> would fail otherwise)
    b2 = ClaudeCodeBackend(model="haiku", use_cache=True, cache_dir=tmp_path)
    assert b2.complete_json("s", "p", schema) == {"status": "partial"}
    assert b2.usage.cache_hits == 1 and b2.usage.calls == 0


def test_cache_disabled_by_env(monkeypatch):
    monkeypatch.setenv("CCAUDITOR_NO_CACHE", "1")
    assert ClaudeCodeBackend().cache is None


def test_claude_backend_gives_up(monkeypatch):
    fake = _FakeRun([_envelope("nope")] * 3)
    monkeypatch.setattr(subprocess, "run", fake)
    b = ClaudeCodeBackend(use_cache=False, max_retries=2)
    with pytest.raises(LLMError):
        b.complete_json("s", "p")
    assert len(fake.cmds) == 3


def test_disk_cache_key_depends_on_all_inputs():
    k = DiskCache.key("m", "s", "p", None)
    assert k != DiskCache.key("m2", "s", "p", None)
    assert k != DiskCache.key("m", "s2", "p", None)
    assert k != DiskCache.key("m", "s", "p2", None)
    assert k != DiskCache.key("m", "s", "p", {"type": "object"})


@pytest.mark.live
def test_live_claude_backend_smoke():
    b = ClaudeCodeBackend(model="haiku", use_cache=False)
    out = b.complete_json("You are a JSON API.", 'Return {"ok": true, "n": 3}.',
                          {"type": "object", "properties": {"ok": {"type": "boolean"}, "n": {"type": "integer"}},
                           "required": ["ok", "n"]})
    assert out["ok"] is True and out["n"] == 3
    assert b.usage.calls == 1
