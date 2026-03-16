"""Tests for agent/agents/validators.py"""
import pytest
from agent.agents.validators import (
    require_keys,
    require_list_of_str,
    require_list_of_dict,
    require_float_0_1,
)


class TestRequireKeys:
    def test_all_keys_present(self):
        require_keys({"a": 1, "b": 2}, ["a", "b"])  # no exception

    def test_missing_key_raises(self):
        with pytest.raises(ValueError, match="Missing required field: b"):
            require_keys({"a": 1}, ["a", "b"])

    def test_empty_keys_list(self):
        require_keys({}, [])  # no exception


class TestRequireListOfStr:
    def test_valid_list(self):
        require_list_of_str(["a", "b"], "field")

    def test_empty_list(self):
        require_list_of_str([], "field")

    def test_not_a_list_raises(self):
        with pytest.raises(ValueError, match="field must be a list of strings"):
            require_list_of_str("not a list", "field")

    def test_list_with_non_str_raises(self):
        with pytest.raises(ValueError):
            require_list_of_str(["a", 1], "field")

    def test_exceeds_max_items_raises(self):
        with pytest.raises(ValueError, match="at most 2 items"):
            require_list_of_str(["a", "b", "c"], "field", max_items=2)

    def test_at_max_items_ok(self):
        require_list_of_str(["a", "b"], "field", max_items=2)


class TestRequireListOfDict:
    def test_valid_list(self):
        result = require_list_of_dict([{"x": 1}], "field")
        assert result == [{"x": 1}]

    def test_empty_list(self):
        result = require_list_of_dict([], "field")
        assert result == []

    def test_not_a_list_raises(self):
        with pytest.raises(ValueError, match="field must be a list of objects"):
            require_list_of_dict("nope", "field")

    def test_list_with_non_dict_raises(self):
        with pytest.raises(ValueError):
            require_list_of_dict([{"a": 1}, "not a dict"], "field")

    def test_exceeds_max_items_raises(self):
        with pytest.raises(ValueError, match="at most 1 items"):
            require_list_of_dict([{"a": 1}, {"b": 2}], "field", max_items=1)


class TestRequireFloat01:
    def test_valid_values(self):
        for v in [0.0, 0.5, 1.0, 0, 1]:
            require_float_0_1(v, "conf")  # no exception

    def test_below_zero_raises(self):
        with pytest.raises(ValueError, match="conf must be a number between 0 and 1"):
            require_float_0_1(-0.1, "conf")

    def test_above_one_raises(self):
        with pytest.raises(ValueError):
            require_float_0_1(1.1, "conf")

    def test_non_number_raises(self):
        with pytest.raises(ValueError):
            require_float_0_1("0.5", "conf")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            require_float_0_1(None, "conf")
