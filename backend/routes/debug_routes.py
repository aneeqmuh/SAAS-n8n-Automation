# Create this file: app/routes/debug_routes.py

import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from database.db import sb
from database.sb_utils import get_data, get_error
from thirdPartyIntegrations.google_oauth import is_token_expired

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/debug/tokens")
def debug_all_tokens():
    """Debug endpoint to check all user tokens status."""
    try:
        # Get all Google integrations
        res = sb.table("user_integrations").select("*").eq("provider", "google").execute()
        integrations = get_data(res) or []
        
        results = []
        for integ in integrations:
            token_status = {
                "user_id": integ["user_id"],
                "integration_id": integ["id"],
                "has_access_token": bool(integ.get("access_token")),
                "has_refresh_token": bool(integ.get("refresh_token")),
                "expiry": integ.get("expiry"),
                "is_expired": is_token_expired(integ.get("expiry")) if integ.get("expiry") else True,
                "created_at": integ.get("created_at"),
                "updated_at": integ.get("updated_at")
            }
            
            # Check how many days since last update
            if integ.get("updated_at"):
                try:
                    updated = datetime.fromisoformat(integ["updated_at"].replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    days_old = (now - updated).days
                    token_status["days_since_update"] = days_old
                    token_status["likely_7_day_expired"] = days_old > 7
                except:
                    pass
            
            results.append(token_status)
        
        return {
            "total_integrations": len(results),
            "integrations": results,
            "action_needed": "If likely_7_day_expired is true, users need to re-authenticate",
            "solution": "1. OAuth app should now be published, 2. Clear expired tokens, 3. Have users re-authenticate"
        }
        
    except Exception as e:
        return {"error": str(e)}

@router.post("/debug/clear-expired-tokens")
def clear_expired_tokens():
    """Clear all expired tokens to force re-authentication."""
    try:
        logger.info("Clearing all expired Google tokens...")
        
        # Update all Google integrations to clear expired tokens
        update_res = (
            sb.table("user_integrations")
            .update({
                "access_token": None,
                "refresh_token": None,
                "expiry": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("provider", "google")
            .execute()
        )
        
        if get_error(update_res):
            raise Exception(f"Database error: {get_error(update_res)}")
        
        logger.info("Successfully cleared all Google tokens")
        
        return {
            "success": True,
            "message": "Cleared all Google tokens. Users will need to re-authenticate.",
            "next_steps": [
                "1. OAuth app is now published (no more 7-day expiry)",
                "2. Users should try to install/use workflows again",
                "3. They'll be prompted to re-authenticate",
                "4. New tokens won't expire after 7 days"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to clear tokens: {e}")
        return {"error": str(e)}

@router.get("/debug/oauth-status")
def check_oauth_status():
    """Show current OAuth configuration status."""
    return {
        "oauth_app_status": "Should now be 'In production' (you just published it)",
        "token_expiry": "New tokens won't expire after 7 days",
        "required_actions": [
            "✅ OAuth app published to production",
            "🔄 Clear expired tokens (use /debug/clear-expired-tokens)",
            "🔄 Users need to re-authenticate",
            "✅ Future tokens will be long-lived"
        ],
        "test_workflow": "Try installing a Gmail workflow - should prompt for re-auth"
    }