"""Tests for agent/agents/pattern_detector.py"""
import json
import pytest
from agent.agents.pattern_detector import PatternDetectorAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD, SAMPLE_RECENT_MATCHES
from tests.fixtures.sample_outputs import PATTERNS_OUTPUT, as_json


class TestPatternDetectorAgent:
    def setup_method(self):
        self.agent = PatternDetectorAgent()

    def test_run_with_valid_llm_output(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: as_json(PATTERNS_OUTPUT))
        assert "patterns" in result
        assert len(result["patterns"]) == 2

    def test_run_without_llm_call_returns_default(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD)
        assert "patterns" in result
        assert isinstance(result["patterns"], list)

    def test_recent_matches_included_in_prompt(self):
        prompt = self.agent._build_prompt(SAMPLE_MATCH_RECORD, recent_matches=SAMPLE_RECENT_MATCHES)
        assert "recent_matches" in prompt
        assert "abc123" in prompt  # match_id from sample

    def test_no_recent_matches_not_in_json_payload(self):
        prompt = self.agent._build_prompt(SAMPLE_MATCH_RECORD, recent_matches=None)
        # "recent_matches" appears in template text; check the JSON payload section only
        json_section = prompt.split("INPUT:")[-1]
        assert '"recent_matches"' not in json_section

    def test_empty_recent_matches_included(self):
        prompt = self.agent._build_prompt(SAMPLE_MATCH_RECORD, recent_matches=[])
        assert "recent_matches" in prompt

    def test_run_passes_recent_matches_to_prompt(self):
        prompts_seen = []

        def capture_llm(p):
            prompts_seen.append(p)
            return as_json(PATTERNS_OUTPUT)

        self.agent.run(SAMPLE_MATCH_RECORD, recent_matches=SAMPLE_RECENT_MATCHES, llm_call=capture_llm)
        assert "recent_matches" in prompts_seen[0]

    def test_run_with_invalid_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: '{"bad": true}')
