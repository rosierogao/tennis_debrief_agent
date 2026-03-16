"""Tests for shared/constants.py"""
import pytest
from shared.constants import (
    OPPONENT_LEVELS,
    TECHNICAL_KEYWORDS,
    TACTICAL_KEYWORDS,
    MENTAL_KEYWORDS,
    Priority,
    CONFIDENCE_THRESHOLDS,
    confidence_to_priority,
    Category,
    ALL_CATEGORIES,
)


class TestOpponentLevels:
    def test_contains_expected_levels(self):
        for level in ("beginner", "intermediate", "advanced", "competitive", "tournament", "professional"):
            assert level in OPPONENT_LEVELS

    def test_all_strings(self):
        assert all(isinstance(l, str) for l in OPPONENT_LEVELS)


class TestKeywords:
    def test_technical_keywords_non_empty(self):
        assert len(TECHNICAL_KEYWORDS) > 0

    def test_tactical_keywords_non_empty(self):
        assert len(TACTICAL_KEYWORDS) > 0

    def test_mental_keywords_non_empty(self):
        assert len(MENTAL_KEYWORDS) > 0

    def test_common_technical_terms_present(self):
        assert "forehand" in TECHNICAL_KEYWORDS
        assert "backhand" in TECHNICAL_KEYWORDS
        assert "first serve" in TECHNICAL_KEYWORDS

    def test_common_mental_terms_present(self):
        assert "nervous" in MENTAL_KEYWORDS
        assert "confident" in MENTAL_KEYWORDS


class TestConfidenceToPriority:
    def test_high_boundary(self):
        assert confidence_to_priority(0.75) == Priority.HIGH
        assert confidence_to_priority(1.0) == Priority.HIGH

    def test_just_below_high(self):
        assert confidence_to_priority(0.74) == Priority.MEDIUM

    def test_medium_boundary(self):
        assert confidence_to_priority(0.50) == Priority.MEDIUM
        assert confidence_to_priority(0.74) == Priority.MEDIUM

    def test_just_below_medium(self):
        assert confidence_to_priority(0.49) == Priority.LOW

    def test_low(self):
        assert confidence_to_priority(0.0) == Priority.LOW
        assert confidence_to_priority(0.1) == Priority.LOW

    def test_thresholds_consistent(self):
        assert CONFIDENCE_THRESHOLDS[Priority.HIGH] == 0.75
        assert CONFIDENCE_THRESHOLDS[Priority.MEDIUM] == 0.50


class TestCategory:
    def test_all_categories_present(self):
        assert Category.TECHNICAL in ALL_CATEGORIES
        assert Category.TACTICAL in ALL_CATEGORIES
        assert Category.MENTAL in ALL_CATEGORIES
        assert Category.PHYSICAL in ALL_CATEGORIES

    def test_values_are_strings(self):
        assert all(isinstance(c, str) for c in ALL_CATEGORIES)
