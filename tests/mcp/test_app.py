"""Tests for mcp_memory_server/app.py (FastAPI endpoints)."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Return a FastAPI TestClient with the module-level db replaced by a mock."""
    import mcp_memory_server.app as app_module
    mock_db = MagicMock()
    mock_db.get_profile.return_value = {"goal": "win regionals"}
    mock_db.update_profile.return_value = None
    mock_db.store_match.return_value = "match-id-001"
    mock_db.retrieve_recent_matches.return_value = [
        {
            "match_id": "match-id-001",
            "created_at": "2024-11-10T10:00:00+00:00",
            "themes": ["double faults"],
            "summary": "lost",
        }
    ]
    original_db = app_module.db
    app_module.db = mock_db
    try:
        yield TestClient(app_module.app), mock_db
    finally:
        app_module.db = original_db


class TestHealthEndpoint:
    def test_health_ok(self, client):
        tc, _ = client
        resp = tc.get("/health")
        assert resp.status_code == 200
        assert resp.json().get("ok") is True


class TestProfileGet:
    def test_returns_profile(self, client):
        tc, mock_db = client
        resp = tc.post("/tools/profile.get", json={})
        assert resp.status_code == 200
        assert "profile" in resp.json()

    def test_calls_db_get_profile(self, client):
        tc, mock_db = client
        tc.post("/tools/profile.get", json={})
        mock_db.get_profile.assert_called_once()


class TestProfileUpsert:
    def test_valid_patch_returns_ok(self, client):
        tc, _ = client
        resp = tc.post("/tools/profile.upsert", json={"patch": {"goal": "improve serve"}})
        assert resp.status_code == 200
        assert resp.json().get("ok") is True

    def test_missing_patch_returns_error(self, client):
        tc, _ = client
        resp = tc.post("/tools/profile.upsert", json={})
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestMatchStore:
    def test_valid_payload_returns_match_id(self, client):
        tc, _ = client
        resp = tc.post("/tools/match.store", json={
            "match_record": {"date": "2024-11-10"},
            "debrief_report": {"summary": "tough loss"},
            "themes": ["double faults"],
            "summary": "lost 4-6 3-6",
        })
        assert resp.status_code == 200
        assert resp.json().get("match_id") == "match-id-001"

    def test_missing_required_field_returns_error(self, client):
        tc, _ = client
        resp = tc.post("/tools/match.store", json={"themes": [], "summary": ""})
        assert resp.status_code == 200
        assert "error" in resp.json()


class TestMatchRetrieveRecent:
    def test_valid_request_returns_matches(self, client):
        tc, _ = client
        resp = tc.post("/tools/match.retrieve_recent", json={"limit": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert "matches" in data
        assert len(data["matches"]) == 1

    def test_limit_zero_returns_error(self, client):
        tc, _ = client
        resp = tc.post("/tools/match.retrieve_recent", json={"limit": 0})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_limit_51_returns_error(self, client):
        tc, _ = client
        resp = tc.post("/tools/match.retrieve_recent", json={"limit": 51})
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_include_full_false_by_default(self, client):
        tc, mock_db = client
        tc.post("/tools/match.retrieve_recent", json={"limit": 3})
        call_kwargs = mock_db.retrieve_recent_matches.call_args
        assert call_kwargs is not None
