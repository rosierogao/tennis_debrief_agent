"""Tests for agent/agents/technical.py"""
import pytest
from agent.agents.technical import TechnicalAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD
from tests.fixtures.sample_outputs import TECHNICAL_OUTPUT, as_json


class TestTechnicalAgent:
    def setup_method(self):
        self.agent = TechnicalAgent()

    def test_run_with_valid_llm_output(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: as_json(TECHNICAL_OUTPUT))
        assert "technical_hypotheses" in result
        assert len(result["technical_hypotheses"]) == 2

    def test_run_without_llm_call_returns_default(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD)
        assert "technical_hypotheses" in result
        assert isinstance(result["technical_hypotheses"], list)

    def test_prompt_includes_match_record(self):
        prompt = self.agent._build_prompt(SAMPLE_MATCH_RECORD)
        assert "double faults" in prompt

    def test_run_with_invalid_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: '{"wrong": "schema"}')
