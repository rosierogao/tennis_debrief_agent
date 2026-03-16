"""
Pattern detector agent wrapper: returns patterns JSON.
ADK Agent is created for orchestration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Callable, Optional

from agent.utils.llm_json import parse_json_with_retry
from agent.agents.validators import (
    require_keys,
    require_list_of_dict,
    require_float_0_1,
)

try:
    from google.adk import Agent  # type: ignore
except Exception:  # pragma: no cover - optional during development
    Agent = None  # type: ignore


class PatternDetectorAgent:
    """Produces structured pattern detections."""

    def __init__(self) -> None:
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "pattern_detector.md"
        self.agent = self._build_adk_agent()

    def run(
        self,
        match_record: Dict[str, Any],
        recent_matches: Optional[list] = None,
        llm_call: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(match_record, recent_matches)
        validator = self._validate_output

        if llm_call is None:
            llm_call = lambda _: json.dumps(self._default_output())

        return parse_json_with_retry(prompt, llm_call, validator)

    def _build_adk_agent(self):
        """Create the ADK agent instance for this role."""
        if Agent is None:
            return None
        return Agent(
            name="pattern_detector_agent",
            model="gemini-2.0-flash",
            instructions=self.prompt_path.read_text(),
        )

    def _build_prompt(self, match_record: Dict[str, Any], recent_matches: Optional[list] = None) -> str:
        template = self.prompt_path.read_text()
        payload: Dict[str, Any] = {"match_record": match_record}
        if recent_matches is not None:
            payload["recent_matches"] = recent_matches
        return f"{template}\n\nINPUT:\n{json.dumps(payload, ensure_ascii=True)}"

    def _default_output(self) -> Dict[str, Any]:
        return {
            "patterns": [],
            "confidence": 0.4,
        }

    def _validate_output(self, obj: Dict[str, Any]) -> None:
        require_keys(obj, ["patterns", "confidence"])
        items = require_list_of_dict(obj.get("patterns"), "patterns", 5)
        for item in items:
            require_keys(item, ["pattern", "evidence", "confidence"])
            require_float_0_1(item.get("confidence"), "patterns[].confidence")
        require_float_0_1(obj.get("confidence"), "confidence")
