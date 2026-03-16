"""Tests for mcp_memory_server/models.py"""
import pytest
from pydantic import ValidationError
from mcp_memory_server.models import (
    MatchStoreInput,
    MatchRetrieveRecentInput,
    MatchItem,
    ProfileUpsertInput,
)


class TestMatchStoreInput:
    def test_valid_input(self):
        obj = MatchStoreInput(
            match_record={"date": "2024-11-10"},
            debrief_report={"summary": "good match"},
            themes=["double faults"],
            summary="Lost 4-6 3-6",
        )
        assert obj.summary == "Lost 4-6 3-6"

    def test_optional_match_id(self):
        obj = MatchStoreInput(
            match_record={}, debrief_report={}, themes=[], summary="",
        )
        assert obj.match_id is None

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            MatchStoreInput(match_record={}, themes=[], summary="")  # missing debrief_report


class TestMatchRetrieveRecentInput:
    def test_valid_input(self):
        obj = MatchRetrieveRecentInput(limit=5)
        assert obj.limit == 5
        assert obj.include_full is False

    def test_include_full_true(self):
        obj = MatchRetrieveRecentInput(limit=10, include_full=True)
        assert obj.include_full is True

    def test_limit_below_min_raises(self):
        with pytest.raises(ValidationError):
            MatchRetrieveRecentInput(limit=0)

    def test_limit_above_max_raises(self):
        with pytest.raises(ValidationError):
            MatchRetrieveRecentInput(limit=51)

    def test_limit_at_boundaries_ok(self):
        MatchRetrieveRecentInput(limit=1)
        MatchRetrieveRecentInput(limit=50)


class TestMatchItem:
    def test_valid_item(self):
        obj = MatchItem(
            match_id="abc",
            created_at="2024-11-10T10:00:00",
            themes=["double faults"],
            summary="tough loss",
        )
        assert obj.match_id == "abc"

    def test_optional_full_fields(self):
        obj = MatchItem(match_id="x", created_at="2024-01-01", themes=[], summary="")
        assert obj.match_record is None
        assert obj.debrief_report is None


class TestProfileUpsertInput:
    def test_valid_patch(self):
        obj = ProfileUpsertInput(patch={"goal": "win regionals"})
        assert obj.patch == {"goal": "win regionals"}

    def test_empty_patch(self):
        obj = ProfileUpsertInput(patch={})
        assert obj.patch == {}
