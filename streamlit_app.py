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
2. Remove match-specific numbers, percentages, or counts so bullets are reusable across future matches (e.g. "First serve was 70% in" → "First serve percentage was high", "Made 6 double faults" → "Double faults under pressure")
3. Check each polished new item against the existing bullets — if semantically the same or very similar, keep only the better-phrased version and discard the duplicate
4. Return the full merged list (existing bullets + non-duplicate new items), all polished

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
    new_raw = ""

    if saved:
        with st.expander(label):
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
                height=50,
                key=f"new_{field}",
            )
    else:
        new_raw = st.text_area(
            label,
            placeholder=placeholder,
            height=68,
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


_COMPARE_COLORS = [
    ("#4f8ef7", "rgba(79,142,247,0.12)"),
    ("#ff8c00", "rgba(255,140,0,0.12)"),
    ("#2ecc71", "rgba(46,204,113,0.12)"),
    ("#e74c3c", "rgba(231,76,60,0.12)"),
    ("#9b59b6", "rgba(155,89,182,0.12)"),
    ("#795548", "rgba(121,85,72,0.12)"),
]


def _render_compare_radar(overlays: List[Dict[str, Any]]) -> None:
    """Render overlaid radar polygons, one per match. Max 6 overlays."""
    if not overlays:
        st.caption("No matches selected.")
        return

    all_labels = [_TECHNIQUE_LABELS[k] for k in _TECHNIQUE_ORDER]
    fig = go.Figure()

    # Ghost trace to establish all axis labels
    fig.add_trace(go.Scatterpolar(
        r=[0] * (len(all_labels) + 1),
        theta=all_labels + [all_labels[0]],
        mode="lines",
        line=dict(color="rgba(0,0,0,0)", width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    for i, overlay in enumerate(overlays[:6]):
        line_color, fill_color = _COMPARE_COLORS[i]
        scores = overlay["scores"]
        scored_keys = [k for k in _TECHNIQUE_ORDER if scores.get(k) is not None]
        if not scored_keys:
            continue
        scored_labels = [_TECHNIQUE_LABELS[k] for k in scored_keys]
        scored_vals = [scores[k] for k in scored_keys]
        fig.add_trace(go.Scatterpolar(
            r=scored_vals + [scored_vals[0]],
            theta=scored_labels + [scored_labels[0]],
            fill="toself",
            fillcolor=fill_color,
            line=dict(color=line_color, width=2),
            name=overlay["label"],
            hovertemplate="%{theta}: %{r}/5<extra>" + overlay["label"] + "</extra>",
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5]),
            angularaxis=dict(tickfont=dict(size=10)),
        ),
        showlegend=True,
        legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=40, r=40, t=30, b=30),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cccccc"),
    )
    st.plotly_chart(fig, use_container_width=True, key="compare_radar")


def _ntrp_multiplier(opponent_level: str, factor: float = 0.15) -> float:
    """Return a score multiplier based on opponent NTRP rating.

    Baseline is 4.0 (multiplier = 1.0). Each 1.0 NTRP step adds/subtracts `factor`.
    Unknown opponent level returns 1.0 (no adjustment).
    """
    try:
        ntrp = float(opponent_level)
    except (TypeError, ValueError):
        return 1.0
    return 1.0 + (ntrp - 4.0) * factor


def _parse_win_loss(scoreline: str) -> Optional[bool]:
    """Return True=win, False=loss, None=unknown from a scoreline string."""
    if not scoreline:
        return None
    s = scoreline.lower().strip()
    if s.startswith("won") or s.startswith("w "):
        return True
    if s.startswith("lost") or s.startswith("l "):
        return False
    sets = re.findall(r'(\d+)[-–](\d+)', scoreline)
    if not sets:
        return None
    player_sets = sum(1 for p, o in sets if int(p) > int(o))
    opp_sets = sum(1 for p, o in sets if int(o) > int(p))
    if player_sets > opp_sets:
        return True
    if opp_sets > player_sets:
        return False
    return None


def _render_trend_charts(matches: List[Dict[str, Any]]) -> None:
    """Render 10 technique trend charts from match history."""
    series: Dict[str, List] = {k: [] for k in _TECHNIQUE_ORDER}
    dates: List[str] = []
    win_loss: List[Optional[bool]] = []
    opponent_levels: List[str] = []

    for m in matches:
        record = m.get("match_record") or {}
        report = m.get("debrief_report") or {}
        date = record.get("match_date") or m.get("created_at", "")[:10]
        dates.append(date)
        win_loss.append(_parse_win_loss(record.get("scoreline") or ""))
        opponent_levels.append(record.get("opponent_level") or "")
        scores = report.get("technique_scores") or {}
        for key in _TECHNIQUE_ORDER:
            series[key].append(scores.get(key))  # None if not mentioned

    if not dates:
        st.info("No match history yet. Complete your first debrief to start tracking progress.")
        return

    normalize = st.toggle("Adjust for opponent level", key="normalize_progress")
    adj_factor = 0.15
    if normalize:
        adj_factor = st.slider(
            "Adjustment strength (% per NTRP step from 4.0)",
            min_value=5, max_value=30, value=15, step=5,
            format="%d%%", key="adj_factor_progress",
        ) / 100.0
        st.caption(
            f"e.g. vs 5.0 NTRP → ×{1.0 + (5.0 - 4.0) * adj_factor:.2f} | "
            f"vs 3.0 NTRP → ×{1.0 + (3.0 - 4.0) * adj_factor:.2f}"
        )

    # Global date range so all charts share the same x-axis
    x_min, x_max = dates[0], dates[-1]

    cols = st.columns(2)
    for idx, key in enumerate(_TECHNIQUE_ORDER):
        label = _TECHNIQUE_LABELS[key]
        vals = series[key]
        col = cols[idx % 2]

        with col:
            st.markdown(f"**{label}**")

            if normalize:
                vals = [
                    round(min(5.0, v * _ntrp_multiplier(opponent_levels[i], adj_factor)), 1)
                    if v is not None else None
                    for i, v in enumerate(vals)
                ]
            adj_label = " (adj)" if normalize else ""

            if not any(v is not None for v in vals):
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

            # Rolling baseline: mean of last 5 scored values at each scored point
            scored_indices = [(i, d, v) for i, (d, v) in enumerate(zip(dates, vals)) if v is not None]
            baseline_dates: List[str] = []
            baseline_vals: List[float] = []
            for rank, (i, d, v) in enumerate(scored_indices):
                window = [sv for _, _, sv in scored_indices[max(0, rank - 4): rank + 1]]
                baseline_dates.append(d)
                baseline_vals.append(round(sum(window) / len(window), 2))

            # Build full-length arrays per outcome (None for other-outcome positions)
            # so connectgaps=False only links consecutive same-outcome points.
            s_dates = [d for _, d, _ in scored_indices]
            win_y, loss_y, unk_y = [], [], []
            win_text, loss_text, unk_text = [], [], []
            for orig_idx, d, v in scored_indices:
                wl = win_loss[orig_idx]
                label = f"{'W' if wl is True else ('L' if wl is False else '?')} {d}: {v}/5{adj_label}"
                win_y.append(v if wl is True else None)
                loss_y.append(v if wl is False else None)
                unk_y.append(v if wl is None else None)
                win_text.append(label if wl is True else "")
                loss_text.append(label if wl is False else "")
                unk_text.append(label if wl is None else "")

            fig = go.Figure()

            # Rolling baseline trace (dashed grey)
            if len(baseline_dates) >= 2:
                fig.add_trace(go.Scatter(
                    x=baseline_dates,
                    y=baseline_vals,
                    mode="lines",
                    line=dict(color="#888888", width=1.5, dash="dash"),
                    opacity=0.6,
                    connectgaps=False,
                    showlegend=False,
                    hovertemplate="Baseline (last 5): %{y:.1f}<extra></extra>",
                ))

            # Win trend line (green) — connects all wins across gaps
            if any(v is not None for v in win_y):
                fig.add_trace(go.Scatter(
                    x=s_dates, y=win_y,
                    mode="lines+markers",
                    line=dict(color="#4CAF50", width=2),
                    marker=dict(size=8, color="#4CAF50", line=dict(width=1, color="#ffffff")),
                    connectgaps=True, showlegend=False,
                    text=win_text,
                    hovertemplate="%{text}<extra></extra>",
                ))

            # Loss trend line (red) — connects all losses across gaps
            if any(v is not None for v in loss_y):
                fig.add_trace(go.Scatter(
                    x=s_dates, y=loss_y,
                    mode="lines+markers",
                    line=dict(color="#f44336", width=2),
                    marker=dict(size=8, color="#f44336", line=dict(width=1, color="#ffffff")),
                    connectgaps=True, showlegend=False,
                    text=loss_text,
                    hovertemplate="%{text}<extra></extra>",
                ))

            # Unknown outcome (blue) — connects all unknowns across gaps
            if any(v is not None for v in unk_y):
                fig.add_trace(go.Scatter(
                    x=s_dates, y=unk_y,
                    mode="lines+markers",
                    line=dict(color=_TECHNIQUE_COLOR, width=2),
                    marker=dict(size=8, color=_TECHNIQUE_COLOR, line=dict(width=1, color="#ffffff")),
                    connectgaps=True, showlegend=False,
                    text=unk_text,
                    hovertemplate="%{text}<extra></extra>",
                ))

            # Trend direction: slope across last 3 scored points (fallback: last 2)
            all_scored_vals = [v for _, _, v in scored_indices]
            if len(all_scored_vals) >= 3:
                delta = all_scored_vals[-1] - all_scored_vals[-3]
            elif len(all_scored_vals) >= 2:
                delta = all_scored_vals[-1] - all_scored_vals[-2]
            else:
                delta = 0
            trend = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            trend_color = "#4CAF50" if delta > 0 else ("#f44336" if delta < 0 else "#aaaaaa")

            fig.update_layout(
                yaxis=dict(range=[0.5, 5.4], tickvals=[1, 2, 3, 4, 5], tickfont=dict(size=9)),
                xaxis=dict(range=[x_min, x_max], tickfont=dict(size=9)),
                margin=dict(l=30, r=10, t=10, b=30),
                height=160,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#cccccc"),
            )

            st.plotly_chart(fig, use_container_width=True, key=f"trend_{key}")
            st.markdown(
                f"<div style='text-align:right;font-size:0.75rem;color:{trend_color}'>"
                f"{trend} last match: {all_scored_vals[-1]}/5</div>",
                unsafe_allow_html=True,
            )


def _render_debrief(report: Dict[str, Any], opponent_level: str = "Unknown") -> None:
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
        normalize_d = st.toggle("Adjust for opponent level", key="normalize_debrief")
        adj_factor_d = 0.15
        if normalize_d:
            adj_factor_d = st.slider(
                "Adjustment strength (% per NTRP step from 4.0)",
                min_value=5, max_value=30, value=15, step=5,
                format="%d%%", key="adj_factor_debrief",
            ) / 100.0
            mult = _ntrp_multiplier(opponent_level, adj_factor_d)
            st.caption(f"vs {opponent_level} NTRP → ×{mult:.2f}")
            technique_scores = {
                k: round(min(5.0, v * mult), 1) if v is not None else None
                for k, v in technique_scores.items()
            }
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

st.set_page_config(page_title="Court Debrief", page_icon="🎾", layout="wide", initial_sidebar_state="collapsed")
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

tab_debrief, tab_compare, tab_progress, tab_history = st.tabs(
    ["New Debrief", "Compare", "Progress", "Match History"]
)

# ── Tab 1: New Debrief ────────────────────────────────────────────────────────

with tab_debrief:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Match Intake")
        match_date = st.date_input("Match date")
        opponent_level = st.selectbox(
            "Opponent NTRP rating",
            ["Unknown", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.5", "7.0"],
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
                st.session_state["last_debrief"] = final_report
                st.session_state["last_events"] = events
                st.session_state["last_opponent_level"] = str(opponent_level)

            if final_report:
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

        if st.session_state.get("last_debrief"):
            _render_debrief(
                st.session_state["last_debrief"],
                opponent_level=st.session_state.get("last_opponent_level", "Unknown"),
            )
            st.success("Debrief complete.")

            with st.expander("Event log"):
                for author, text in st.session_state.get("last_events", []):
                    st.write(f"**{author}**: {text}")

            with st.expander("Raw JSON"):
                st.json(st.session_state["last_debrief"])

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
    st.caption("🟢 Win · 🔴 Loss · 🔵 Unknown  ·  Opponent level adjustment: baseline 4.0 NTRP, ±15% per 1.0 rating step, capped at 5.")

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

# ── Tab 4: Compare ────────────────────────────────────────────────────────────

with tab_compare:
    st.subheader("Compare Matches")
    st.caption("Overlay up to 6 technique snapshots on a single radar.")

    if st.button("Load matches", key="load_compare"):
        st.session_state["compare_loaded"] = True

    if st.session_state.get("compare_loaded"):
        result = _mcp_post("/tools/match.retrieve_recent", {"limit": 20, "include_full": True})
        c_matches = (result or {}).get("matches") or []

        if not c_matches:
            st.info("No past matches found.")
        else:
            def _match_label(m: Dict[str, Any]) -> str:
                record = m.get("match_record") or {}
                date   = record.get("match_date") or m.get("created_at", "")[:10]
                score  = record.get("scoreline") or "—"
                lvl    = record.get("opponent_level") or ""
                label  = f"{date} · {score}"
                if lvl:
                    label += f" · vs {lvl} NTRP"
                return label

            options = [_match_label(m) for m in c_matches]
            selected_labels = st.multiselect(
                "Select matches to compare (max 6)",
                options=options,
                key="compare_selected",
            )
            if len(selected_labels) > 6:
                st.warning("Max 6 matches. Only the first 6 will be shown.")
                selected_labels = selected_labels[:6]

            if selected_labels:
                normalize_c = st.toggle("Adjust for opponent level", key="normalize_compare")
                adj_factor_c = 0.15
                if normalize_c:
                    adj_factor_c = st.slider(
                        "Adjustment strength (% per NTRP step from 4.0)",
                        min_value=5, max_value=30, value=15, step=5,
                        format="%d%%", key="adj_factor_compare",
                    ) / 100.0
                    st.caption(
                        f"e.g. vs 5.0 NTRP → ×{1.0 + (5.0 - 4.0) * adj_factor_c:.2f} | "
                        f"vs 3.0 NTRP → ×{1.0 + (3.0 - 4.0) * adj_factor_c:.2f}"
                    )

                label_to_match = {_match_label(m): m for m in c_matches}
                overlays = []
                for lbl in selected_labels:
                    m = label_to_match.get(lbl)
                    if not m:
                        continue
                    record = m.get("match_record") or {}
                    report = m.get("debrief_report") or {}
                    raw_scores = report.get("technique_scores") or {}
                    opp_lvl = record.get("opponent_level") or "Unknown"
                    if normalize_c:
                        scores = {
                            k: round(min(5.0, v * _ntrp_multiplier(opp_lvl, adj_factor_c)), 1)
                            if v is not None else None
                            for k, v in raw_scores.items()
                        }
                    else:
                        scores = raw_scores
                    overlays.append({"label": lbl, "scores": scores})

                _render_compare_radar(overlays)
