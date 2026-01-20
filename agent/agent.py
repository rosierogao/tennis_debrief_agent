"""
ADK multi-agent workflow entrypoint for tennis debrief system.

This file follows ADK's Python project structure:
  agent/agent.py
  agent/__init__.py
"""
from __future__ import annotations

from typing import Any, Dict, AsyncGenerator, Callable, Iterable
from pathlib import Path
import json
from datetime import datetime, date

from agent.utils.mcp_client import post_tool, MCPClientError
from agent.utils.json_guard import (
    validate_intake,
    validate_technical,
    validate_tactical,
    validate_mental,
    validate_patterns,
    validate_head_coach,
)


try:
    # ADK imports (per google-adk package)
    from google.adk import Agent  # type: ignore
    from google.adk.agents.base_agent import BaseAgent  # type: ignore
    from google.adk.agents.invocation_context import InvocationContext  # type: ignore
    from google.adk.events.event import Event  # type: ignore
    from google.genai import types  # type: ignore
except Exception:  # pragma: no cover - optional during development
    Agent = None  # type: ignore
    BaseAgent = None  # type: ignore
    InvocationContext = None  # type: ignore
    Event = None  # type: ignore
    types = None  # type: ignore


def _tool_profile_get() -> Dict[str, Any]:
    """Tool: profile.get."""
    try:
        return post_tool("/tools/profile.get", {})
    except MCPClientError as exc:
        return {"error": {"code": "INTERNAL", "message": str(exc)}}


def _tool_profile_upsert(patch: Dict[str, Any]) -> Dict[str, Any]:
    """Tool: profile.upsert."""
    try:
        return post_tool("/tools/profile.upsert", {"patch": patch})
    except MCPClientError as exc:
        return {"error": {"code": "INTERNAL", "message": str(exc)}}


def _tool_match_store(
    match_record: Dict[str, Any],
    debrief_report: Dict[str, Any],
    themes: list[str],
    summary: str,
    match_id: str | None = None,
) -> Dict[str, Any]:
    """Tool: match.store."""
    payload = {
        "match_record": match_record,
        "debrief_report": debrief_report,
        "themes": themes,
        "summary": summary,
        "match_id": match_id,
    }
    try:
        return post_tool("/tools/match.store", payload)
    except MCPClientError as exc:
        return {"error": {"code": "INTERNAL", "message": str(exc)}}


def _tool_match_retrieve_recent(limit: int, include_full: bool = False) -> Dict[str, Any]:
    """Tool: match.retrieve_recent."""
    payload = {"limit": limit, "include_full": include_full}
    try:
        return post_tool("/tools/match.retrieve_recent", payload)
    except MCPClientError as exc:
        return {"error": {"code": "INTERNAL", "message": str(exc)}}


def _prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / name).read_text()


