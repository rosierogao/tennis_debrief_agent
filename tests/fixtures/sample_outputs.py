"""Sample valid agent output payloads for tests."""
import json

INTAKE_OUTPUT = {
    "opponent_level": "advanced",
    "scoreline": "Lost 4-6, 3-6",
    "set_scores": [{"set": 1, "score": "4-6"}, {"set": 2, "score": "3-6"}],
    "what_went_well": ["first serve consistency"],
    "what_went_poorly": ["second serve", "backhand under pressure"],
    "feelings": "nervous in key moments",
    "opponent_characteristics": ["heavy topspin"],
    "pressure_moments": ["3-3 in first set"],
    "patterns_noticed": ["double faults on big points"],
    "confidence": 0.6,
}

TECHNICAL_OUTPUT = {
    "technical_hypotheses": [
        {"hypothesis": "Ball toss inconsistency causing double faults", "evidence": "3 double faults in second set", "confidence": 0.75},
        {"hypothesis": "Backhand slice breaking down under pace", "evidence": "errors on high balls to backhand", "confidence": 0.65},
    ],
    "confidence": 0.7,
}

TACTICAL_OUTPUT = {
    "tactical_observations": [
        {"observation": "Opponent exploited wide forehand on deuce side", "evidence": "lost 4 games from that pattern", "confidence": 0.8},
        {"observation": "Net approach success rate low on second serve", "evidence": "lost 3 of 4 approach points", "confidence": 0.6},
    ],
    "confidence": 0.7,
}

MENTAL_OUTPUT = {
    "mental_observations": [
        {"observation": "Tightened up on break points", "evidence": "3 double faults at break point", "confidence": 0.85},
        {"observation": "Recovered composure mid-second set", "evidence": "won 3 games in a row after falling behind", "confidence": 0.7},
    ],
    "confidence": 0.75,
}

PATTERNS_OUTPUT = {
    "patterns": [
        {"pattern": "Double faults cluster on high-pressure points", "evidence": "observed in this match and Oct 15 match", "confidence": 0.85},
        {"pattern": "Backhand errors increase against heavy topspin", "evidence": "consistent across recent matches", "confidence": 0.7},
    ],
    "confidence": 0.75,
}

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
}


def as_json(obj) -> str:
    return json.dumps(obj)
