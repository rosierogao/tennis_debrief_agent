"""
Shared pytest configuration and fixtures.

Patches google.adk (so agent.agent defines all helpers) and
google.cloud.firestore (so mcp_memory_server.app can be imported without
real GCP credentials) before any test modules are collected.
"""
import sys
from unittest.mock import MagicMock

_ADK_MOCKS = [
    "google.adk",
    "google.adk.agents",
    "google.adk.agents.base_agent",
    "google.adk.agents.invocation_context",
    "google.adk.events",
    "google.adk.events.event",
    "google.genai",
    "google.genai.types",
]

_FIRESTORE_MOCKS = [
    "google.cloud",
    "google.cloud.firestore",
]


def pytest_configure(config):
    """Insert mock modules early before test collection starts."""
    if "google" not in sys.modules:
        sys.modules["google"] = MagicMock()

    # Mock ADK if not installed
    try:
        import google.adk  # noqa: F401
    except ImportError:
        for mod in _ADK_MOCKS:
            sys.modules.setdefault(mod, MagicMock())

    # Mock google.cloud.firestore so mcp_memory_server.app imports without GCP
    try:
        from google.cloud import firestore  # noqa: F401
    except ImportError:
        for mod in _FIRESTORE_MOCKS:
            sys.modules.setdefault(mod, MagicMock())
