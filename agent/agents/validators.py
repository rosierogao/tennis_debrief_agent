"""
Lightweight validation helpers for agent JSON outputs.
"""
from typing import Any, Dict, List


def require_keys(obj: Dict[str, Any], keys: List[str]) -> None:
    for key in keys:
        if key not in obj:
            raise ValueError(f"Missing required field: {key}")


def require_list_of_str(value: Any, field: str, max_items: int | None = None) -> None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"{field} must be a list of strings")
    if max_items is not None and len(value) > max_items:
        raise ValueError(f"{field} must have at most {max_items} items")


def require_list_of_dict(value: Any, field: str, max_items: int | None = None) -> List[Dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise ValueError(f"{field} must be a list of objects")
    if max_items is not None and len(value) > max_items:
        raise ValueError(f"{field} must have at most {max_items} items")
    return value


def require_float_0_1(value: Any, field: str) -> None:
    if not isinstance(value, (int, float)) or not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{field} must be a number between 0 and 1")
