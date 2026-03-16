"""Tests for agent/utils/json_guard.py"""
import pytest
from agent.utils.json_guard import (
    validate_intake,
    validate_technical,
    validate_tactical,
    validate_mental,
    validate_patterns,
    validate_head_coach,
)
from tests.fixtures.sample_outputs import (
    INTAKE_OUTPUT,
    TECHNICAL_OUTPUT,
    TACTICAL_OUTPUT,
    MENTAL_OUTPUT,
    PATTERNS_OUTPUT,
    HEAD_COACH_OUTPUT,
)


class TestValidateIntake:
    def test_valid_payload(self):
        assert validate_intake(INTAKE_OUTPUT) == {"ok": True}

    def test_missing_field_returns_error(self):
        payload = {k: v for k, v in INTAKE_OUTPUT.items() if k != "scoreline"}
        result = validate_intake(payload)
        assert "error" in result

    def test_invalid_confidence_returns_error(self):
        payload = {**INTAKE_OUTPUT, "confidence": 1.5}
        result = validate_intake(payload)
        assert "error" in result

    def test_what_went_well_exceeds_max_returns_error(self):
        payload = {**INTAKE_OUTPUT, "what_went_well": ["a", "b", "c", "d", "e", "f"]}
        result = validate_intake(payload)
        assert "error" in result

    def test_set_scores_not_list_returns_error(self):
        payload = {**INTAKE_OUTPUT, "set_scores": "6-4"}
        result = validate_intake(payload)
        assert "error" in result


class TestValidateTechnical:
    def test_valid_payload(self):
        assert validate_technical(TECHNICAL_OUTPUT) == {"ok": True}

    def test_missing_hypotheses_returns_error(self):
        result = validate_technical({"confidence": 0.5})
        assert "error" in result

    def test_hypothesis_missing_subfield_returns_error(self):
        payload = {
            "technical_hypotheses": [{"hypothesis": "x", "evidence": "y"}],  # missing confidence
            "confidence": 0.5,
        }
        result = validate_technical(payload)
        assert "error" in result

    def test_exceeds_max_hypotheses_returns_error(self):
        item = {"hypothesis": "x", "evidence": "y", "confidence": 0.5}
        payload = {"technical_hypotheses": [item] * 5, "confidence": 0.5}
        result = validate_technical(payload)
        assert "error" in result


class TestValidateTactical:
    def test_valid_payload(self):
        assert validate_tactical(TACTICAL_OUTPUT) == {"ok": True}

    def test_missing_field_returns_error(self):
        result = validate_tactical({"confidence": 0.5})
        assert "error" in result


class TestValidateMental:
    def test_valid_payload(self):
        assert validate_mental(MENTAL_OUTPUT) == {"ok": True}

    def test_missing_field_returns_error(self):
        result = validate_mental({"confidence": 0.5})
        assert "error" in result


class TestValidatePatterns:
    def test_valid_payload(self):
        assert validate_patterns(PATTERNS_OUTPUT) == {"ok": True}

    def test_missing_confidence_returns_error(self):
        payload = {"patterns": []}
        result = validate_patterns(payload)
        assert "error" in result

    def test_pattern_missing_subfield_returns_error(self):
        payload = {
            "patterns": [{"pattern": "x", "evidence": "y"}],  # missing confidence
            "confidence": 0.5,
        }
        result = validate_patterns(payload)
        assert "error" in result


class TestValidateHeadCoach:
    def test_valid_payload(self):
        assert validate_head_coach(HEAD_COACH_OUTPUT) == {"ok": True}

    def test_missing_drills_returns_error(self):
        payload = {k: v for k, v in HEAD_COACH_OUTPUT.items() if k != "drills"}
        result = validate_head_coach(payload)
        assert "error" in result

    def test_missing_history_comparison_returns_error(self):
        payload = {k: v for k, v in HEAD_COACH_OUTPUT.items() if k != "history_comparison"}
        result = validate_head_coach(payload)
        assert "error" in result

    def test_history_comparison_not_dict_returns_error(self):
        payload = {**HEAD_COACH_OUTPUT, "history_comparison": "not a dict"}
        result = validate_head_coach(payload)
        assert "error" in result

    def test_history_comparison_missing_patterns_returns_error(self):
        payload = {**HEAD_COACH_OUTPUT, "history_comparison": {"summary": "ok"}}
        result = validate_head_coach(payload)
        assert "error" in result

    def test_drill_missing_subfield_returns_error(self):
        payload = {
            **HEAD_COACH_OUTPUT,
            "drills": [{"drill": "x", "why": "y"}],  # missing confidence
        }
        result = validate_head_coach(payload)
        assert "error" in result

    def test_focus_areas_exceeds_max_returns_error(self):
        payload = {**HEAD_COACH_OUTPUT, "focus_areas": ["a", "b", "c", "d", "e"]}
        result = validate_head_coach(payload)
        assert "error" in result
