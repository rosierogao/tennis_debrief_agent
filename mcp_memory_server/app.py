"""
MCP Memory Server - FastAPI HTTP server for Cloud Run.
"""
from typing import Dict, Any
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from mcp_memory_server.firestore import FirestoreDB
from mcp_memory_server import models


app = FastAPI(title="tennis-debrief-mcp")
db = FirestoreDB()

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:3000", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validation_error(message: str) -> Dict[str, Any]:
    return {"error": {"code": "VALIDATION_ERROR", "message": message}}


def _not_found(message: str) -> Dict[str, Any]:
    return {"error": {"code": "NOT_FOUND", "message": message}}


def _internal_error(message: str) -> Dict[str, Any]:
    return {"error": {"code": "INTERNAL", "message": message}}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}


@app.post("/tools/profile.get")
def profile_get(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        models.ProfileGetInput.model_validate(payload)
        profile = db.get_profile()
        if profile is None:
            return _not_found("Profile not found")
        return models.ProfileGetOutput(profile=profile).model_dump()
    except ValidationError as exc:
        return _validation_error(str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _internal_error(str(exc))


@app.post("/tools/profile.upsert")
def profile_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = models.ProfileUpsertInput.model_validate(payload)
        db.update_profile(parsed.patch)
        return models.ProfileUpsertOutput().model_dump()
    except ValidationError as exc:
        return _validation_error(str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _internal_error(str(exc))


@app.post("/tools/match.store")
def match_store(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = models.MatchStoreInput.model_validate(payload)
        match_id = db.store_match(
            match_record=parsed.match_record,
            debrief_report=parsed.debrief_report,
            themes=parsed.themes,
            summary=parsed.summary,
            match_id=parsed.match_id,
        )
        return models.MatchStoreOutput(match_id=match_id).model_dump()
    except ValidationError as exc:
        return _validation_error(str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _internal_error(str(exc))


@app.post("/tools/match.retrieve_recent")
def match_retrieve_recent(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = models.MatchRetrieveRecentInput.model_validate(payload)
        matches = db.retrieve_recent_matches(
            limit=parsed.limit,
            include_match_record=parsed.include_full,
            include_debrief_report=parsed.include_full,
        )
        return models.MatchRetrieveRecentOutput(matches=matches).model_dump()
    except ValidationError as exc:
        return _validation_error(str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _internal_error(str(exc))


@app.post("/tools/match.delete")
def match_delete(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = models.MatchDeleteInput.model_validate(payload)
        deleted = db.delete_match(parsed.match_id)
        if not deleted:
            return _not_found(f"Match {parsed.match_id} not found")
        return models.MatchDeleteOutput(ok=True).model_dump()
    except ValidationError as exc:
        return _validation_error(str(exc))
    except Exception as exc:  # pragma: no cover - safety net
        return _internal_error(str(exc))


def main() -> None:
    """Run the FastAPI server locally."""
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
