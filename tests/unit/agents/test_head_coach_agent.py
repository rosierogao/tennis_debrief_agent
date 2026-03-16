"""Tests for agent/agents/head_coach.py"""
import json
import pytest
from agent.agents.head_coach import HeadCoachAgent
from tests.fixtures.sample_matches import SAMPLE_MATCH_RECORD, SAMPLE_RECENT_MATCHES
from tests.fixtures.sample_outputs import (
    TECHNICAL_OUTPUT, TACTICAL_OUTPUT, MENTAL_OUTPUT, PATTERNS_OUTPUT,
    HEAD_COACH_OUTPUT, as_json,
)


def _run(agent, recent_matches=None, llm_output=None):
    llm_call = (lambda _: as_json(llm_output)) if llm_output else None
    return agent.run(
        match_record=SAMPLE_MATCH_RECORD,
        technical=TECHNICAL_OUTPUT,
        tactical=TACTICAL_OUTPUT,
        mental=MENTAL_OUTPUT,
        patterns=PATTERNS_OUTPUT,
        recent_matches=recent_matches,
        llm_call=llm_call,
    )


class TestHeadCoachAgent:
    def setup_method(self):
        self.agent = HeadCoachAgent()

    def test_run_with_valid_llm_output(self):
        result = _run(self.agent, llm_output=HEAD_COACH_OUTPUT)
        assert "summary" in result
        assert "drills" in result
        assert "history_comparison" in result

    def test_run_without_llm_call_returns_default(self):
        result = _run(self.agent)
        assert "drills" in result
        assert isinstance(result["drills"], list)
        assert "history_comparison" in result
        assert isinstance(result["history_comparison"], dict)

    def test_default_output_has_all_required_fields(self):
        default = self.agent._default_output()
        for field in ["summary", "focus_areas", "levers", "drills", "history_comparison", "confidence"]:
            assert field in default, f"Missing field: {field}"

    def test_default_history_comparison_structure(self):
        default = self.agent._default_output()
        hc = default["history_comparison"]
        assert "summary" in hc
        assert "patterns" in hc
        assert isinstance(hc["patterns"], list)

    def test_recent_matches_included_in_prompt(self):
        prompt = self.agent._build_prompt(
            SAMPLE_MATCH_RECORD, TECHNICAL_OUTPUT, TACTICAL_OUTPUT,
            MENTAL_OUTPUT, PATTERNS_OUTPUT, recent_matches=SAMPLE_RECENT_MATCHES,
        )
        assert "recent_matches" in prompt

    def test_no_recent_matches_not_in_json_payload(self):
        prompt = self.agent._build_prompt(
            SAMPLE_MATCH_RECORD, TECHNICAL_OUTPUT, TACTICAL_OUTPUT,
            MENTAL_OUTPUT, PATTERNS_OUTPUT, recent_matches=None,
        )
        # Check the JSON payload section only (template may mention "recent_matches")
        json_section = prompt.split("INPUT:")[-1]
        assert '"recent_matches"' not in json_section

    def test_run_with_invalid_output_raises(self):
        from agent.utils.llm_json import LLMJsonError
        with pytest.raises(LLMJsonError):
            _run(self.agent, llm_output={"summary": "ok"})  # missing required fields
