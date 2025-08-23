import os
import time
import requests
import json
import logging
from typing import Optional, Dict, Any, List, Tuple

from src.utils.logger import setup_logger
from src.config.env import apify_token, apify_actor_or_task, apify_timeout

logger = setup_logger(__name__)
log = logging.getLogger("apify")

API = os.getenv("APIFY_API_BASE_URL", "https://api.apify.com")

def run_apify_transcript(video_id: str, url: str | None = None, wait_budget_s: int = 18) -> Tuple[str | None, str | None]:
    """
    Hardened Apify transcript extraction with proper error handling.
    
    Args:
        video_id: YouTube video ID
        url: Full YouTube URL (optional, will be constructed if not provided)
        wait_budget_s: Maximum time to wait for completion
        
    Returns:
        Tuple of (transcript_text, run_id) - either can be None
    """
    token = apify_token()
    actor, task = apify_actor_or_task()
    
    if not token or not (actor or task):
        log.error("Apify missing config; skipping call.")
        return None, None

    # Prepare payload in the format the actor expects (based on working Docker version)
    payload = {
        "startUrls": [url or f"https://www.youtube.com/watch?v={video_id}"],
        "language": "Default",
        "includeTimestamps": "No"
    }
    
    # Convert actor format for API URL: topaz_sharingan/Youtube-Transcript-Scraper → topaz_sharingan~youtube-transcript-scraper  
    if actor:
        actor_url_format = actor.replace('/', '~').lower().replace('youtube-transcript-scraper', 'youtube-transcript-scraper')
        start_url = f"{API}/v2/acts/{actor_url_format}/runs"
    else:
        start_url = f"{API}/v2/actor-tasks/{task}/runs"
    
    try:
        # Start the run
        log.info("Starting Apify run for video %s...", video_id)
        r = requests.post(start_url, params={"token": token}, json=payload, timeout=8)
        r.raise_for_status()
        
        run_data = r.json().get("data", {})
        run_id = run_data.get("id")
        
        if not run_id:
            log.error("Apify run start failed - no run ID returned")
            return None, None
            
        log.info("✅ Apify run started: %s (mode=%s)", run_id, "ACTOR" if actor else "TASK")

        # Wait for completion
        t0 = time.time()
        while time.time() - t0 < wait_budget_s:
            try:
                rr = requests.get(f"{API}/v2/actor-runs/{run_id}", params={"token": token}, timeout=8)
                rr.raise_for_status()
                
                data = rr.json().get("data", {})
                status = data.get("status", "UNKNOWN")
                
                if status in ("SUCCEEDED", "SUCCEEDED_WITH_WARNINGS"):
                    dataset_id = data.get("defaultDatasetId")
                    if not dataset_id:
                        log.error("Apify run %s succeeded but no datasetId", run_id)
                        return None, run_id
                    
                    # Get transcript data
                    items_response = requests.get(
                        f"{API}/v2/datasets/{dataset_id}/items", 
                        params={"token": token, "format": "json"}, 
                        timeout=8
                    )
                    items_response.raise_for_status()
                    items = items_response.json()
                    
                    # Extract transcript text using existing helper
                    texts = [_flatten_transcript_item(item) for item in items]
                    text = " ".join(t for t in texts if t).strip()
                    
                    if text:
                        log.info("✅ Apify run %s completed: %d chars", run_id, len(text))
                        return text, run_id
                    else:
                        log.warning("Apify run %s completed but no transcript text extracted", run_id)
                        return None, run_id
                        
                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    log.error("Apify run %s finished with status: %s", run_id, status)
                    return None, run_id
                    
                # Still running, wait a bit more
                time.sleep(1.0)
                
            except requests.RequestException as e:
                log.warning("Error checking Apify run %s status: %s", run_id, e)
                time.sleep(2.0)  # Wait longer on network errors
                
        # Exceeded budget
        log.error("Apify run %s exceeded local wait budget (%ss)", run_id, wait_budget_s)
        return None, run_id
        
    except requests.RequestException as e:
        log.error("Apify API call failed: %s", e)
        return None, None
    except Exception as e:
        log.error("Unexpected error in Apify call: %s", e)
        return None, None

def _flatten_transcript_item(item: Dict[str, Any]) -> str:
    """
    Best-effort extraction of transcript text from a dataset item returned by the
    Apify Youtube-Transcript-Scraper actor. Some builds emit `transcript`, some `segments`.
    """
    if not item:
        return ""

    # 1) Plain transcript text
    txt = item.get("transcript") or item.get("text")
    if txt and isinstance(txt, str):
        return txt.strip()

    # 2) Segments array -> join
    segments: List[Dict[str, Any]] = item.get("segments") or []
    if isinstance(segments, list) and segments:
        parts: List[str] = []
        for seg in segments:
            t = seg.get("text") or seg.get("line") or ""
            if isinstance(t, str) and t.strip():
                parts.append(t.strip())
        if parts:
            return " ".join(parts)

    # 3) Fallback common fields
    fields = ["caption", "captions", "body", "content"]
    for f in fields:
        v = item.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return ""

