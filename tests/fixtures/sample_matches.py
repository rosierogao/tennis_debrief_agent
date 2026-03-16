"""Reusable sample data for tests."""

SAMPLE_MATCH_RECORD = {
    "match_date": "2024-11-10",
    "opponent_level": "advanced",
    "scoreline": "Lost 4-6, 3-6",
    "set_scores": [{"set": 1, "score": "4-6"}, {"set": 2, "score": "3-6"}],
    "what_went_well": ["first serve consistency", "net approaches"],
    "what_went_poorly": ["second serve", "backhand under pressure"],
    "feelings": "nervous in key moments, recovered somewhat in second set",
    "opponent_characteristics": ["heavy topspin", "strong baseline"],
    "pressure_moments": ["3-3 in first set", "0-40 games"],
    "patterns_noticed": ["double faults on big points"],
    "confidence": 0.6,
}

SAMPLE_RECENT_MATCH = {
    "match_id": "abc123",
    "created_at": "2024-10-15T10:00:00",
    "themes": ["double faults", "backhand errors"],
    "summary": "Lost due to second serve struggles and tight play on break points.",
    "match_record": {
        "match_date": "2024-10-15",
        "opponent_level": "competitive",
        "scoreline": "Lost 5-7, 6-4, 3-6",
        "set_scores": [{"set": 1, "score": "5-7"}, {"set": 2, "score": "6-4"}, {"set": 3, "score": "3-6"}],
        "what_went_well": ["forehand aggression"],
        "what_went_poorly": ["second serve", "mental toughness in third set"],
        "feelings": "started well but faded late",
        "opponent_characteristics": ["consistent", "good movement"],
        "pressure_moments": ["serving for first set at 5-6"],
        "patterns_noticed": ["double faults under pressure"],
        "confidence": 0.5,
    },
    "debrief_report": {
        "summary": "Struggled with second serve and mental game in tight moments.",
        "focus_areas": ["second serve reliability", "mental reset routines"],
        "levers": [{"lever": "kick serve to backhand", "why": "reduces double fault risk", "confidence": 0.7}],
        "drills": [{"drill": "pressure serve practice", "why": "simulate match stress", "confidence": 0.7}],
        "history_comparison": {"summary": "N/A", "patterns": []},
        "confidence": 0.65,
    },
}

SAMPLE_RECENT_MATCHES = [SAMPLE_RECENT_MATCH]
