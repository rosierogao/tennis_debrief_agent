"""Tests for agent/agents/mental.py"""
import pytest
from agent.agents.mental import MentalAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD
from tests.fixtures.sample_outputs import MENTAL_OUTPUT, as_json


class TestMentalAgent:
    def setup_method(self):
        self.agent = MentalAgent()

    def test_run_with_valid_llm_output(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: as_json(MENTAL_OUTPUT))
        assert "mental_observations" in result
        assert len(result["mental_observations"]) == 2

    def test_run_without_llm_call_returns_default(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD)
        assert "mental_observations" in result

    def test_run_with_invalid_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: '{}')
