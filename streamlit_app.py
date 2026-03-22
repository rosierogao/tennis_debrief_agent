import asyncio
import json
import os
import re
import plotly.graph_objects as go
from typing import Any, Dict, List, Optional, Tuple

import requests
import google.genai as genai
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

_MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:8080")

# Keys for bullet storage in player profile
_BULLET_FIELDS = [
    "what_went_well",
    "what_went_poorly",
    "opponent_characteristics",
    "pressure_moments",
    "patterns_noticed",
]

_TECHNIQUE_LABELS = {
    "first_serve_pct": "1st Serve %",
    "double_faults": "Double Faults",
    "forehand": "Forehand",
    "backhand": "Backhand",
    "rally_depth": "Rally Depth",
    "unforced_errors": "Unforced Errors",
    "return_of_serve": "Return",
    "footwork": "Footwork",
    "pressure_performance": "Pressure",
    "momentum": "Momentum",
}

_TECHNIQUE_ORDER = list(_TECHNIQUE_LABELS.keys())

_TECHNIQUE_COLOR = "#4f8ef7"


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


def _mcp_post(path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """POST to MCP server; returns parsed JSON or None on failure."""
    try:
        resp = requests.post(
            f"{_MCP_BASE_URL}{path}",
            json=payload,
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _load_profile() -> Dict[str, Any]:
    """Fetch player profile from MCP. Returns empty dict if unavailable."""
    result = _mcp_post("/tools/profile.get", {})
    if isinstance(result, dict):
        return result.get("profile") or {}
    return {}


def _ai_polish_and_dedup(field_label: str, existing: List[str], new_items: List[str]) -> List[str]:
    """
    Use Gemini to:
    1. Polish new items (fix typos, improve phrasing into clean tennis bullets)
    2. Deduplicate semantically against existing saved bullets
    3. Return the merged list

    Falls back to simple append-deduplicate on any error.
    """
    if not new_items:
        return existing

    prompt = f"""You are maintaining a tennis player's personal match notes library.

Field: {field_label}

Currently saved bullets:
{json.dumps(existing, indent=2)}

Newly entered items (raw — may have typos, rough phrasing, or overlap with existing ones):
{json.dumps(new_items, indent=2)}

Instructions:
1. Polish each new item: fix typos, improve phrasing into a clear concise tennis-specific bullet (e.g. "bkhand depth low" → "Backhand depth consistently short")
2. Check each polished new item against the existing bullets — if semantically the same or very similar, keep only the better-phrased version and discard the duplicate
3. Return the full merged list (existing bullets + non-duplicate new items), all polished

Return valid JSON only, no markdown:
{{"bullets": ["...", "..."]}}"""

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        text = re.sub(r"^```json\s*|^```\s*|\s*```$", "", response.text.strip(), flags=re.MULTILINE).strip()
        data = json.loads(text)
        return data.get("bullets") or (existing + new_items)
    except Exception:
        return list(dict.fromkeys(existing + new_items))


def _save_bullets_to_profile(
    field_items: Dict[str, List[str]],
    profile: Dict[str, Any],
    field_labels: Dict[str, str],
) -> None:
    """Polish + deduplicate new bullets with AI, then upsert profile."""
    patch: Dict[str, Any] = {}
    for field, new_items in field_items.items():
        if not new_items:
            continue
        key = f"{field}_bullets"
        existing: List[str] = profile.get(key) or []
        merged = _ai_polish_and_dedup(field_labels[field], existing, new_items)
        patch[key] = merged
    if patch:
        _mcp_post("/tools/profile.upsert", {"patch": patch})
        st.session_state["profile"].update(patch)


def _bullet_input(label: str, field: str, placeholder: str, profile: Dict[str, Any]) -> List[str]:
    """
    Render a bullet-picker widget.

    - If saved bullets exist: show pill toggles for saved bullets + a text area for new ones.
    - If no saved bullets yet: show just a text area (first-time experience).

    Returns the combined list of selected + newly typed items.
    """
    key = f"{field}_bullets"
    saved: List[str] = profile.get(key) or []

    selected: List[str] = []

    if saved:
        st.caption(label)
        selected = st.pills(
            label,
            options=saved,
            selection_mode="multi",
            key=f"select_{field}",
            label_visibility="collapsed",
        )
        new_raw = st.text_area(
            "➕ Add new",
            placeholder=placeholder,
            height=60,
            key=f"new_{field}",
        )
    else:
        new_raw = st.text_area(
            label,
            placeholder=placeholder,
            height=90,
            key=f"new_{field}",
        )

    new_items = _parse_list(new_raw)
    return selected + new_items


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


def _render_radar(technique_scores: Dict[str, Any]) -> None:
    """Render a Plotly radar chart for the given technique scores dict.

    Null-scored techniques show a grey dashed polygon outline at r=5.
    Scored techniques form a solid blue filled polygon.
    """
    scores = {k: technique_scores.get(k) for k in _TECHNIQUE_ORDER}
    scored_keys = [k for k in _TECHNIQUE_ORDER if scores[k] is not None]
    null_keys = [k for k in _TECHNIQUE_ORDER if scores[k] is None]

    if not scored_keys:
        st.caption(
            "No technique data — mention specific techniques in your notes to see scoring."
        )
        return

    all_labels = [_TECHNIQUE_LABELS[k] for k in _TECHNIQUE_ORDER]
    scored_labels = [_TECHNIQUE_LABELS[k] for k in scored_keys]
    scored_values = [scores[k] for k in scored_keys]
    # Close the polygon
    scored_labels_closed = scored_labels + [scored_labels[0]]
    scored_values_closed = scored_values + [scored_values[0]]

    fig = go.Figure()

    # Ghost trace — establishes all 10 axis labels at radius 0 (invisible)
    fig.add_trace(go.Scatterpolar(
        r=[0] * (len(all_labels) + 1),
        theta=all_labels + [all_labels[0]],
        mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Null-techniques trace — grey dashed polygon at r=5 (approximates "grey axes")
    if null_keys:
        null_labels = [_TECHNIQUE_LABELS[k] for k in null_keys]
        fig.add_trace(go.Scatterpolar(
            r=[5] * (len(null_labels) + 1),
            theta=null_labels + [null_labels[0]],
            mode="lines",
            line=dict(color="#555555", width=1, dash="dot"),
            opacity=0.4,
            showlegend=False,
            hoverinfo="skip",
        ))

    # Scored polygon — only non-null techniques
    fig.add_trace(go.Scatterpolar(
        r=scored_values_closed,
        theta=scored_labels_closed,
        fill="toself",
        fillcolor="rgba(79,142,247,0.15)",
        line=dict(color=_TECHNIQUE_COLOR, width=2),
        showlegend=False,
        hovertemplate="%{theta}: %{r}/5<extra></extra>",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5]),
            angularaxis=dict(tickfont=dict(size=10)),
        ),
        showlegend=False,
        margin=dict(l=40, r=40, t=30, b=30),
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cccccc"),
    )

    st.plotly_chart(fig, use_container_width=True)
    if null_keys:
        st.caption("grey axes = not mentioned this match")


def _render_trend_charts(matches: List[Dict[str, Any]]) -> None:
    """Render 10 technique trend charts from match history."""
    series: Dict[str, List] = {k: [] for k in _TECHNIQUE_ORDER}
    dates: List[str] = []

    for m in matches:
        record = m.get("match_record") or {}
        report = m.get("debrief_report") or {}
        date = record.get("match_date") or m.get("created_at", "")[:10]
        dates.append(date)
        scores = report.get("technique_scores") or {}
        for key in _TECHNIQUE_ORDER:
            series[key].append(scores.get(key))  # None if not mentioned

    if not dates:
        st.info("No match history yet. Complete your first debrief to start tracking progress.")
        return

    cols = st.columns(2)
    for idx, key in enumerate(_TECHNIQUE_ORDER):
        label = _TECHNIQUE_LABELS[key]
        vals = series[key]
        col = cols[idx % 2]

        with col:
            st.markdown(f"**{label}**")

            scored_dates = [d for d, v in zip(dates, vals) if v is not None]
            scored_vals = [v for v in vals if v is not None]

            if not scored_dates:
                st.caption("No data yet")
                continue

            # Compute interpolated y for null positions (midpoint of adjacent scores)
            interp_null_dates: List[str] = []
            interp_null_vals: List[float] = []
            for i, (d, v) in enumerate(zip(dates, vals)):
                if v is not None:
                    continue
                before = next((vals[j] for j in range(i - 1, -1, -1) if vals[j] is not None), None)
                after = next((vals[j] for j in range(i + 1, len(vals)) if vals[j] is not None), None)
                if before is not None or after is not None:
                    interp_y = ((before or after) + (after or before)) / 2
                    interp_null_dates.append(d)
                    interp_null_vals.append(interp_y)

            fig = go.Figure()

            # Dashed gap-connector trace (connects across nulls, low opacity)
            fig.add_trace(go.Scatter(
                x=dates,
                y=vals,
                mode="lines",
                line=dict(color=_TECHNIQUE_COLOR, width=1, dash="dot"),
                opacity=0.3,
                connectgaps=True,
                showlegend=False,
                hoverinfo="skip",
            ))

            # Hollow circle markers at null positions (interpolated y)
            if interp_null_dates:
                fig.add_trace(go.Scatter(
                    x=interp_null_dates,
                    y=interp_null_vals,
                    mode="markers",
                    marker=dict(
                        symbol="circle-open",
                        size=7,
                        color=_TECHNIQUE_COLOR,
                        opacity=0.4,
                        line=dict(width=1.5),
                    ),
                    showlegend=False,
                    hoverinfo="skip",
                ))

            # Solid scored-points trace
            fig.add_trace(go.Scatter(
                x=scored_dates,
                y=scored_vals,
                mode="lines+markers",
                line=dict(color=_TECHNIQUE_COLOR, width=2),
                marker=dict(size=7, color=_TECHNIQUE_COLOR),
                connectgaps=False,
                showlegend=False,
                hovertemplate="%{x}: %{y}/5<extra></extra>",
            ))

            # Trend direction: slope across last 3 scored points (fallback: last 2)
            if len(scored_vals) >= 3:
                delta = scored_vals[-1] - scored_vals[-3]
            elif len(scored_vals) >= 2:
                delta = scored_vals[-1] - scored_vals[-2]
            else:
                delta = 0
            trend = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            trend_color = "#4CAF50" if delta > 0 else ("#f44336" if delta < 0 else "#aaaaaa")

            fig.update_layout(
                yaxis=dict(range=[0, 5], tickvals=[1, 2, 3, 4, 5], tickfont=dict(size=9)),
                xaxis=dict(tickfont=dict(size=9)),
                margin=dict(l=30, r=10, t=10, b=30),
                height=160,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#cccccc"),
            )

            st.plotly_chart(fig, use_container_width=True)
            st.markdown(
                f"<div style='text-align:right;font-size:0.75rem;color:{trend_color}'>"
                f"{trend} last match: {scored_vals[-1]}/5</div>",
                unsafe_allow_html=True,
            )


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

    technique_scores = report.get("technique_scores")
    if technique_scores:
        st.markdown("#### Technique Snapshot")
        _render_radar(technique_scores)

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
            "technique_scores",
        }
    }
    if other_keys:
        st.markdown("#### Additional Notes")
        st.json(other_keys)


