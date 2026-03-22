# Technique Visualization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-inferred 1–5 technique scores to head_coach output, display a radar snapshot in the debrief output, and show 10 trend line charts in a new Progress tab.

**Architecture:** head_coach.md prompt and json_guard validator are extended to include `technique_scores` (10 keys, int 1–5 or null). Scores are stored in Firestore as part of `debrief_report` (no schema change). Streamlit renders a Plotly radar in the debrief output and 10 Plotly trend charts in a new Progress tab.

**Tech Stack:** Python 3.11, Google ADK, Streamlit, Plotly 5+, Firestore via MCP REST API

---

## Chunk 1: Data layer — scoring schema, prompt, validator, fixtures, tests

### Task 1: Add `technique_scores` to `HEAD_COACH_OUTPUT` fixture and update `_default_output`

**Files:**
- Modify: `tests/fixtures/sample_outputs.py`
- Modify: `agent/agents/head_coach.py`

- [ ] **Step 1: Update `HEAD_COACH_OUTPUT` in `tests/fixtures/sample_outputs.py`**

Add `technique_scores` to the existing dict (after `"confidence": 0.75`):

```python
HEAD_COACH_OUTPUT = {
    "summary": "Serve reliability and mental game under pressure are the primary blockers to winning tight matches.",
    "focus_areas": ["second serve reliability", "mental reset between points", "backhand vs topspin"],
    "levers": [
        {"lever": "Add kick serve to backhand corner", "why": "reduces double fault risk and creates weak return", "confidence": 0.8},
        {"lever": "Shorten backswing on backhand against topspin", "why": "reduces timing errors on high balls", "confidence": 0.7},
    ],
    "drills": [
        {"drill": "Pressure serve drill: 10 serves at 4-4 in set scenario", "why": "simulate match stress on serve", "confidence": 0.8},
        {"drill": "High ball backhand block drill", "why": "build consistency against topspin", "confidence": 0.65},
    ],
    "history_comparison": {
        "summary": "Double faults under pressure appear in both recent matches, indicating a recurring pattern.",
        "patterns": ["double faults on break points recur across matches", "backhand errors increase in final sets"],
    },
    "confidence": 0.75,
    "technique_scores": {
        "first_serve_pct": None,
        "double_faults": 2,
        "forehand": None,
        "backhand": 2,
        "rally_depth": None,
        "unforced_errors": 2,
        "return_of_serve": None,
        "footwork": None,
        "pressure_performance": 2,
        "momentum": None,
    },
}
```

- [ ] **Step 2: Update `_default_output` in `agent/agents/head_coach.py`**

Replace the existing `_default_output` method:

```python
def _default_output(self) -> Dict[str, Any]:
    return {
        "summary": "",
        "focus_areas": [],
        "levers": [],
        "drills": [],
        "history_comparison": {"summary": "", "patterns": []},
        "confidence": 0.4,
        "technique_scores": {
            "first_serve_pct": None,
            "double_faults": None,
            "forehand": None,
            "backhand": None,
            "rally_depth": None,
            "unforced_errors": None,
            "return_of_serve": None,
            "footwork": None,
            "pressure_performance": None,
            "momentum": None,
        },
    }
```

- [ ] **Step 3: Run existing head_coach tests to confirm no regressions**

```bash
cd /Users/ruoqigao/Documents/tennis_debrief_agent
python -m pytest tests/unit/agents/test_head_coach_agent.py -v
```

