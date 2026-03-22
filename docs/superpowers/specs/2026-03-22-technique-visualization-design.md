# Technique Visualization — Design Spec
**Date:** 2026-03-22
**Status:** Approved

---

## Overview

Add per-technique scoring and visualization to Court Debrief. After each match debrief, the head_coach agent infers a 1–5 score for up to 10 tennis techniques based on evidence in the match notes and analyses. Scores are visualized as a radar snapshot in the debrief output and as trend lines in a new Progress tab.

---

## Tracked Techniques

| Key | Label | Scoring direction |
|-----|-------|-------------------|
| `first_serve_pct` | First Serve % | Higher = better |
| `double_faults` | Double Faults | Inverted — 5 = none, 1 = many |
| `forehand` | Forehand | Higher = better |
| `backhand` | Backhand | Higher = better |
| `rally_depth` | Rally Depth | Higher = better |
| `unforced_errors` | Unforced Errors | Inverted — 5 = none, 1 = many |
| `return_of_serve` | Return of Serve | Higher = better |
| `footwork` | Footwork / Positioning | Higher = better |
| `pressure_performance` | Pressure Point Performance | Higher = better |
| `momentum` | Momentum Swings | Higher = better |

---

## Scoring Rules

- Scale: integer 1–5, or `null` if not mentioned
- `null` means the technique was not referenced in the match record or any upstream analysis — the agent must not guess
- For inverted metrics (`double_faults`, `unforced_errors`): 5 = excellent (few/none), 1 = poor (many) — so the radar always points "outward = good"
- Score definitions: 1 = very poor, 2 = poor, 3 = average, 4 = good, 5 = excellent

---

## Data Model

`technique_scores` is added as a new field to the head_coach JSON output:

```json
{
  "summary": "...",
  "focus_areas": [...],
  "levers": [...],
  "drills": [...],
  "history_comparison": {...},
  "confidence": 0.85,
  "technique_scores": {
    "first_serve_pct": 4,
    "double_faults": 3,
    "forehand": null,
    "backhand": 2,
    "rally_depth": null,
    "unforced_errors": 2,
    "return_of_serve": null,
    "footwork": null,
    "pressure_performance": 3,
    "momentum": 3
  }
}
```

Scores are stored as part of `debrief_report` in Firestore — no MCP or Firestore schema changes required.

---

## Changes Required

### 1. `agent/prompts/head_coach.md`

Add `technique_scores` to the output schema definition. Add a scoring rules block:

- Only score a technique if it appears in the player's notes or in the technical, tactical, or mental analyses
- Use `null` for unmentioned techniques — do not infer without evidence
- Score inverted metrics from the player's perspective (5 = good outcome)
- `validate_head_coach` tool call applies to the full output including `technique_scores`

### 2. `agent/agents/head_coach.py`

- Add `technique_scores` to `_default_output()` — all 10 keys present, all values `null`
- Note: `_validate_output()` in the class wrapper is not called by the live pipeline (the live agent is defined directly in `agent/agent.py` as an ADK `Agent`). This file only needs `_default_output()` updated for consistency; the runtime validation is in `json_guard.py`.

### 3. `agent/utils/json_guard.py` — `validate_head_coach`

This is the actual runtime validator (passed as a tool to the ADK agent in `agent/agent.py`). Update it to accept the new `technique_scores` field:

- `technique_scores` is optional (may be absent for backwards compatibility)
- If present, must be a dict with exactly the 10 technique keys
- Each value must be an integer 1–5 or `null`
- Return a validation error if any value is outside 1–5 (excluding null)

### 4. `streamlit_app.py` — Exclude `technique_scores` from "Additional Notes"

`_render_debrief()` has a catch-all `other_keys` block (around line 276) that renders unrecognised keys as raw JSON under "Additional Notes". Add `"technique_scores"` to the exclusion set in that block at the same time as adding the radar chart — otherwise `technique_scores` will appear as raw JSON immediately after deployment.

### 5. `streamlit_app.py` — Radar in debrief output

- After the existing text sections in `_render_debrief()`, render a radar chart using `plotly.graph_objects.Scatterpolar`
- Only plot techniques with non-null scores as filled polygon vertices
- Techniques with null scores show their axis line but contribute no polygon vertex — show them as dashed grey axes with a caption "grey axes = not mentioned this match"
- **All-null edge case:** if every technique score is null (terse match note), skip the radar entirely and show `st.caption("No technique data — mention specific techniques in your notes to see scoring.")` instead
- Range: 0–5 on all axes

### 6. `streamlit_app.py` — Progress tab

- Add a third tab: `tab_debrief, tab_history, tab_progress = st.tabs(["New Debrief", "Match History", "Progress"])`
- On load button click: fetch matches via `_mcp_post("/tools/match.retrieve_recent", {"limit": 20, "include_full": True})`
- **Empty history edge case:** if no matches are returned, show `st.info("No match history yet. Complete your first debrief to start tracking progress.")` — do not render charts
- For each of the 10 techniques, extract the time series: `[(match_date, score_or_null), ...]` sorted by date ascending
- Render 10 small Plotly line charts in a 2-column grid using `st.columns(2)` with `st.plotly_chart(..., use_container_width=True)`
- Each chart uses two traces:
  1. Solid line + filled circles — only non-null points (`connectgaps=False`)
  2. Dashed line — connects across nulls (`connectgaps=True`, no markers, low opacity 0.3)
- Null-position hollow circle marker on the dashed trace to signal missing data
- X-axis: match dates; Y-axis: fixed range 0–5
- Trend direction indicator (↑ improving / ↓ declining / → stable) based on slope of last 3 scored points

### 7. `agent/requirements.txt`

Add `plotly>=5.0` as a hard dependency. No graceful fallback — if plotly is missing the app will fail to start, which is the correct behaviour for a missing required dependency (same as all other imports in the file).

---

## Visualization Detail

### Radar chart
- Library: `plotly.graph_objects.Scatterpolar`
- Range: 0–5 on all axes
- Null techniques: axis rendered but no vertex — polygon only connects scored techniques
- Fill: semi-transparent blue fill inside polygon
- Shown below Summary in the debrief output right column

### Trend line charts
- Library: `plotly.graph_objects.Scatter`
- Two traces per chart:
  1. Solid line + filled circles — only non-null points (`connectgaps=False`)
  2. Dashed line — connects across nulls (`connectgaps=True`, no markers, low opacity)
- Null-position hollow circle marker on the dashed trace to signal missing data
- X-axis: match dates
- Y-axis: 1–5 fixed range
- Colour per technique (consistent palette across radar and trend)
- Trend direction indicator (↑ improving / ↓ declining / → stable) based on last 3 scored points

---

## Out of Scope

- Editing scores manually after the fact
- Comparing two matches side-by-side on the radar
- Exporting charts
- Per-technique drill recommendations driven by score thresholds
