# src/utils/cooldown.py
import os
import time

# Global cooldown configuration
_COOL = int(os.getenv("YT_429_COOLDOWN_SEC", "900"))  # Default 15 minutes
_COOLS = {}  # key -> unblock_epoch

def should_wait(key: str) -> float:
    """
    Check if a session/proxy should wait due to 429 cooldown.
    
    Args:
        key: Session identifier (e.g., proxy session ID)
        
    Returns:
        Seconds to wait (0 if no cooldown active)
    """
    return max(0, _COOLS.get(key, 0) - time.monotonic())

def backoff(key: str, retry_after: float = None) -> None:
    """
    Put a session/proxy into cooldown quarantine after 429.
    
    Args:
        key: Session identifier to quarantine
        retry_after: YouTube's Retry-After header value (optional)
    """
    dur = retry_after if (retry_after and retry_after > 0) else _COOL
    _COOLS[key] = time.monotonic() + dur
    
    # Clean up old entries to prevent memory leak
    now = time.monotonic()
    expired_keys = [k for k, expires_at in _COOLS.items() if expires_at < now]
    for k in expired_keys:
        del _COOLS[k]

def clear_backoff(key: str) -> None:
    """Clear cooldown for successful requests"""
    _COOLS.pop(key, None)

def get_active_cooldowns() -> dict:
    """Get all active cooldowns for debugging (returns key -> seconds_remaining)"""
    now = time.monotonic()
    return {k: max(0, expires_at - now) for k, expires_at in _COOLS.items() if expires_at > now}