# ── Page setup ────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Court Debrief", page_icon="🎾", layout="wide")
st.title("🎾 Court Debrief")

with st.sidebar:
    st.header("Instructions")
    st.write(
        "Fill out the match form and submit. The app will run the multi-agent "
        "analysis and save results to the MCP memory server if it is running."
    )
    st.caption("Make sure you set your `GOOGLE_API_KEY` or Vertex AI env vars.")

# ── Load profile once per session ─────────────────────────────────────────────

if "profile" not in st.session_state:
    st.session_state["profile"] = _load_profile()

profile = st.session_state["profile"]

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_debrief, tab_history, tab_progress = st.tabs(["New Debrief", "Match History", "Progress"])

# ── Tab 1: New Debrief ────────────────────────────────────────────────────────

with tab_debrief:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Match Intake")
        match_date = st.date_input("Match date")
        opponent_level = st.selectbox(
            "Opponent level",
            ["Beginner", "Intermediate", "Advanced", "Competitive", "Unknown"],
        )
        scoreline = st.text_input("Scoreline", placeholder="6-4 3-6 6-2")

        what_went_well = _bullet_input(
            "What went well",
            "what_went_well",
            "First serve percentage, Forehand cross-court",
            profile,
        )
        what_went_poorly = _bullet_input(
            "What went poorly",
            "what_went_poorly",
            "Second serve under pressure, Backhand depth",
            profile,
        )

        feelings = _bullet_input(
            "Feelings",
            "feelings",
            "Started confident, tight in set 2",
            profile,
        )

        opponent_characteristics = _bullet_input(
            "Opponent characteristics",
            "opponent_characteristics",
            "Likes high balls, Strong backhand",
            profile,
        )
        pressure_moments = _bullet_input(
            "Pressure moments",
            "pressure_moments",
            "Serving at 4-5 in set 2, double faulted",
            profile,
        )
        patterns_noticed = _bullet_input(
            "Patterns noticed",
            "patterns_noticed",
            "Opponent attacked second serve",
            profile,
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
                "what_went_well": what_went_well,
                "what_went_poorly": what_went_poorly,
                "feelings": ", ".join(feelings),
                "opponent_characteristics": opponent_characteristics,
                "pressure_moments": pressure_moments,
                "patterns_noticed": patterns_noticed,
            }

            payload = json.dumps(match_record, ensure_ascii=True)
            with st.spinner("Running agents..."):
                events, final_report = _run_async(_run_agent_once(payload))

            if final_report:
                _render_debrief(final_report)
                st.success("Debrief complete.")

                _field_labels = {
                    "what_went_well": "What went well",
                    "what_went_poorly": "What went poorly",
                    "feelings": "Feelings",
                    "opponent_characteristics": "Opponent characteristics",
                    "pressure_moments": "Pressure moments",
                    "patterns_noticed": "Patterns noticed",
                }
                new_field_items = {
                    "what_went_well": what_went_well,
                    "what_went_poorly": what_went_poorly,
                    "feelings": feelings,
                    "opponent_characteristics": opponent_characteristics,
                    "pressure_moments": pressure_moments,
                    "patterns_noticed": patterns_noticed,
                }
                with st.spinner("Saving and polishing bullets..."):
                    _save_bullets_to_profile(new_field_items, profile, _field_labels)
            else:
                st.warning("No final report detected. Check the event log.")

            with st.expander("Event log"):
                for author, text in events:
                    st.write(f"**{author}**: {text}")

            with st.expander("Raw JSON"):
                st.json(final_report)

