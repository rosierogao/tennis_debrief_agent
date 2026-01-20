"""
Intake agent wrapper: returns MatchRecord JSON.
ADK Agent is created for orchestration.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Callable, Optional

from agent.utils.llm_json import parse_json_with_retry
from agent.agents.validators import (
    require_keys,
    require_list_of_str,
    require_float_0_1,
)

try:
    from google.adk import Agent  # type: ignore
except Exception:  # pragma: no cover - optional during development
    Agent = None  # type: ignore


class IntakeAgent:
    """Builds a structured MatchRecord from raw form input."""

    def __init__(self) -> None:
        self.prompt_path = Path(__file__).parent.parent / "prompts" / "intake.md"
        self.agent = self._build_adk_agent()

    def run(
        self,
        form_input: Dict[str, Any],
        llm_call: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, Any]:
        prompt = self._build_prompt(form_input)
        validator = self._validate_output

        if llm_call is None:
            llm_call = lambda _: json.dumps(self._default_output(form_input))

        return parse_json_with_retry(prompt, llm_call, validator)

    def _build_adk_agent(self):
        """Create the ADK agent instance for this role."""
        if Agent is None:
            return None
        return Agent(
            name="intake_agent",
            model="gemini-2.0-flash",
            instructions=self.prompt_path.read_text(),
        )

    def _build_prompt(self, form_input: Dict[str, Any]) -> str:
        template = self.prompt_path.read_text()
        return f"{template}\n\nINPUT_JSON:\n{json.dumps(form_input, ensure_ascii=True)}"

    def _default_output(self, form_input: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "opponent_level": str(form_input.get("opponent_level", "")),
            "scoreline": str(form_input.get("scoreline", "")),
            "set_scores": form_input.get("set_scores", []),
            "what_went_well": form_input.get("what_went_well", []),
            "what_went_poorly": form_input.get("what_went_poorly", []),
            "feelings": str(form_input.get("feelings", "")),
            "opponent_characteristics": form_input.get("opponent_characteristics", []),
            "pressure_moments": form_input.get("pressure_moments", []),
            "patterns_noticed": form_input.get("patterns_noticed", []),
            "confidence": 0.6,
        }

    def _validate_output(self, obj: Dict[str, Any]) -> None:
        require_keys(
            obj,
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
        if not isinstance(obj.get("set_scores"), list):
            raise ValueError("set_scores must be a list")
        require_list_of_str(obj.get("what_went_well"), "what_went_well", max_items=5)
        require_list_of_str(obj.get("what_went_poorly"), "what_went_poorly", max_items=5)
        require_list_of_str(
            obj.get("opponent_characteristics"), "opponent_characteristics", max_items=5
        )
        require_list_of_str(obj.get("pressure_moments"), "pressure_moments", max_items=5)
        require_list_of_str(obj.get("patterns_noticed"), "patterns_noticed", max_items=5)
        require_float_0_1(obj.get("confidence"), "confidence")
