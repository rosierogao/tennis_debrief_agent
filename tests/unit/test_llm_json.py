"""Tests for agent/utils/llm_json.py"""
import json
import pytest
from agent.utils.llm_json import parse_json_with_retry, LLMJsonError


def _llm(response: str):
    """Return a callable that always returns the given string."""
    return lambda _: response


class TestParseJsonWithRetry:
    def test_success_on_first_attempt(self):
        result = parse_json_with_retry('prompt', _llm('{"key": "val"}'))
        assert result == {"key": "val"}

    def test_retry_succeeds_on_second_attempt(self):
        calls = []

        def flaky_llm(prompt):
            calls.append(prompt)
            if len(calls) == 1:
                return "not json"
            return '{"key": "val"}'

        result = parse_json_with_retry('prompt', flaky_llm)
        assert result == {"key": "val"}
        assert len(calls) == 2

    def test_both_attempts_fail_raises(self):
        with pytest.raises(LLMJsonError):
            parse_json_with_retry('prompt', _llm('invalid json{{'))

    def test_non_string_output_raises(self):
        with pytest.raises(LLMJsonError):
            parse_json_with_retry('prompt', lambda _: 42)

    def test_validator_called_on_success(self):
        validated = []

        def validator(obj):
            validated.append(obj)

        parse_json_with_retry('prompt', _llm('{"x": 1}'), validate_fn=validator)
        assert validated == [{"x": 1}]

    def test_validator_failure_triggers_retry(self):
        calls = []

        def llm(prompt):
            calls.append(prompt)
            return '{"x": 1}'

        def strict_validator(obj):
            if len(calls) < 2:
                raise ValueError("not good enough")

        result = parse_json_with_retry('prompt', llm, validate_fn=strict_validator)
        assert result == {"x": 1}
        assert len(calls) == 2

    def test_validator_fails_both_attempts_raises(self):
        def bad_validator(obj):
            raise ValueError("always bad")

        with pytest.raises(LLMJsonError):
            parse_json_with_retry('prompt', _llm('{"x": 1}'), validate_fn=bad_validator)

    def test_fix_prompt_appended_on_retry(self):
        prompts_seen = []

        def llm(p):
            prompts_seen.append(p)
            if len(prompts_seen) == 1:
                return "bad"
            return '{"ok": true}'

        parse_json_with_retry('base_prompt', llm)
        assert "base_prompt" in prompts_seen[1]
        assert "FIX_JSON" in prompts_seen[1]
