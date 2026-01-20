"""
HTTP client for MCP memory server tools.
"""
from __future__ import annotations

import os
from typing import Any, Dict

import requests


class MCPClientError(RuntimeError):
    """Raised when MCP server returns an error or invalid response."""


def _base_url() -> str:
    return os.getenv("MCP_BASE_URL", "http://localhost:8080").rstrip("/")


def post_tool(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    POST JSON to an MCP tool endpoint and return JSON response.
    """
    url = f"{_base_url()}{path}"
    resp = requests.post(url, json=payload, timeout=20)
    try:
        data = resp.json()
    except Exception as exc:  # pragma: no cover
        raise MCPClientError(f"Non-JSON response from MCP: {resp.text}") from exc

    if isinstance(data, dict) and data.get("error"):
        raise MCPClientError(str(data["error"]))
    return data
