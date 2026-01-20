"""
Pydantic models for MCP tool inputs and outputs.
Single-user assumption - no user_id required.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Profile Tools
# ============================================================================

class ProfileGetInput(BaseModel):
    """Input for profile.get tool."""
    pass


class ProfileGetOutput(BaseModel):
    """Output for profile.get tool."""
    profile: Dict[str, Any] = Field(..., description="Profile data dictionary")


class ProfileUpsertInput(BaseModel):
    """Input for profile.upsert tool."""
    patch: Dict[str, Any] = Field(..., description="Profile data to update/insert")


class ProfileUpsertOutput(BaseModel):
    """Output for profile.upsert tool."""
    ok: bool = Field(True, description="Operation success status")


# ============================================================================
# Match Tools
# ============================================================================

class MatchStoreInput(BaseModel):
    """Input for match.store tool."""
    match_id: Optional[str] = Field(None, description="Optional match ID (auto-generated if not provided)")
    match_record: Dict[str, Any] = Field(..., description="Raw match data (opponent, scoreline, etc.)")
    debrief_report: Dict[str, Any] = Field(..., description="Analysis report from agents")
    themes: List[str] = Field(..., description="List of extracted themes")
    summary: str = Field(..., description="Text summary of the match")


class MatchStoreOutput(BaseModel):
    """Output for match.store tool."""
    ok: bool = Field(True, description="Operation success status")
    match_id: str = Field(..., description="Match document ID")


class MatchRetrieveRecentInput(BaseModel):
    """Input for match.retrieve_recent tool."""
    limit: int = Field(..., ge=1, le=50, description="Number of matches to retrieve (1-50)")
    include_full: bool = Field(False, description="Whether to include full match_record and debrief_report")
    
    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Validate limit is within bounds."""
        if not 1 <= v <= 50:
            raise ValueError('limit must be between 1 and 50')
        return v


class MatchItem(BaseModel):
    """Individual match item in retrieve_recent output."""
    match_id: str = Field(..., description="Match document ID")
    created_at: str = Field(..., description="ISO timestamp string")
    themes: List[str] = Field(..., description="List of themes")
    summary: str = Field(..., description="Match summary")
    match_record: Optional[Dict[str, Any]] = Field(None, description="Full match record (included when include_full=True)")
    debrief_report: Optional[Dict[str, Any]] = Field(None, description="Full debrief report (included when include_full=True)")


class MatchRetrieveRecentOutput(BaseModel):
    """Output for match.retrieve_recent tool."""
    matches: List[MatchItem] = Field(..., description="List of recent matches")