Expected: all tests pass (the new field is additive).

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/sample_outputs.py agent/agents/head_coach.py
git commit -m "feat: add technique_scores to head_coach default output and fixture"
```

---

### Task 2: Update `validate_head_coach` in `json_guard.py`

**Files:**
- Modify: `agent/utils/json_guard.py`
- Modify: `tests/unit/test_json_guard.py`

- [ ] **Step 1: Write failing tests for `validate_head_coach` with `technique_scores`**

Add to `tests/unit/test_json_guard.py` inside `class TestValidateHeadCoach` (or append a new class after existing ones):

```python
class TestValidateHeadCoachTechniqueScores:
    """Tests for technique_scores field in validate_head_coach."""

    def _base(self):
        """Return a valid HEAD_COACH_OUTPUT with technique_scores."""
        from tests.fixtures.sample_outputs import HEAD_COACH_OUTPUT
        import copy
        return copy.deepcopy(HEAD_COACH_OUTPUT)

    def test_valid_with_technique_scores(self):
        result = validate_head_coach(self._base())
        assert result == {"ok": True}

    def test_valid_without_technique_scores(self):
        """technique_scores is optional for backwards compatibility."""
        payload = self._base()
        del payload["technique_scores"]
        assert validate_head_coach(payload) == {"ok": True}

    def test_all_null_technique_scores_is_valid(self):
        payload = self._base()
        payload["technique_scores"] = {k: None for k in payload["technique_scores"]}
        assert validate_head_coach(payload) == {"ok": True}

    def test_score_out_of_range_returns_error(self):
        payload = self._base()
        payload["technique_scores"]["forehand"] = 6
        result = validate_head_coach(payload)
        assert "error" in result

    def test_score_zero_returns_error(self):
        payload = self._base()
        payload["technique_scores"]["backhand"] = 0
        result = validate_head_coach(payload)
        assert "error" in result

    def test_score_float_returns_error(self):
        payload = self._base()
        payload["technique_scores"]["forehand"] = 3.5
        result = validate_head_coach(payload)
        assert "error" in result

    def test_score_string_returns_error(self):
        """LLM may produce "3" instead of 3 — must be rejected."""
        payload = self._base()
        payload["technique_scores"]["forehand"] = "3"
        result = validate_head_coach(payload)
        assert "error" in result

    def test_unknown_key_in_technique_scores_is_ignored(self):
        """Extra keys are tolerated."""
        payload = self._base()
        payload["technique_scores"]["mystery_shot"] = 3
        assert validate_head_coach(payload) == {"ok": True}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/unit/test_json_guard.py::TestValidateHeadCoachTechniqueScores -v
```

Expected: FAIL — `validate_head_coach` does not yet validate `technique_scores`.

- [ ] **Step 3: Update `validate_head_coach` in `agent/utils/json_guard.py`**

Add a module-level constant and replace the existing `validate_head_coach` function. Place `_TECHNIQUE_KEYS` immediately above `validate_head_coach` in the file:

```python
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
                if not isinstance(val, int) or val < 1 or val > 5:
                    raise ValueError(
                        f"technique_scores.{key} must be an integer 1-5 or null, got {val!r}"
                    )

        return _ok()
    except Exception as exc:
        return _err(str(exc))
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/unit/test_json_guard.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/utils/json_guard.py tests/unit/test_json_guard.py
git commit -m "feat: validate technique_scores in validate_head_coach"
```

---

### Task 3: Update `head_coach.md` prompt

**Files:**
- Modify: `agent/prompts/head_coach.md`

- [ ] **Step 1: Read `agent/prompts/head_coach.md` to verify current content, then replace with the updated file below**

```bash
cat agent/prompts/head_coach.md
```

Confirm the file matches the known content before overwriting. Then write the full updated file:

```markdown
You are the Head Coach agent. Synthesize all analyses into a concrete, actionable debrief report.

Output must be valid JSON only. DO NOT output markdown. DO NOT include explanations.

Return JSON with this schema:
{
  "summary": "string",
  "focus_areas": ["string"],
  "levers": [
    {"lever": "string", "why": "string", "confidence": 0.0}
  ],
  "drills": [
    {"drill": "string", "why": "string", "confidence": 0.0}
  ],
  "history_comparison": {
    "summary": "string",
    "patterns": ["string"]
  },
  "confidence": 0.0,
  "technique_scores": {
    "first_serve_pct": null,
    "double_faults": null,
    "forehand": null,
    "backhand": null,
    "rally_depth": null,
    "unforced_errors": null,
    "return_of_serve": null,
    "footwork": null,
    "pressure_performance": null,
    "momentum": null
  }
}

