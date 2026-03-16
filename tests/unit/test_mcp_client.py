"""Tests for agent/utils/mcp_client.py"""
import os
import pytest
from unittest.mock import patch, MagicMock
from agent.utils.mcp_client import post_tool, MCPClientError


def _mock_response(json_data=None, text="", raise_exc=None):
    resp = MagicMock()
    resp.text = text
    if raise_exc:
        resp.json.side_effect = raise_exc
    else:
        resp.json.return_value = json_data
    return resp


class TestPostTool:
    def test_successful_response(self):
        mock_resp = _mock_response(json_data={"ok": True})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = post_tool("/tools/profile.get", {})
        assert result == {"ok": True}
        mock_post.assert_called_once()

    def test_correct_url_built(self):
        mock_resp = _mock_response(json_data={})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            with patch.dict(os.environ, {"MCP_BASE_URL": "http://test-server:9000"}):
                post_tool("/tools/match.store", {"x": 1})
        call_url = mock_post.call_args[0][0]
        assert call_url == "http://test-server:9000/tools/match.store"

    def test_default_base_url(self):
        mock_resp = _mock_response(json_data={})
        with patch("requests.post", return_value=mock_resp) as mock_post:
            with patch.dict(os.environ, {}, clear=True):
                post_tool("/tools/health", {})
        call_url = mock_post.call_args[0][0]
        assert call_url.startswith("http://localhost:8080")

    def test_error_in_response_raises(self):
        mock_resp = _mock_response(json_data={"error": "not found"})
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MCPClientError):
                post_tool("/tools/something", {})

    def test_non_json_response_raises(self):
        mock_resp = _mock_response(text="<html>error</html>", raise_exc=ValueError("not json"))
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(MCPClientError, match="Non-JSON response"):
                post_tool("/tools/something", {})

    def test_payload_forwarded(self):
        mock_resp = _mock_response(json_data={"ok": True})
        payload = {"match_id": "abc", "limit": 5}
        with patch("requests.post", return_value=mock_resp) as mock_post:
            post_tool("/tools/match.retrieve_recent", payload)
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == payload
