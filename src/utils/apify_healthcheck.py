# src/utils/apify_healthcheck.py
import requests
import logging
from src.config.env import apify_token, apify_actor_or_task, is_apify_enabled

log = logging.getLogger("startup")

def apify_startup_check():
    """
    Validate Apify configuration at startup.
    Fails fast if Apify is enabled but misconfigured.
    """
    if not is_apify_enabled():
        log.info("Apify disabled - skipping healthcheck")
        return
    
    token = apify_token()
    actor, task = apify_actor_or_task()

    log.info("APIFY_TOKEN present? %s", "YES" if token else "NO")
    log.info("APIFY ACTOR/TASK present? %s", "YES" if (actor or task) else "NO")
    
    if not token:
        raise RuntimeError("Apify enabled but no token found. Set APIFY_TOKEN or APIFY_API_TOKEN in environment")
    
    if not (actor or task):
        raise RuntimeError("Apify enabled but no actor/task found. Set APIFY_ACTOR_ID, APIFY_ACTOR, or APIFY_TASK_ID in environment")

    # Test Apify API connectivity
    try:
        log.info("Testing Apify API connectivity...")
        r = requests.get("https://api.apify.com/v2/me", params={"token": token}, timeout=6)
        r.raise_for_status()
        
        user_data = r.json().get("data", {})
        username = user_data.get("username", "unknown")
        log.info("✅ Apify auth OK for user: %s", username)
        
        # Log configured actor/task
        if actor:
            log.info("✅ Apify actor configured: %s", actor)
        if task:
            log.info("✅ Apify task configured: %s", task)
            
    except requests.RequestException as e:
        raise RuntimeError(f"Apify API connectivity test failed: {e}. Check token and network access.")
    except Exception as e:
        raise RuntimeError(f"Apify healthcheck failed: {e}")

def quick_apify_check() -> bool:
    """
    Quick check if Apify is properly configured without throwing exceptions.
    
    Returns:
        True if Apify is properly configured, False otherwise
    """
    try:
        if not is_apify_enabled():
            return True  # Disabled is fine
            
        token = apify_token()
        actor, task = apify_actor_or_task()
        
        return bool(token and (actor or task))
        
    except Exception:
        return False