def get_transcript_from_apify(video_url: str, timeout_s: int = None) -> Optional[str]:
    """
    Hardened Apify transcript extraction with proper error handling.
    
    Args:
        video_url: YouTube URL to process
        timeout_s: Maximum timeout (optional, uses default from config)
        
    Returns:
        Transcript text or None if extraction failed
    """
    # Extract video ID from URL
    video_id = video_url.split('v=')[-1].split('&')[0] if 'v=' in video_url else video_url
    
    # Use default timeout if not specified
    wait_budget = timeout_s or apify_timeout() or 120
    # Cap at reasonable limit for transcript extraction
    wait_budget = min(wait_budget, 120)
    
    # Use the new hardened wrapper
    text, run_id = run_apify_transcript(video_id, video_url, wait_budget)
    
    # Guard the result and provide fallback handling
    if not isinstance(text, str) or len(text.strip()) < 50:
        logger.error("Apify returned no transcript text%s",
                     f" (run_id={run_id})" if run_id else "")
        return None
    
    logger.info(f"✅ Apify transcript successful: {len(text)} chars (run_id={run_id})")
    return text

def get_transcript_from_apify_legacy(video_url: str, timeout_s: int = None) -> Optional[str]:
    """
    LEGACY: Original Apify implementation using ApifyClient library.
    Kept for backward compatibility but not recommended for production.
    """
    try:
        from apify_client import ApifyClient  # Lazy import
    except Exception as e:
        logger.warning(f"Apify client not available: {e}")
        return None

    token = os.getenv("APIFY_API_TOKEN")
    actor = os.getenv("APIFY_YT_ACTOR") or "topaz_sharingan/Youtube-Transcript-Scraper"
    if not token or not actor:
        logger.debug("Apify token or actor slug not set; skipping Apify")
        return None

    hard_timeout = int(os.getenv("APIFY_YT_TIMEOUT_S", "120"))
    if timeout_s:
        hard_timeout = min(hard_timeout, timeout_s)

    # Strategy 1: Official client call; then read dataset
    try:
        client = ApifyClient(token)
        run_input: Dict[str, Any] = {
            "startUrls": [video_url],
            "language": "Default",
            "includeTimestamps": "No",
        }

        logger.info(f"▶️ Apify client call {actor} for {video_url} (timeout {hard_timeout}s)")
        run = client.actor(actor).call(run_input=run_input, timeout_secs=hard_timeout)

        dataset_id = None
        if isinstance(run, dict):
            dataset_id = run.get("defaultDatasetId") or run.get("defaultDatasetId".lower())

        items: List[Dict[str, Any]] = []
        if dataset_id:
            items = list(client.dataset(dataset_id).iterate_items())

        if items:
            text = _flatten_transcript_item(items[0])
            if text and len(text) > 50:
                logger.info(f"✅ Apify transcript (client): {len(text)} chars")
                return text
            logger.warning("Apify (client) returned empty/short transcript")
        else:
            logger.warning("Apify (client) returned no dataset items; falling back to run-sync endpoint")

    except Exception as e:
        logger.debug(f"Apify client path failed: {e}")

    # Strategy 2: Direct run-sync-get-dataset-items endpoint for robustness
    try:
        import requests
        endpoint = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?token={token}&format=json&limit=1"
        body = {
            "startUrls": [video_url],
            "language": "Default",
            "includeTimestamps": "No",
        }
        logger.info(f"▶️ Apify HTTP run-sync for {video_url}")
        r = requests.post(endpoint, json=body, timeout=hard_timeout)
        if r.status_code != 200:
            logger.warning(f"Apify HTTP failed: {r.status_code} {r.text[:200]}")
            return None
        items = r.json() if r.content else []
        if isinstance(items, dict):
            # Some actors return an object with items
            items = items.get("items") or items.get("data") or []
        if not items:
            logger.warning("Apify HTTP returned no items")
            return None
        text = _flatten_transcript_item(items[0])
        if text and len(text) > 50:
            logger.info(f"✅ Apify transcript (HTTP): {len(text)} chars")
            return text
        logger.warning("Apify HTTP transcript empty or too short")
        return None
    except Exception as e:
        logger.warning(f"Apify HTTP path failed: {e}")
        return None


