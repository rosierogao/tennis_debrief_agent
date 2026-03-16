"""Tests for mcp_memory_server/firestore.py (Firestore client mocked)."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


@pytest.fixture
def mock_fs_client():
    """Mock google.cloud.firestore.Client before FirestoreDB is instantiated."""
    mock_client = MagicMock()
    with patch("google.cloud.firestore.Client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def db(mock_fs_client):
    from mcp_memory_server.firestore import FirestoreDB
    return FirestoreDB()


class TestStoreMatch:
    def test_returns_document_id(self, db, mock_fs_client):
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "generated-id-123"
        mock_fs_client.collection.return_value.add.return_value = (None, mock_doc_ref)

        match_id = db.store_match(
            match_record={"date": "2024-11-10"},
            debrief_report={"summary": "test"},
            themes=["serve"],
            summary="lost",
        )
        assert match_id == "generated-id-123"

    def test_uses_provided_match_id(self, db, mock_fs_client):
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "custom-id"
        mock_fs_client.collection.return_value.document.return_value.set.return_value = None
        mock_fs_client.collection.return_value.document.return_value.id = "custom-id"

        match_id = db.store_match(
            match_record={}, debrief_report={}, themes=[], summary="", match_id="custom-id"
        )
        assert match_id == "custom-id"


class TestRetrieveRecentMatches:
    def test_returns_list(self, db, mock_fs_client):
        mock_doc = MagicMock()
        mock_doc.id = "doc1"
        mock_doc.to_dict.return_value = {
            "themes": ["double faults"],
            "summary": "lost",
            "created_at": datetime(2024, 11, 10, tzinfo=timezone.utc),
        }
        mock_fs_client.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [mock_doc]

        results = db.retrieve_recent_matches(limit=5)
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["match_id"] == "doc1"

    def test_empty_collection_returns_empty(self, db, mock_fs_client):
        mock_fs_client.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = []
        results = db.retrieve_recent_matches()
        assert results == []


class TestGetProfile:
    def test_returns_none_when_not_found(self, db, mock_fs_client):
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_fs_client.document.return_value.get.return_value = mock_doc

        result = db.get_profile()
        assert result is None

    def test_returns_profile_when_found(self, db, mock_fs_client):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"goal": "win regionals"}
        mock_fs_client.document.return_value.get.return_value = mock_doc

        result = db.get_profile()
        assert result == {"goal": "win regionals"}
