"""
Shared constants and vocabulary for tennis debrief system.
"""

# ---------------------------------------------------------------------------
# Opponent levels
# Used by: intake agent (opponent_level field), validators
# ---------------------------------------------------------------------------
OPPONENT_LEVELS = (
    "beginner",
    "intermediate",
    "advanced",
    "competitive",
    "tournament",
    "professional",
)

# ---------------------------------------------------------------------------
# Technical keywords
# Used by: technical agent hypotheses, head coach levers/drills
# ---------------------------------------------------------------------------
TECHNICAL_KEYWORDS = (
    # Serve
    "first serve",
    "second serve",
    "double fault",
    "serve percentage",
    "ball toss",
    "serve motion",
    "kick serve",
    "flat serve",
    "slice serve",
    # Groundstrokes
    "forehand",
    "backhand",
    "topspin",
    "slice",
    "inside-out",
    "inside-in",
    "crosscourt",
    "down the line",
    "contact point",
    "swing path",
    "follow-through",
    "footwork",
    "split step",
    # Net game
    "volley",
    "overhead",
    "approach shot",
    "half volley",
    "drop shot",
    # Return
    "return of serve",
    "chip return",
    "drive return",
    # General mechanics
    "racket head speed",
    "grip",
    "wrist",
    "elbow",
    "shoulder rotation",
    "hip rotation",
    "weight transfer",
    "balance",
    "recovery",
)

# ---------------------------------------------------------------------------
# Tactical keywords
# Used by: tactical agent observations, head coach levers
# ---------------------------------------------------------------------------
TACTICAL_KEYWORDS = (
    # Court positioning
    "baseline",
    "net",
    "mid-court",
    "behind the baseline",
    "inside the baseline",
    "net approach",
    "serve and volley",
    # Rally patterns
    "rally",
    "short ball",
    "high ball",
    "angle",
    "wide",
    "body serve",
    "T serve",
    "net cord",
    # Strategic patterns
    "opening the court",
    "moving opponent",
    "dictating play",
    "defending",
    "counterpunching",
    "high-percentage",
    "aggressive",
    "consistency",
    "depth",
    "spin variation",
    "pace variation",
    # Score/game situations
    "break point",
    "break",
    "hold",
    "deuce",
    "ad point",
    "tie-break",
    "big points",
    "clutch",
)

# ---------------------------------------------------------------------------
# Mental keywords
# Used by: mental agent observations, head coach focus areas
# ---------------------------------------------------------------------------
MENTAL_KEYWORDS = (
    # Emotional states
    "nervous",
    "anxious",
    "confident",
    "frustrated",
    "focused",
    "distracted",
    "relaxed",
    "tight",
    "overwhelmed",
    "composed",
    "angry",
    "flat",
    "energized",
    # Behavioral patterns
    "rushed",
    "passive",
    "tentative",
    "overaggressive",
    "overthinking",
    "on autopilot",
    # Match situations
    "pressure",
    "momentum",
    "losing streak",
    "comeback",
    "tight set",
    "bagel",
    "serving for the set",
    "match point",
    "choking",
    "clutch play",
    # Mental skills
    "reset",
    "routine",
    "breathing",
    "positive self-talk",
    "body language",
    "between-point ritual",
)

# ---------------------------------------------------------------------------
# Priority levels
# Maps to confidence score thresholds for surfacing findings
# ---------------------------------------------------------------------------
class Priority:
    HIGH = "high"       # confidence >= 0.75
    MEDIUM = "medium"   # confidence >= 0.50
    LOW = "low"         # confidence < 0.50

CONFIDENCE_THRESHOLDS = {
    Priority.HIGH: 0.75,
    Priority.MEDIUM: 0.50,
    Priority.LOW: 0.0,
}

def confidence_to_priority(confidence: float) -> str:
    """Map a confidence float [0, 1] to a Priority level string."""
    if confidence >= CONFIDENCE_THRESHOLDS[Priority.HIGH]:
        return Priority.HIGH
    if confidence >= CONFIDENCE_THRESHOLDS[Priority.MEDIUM]:
        return Priority.MEDIUM
    return Priority.LOW


# ---------------------------------------------------------------------------
# Categories
# Used by: head coach to classify levers, drills, focus areas
# ---------------------------------------------------------------------------
class Category:
    TECHNICAL = "technical"
    TACTICAL = "tactical"
    MENTAL = "mental"
    PHYSICAL = "physical"

ALL_CATEGORIES = (
    Category.TECHNICAL,
    Category.TACTICAL,
    Category.MENTAL,
    Category.PHYSICAL,
)