if Agent is not None:
    def _strip_json_fence(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
                return "\n".join(lines[1:-1]).strip()
        return stripped

    def _extract_json_objects(text: str) -> list[str]:
        starts: list[int] = []
        results: list[str] = []
        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_string = False
                continue
            if ch == "\"":
                in_string = True
                continue
            if ch == "{":
                if depth == 0:
                    starts.append(i)
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and starts:
                    start = starts.pop()
                    results.append(text[start : i + 1])
        return results

    def _parse_json_maybe(value: Any) -> Any:
        if isinstance(value, str):
            try:
                cleaned = _strip_json_fence(value)
                objects = _extract_json_objects(cleaned)
                candidate = objects[0] if objects else cleaned
                if objects:
                    candidate = max(objects, key=len)
                cleaned = candidate
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return value
        return value

    def _parse_match_record_from_text(text: str) -> Dict[str, Any] | None:
        cleaned = _strip_json_fence(text)
        # Prefer full JSON if possible.
        try:
            loaded = json.loads(cleaned)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass

        candidates = _extract_json_objects(cleaned)
        for chunk in candidates:
            try:
                loaded = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if not isinstance(loaded, dict):
                continue
            if {"scoreline", "set_scores"} <= set(loaded.keys()):
                return loaded
            if {"opponent_level", "scoreline"} <= set(loaded.keys()):
                return loaded
        return None

    def _instruction_with_state(prompt_name: str, state_keys: Iterable[str]) -> Callable[[Any], str]:
        template = _prompt(prompt_name)

        def _provider(ctx: Any) -> str:
            payload = {key: ctx.state.get(key) for key in state_keys}
            return f"{template}\n\nINPUT:\n{json.dumps(payload, ensure_ascii=True)}"

        return _provider

    def _content_to_text(content: Any) -> str:
        if content is None:
            return ""
        parts = getattr(content, "parts", None)
        if parts:
            texts = []
            for part in parts:
                text = getattr(part, "text", None)
                if text:
                    texts.append(text)
            if texts:
                return "".join(texts).strip()
        text = getattr(content, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        if hasattr(content, "model_dump"):
            try:
                return json.dumps(content.model_dump(), ensure_ascii=True)
            except Exception:
                pass
        return str(content)

    def _last_user_text(ctx: InvocationContext) -> str:
        for event in reversed(ctx.session.events):
            if event.author != "user" or not event.content:
                continue
            text = _content_to_text(event.content)
            if text.strip():
                return text.strip()
        return ""

    def _find_match_record_in_events(ctx: InvocationContext) -> Dict[str, Any] | None:
        for event in reversed(ctx.session.events):
            if event.author != "user" or not event.content:
                continue
            text = _content_to_text(event.content)
            if not text:
                continue
            parsed = _parse_match_record_from_text(text)
            if parsed is not None:
                return parsed
        return None

    def _recent_user_buffer(ctx: InvocationContext, max_events: int = 60) -> str:
        buffer = ""
        count = 0
        for event in reversed(ctx.session.events):
            if event.author != "user" or not event.content:
                continue
            text = _content_to_text(event.content).strip()
            if not text:
                continue
            buffer = f"{text}\n{buffer}" if buffer else text
            count += 1
            if count >= max_events:
                break
        return buffer

    def _parse_match_record_from_recent_events(
        ctx: InvocationContext, max_events: int = 60
    ) -> Dict[str, Any] | None:
        buffer = _recent_user_buffer(ctx, max_events=max_events)
        if not buffer:
            return None
        return _parse_match_record_from_text(buffer)

    def _last_agent_text(ctx: InvocationContext, agent_name: str) -> str:
        for event in reversed(ctx.session.events):
            if event.author != agent_name or not event.content:
                continue
            text = _content_to_text(event.content)
            if text.strip():
                return text.strip()
        return ""

    def _parse_match_date(match_record: Dict[str, Any]) -> date | None:
        raw = match_record.get("match_date")
        if not raw:
            return None
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw).date()
            except ValueError:
                return None
        return None

    def _filter_recent_matches(
        match_record: Dict[str, Any], matches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        cutoff = _parse_match_date(match_record)
        if cutoff is None:
            return matches
        filtered: list[dict[str, Any]] = []
        for item in matches:
            item_date: date | None = None
            match_payload = item.get("match_record")
            if isinstance(match_payload, dict):
                raw_match_date = match_payload.get("match_date")
                if isinstance(raw_match_date, str):
                    try:
                        item_date = datetime.fromisoformat(raw_match_date).date()
                    except ValueError:
                        item_date = None
            if item_date is None:
                created_at = item.get("created_at")
                if not isinstance(created_at, str):
                    continue
                try:
                    item_date = datetime.fromisoformat(created_at).date()
                except ValueError:
                    continue
            if item_date < cutoff:
                filtered.append(item)
        return filtered

    def _is_agent_echo(text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in (
                "[technical_agent]",
                "[tactical_agent]",
                "[mental_agent]",
                "[pattern_detector_agent]",
                "[head_coach_agent]",
                "[tennis_debrief_workflow]",
                "[intake_agent]",
            )
        )

    class SequentialOrchestrator(BaseAgent):  # type: ignore[misc]
        """Runs sub-agents in a fixed order without extra user input."""

        async def _run_async_impl(
            self, ctx: InvocationContext
        ) -> AsyncGenerator["Event", None]:
            if ctx.session.state.get("_pipeline_completed_for") == ctx.invocation_id:
                return
            ctx.session.state["_pipeline_completed_for"] = ctx.invocation_id

            if ctx.user_content and "match_record" not in ctx.session.state:
                user_text = _content_to_text(ctx.user_content).strip()
                if user_text:
                    parsed = _parse_match_record_from_text(user_text)
                    if parsed is not None:
                        fingerprint = json.dumps(parsed, sort_keys=True, ensure_ascii=True)
                        last_fingerprint = ctx.session.state.get("_last_input_fingerprint")
                        if fingerprint == last_fingerprint:
                            if Event is not None and types is not None:
                                content = types.Content(
                                    role="model",
                                    parts=[types.Part(text="Already processed this input. Paste a new match JSON to run again.")],
                                )
                                ctx.end_invocation = True
                                yield Event(
                                    invocation_id=ctx.invocation_id,
                                    author=self.name,
                                    branch=ctx.branch,
                                    content=content,
                                )
                                return
                        ctx.session.state["_last_input_fingerprint"] = fingerprint
                        ctx.session.state["match_record"] = parsed
            if "match_record" not in ctx.session.state:
                fallback_text = _last_user_text(ctx)
                if fallback_text:
                    parsed = _parse_match_record_from_text(fallback_text)
                    if parsed is not None:
                        ctx.session.state["match_record"] = parsed
            if "match_record" not in ctx.session.state:
                parsed = _parse_match_record_from_recent_events(ctx)
                if parsed is not None:
                    ctx.session.state["match_record"] = parsed
            if "match_record" not in ctx.session.state:
                buffer = _recent_user_buffer(ctx)
                if "{" in buffer and "}" not in buffer:
                    return
                last_agent_text = _last_agent_text(ctx, self.name)
                if last_agent_text == "Paste a match JSON object to start the debrief.":
                    return
                if Event is not None and types is not None:
                    content = types.Content(
                        role="model",
                        parts=[types.Part(text="Paste a match JSON object to start the debrief.")],
                    )
                    ctx.end_invocation = True
                    yield Event(
                        invocation_id=ctx.invocation_id,
                        author=self.name,
                        branch=ctx.branch,
                        content=content,
                    )
                return

            for sub_agent in self.sub_agents:
                if sub_agent.name == "intake_agent" and ctx.session.state.get("match_record"):
                    continue
                if sub_agent.name == "head_coach_agent":
                    recent = _tool_match_retrieve_recent(limit=5, include_full=True)
                    matches = recent.get("matches") if isinstance(recent, dict) else None
                    if isinstance(matches, list):
                        match_record = ctx.session.state.get("match_record")
                        if isinstance(match_record, dict):
                            ctx.session.state["recent_matches"] = _filter_recent_matches(
                                match_record, matches
                            )
                        else:
                            ctx.session.state["recent_matches"] = matches
                    else:
                        ctx.session.state["recent_matches"] = []

                async for event in sub_agent.run_async(ctx):
                    yield event
                if ctx.end_invocation:
                    return

                if getattr(sub_agent, "output_key", None):
                    key = sub_agent.output_key
                    ctx.session.state[key] = _parse_json_maybe(ctx.session.state.get(key))

            debrief_report = ctx.session.state.get("debrief_report")
            if debrief_report is None:
                return

            output_dir = Path(__file__).resolve().parents[1] / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "debrief_report.json"

            payload = _parse_json_maybe(debrief_report)
            if isinstance(payload, str):
                payload = {"raw": payload}

            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            match_record = ctx.session.state.get("match_record")
            summary = ""
            if isinstance(payload, dict):
                summary = str(payload.get("summary", ""))
            patterns = ctx.session.state.get("patterns")
            themes: list[str] = []
            if isinstance(patterns, list):
                for item in patterns:
                    if isinstance(item, dict) and item.get("pattern"):
                        themes.append(str(item.get("pattern")))
            if isinstance(match_record, dict):
                _tool_match_store(
                    match_record=match_record,
                    debrief_report=payload if isinstance(payload, dict) else {},
                    themes=themes,
                    summary=summary,
                )

            if Event is not None and types is not None:
                content = types.Content(role="model", parts=[types.Part(text=json.dumps(payload))])
                ctx.end_invocation = True
                yield Event(
                    invocation_id=ctx.invocation_id,
                    author=self.name,
                    branch=ctx.branch,
                    content=content,
                )
                return

    intake_agent = Agent(
        name="intake_agent",
        model="gemini-2.0-flash",
        instruction=_prompt("intake.md"),
        output_key="match_record",
        tools=[validate_intake],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    technical_agent = Agent(
        name="technical_agent",
        model="gemini-2.0-flash",
        instruction=_instruction_with_state("technical.md", ["match_record"]),
        output_key="technical_hypotheses",
        tools=[validate_technical],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    tactical_agent = Agent(
        name="tactical_agent",
        model="gemini-2.0-flash",
        instruction=_instruction_with_state("tactical.md", ["match_record"]),
        output_key="tactical_observations",
        tools=[validate_tactical],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    mental_agent = Agent(
        name="mental_agent",
        model="gemini-2.0-flash",
        instruction=_instruction_with_state("mental.md", ["match_record"]),
        output_key="mental_observations",
        tools=[validate_mental],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    pattern_detector_agent = Agent(
        name="pattern_detector_agent",
        model="gemini-2.0-flash",
        instruction=_instruction_with_state(
            "pattern_detector.md",
            ["match_record", "technical_hypotheses", "tactical_observations", "mental_observations"],
        ),
        output_key="patterns",
        tools=[validate_patterns],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    head_coach_agent = Agent(
        name="head_coach_agent",
        model="gemini-2.0-flash",
        instruction=_instruction_with_state(
            "head_coach.md",
            [
                "match_record",
                "technical_hypotheses",
                "tactical_observations",
                "mental_observations",
                "patterns",
                "recent_matches",
            ],
        ),
        output_key="debrief_report",
        tools=[
            validate_head_coach,
            _tool_profile_get,
            _tool_profile_upsert,
            _tool_match_store,
            _tool_match_retrieve_recent,
        ],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )

    root_agent = SequentialOrchestrator(
        name="tennis_debrief_workflow",
        sub_agents=[intake_agent, technical_agent, tactical_agent, mental_agent, pattern_detector_agent, head_coach_agent],
    )
else:
    # Fallback placeholder so imports don't crash if ADK isn't installed yet.
    root_agent = None
