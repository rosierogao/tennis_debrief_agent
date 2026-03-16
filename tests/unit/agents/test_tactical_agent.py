"""Tests for agent/agents/tactical.py"""
import pytest
from agent.agents.tactical import TacticalAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD
from tests.fixtures.sample_outputs import TACTICAL_OUTPUT, as_json


class TestTacticalAgent:
    def setup_method(self):
        self.agent = TacticalAgent()

    def test_run_with_valid_llm_output(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: as_json(TACTICAL_OUTPUT))
        assert "tactical_observations" in result
        assert result["confidence"] == TACTICAL_OUTPUT["confidence"]

    def test_run_without_llm_call_returns_default(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD)
        assert "tactical_observations" in result

    def test_run_with_invalid_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: '{"x": 1}')
