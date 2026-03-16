import asyncio
import json
import re
from typing import Any, Dict, List, Tuple

import streamlit as st

from google.adk.apps.app import App
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import (
    InMemoryCredentialService,
)
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from agent.agent import root_agent


def _parse_list(text: str) -> List[str]:
    if not text:
        return []
    items = re.split(r"[\n,]", text)
    return [item.strip() for item in items if item.strip()]


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _run_agent_once(message: str) -> Tuple[List[Tuple[str, str]], Dict[str, Any]]:
    app = App(name="tennis_debrief_app", root_agent=root_agent)
    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    credential_service = InMemoryCredentialService()

    session = await session_service.create_session(app_name=app.name, user_id="web_ui")
    runner = Runner(
        app=app,
        session_service=session_service,
        artifact_service=artifact_service,
        credential_service=credential_service,
    )

    content = types.Content(role="user", parts=[types.Part(text=message)])
    events: List[Tuple[str, str]] = []
    final_report: Dict[str, Any] = {}

    async for event in runner.run_async(
        user_id=session.user_id, session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            text = "".join(part.text or "" for part in event.content.parts)
            if text:
                events.append((event.author, text))
                if event.author == "tennis_debrief_workflow":
                    try:
                        final_report = json.loads(text)
                    except json.JSONDecodeError:
                        final_report = {"raw": text}

    await runner.close()
    return events, final_report


def _render_debrief(report: Dict[str, Any]) -> None:
    if not report:
        st.warning("No debrief report found.")
        return

    if "raw" in report:
        st.write(report["raw"])
        return

    summary = report.get("summary")
    focus_areas = report.get("focus_areas") or []
    levers = report.get("levers") or []
    drills = report.get("drills") or []
    history = report.get("history_comparison") or {}
    confidence = report.get("confidence")

    st.markdown("#### Summary")
    st.write(summary or "No summary provided.")

    st.markdown("#### Focus Areas")
    if focus_areas:
        for item in focus_areas:
            st.write(f"• {item}")
    else:
        st.write("No focus areas listed.")

    st.markdown("#### Improvement Levers")
    if levers:
        for idx, lever in enumerate(levers, start=1):
            title = lever.get("lever") if isinstance(lever, dict) else str(lever)
            reason = lever.get("why") if isinstance(lever, dict) else None
            st.markdown(f"**{idx}. {title}**")
            if reason:
                st.caption(reason)
    else:
        st.write("No levers provided.")

    st.markdown("#### Practice Drills")
    if drills:
        for idx, drill in enumerate(drills, start=1):
            title = drill.get("drill") if isinstance(drill, dict) else str(drill)
            reason = drill.get("why") if isinstance(drill, dict) else None
            st.markdown(f"**{idx}. {title}**")
            if reason:
                st.caption(reason)
    else:
        st.write("No drills provided.")

    st.markdown("#### Compared to Recent Matches")
    history_summary = history.get("summary") if isinstance(history, dict) else None
    history_patterns = history.get("patterns") if isinstance(history, dict) else None
    if history_summary:
        st.write(history_summary)
    else:
        st.write("No comparison summary provided.")
    if history_patterns:
        for item in history_patterns:
            st.write(f"• {item}")

    other_keys = {
        key: value
        for key, value in report.items()
        if key
        not in {
            "summary",
            "focus_areas",
            "levers",
            "drills",
            "history_comparison",
            "confidence",
        }
    }
    if other_keys:
        st.markdown("#### Additional Notes")
        st.json(other_keys)


st.set_page_config(page_title="Tennis Debrief", page_icon="🎾", layout="wide")
st.title("🎾 Tennis Debrief Agent")

with st.sidebar:
    st.header("Instructions")
    st.write(
        "Fill out the match form and submit. The app will run the multi-agent "
        "analysis and save results to the MCP memory server if it is running."
    )
    st.caption("Make sure you set your `GOOGLE_API_KEY` or Vertex AI env vars.")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Match Intake")
    match_date = st.date_input("Match date")
    opponent_level = st.selectbox(
        "Opponent level",
        ["Beginner", "Intermediate", "Advanced", "Competitive", "Unknown"],
    )
    scoreline = st.text_input("Scoreline", placeholder="6-4 3-6 6-2")
    what_went_well_raw = st.text_area(
        "What went well (comma or newline separated)",
        placeholder="First serve percentage, Forehand cross-court",
        height=90,
    )
    what_went_poorly_raw = st.text_area(
        "What went poorly (comma or newline separated)",
        placeholder="Second serve under pressure, Backhand depth",
        height=90,
    )
    feelings = st.text_input("Feelings", placeholder="Started confident, tight in set 2")
    opponent_characteristics_raw = st.text_area(
        "Opponent characteristics (comma or newline separated)",
        placeholder="Likes high balls, Strong backhand",
        height=90,
    )
    pressure_moments_raw = st.text_area(
        "Pressure moments (comma or newline separated)",
        placeholder="Serving at 4-5 in set 2, double faulted",
        height=90,
    )
    patterns_noticed_raw = st.text_area(
        "Patterns noticed (comma or newline separated)",
        placeholder="Opponent attacked second serve",
        height=90,
    )

    submitted = st.button("Run Debrief", type="primary")

with col_right:
    st.subheader("Debrief Output")
    if submitted:
        match_record = {
            "match_date": match_date.isoformat() if match_date else "",
            "opponent_level": opponent_level,
            "scoreline": scoreline,
            "set_scores": [],
            "what_went_well": _parse_list(what_went_well_raw),
            "what_went_poorly": _parse_list(what_went_poorly_raw),
            "feelings": feelings,
            "opponent_characteristics": _parse_list(opponent_characteristics_raw),
            "pressure_moments": _parse_list(pressure_moments_raw),
            "patterns_noticed": _parse_list(patterns_noticed_raw),
        }

        payload = json.dumps(match_record, ensure_ascii=True)
        with st.spinner("Running agents..."):
            events, final_report = _run_async(_run_agent_once(payload))

        if final_report:
            _render_debrief(final_report)
            st.success("Debrief complete.")
        else:
            st.warning("No final report detected. Check the event log.")

        with st.expander("Event log"):
            for author, text in events:
                st.write(f"**{author}**: {text}")

        with st.expander("Raw JSON"):
            st.json(final_report)