Constraints:
- focus_areas: max 4 items
- levers: max 3 items (hard limit)
- drills: max 3 items (hard limit)
- history_comparison.patterns: max 4 items
- confidence fields are numbers in [0, 1]

Quality rules for "levers":
- A lever is a specific tactical or technical adjustment the player can make IN A MATCH — something they can decide and execute during play
- Must be concrete and matchplay-focused (e.g. "Attack opponent's second serve with aggressive crosscourt forehand return" not "be more aggressive")
- Must reference the specific evidence from technical, tactical, or mental analyses that justifies it
- Rank by expected impact: highest-confidence, highest-impact lever first
- Do NOT include generic advice like "stay focused" or "play more consistently"

Quality rules for "drills":
- Each drill must directly address one of the levers or a recurring weakness identified in the analyses
- Must include: (1) what to do, (2) how many reps or how long, (3) the specific success condition
- Example of good drill: "Serve wide to deuce then recover to T — 20 reps, success = 15/20 land in box and recover in time"
- Example of bad drill: "Practice serves" or "work on footwork"
- The "why" field must name the specific weakness or lever it addresses

Quality rules for "summary":
- 2-3 sentences maximum
- Lead with the match outcome and the single most important takeaway
- Ground everything in what the player actually described — do not invent facts

Quality rules for "technique_scores":
- Score each technique only if it is explicitly mentioned in the player's match_record OR in the technical, tactical, or mental analyses
- Set null for any technique with no supporting evidence — do NOT guess or infer from context
- Scale: 1 = very poor, 2 = poor, 3 = average, 4 = good, 5 = excellent
- Inverted metrics — score from the player's perspective (higher = better outcome):
  - double_faults: 5 = no double faults, 1 = many double faults
  - unforced_errors: 5 = very few errors, 1 = many errors
- Values must be integers 1–5 or null (not floats, not 0)

Tool usage:
1) Call match.store with the current match_record + debrief_report payload.
2) If recent_matches is not provided in INPUT, call match.retrieve_recent with limit=8, include_full=false.
Use the retrieved history only to refine the summary, focus_areas, and history_comparison.
When comparing to history, only consider matches that occurred before the current match_date.

After you produce the JSON, call the tool `validate_head_coach` with the JSON.
If the tool returns an error, fix the JSON and call `validate_head_coach` again.
```

- [ ] **Step 2: Verify the file was written correctly**

```bash
grep -c "technique_scores" agent/prompts/head_coach.md
```

Expected: output is `2` or more (appears in schema and in quality rules section).

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
python -m pytest -v
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add agent/prompts/head_coach.md
git commit -m "feat: add technique_scores scoring rules to head_coach prompt"
```

---

### Task 4: Add `plotly` dependency

**Files:**
- Modify: `agent/requirements.txt`

- [ ] **Step 1: Add plotly to requirements**

Append to `agent/requirements.txt`:

```
plotly>=5.0
```

- [ ] **Step 2: Install locally inside the project virtual environment**

```bash
python -m pip install "plotly>=5.0"
```

Expected: installs without error.

- [ ] **Step 3: Verify import works**

```bash
python -c "import plotly; print(plotly.__version__)"
```

Expected: prints a version >= 5.0.

- [ ] **Step 4: Commit**

```bash
git add agent/requirements.txt
git commit -m "feat: add plotly dependency for technique visualization"
```

---

## Chunk 2: Streamlit — radar in debrief output + Progress tab

### Task 5: Add radar chart to debrief output

**Files:**
- Modify: `streamlit_app.py`

- [ ] **Step 1: Add plotly import at the top of `streamlit_app.py`**

Add `import plotly.graph_objects as go` to the stdlib/third-party import block at the top of the file, after `import re` and before `from typing import ...`:

