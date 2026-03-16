"""
Integration tests for pure helper functions in agent/agent.py.
These functions live inside `if Agent is not None:` but have no ADK dependency.
The conftest.py pytest_configure hook ensures ADK is mocked before this import.
"""
import pytest

# Import after conftest has patched sys.modules
import agent.agent as agent_module


# Verify helpers are available (will skip if ADK mock didn't work)
pytestmark = pytest.mark.skipif(
    not hasattr(agent_module, "_strip_json_fence"),
    reason="agent.agent helpers not available (ADK mock not active)",
)

_strip = agent_module._strip_json_fence
_extract = agent_module._extract_json_objects
_parse_maybe = agent_module._parse_json_maybe
_parse_record = agent_module._parse_match_record_from_text
_filter = agent_module._filter_recent_matches
_is_echo = agent_module._is_agent_echo


class TestStripJsonFence:
    def test_no_fence(self):
        assert _strip('{"key": 1}') == '{"key": 1}'

    def test_strips_json_fence(self):
        result = _strip("```json\n{\"key\": 1}\n```")
        assert result == '{"key": 1}'

    def test_strips_plain_fence(self):
        result = _strip("```\n{\"key\": 1}\n```")
        assert result == '{"key": 1}'

    def test_strips_whitespace(self):
        assert _strip("  hello  ") == "hello"


class TestExtractJsonObjects:
    def test_single_object(self):
        result = _extract('{"a": 1}')
        assert result == ['{"a": 1}']

    def test_multiple_objects(self):
        result = _extract('{"a": 1} some text {"b": 2}')
        assert len(result) == 2

    def test_nested_object(self):
        result = _extract('{"a": {"b": 1}}')
        assert len(result) == 1
        assert '"b"' in result[0]

    def test_no_objects(self):
        assert _extract("no json here") == []

    def test_string_with_braces_not_confused(self):
        result = _extract('{"key": "val with { brace }"}')
        assert len(result) == 1


class TestParseJsonMaybe:
    def test_parses_valid_json_string(self):
        assert _parse_maybe('{"a": 1}') == {"a": 1}

    def test_returns_dict_unchanged(self):
        d = {"a": 1}
        assert _parse_maybe(d) is d

    def test_returns_string_on_invalid_json(self):
        result = _parse_maybe("not json")
        assert result == "not json"

    def test_strips_fence_before_parsing(self):
        result = _parse_maybe("```json\n{\"a\": 1}\n```")
        assert result == {"a": 1}


class TestParseMatchRecordFromText:
    def test_parses_full_json(self):
        text = '{"scoreline": "6-4", "set_scores": [{"set": 1, "score": "6-4"}], "opponent_level": "advanced"}'
        result = _parse_record(text)
        assert result["scoreline"] == "6-4"

    def test_returns_none_for_plain_text(self):
        result = _parse_record("I won my match today 6-4 6-2")
        assert result is None


class TestFilterRecentMatches:
    def test_filters_matches_after_cutoff(self):
        match_record = {"match_date": "2024-11-10"}
        matches = [
            {"match_record": {"match_date": "2024-10-01"}},  # before, within 6 months → keep
            {"match_record": {"match_date": "2024-11-15"}},  # after cutoff → exclude
        ]
        result = _filter(match_record, matches)
        assert len(result) == 1
        assert result[0]["match_record"]["match_date"] == "2024-10-01"

    def test_filters_matches_older_than_6_months(self):
        match_record = {"match_date": "2024-11-10"}
        matches = [
            {"match_record": {"match_date": "2024-10-01"}},  # 40 days ago → keep
            {"match_record": {"match_date": "2024-04-01"}},  # ~7 months ago → exclude
        ]
        result = _filter(match_record, matches)
        assert len(result) == 1
        assert result[0]["match_record"]["match_date"] == "2024-10-01"

    def test_returns_all_when_no_match_date(self):
        matches = [{"match_record": {"match_date": "2024-10-01"}}]
        result = _filter({}, matches)
        assert result == matches

    def test_falls_back_to_created_at(self):
        match_record = {"match_date": "2024-11-10"}
        matches = [
            {"created_at": "2024-09-01T00:00:00"},  # within 6 months → keep
            {"created_at": "2024-12-01T00:00:00"},  # after cutoff → exclude
            {"created_at": "2024-01-01T00:00:00"},  # older than 6 months → exclude
        ]
        result = _filter(match_record, matches)
        assert len(result) == 1


class TestIsAgentEcho:
    def test_detects_agent_markers(self):
        assert _is_echo("[technical_agent]") is True
        assert _is_echo("[head_coach_agent]") is True

    def test_normal_text_not_echo(self):
        assert _is_echo("I lost 4-6 3-6 today") is False

    def test_case_insensitive(self):
        assert _is_echo("[TECHNICAL_AGENT]") is True
