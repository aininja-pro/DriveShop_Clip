# src/config/env.py
import os
import sys
from typing import Optional, Iterable

def init_environment() -> None:
    """
    Initialize environment variables for the application.
    Loads .env file if it exists (dev), continues without it (production).
    Safe to call multiple times.
    """
    try:
        from dotenv import load_dotenv, find_dotenv
        
        # Find .env file in current directory or parent directories
        path = find_dotenv(usecwd=True)
        if path:
            load_dotenv(path, override=False)
            print(f"[startup] .env loaded from: {path}")
        else:
            print("[startup] No .env file found (expected in Render). Continuing with OS env.")
            
    except ImportError:
        # dotenv not installed - continue with OS environment variables
        print("[startup] python-dotenv not installed. Using OS environment variables only.")
    except Exception as e:
        print(f"[startup] Error loading .env file: {e}. Continuing with OS env.")
    
    # Log environment status for debugging
    apify_token_present = bool(apify_token())
    youtube_proxy_present = bool(youtube_proxy_url())
    print(f"[startup] Environment status: APIFY_TOKEN={'✅' if apify_token_present else '❌'}, YOUTUBE_PROXY={'✅' if youtube_proxy_present else '❌'}")

def getenv_any(keys: Iterable[str], default: Optional[str] = None) -> Optional[str]:
    """
    Get environment variable value from multiple possible key names.
    Returns the first non-empty value found, or default if none found.
    
    Args:
        keys: Iterable of environment variable names to check
        default: Default value if no keys are found
        
    Returns:
        First non-empty environment variable value or default
    """
    for k in keys:
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default

def apify_token() -> Optional[str]:
    """Get Apify API token from multiple possible environment variable names."""
    return getenv_any(["APIFY_TOKEN", "APIFY_API_TOKEN"])

def apify_actor_or_task() -> tuple[Optional[str], Optional[str]]:
    """
    Get Apify actor ID and task ID from environment variables.
    
    Returns:
        Tuple of (actor_id, task_id) - either can be None
    """
    actor = getenv_any(["APIFY_ACTOR_ID", "APIFY_ACTOR", "APIFY_YT_ACTOR"])
    task = getenv_any(["APIFY_TASK_ID"])
    return actor, task

def cookiefile_path() -> Optional[str]:
    """
    Get YouTube cookies file path if it exists.
    
    Returns:
        Path to cookies file if exists, None otherwise
    """
    p = getenv_any(["YTDLP_COOKIES", "YOUTUBE_COOKIES"])
    return p if p and os.path.exists(p) else None

def youtube_proxy_url() -> Optional[str]:
    """Get YouTube proxy URL from environment variables."""
    return getenv_any(["YOUTUBE_PROXY_URL", "YT_PROXY_URL"])

def apify_timeout() -> int:
    """Get Apify timeout in seconds, with sensible default."""
    timeout_str = getenv_any(["APIFY_YT_TIMEOUT_S", "APIFY_TIMEOUT"], "120")
    try:
        return int(timeout_str)
    except (ValueError, TypeError):
        return 120

def is_apify_enabled() -> bool:
    """Check if Apify is enabled for YouTube transcript extraction."""
    enabled = getenv_any(["YOUTUBE_APIFY_ENABLE", "APIFY_ENABLE"], "true")
    return enabled.lower() in {"1", "true", "yes", "on"}

def should_force_apify() -> bool:
    """Check if we should force Apify usage (skip yt-dlp entirely)."""
    force = getenv_any(["YOUTUBE_FORCE_APIFY", "FORCE_APIFY"], "false")
    return force.lower() in {"1", "true", "yes", "on"}

def validate_apify_config() -> tuple[bool, str]:
    """
    Validate Apify configuration at startup.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not is_apify_enabled():
        return True, "Apify disabled - no validation needed"
    
    token = apify_token()
    if not token:
        return False, "Apify enabled but no token found. Set APIFY_TOKEN or APIFY_API_TOKEN"
    
    actor, task = apify_actor_or_task()
    if not actor and not task:
        return False, "Apify enabled but no actor/task found. Set APIFY_ACTOR_ID or APIFY_TASK_ID"
    
    return True, f"Apify configured: token={token[:10]}..., actor={actor}, task={task}"