```python
import plotly.graph_objects as go
```

- [ ] **Step 2: Add `_TECHNIQUE_LABELS` and `_TECHNIQUE_COLORS` constants**

After the `_BULLET_FIELDS` constant (which ends at line 31), add:

```python
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
```

- [ ] **Step 3: Add `_render_radar` helper function**

Add after the `_mcp_post` function.

The radar uses three Plotly traces:
1. A ghost ring at r=0 — establishes all 10 axis labels (invisible, zero-width)
2. A null-techniques trace at r=5, grey, dashed, low opacity — visually marks "grey axes = not mentioned this match"
3. A scored polygon (only non-null techniques, solid blue fill)

Note: Plotly Scatterpolar does not support per-axis line styling. The null-axes trace draws a dashed grey polygon connecting all null-technique axes at max radius, approximating "grey axes" from the spec. This is the closest achievable in Plotly without a custom SVG overlay.

```python
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
```

- [ ] **Step 4: Exclude `technique_scores` from "Additional Notes" and call `_render_radar`**

In `_render_debrief`, find the `other_keys` exclusion set (around line 275) and add `"technique_scores"`:

```python
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
            "technique_scores",   # ← add this
        }
    }
```

Also add the radar call immediately after the Summary section (after `st.write(summary or "No summary provided.")`), not at the bottom of the function:

```python
    st.markdown("#### Summary")
    st.write(summary or "No summary provided.")

    technique_scores = report.get("technique_scores")
    if technique_scores:
        st.markdown("#### Technique Snapshot")
        _render_radar(technique_scores)
```

- [ ] **Step 5: Smoke-test the radar manually**

Start MCP server and Streamlit, run a debrief, confirm:
- Radar appears immediately below the Summary section in the debrief output
- Grey dashed polygon appears for null-scored techniques, solid blue polygon for scored ones
- Caption "Grey dashed axes = not mentioned this match" appears when any techniques are null
- "Additional Notes" does NOT appear for `technique_scores`
- If all scores are null, a caption appears instead of an empty chart

```bash
bash scripts/run_local_mcp.sh   # Terminal 1
export $(grep -v '^#' .env | xargs) && streamlit run streamlit_app.py   # Terminal 2
```

- [ ] **Step 6: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add technique radar snapshot to debrief output"
```

---

### Task 6: Add Progress tab with trend line charts

**Files:**
- Modify: `streamlit_app.py`

- [ ] **Step 1: Add `_render_trend_charts` helper function**

Add after `_render_radar`:

```python
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
```

- [ ] **Step 2: Add the Progress tab to the tab declaration**

Find the tab declaration (around line 311):

```python
tab_debrief, tab_history = st.tabs(["New Debrief", "Match History"])
```

Replace with:

```python
tab_debrief, tab_history, tab_progress = st.tabs(["New Debrief", "Match History", "Progress"])
```

- [ ] **Step 3: Add the Progress tab body at the bottom of `streamlit_app.py`**

After the `with tab_history:` block, add:

```python
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
```

- [ ] **Step 4: Smoke-test the Progress tab**

With MCP server running and at least 2 debriefs stored, open the Progress tab, click "Load progress", and verify:
- 10 charts render in 2-column grid
- Charts with no data show "No data yet" caption
- Dashed connector appears between non-adjacent scored points
- Trend indicator (↑ ↓ →) appears below each chart

- [ ] **Step 5: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add Progress tab with technique trend line charts"
```

---

### Task 7: Final integration check and push

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify `technique_scores` round-trip in a live debrief**

Run a full debrief with match notes that mention at least 3 techniques. Confirm:
- Radar appears in debrief output with scored techniques filled, unmentioned ones not plotted
- Match is saved to Firestore (check via "Load history" in Match History tab)
- Progress tab shows the new match's scores on the trend lines

- [ ] **Step 3: Push**

```bash
git push origin main
```
