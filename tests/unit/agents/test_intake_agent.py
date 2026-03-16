"""Tests for agent/agents/intake.py"""
import json
import pytest
from agent.agents.intake import IntakeAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD
from tests.fixtures.sample_outputs import INTAKE_OUTPUT, as_json


class TestIntakeAgent:
    def setup_method(self):
        self.agent = IntakeAgent()

    def test_run_with_valid_llm_output(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: as_json(INTAKE_OUTPUT))
        assert result["opponent_level"] == INTAKE_OUTPUT["opponent_level"]
        assert result["confidence"] == INTAKE_OUTPUT["confidence"]

    def test_run_without_llm_call_returns_default(self):
        result = self.agent.run(SAMPLE_MATCH_RECORD)
        assert "opponent_level" in result
        assert "confidence" in result

    def test_default_output_is_valid(self):
        default = self.agent._default_output(SAMPLE_MATCH_RECORD)
        assert isinstance(default["what_went_well"], list)
        assert isinstance(default["confidence"], float)

    def test_prompt_contains_form_input(self):
        prompt = self.agent._build_prompt({"scoreline": "6-4"})
        assert "6-4" in prompt

    def test_run_with_invalid_llm_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            self.agent.run(SAMPLE_MATCH_RECORD, llm_call=lambda _: '{"bad": "output"}')
