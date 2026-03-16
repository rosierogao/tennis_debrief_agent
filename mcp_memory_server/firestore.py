"""
Firestore database layer for tennis match debrief storage and retrieval.
Uses Application Default Credentials (ADC) for authentication.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from google.cloud import firestore


class FirestoreDB:
    """Firestore database client for match debrief operations."""
    
    PROFILE_DOC_PATH = "profile/singleton"
    MATCHES_COLLECTION = "matches"
    
    def __init__(self):
        """Initialize Firestore client using Application Default Credentials."""
        self.client = firestore.Client()
        self.profile_ref = self.client.document(self.PROFILE_DOC_PATH)
        self.matches_ref = self.client.collection(self.MATCHES_COLLECTION)
    
    def store_match(
        self,
        match_record: Dict[str, Any],
        debrief_report: Dict[str, Any],
        themes: Dict[str, Any],
        summary: str,
        match_id: Optional[str] = None,
    ) -> str:
        """
        Store a match debrief in Firestore.
        
        Args:
            match_record: Raw match data (opponent, scoreline, etc.)
            debrief_report: Analysis report from agents
            themes: Extracted themes (technical, tactical, mental)
            summary: Text summary of the match
            
        Returns:
            Document ID of the created/updated match document
        """
        created_at = datetime.now(timezone.utc).isoformat()
        
        match_data = {
            "created_at": created_at,
            "match_record": match_record,
            "debrief_report": debrief_report,
            "themes": themes,
            "summary": summary,
        }
        
        # Add or update document in matches collection
        if match_id:
            doc_ref = self.matches_ref.document(match_id)
            doc_ref.set(match_data)
            return doc_ref.id

        doc_ref = self.matches_ref.add(match_data)[1]
        return doc_ref.id
    
    def retrieve_recent_matches(
        self,
        limit: int = 10,
        include_match_record: bool = False,
        include_debrief_report: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent matches ordered by created_at descending.
        
        Args:
            limit: Maximum number of matches to retrieve
            include_match_record: Whether to include match_record in response
            include_debrief_report: Whether to include debrief_report in response
            
        Returns:
            List of dictionaries containing match data with keys:
            - match_id: Document ID
            - created_at: ISO timestamp string
            - themes: Extracted themes
            - summary: Match summary
            - match_record: (optional) Raw match data
            - debrief_report: (optional) Analysis report
        """
        # Query matches ordered by created_at descending
        # Using string constant for direction (alternative: firestore.Query.DESCENDING)
        query = self.matches_ref.order_by("created_at", direction="DESCENDING").limit(limit)
        docs = query.stream()
        
        results = []
        for doc in docs:
            data = doc.to_dict()
            result: Dict[str, Any] = {
                "match_id": doc.id,
                "created_at": data.get("created_at", ""),
                "themes": data.get("themes", {}),
                "summary": data.get("summary", ""),
            }
            
            if include_match_record:
                result["match_record"] = data.get("match_record", {})
            
            if include_debrief_report:
                result["debrief_report"] = data.get("debrief_report", {})
            
            results.append(result)
        
        return results
    
    def get_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific match by ID.
        
        Args:
            match_id: Document ID of the match
            
        Returns:
            Dictionary containing all match data, or None if not found
        """
        doc_ref = self.matches_ref.document(match_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        data["match_id"] = doc.id
        return data
    
    def update_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        Update the profile singleton document.
        
        Args:
            profile_data: Dictionary of profile data to update
        """
        self.profile_ref.set(profile_data, merge=True)
    
    def get_profile(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve the profile singleton document.
        
        Returns:
            Dictionary containing profile data, or None if not found
        """
        doc = self.profile_ref.get()
        
        if not doc.exists:
            return None
        
        return doc.to_dict()