# ── Tab 2: Match History ──────────────────────────────────────────────────────

with tab_history:
    st.subheader("Match History")

    col_load, col_clear = st.columns([2, 1])
    with col_load:
        if st.button("Load history", key="load_history"):
            st.session_state["history_loaded"] = True
    with col_clear:
        if st.button("🗑 Clear all history", key="clear_all_btn"):
            st.session_state["confirm_clear_all"] = True

    if st.session_state.get("confirm_clear_all"):
        st.warning("This will permanently delete all match records and reset your saved form bullets. Are you sure?")
        col_yes, col_no = st.columns([1, 3])
        with col_yes:
            if st.button("Yes, clear everything", key="confirm_clear_yes", type="primary"):
                # Delete all matches
                _mcp_post("/tools/match.delete_all", {})
                # Clear all bullet fields from profile
                _BULLET_KEYS = [f"{f}_bullets" for f in [
                    "what_went_well", "what_went_poorly", "feelings",
                    "opponent_characteristics", "pressure_moments", "patterns_noticed",
                ]]
                empty_patch = {k: [] for k in _BULLET_KEYS}
                _mcp_post("/tools/profile.upsert", {"patch": empty_patch})
                # Reset local session state
                st.session_state["profile"].update(empty_patch)
                st.session_state.pop("confirm_clear_all", None)
                st.session_state["history_loaded"] = False
                st.success("All match history and saved bullets cleared.")
                st.rerun()
        with col_no:
            if st.button("Cancel", key="confirm_clear_no"):
                st.session_state.pop("confirm_clear_all", None)
                st.rerun()

    if st.session_state.get("history_loaded"):
        result = _mcp_post("/tools/match.retrieve_recent", {"limit": 20, "include_full": True})
        matches = (result or {}).get("matches") or []

        if not matches:
            st.info("No past matches found. Complete your first debrief to start building history.")
        else:
            st.caption(f"{len(matches)} match{'es' if len(matches) != 1 else ''} found")
            for m in matches:
                record = m.get("match_record") or {}
                report = m.get("debrief_report") or {}
                date = record.get("match_date") or m.get("created_at", "")[:10]
                scoreline = record.get("scoreline") or "—"
                opponent_level = record.get("opponent_level") or ""
                summary = report.get("summary") or m.get("summary") or "No summary."
                themes = m.get("themes") or []

                header = f"**{date}** · {scoreline}"
                if opponent_level:
                    header += f" · vs {opponent_level}"

                with st.expander(header):
                    st.write(summary)

                    if themes:
                        st.caption("Themes: " + " · ".join(themes))

                    if report:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            levers = report.get("levers") or []
                            if levers:
                                st.markdown("**Improvement Levers**")
                                for lv in levers:
                                    title = lv.get("lever") if isinstance(lv, dict) else str(lv)
                                    st.write(f"• {title}")
                        with col_b:
                            drills = report.get("drills") or []
                            if drills:
                                st.markdown("**Practice Drills**")
                                for dr in drills:
                                    title = dr.get("drill") if isinstance(dr, dict) else str(dr)
                                    st.write(f"• {title}")

                    match_id = m.get("match_id")
                    confirm_key = f"confirm_delete_{match_id}"
                    if st.session_state.get(confirm_key):
                        st.warning("Are you sure? This cannot be undone.")
                        col_yes, col_no = st.columns([1, 3])
                        with col_yes:
                            if st.button("Yes, delete", key=f"yes_{match_id}", type="primary"):
                                result = _mcp_post("/tools/match.delete", {"match_id": match_id})
                                if result and result.get("ok"):
                                    st.session_state.pop(confirm_key, None)
                                    st.session_state["history_loaded"] = False
                                    st.success("Match deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete failed.")
                        with col_no:
                            if st.button("Cancel", key=f"no_{match_id}"):
                                st.session_state.pop(confirm_key, None)
                                st.rerun()
                    else:
                        if st.button("🗑 Delete this match", key=f"del_{match_id}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

# ── Tab 3: Progress ───────────────────────────────────────────────────────────

with tab_progress:
    st.subheader("Technique Progress")
    st.caption("Scores are AI-inferred from your match notes. Only techniques you mention are scored.")

    if st.button("Load progress", key="load_progress"):
        st.session_state["progress_loaded"] = True

    if st.session_state.get("progress_loaded"):
        result = _mcp_post("/tools/match.retrieve_recent", {"limit": 20, "include_full": True})
        matches = (result or {}).get("matches") or []

        if not matches:
            st.info("No match history yet. Complete your first debrief to start tracking progress.")
        else:
            # Sort ascending by date for chronological trend lines
            matches = sorted(
                matches,
                key=lambda m: (m.get("match_record") or {}).get("match_date") or m.get("created_at", ""),
            )
            _render_trend_charts(matches)
