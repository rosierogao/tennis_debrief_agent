"""
Validation tools for strict JSON outputs.
"""
from typing import Any, Dict

from agent.agents.validators import (
    require_keys,
    require_list_of_str,
    require_list_of_dict,
    require_float_0_1,
)


def _ok() -> Dict[str, Any]:
    return {"ok": True}


def _err(message: str) -> Dict[str, Any]:
    return {"error": {"code": "VALIDATION_ERROR", "message": message}}


def validate_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(
            payload,
            [
                "opponent_level",
                "scoreline",
                "set_scores",
                "what_went_well",
                "what_went_poorly",
                "feelings",
                "opponent_characteristics",
                "pressure_moments",
                "patterns_noticed",
                "confidence",
            ],
        )
        if not isinstance(payload.get("set_scores"), list):
            raise ValueError("set_scores must be a list")
        require_list_of_str(payload.get("what_went_well"), "what_went_well", max_items=5)
        require_list_of_str(payload.get("what_went_poorly"), "what_went_poorly", max_items=5)
        require_list_of_str(
            payload.get("opponent_characteristics"), "opponent_characteristics", max_items=5
        )
        require_list_of_str(payload.get("pressure_moments"), "pressure_moments", max_items=5)
        require_list_of_str(payload.get("patterns_noticed"), "patterns_noticed", max_items=5)
        require_float_0_1(payload.get("confidence"), "confidence")
        return _ok()
    except Exception as exc:
        return _err(str(exc))


def validate_technical(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(payload, ["technical_hypotheses", "confidence"])
        items = require_list_of_dict(payload.get("technical_hypotheses"), "technical_hypotheses", 4)
        for item in items:
            require_keys(item, ["hypothesis", "evidence", "confidence"])
            require_float_0_1(item.get("confidence"), "technical_hypotheses[].confidence")
        require_float_0_1(payload.get("confidence"), "confidence")
        return _ok()
    except Exception as exc:
        return _err(str(exc))


def validate_tactical(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(payload, ["tactical_observations", "confidence"])
        items = require_list_of_dict(payload.get("tactical_observations"), "tactical_observations", 4)
        for item in items:
            require_keys(item, ["observation", "evidence", "confidence"])
            require_float_0_1(item.get("confidence"), "tactical_observations[].confidence")
        require_float_0_1(payload.get("confidence"), "confidence")
        return _ok()
    except Exception as exc:
        return _err(str(exc))


def validate_mental(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(payload, ["mental_observations", "confidence"])
        items = require_list_of_dict(payload.get("mental_observations"), "mental_observations", 4)
        for item in items:
            require_keys(item, ["observation", "evidence", "confidence"])
            require_float_0_1(item.get("confidence"), "mental_observations[].confidence")
        require_float_0_1(payload.get("confidence"), "confidence")
        return _ok()
    except Exception as exc:
        return _err(str(exc))


def validate_patterns(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(payload, ["patterns", "confidence"])
        items = require_list_of_dict(payload.get("patterns"), "patterns", 5)
        for item in items:
            require_keys(item, ["pattern", "evidence", "confidence"])
            require_float_0_1(item.get("confidence"), "patterns[].confidence")
        require_float_0_1(payload.get("confidence"), "confidence")
        return _ok()
    except Exception as exc:
        return _err(str(exc))


_TECHNIQUE_KEYS = {
    "first_serve_pct", "double_faults", "forehand", "backhand",
    "rally_depth", "unforced_errors", "return_of_serve",
    "footwork", "pressure_performance", "momentum",
}


def validate_head_coach(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        require_keys(
            payload,
            ["summary", "focus_areas", "levers", "drills", "history_comparison", "confidence"],
        )
        require_list_of_str(payload.get("focus_areas"), "focus_areas", max_items=4)
        levers = require_list_of_dict(payload.get("levers"), "levers", max_items=3)
        for item in levers:
            require_keys(item, ["lever", "why", "confidence"])
            require_float_0_1(item.get("confidence"), "levers[].confidence")
        drills = require_list_of_dict(payload.get("drills"), "drills", max_items=3)
        for item in drills:
            require_keys(item, ["drill", "why", "confidence"])
            require_float_0_1(item.get("confidence"), "drills[].confidence")
        history = payload.get("history_comparison")
        if not isinstance(history, dict):
            raise ValueError("history_comparison must be an object")
        require_keys(history, ["summary", "patterns"])
        require_list_of_str(history.get("patterns"), "history_comparison.patterns", max_items=4)
        require_float_0_1(payload.get("confidence"), "confidence")

        # Validate technique_scores if present (optional field)
        scores = payload.get("technique_scores")
        if scores is not None:
            if not isinstance(scores, dict):
                raise ValueError("technique_scores must be an object")
            for key, val in scores.items():
                if key not in _TECHNIQUE_KEYS:
                    continue  # extra keys tolerated
                if val is None:
                    continue
                if not isinstance(val, int) or isinstance(val, bool) or val < 1 or val > 5:
                    raise ValueError(
                        f"technique_scores.{key} must be an integer 1-5 or null, got {val!r}"
                    )

        return _ok()
    except Exception as exc:
        return _err(str(exc))
