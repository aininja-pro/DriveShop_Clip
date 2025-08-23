"""
Fast, reliable YouTube transcript extraction using yt-dlp.
Based on ChatGPT-5's optimized implementation plan.
"""
from __future__ import annotations
from yt_dlp import YoutubeDL
import io
import json
import os
import re
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import httpx
import webvtt
import random
import secrets
import string
from urllib.parse import urlparse
import http.cookiejar

from src.utils.logger import setup_logger
from src.utils.rate_limiter import should_wait, register_backoff, clear_backoff
from src.utils.proxy_pool import get_session_pool

logger = setup_logger(__name__)

# Language preferences - prefer English variants
LANG_PREF = ["en", "en-US", "en-GB"]
AUTO_OK = True

def _normalize_proxy_url(value: str) -> str:
    """Accepts either full URL or HOST:PORT:USER:PASS and returns http URL string."""
    if not value:
        return None
    v = value.strip()
    if v.startswith("http://") or v.startswith("https://"):
        return v
    # HOST:PORT:USER:PASS form
    parts = v.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    return v

def _random_token(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def load_netscape_cookies(cookiefile: str) -> Optional[Dict[str, str]]:
    """
    Load cookies from Netscape/Mozilla format cookie file.
    Compatible with yt-dlp cookie files.
    """
    try:
        cj = http.cookiejar.MozillaCookieJar(cookiefile)
        cj.load(ignore_discard=True, ignore_expires=True)
        
        # Convert to dict format for httpx
        cookies = {}
        for cookie in cj:
            # Only include cookies for YouTube domains
            if cookie.domain in ['.youtube.com', 'youtube.com', '.google.com', 'google.com']:
                cookies[cookie.name] = cookie.value
        
        return cookies if cookies else None
        
    except Exception as e:
        logger.debug(f"Failed to load Netscape cookies from {cookiefile}: {e}")
        return None

def _make_sticky_from_base(base: str, region: str, ttl_minutes: str) -> str:
    """
    Build a sticky-session proxy URL from a base credential.
    Supports:
      - http://USER:PASS@host:port
      - host:port:USER:PASS
    Returns http://USER_region-REG_session-RANDOM_lifetime-TTLm:PASS@host:port
    """
    if not base:
        return None
    url = _normalize_proxy_url(base)
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    user = parsed.username or ""
    pwd = parsed.password or ""
    session = _random_token(8)
    # IPRoyal sticky parameters are appended to the PASSWORD, not the username
    sticky_pwd = f"{pwd}_region-{region}_session-{session}_lifetime-{ttl_minutes}m"
    return f"http://{user}:{sticky_pwd}@{host}:{port}"

# Legacy _pick_proxy replaced by session pool - keeping for compatibility
def _pick_proxy(base: str | None) -> str | None:
    """Legacy function - now uses session pool for better management"""
    session_pool = get_session_pool()
    session_id, proxy_url = session_pool.acquire()
    return proxy_url

def _deadline(budget_s: float):
    t0 = time.monotonic()
    def left():
        return max(0.0, budget_s - (time.monotonic() - t0))
    return left

def _norm_json3(events):
    out=[]
    for cue in events or []:
        s = cue.get("tStartMs",0)/1000.0
        d = cue.get("dDurationMs",0)/1000.0
        txt = "".join(seg.get("utf8","") for seg in (cue.get("segs") or [])).strip()
        if txt: out.append({"start": s, "duration": d, "text": txt})
    return out

def _norm_vtt(b: bytes):
    out=[]
    def to_sec(ts):
        hh,mm,ss = ts.split(":")
        return int(hh)*3600 + int(mm)*60 + float(ss.replace(",", "."))
    for c in webvtt.read_buffer(io.BytesIO(b)):
        txt = re.sub(r"\s+"," ", c.text).strip()
        if txt:
            st, en = to_sec(c.start), to_sec(c.end)
            out.append({"start": st, "duration": max(en-st,0.0), "text": txt})
    return out

# Old _extract_info function removed - replaced by _extract_info_single_attempt for surgical timing control

def _choose_track(info):
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    def pick(d):
        for l in LANG_PREF + list(d.keys()):
            if l in d and d[l]:
                return l, d[l][0]  # respects our json3/vtt preference
        return None, None
    lang, track = pick(subs)
    source = "manual"
    if not track and AUTO_OK:
        lang, track = pick(auto)
        source = "auto" if track else None
    return source, lang, track

def _download_caption(url: str, proxy_info: str | None, total_left_s: float, session_id: str = None) -> tuple[bytes,str]:
    """
    Download caption with separate proxy pool (Pool B) for caption requests.
    On 429, try Pool B rotation or direct connection as fallback.
    """
    # Strict, total deadline. Fail fast on stalls.
    timeout = httpx.Timeout(connect=5.0, read=min(10.0, max(3.0, total_left_s)), write=5.0, pool=5.0)
    
    # Use same headers as yt-dlp for consistency
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # Get separate caption proxy pool (Pool B)
    caption_pool = get_session_pool()  # For now, same pool - TODO: separate Pool B
    caption_session_id, caption_proxy = caption_pool.acquire()
    
    # Load cookies if available (same as yt-dlp) - safe and optional
    cookies = None
    from src.config.env import cookiefile_path
    cookies_file = cookiefile_path()
    if cookies_file:
        try:
            cookies = load_netscape_cookies(cookies_file)
            if cookies:
                logger.debug(f"🍪 Using {len(cookies)} cookies for caption download")
        except Exception as e:
            logger.debug(f"Cookie loading failed: {e}")
            cookies = None
    
    # Two attempts: Pool B → rotate or direct
    for attempt in (1, 2):
        logger.debug(f"Caption download attempt {attempt}, session: {caption_session_id[:8] if caption_session_id else 'none'}, timeout: {total_left_s:.1f}s")
        
        client_kwargs = {
            'headers': headers, 
            'timeout': timeout, 
            'follow_redirects': True, 
            'verify': False, 
            'trust_env': False,
            'cookies': cookies
        }
        
        # Use caption proxy (different from info proxy)
        if caption_proxy:
            client_kwargs['proxy'] = caption_proxy
            
        try:
            with httpx.Client(**client_kwargs) as c:
                r = c.get(url)
                logger.debug(f"Caption response: status={r.status_code}, length={len(r.content)} bytes")
                
                if r.status_code in (403, 429) or not r.content:
                    # Smart backoff based on response
                    retry_after = None
                    if 'retry-after' in r.headers:
                        try:
                            retry_after = float(r.headers['retry-after'])
                            logger.info(f"📡 YouTube Retry-After header: {retry_after}s")
                        except:
                            pass
                    
                    # Register backoff for caption session
                    register_backoff('youtube.com', caption_session_id, retry_after, r.status_code)
                    
                    # On attempt 1, try Pool B rotation or direct
                    if attempt == 1:
                        # Budget-aware backoff (never eat the remaining SLA)
                        min_headroom = 12.0  # seconds needed for final attempt
                        proposed = retry_after or random.uniform(6.0, 10.0)
                        wait_s = max(0.0, min(proposed, max(0.0, total_left_s - min_headroom)))
                        
                        if wait_s > 0:
                            logger.info(f"⏰ Caption retry: waiting {wait_s:.1f}s (budget-aware)")
                            time.sleep(wait_s)
                            total_left_s -= wait_s
                        else:
                            logger.info(f"⚡ Skipping wait - insufficient budget ({total_left_s:.1f}s remaining)")
                            
                        # Update timeout for remaining requests
                        timeout = httpx.Timeout(connect=5.0, read=min(10.0, max(3.0, total_left_s)), write=5.0, pool=5.0)
                        
                        # Rotate caption egress or go direct
                        try:
                            caption_session_id, caption_proxy = caption_pool.rotate()
                            logger.info(f"🔄 Rotated caption session: {caption_session_id[:8]}")
                        except:
                            # Fallback: direct connection (no proxy) with short fuse
                            caption_proxy = None
                            logger.info(f"🔄 Fallback: direct caption download (no proxy)")
                        
                        continue
                        
                else:
                    # Success!
                    clear_backoff('youtube.com', caption_session_id)
                    return r.content, ("json3" if "fmt=json3" in url or "json3" in url else "vtt")
                    
        except Exception as e:
            logger.warning(f"Caption download error (attempt {attempt}): {e}")
            if attempt == 1:
                # Try direct on network error
                caption_proxy = None
                continue
                
    raise RuntimeError(f"Caption fetch failed with status {r.status_code}")

def fetch_youtube_transcript(video_url: str, proxy_base: str | None, timeout_s: int = 25) -> dict:
    """
    Surgical transcript extraction: 1 attempt android (6-8s) → rotate + web (8s) → fail to Apify
    Total budget stays <25s to avoid falling through to expensive Apify every time
    """
    # Initialize session pool with proxy base
    session_pool = get_session_pool(proxy_base)
    session_id, proxy = session_pool.acquire()
    
    # Check if this session is in backoff (post-response only!)
    wait_s = should_wait('youtube.com', session_id)
    if wait_s > 0:
        actual_wait = min(wait_s, max(3.0, timeout_s - 5))  # Don't wait longer than budget allows
        logger.info(f"⏰ Session backoff: waiting {actual_wait:.1f}s (session: {session_id[:8]})")
        time.sleep(actual_wait)
    
    left = _deadline(timeout_s)
    start_time = time.time()

    logger.info(f"🚀 Starting transcript extraction with {timeout_s}s budget, session: {session_id[:8] if session_id else 'none'}")
    
    # SURGICAL APPROACH: 1 android attempt → rotate once + ios → fail fast
    clients_attempts = [
        ("android", min(8, max(6, int(left()) - 10))),  # 6-8s for android
        ("ios", min(8, max(6, int(left()) - 5)))        # 6-8s for ios after rotate (bypasses "not available on this app")
    ]
    
    last_error = None
    for attempt, (client, socket_timeout) in enumerate(clients_attempts, 1):
        if left() < 5:  # Need at least 5s for meaningful attempt
            logger.warning(f"⏰ Insufficient time remaining ({left():.1f}s), aborting")
            break
            
        try:
            logger.info(f"📱 Attempt {attempt}/2: {client} client (timeout: {socket_timeout}s, session: {session_id[:8]})")
            
            # Single extraction attempt with this client/session
            info = _extract_info_single_attempt(video_url, proxy, client, socket_timeout, session_id)
            
            # Success! Extract captions
            src, lang, track = _choose_track(info)
            if not track:
                raise RuntimeError("No captions available (manual or auto).")
            
            if left() < 3:
                raise RuntimeError("Transcript exceeded time budget before caption download.")

            # Use separate proxy for caption download (Pool B concept)
            data, ext = _download_caption(track["url"], None, left(), session_id)  # Uses separate pool internally
            
            segments = _norm_json3(json.loads(data.decode("utf-8", "ignore")).get("events", [])) if ext=="json3" else _norm_vtt(data)
            if not segments:
                raise RuntimeError("Empty caption segments after parsing.")

            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"✅ Transcript extracted: {len(segments)} segments, {src} {lang} in {elapsed_ms}ms")
            
            # Clear any previous backoff on success
            clear_backoff('youtube.com', session_id)
            
            # Log metrics for monitoring
            logger.info(f"📊 Metrics: session_id={session_id[:8]}, client_used={client}, "
                       f"status_code=200, elapsed_ms={elapsed_ms}, fallback_tier=primary, segments={len(segments)}")
            
            return {
                "source": src,
                "lang": lang,
                "segments": segments,
                "raw": {"id": info.get("id"), "title": info.get("title")},
            }
            
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"❌ Attempt {attempt} failed: {error_str}")
            
            # Check for rate limiting - register backoff and rotate session for retry
            if '429' in error_str or 'rate' in error_str.lower() or 'too many requests' in error_str.lower():
                logger.warning(f"⏰ Rate limit detected, registering backoff for session {session_id[:8]}")
                register_backoff('youtube.com', session_id, None, 429)
                
                # Rotate to new session for next attempt (if we have one)
                if attempt < len(clients_attempts):
                    session_id, proxy = session_pool.rotate()
                    logger.info(f"🔄 Rotated to new session: {session_id[:8]}")
                    
            elif '407' in error_str or 'proxy' in error_str.lower():
                logger.warning(f"🔄 Proxy auth issue, rotating session")
                if attempt < len(clients_attempts):
                    session_id, proxy = session_pool.rotate()
                    
            # Continue to next attempt if available
            continue
    
    # All attempts failed - log metrics and raise
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"📊 Metrics: session_id={session_id[:8]}, client_used=failed, "
               f"status_code=failed, elapsed_ms={elapsed_ms}, fallback_tier=failed")
    
    raise RuntimeError(f"All yt-dlp attempts failed in {elapsed_ms}ms: {last_error}")

def _extract_info_single_attempt(url: str, proxy: str | None, client: str, socket_timeout: int, session_id: str) -> dict:
    """Single yt-dlp extraction attempt with specific client and timeout"""
    
    # Base options for fast, reliable extraction
    ydl_opts = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "cachedir": False,
        "proxy": proxy,
        "subtitleslangs": LANG_PREF + ["en.*"],
        "writesubtitles": True,
        "writeautomaticsub": AUTO_OK,
        "subtitlesformat": "json3/vtt/best",
        "retries": 0,  # Single attempt only
        "fragment_retries": 0,
    }
    
    # Enhanced settings for reliability and geo-bypass
    ydl_opts.update({
        "socket_timeout": socket_timeout,
        "source_address": "0.0.0.0",     # Force IPv4
        "extractor_args": {"youtube": {"player_client": [client], "skip": ["dash","hls"]}},
        "geo_bypass_country": "US",       # Consistent geo context
    })
    
    # Add cookies if available for bot protection - safe and optional
    from src.config.env import cookiefile_path
    cookies_file = cookiefile_path()
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file
        logger.debug(f"🍪 Using cookies from {cookies_file} for bot protection")
    
    # Enhanced headers for bot detection evasion
    ydl_opts["http_headers"] = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    logger.debug(f"🎯 Trying {client} client (timeout: {socket_timeout}s, session: {session_id[:8]})")
    
    with YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(url, download=False)
        logger.info(f"✅ yt-dlp info extraction successful with {client} client")
        return result

def detect_language(text: str) -> str:
    """
    Simple language detection for transcript text.
    Returns 'en' for English, 'ar' for Arabic, etc.
    """
    if not text or len(text) < 50:
        return "en"  # Default to English for short text
    
    # Simple heuristic-based detection (can be enhanced with proper library)
    sample = text[:2000].lower()
    
    # Arabic indicators
    arabic_chars = len([c for c in sample if '\u0600' <= c <= '\u06FF'])
    if arabic_chars > len(sample) * 0.1:  # >10% Arabic characters
        return "ar"
    
    # Spanish indicators
    spanish_words = ['el ', 'la ', 'de ', 'que ', 'y ', 'en ', 'un ', 'es ', 'se ', 'no ']
    spanish_count = sum(1 for word in spanish_words if word in sample)
    if spanish_count >= 3:
        return "es"
    
    # French indicators  
    french_words = ['le ', 'de ', 'et ', 'à ', 'un ', 'il ', 'être ', 'et ', 'en ', 'avoir ']
    french_count = sum(1 for word in french_words if word in sample)
    if french_count >= 3:
        return "fr"
    
    # Default to English
    return "en"

def segments_to_text(segments: List[dict], max_chars: int = None) -> str:
    """
    Convert segments to plain text for sentiment analysis.
    Optionally limit to max_chars for token management.
    Includes language detection for non-English content.
    """
    if not segments:
        return ""
    
    text = " ".join(segment["text"].strip() for segment in segments if segment.get("text"))
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    
    # Language detection for auto captions
    detected_lang = detect_language(text)
    if detected_lang != "en":
        logger.info(f"🌍 Non-English content detected: {detected_lang}")
        # For now, log it - translation can be added later
        # TODO: Add translation service integration if needed
    
    if max_chars and len(text) > max_chars:
        # Smart truncation at sentence boundaries
        truncated = text[:max_chars]
        last_sentence = truncated.rfind('.')
        if last_sentence > max_chars * 0.8:  # If we can keep 80% and end at sentence
            text = truncated[:last_sentence + 1]
        else:
            text = truncated + "..."
    
    return text

class TranscriptCache:
    """Simple file-based cache for transcripts with TTL management"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or tempfile.gettempdir()) / "transcript_cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.positive_ttl = 7 * 24 * 3600  # 7 days for successful transcripts
        self.negative_ttl = 2 * 3600       # 2 hours for failures
    
    def _get_cache_path(self, video_id: str) -> Path:
        """Get cache file path for video_id"""
        hash_key = hashlib.md5(video_id.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.json"
    
    def get(self, video_id: str) -> Optional[dict]:
        """Get cached transcript result"""
        try:
            cache_file = self._get_cache_path(video_id)
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check TTL
            cached_time = datetime.fromisoformat(data['cached_at'])
            ttl = self.positive_ttl if data.get('success') else self.negative_ttl
            
            if datetime.now() - cached_time > timedelta(seconds=ttl):
                cache_file.unlink()  # Remove expired cache
                return None
            
            return data.get('result')
        except Exception:
            return None
    
    def set(self, video_id: str, result: dict = None, error: str = None):
        """Cache transcript result or error"""
        try:
            cache_file = self._get_cache_path(video_id)
            cache_data = {
                'video_id': video_id,
                'cached_at': datetime.now().isoformat(),
                'success': error is None,
                'result': result,
                'error': error
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except Exception:
            pass  # Cache errors are non-fatal

class FastTranscriptFetcher:
    """
    Production-ready transcript fetcher following ChatGPT's optimized plan.
    Handles proxy rotation, caching, and fallbacks.
    """
    
    def __init__(self, proxy_base: str = None, cache_dir: str = None, enable_whisper_fallback: bool = True):
        self.proxy_base = proxy_base or os.getenv('YOUTUBE_PROXY_URL')
        self.cache = TranscriptCache(cache_dir)
        self.enable_whisper_fallback = enable_whisper_fallback
        
        if self.proxy_base:
            logger.info("✅ IPRoyal proxy configured for transcript extraction")
        else:
            logger.warning("⚠️ No proxy configured - may face rate limiting")
    
    def get_transcript(self, video_id: str, max_chars: int = None, timeout_s: int = 90) -> Optional[str]:
        """
        Get transcript text for a YouTube video.
        
        Args:
            video_id: YouTube video ID
            max_chars: Maximum characters to return (for token management)
            timeout_s: Timeout in seconds (default 25s)
            
        Returns:
            Transcript text or None if not available
        """
        if not video_id:
            return None
        
        # Check cache first
        cached = self.cache.get(video_id)
        if cached:
            if cached.get('segments'):
                return segments_to_text(cached['segments'], max_chars)
            return None
        
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            result = fetch_youtube_transcript(video_url, self.proxy_base, timeout_s)
            
            # Cache successful result
            self.cache.set(video_id, result)
            
            # Return text
            return segments_to_text(result['segments'], max_chars)
            
        except RuntimeError as e:
            error_msg = str(e)
            logger.warning(f"Transcript extraction failed for {video_id}: {error_msg}")
            
            # Try Faster-Whisper fallback for short videos if enabled
            if self.enable_whisper_fallback and "no captions" in error_msg.lower():
                whisper_text = self._try_whisper_fallback(video_id, timeout_s)
                if whisper_text:
                    # Cache whisper result
                    whisper_result = {
                        'source': 'whisper',
                        'lang': 'en',
                        'segments': [{'start': 0, 'duration': 0, 'text': whisper_text}]
                    }
                    self.cache.set(video_id, whisper_result)
                    return segments_to_text(whisper_result['segments'], max_chars)
            
            # Cache the failure
            self.cache.set(video_id, error=error_msg)
            return None
    
    def _try_whisper_fallback(self, video_id: str, timeout_s: int) -> Optional[str]:
        """
        Fallback to Faster-Whisper for videos without captions.
        Only for short videos to maintain <30s SLA.
        """
        try:
            # Check if faster-whisper is available
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                logger.debug("faster-whisper not available for fallback")
                return None
            
            # Get video duration first
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Quick duration check
            info_opts = {
                "skip_download": True,
                "quiet": True,
                "proxy": _pick_proxy(self.proxy_base)
            }
            
            with YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                duration = info.get('duration', 0)
            
            # Only use Whisper for videos under 6 minutes
            if duration > 360:
                logger.debug(f"Video too long for Whisper fallback: {duration}s")
                return None
            
            logger.info(f"🎙️ Trying Faster-Whisper fallback for {video_id} ({duration}s)")
            start_time = time.time()
            
            # Download audio using yt-dlp
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_file = Path(temp_dir) / f"{video_id}.mp3"
                
                download_opts = {
                    'format': 'bestaudio[ext=m4a]/bestaudio/best',
                    'outtmpl': str(audio_file.with_suffix('.%(ext)s')),
                    'quiet': True,
                    'no_warnings': True,
                    'proxy': _pick_proxy(self.proxy_base)
                }
                
                with YoutubeDL(download_opts) as ydl:
                    ydl.download([video_url])
                
                # Find the downloaded audio file
                audio_files = list(Path(temp_dir).glob(f"{video_id}.*"))
                if not audio_files:
                    return None
                
                actual_audio_file = audio_files[0]
                
                # Transcribe with Faster-Whisper
                model = WhisperModel("base.en", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(
                    str(actual_audio_file),
                    beam_size=1,
                    vad_filter=True
                )
                
                transcript_text = ' '.join(segment.text.strip() for segment in segments)
                
                elapsed = time.time() - start_time
                if elapsed > timeout_s:
                    logger.warning(f"Whisper fallback exceeded timeout: {elapsed:.1f}s")
                    return None
                
                logger.info(f"✅ Whisper fallback successful: {len(transcript_text)} chars in {elapsed:.1f}s")
                return transcript_text
        
        except Exception as e:
            logger.debug(f"Whisper fallback failed for {video_id}: {e}")
            return None

# Global instance for easy importing
_fetcher = None

def get_transcript_fetcher() -> FastTranscriptFetcher:
    """Get global transcript fetcher instance"""
    global _fetcher
    if _fetcher is None:
        _fetcher = FastTranscriptFetcher()
    return _fetcher

def get_transcript(video_id: str, max_chars: int = None) -> Optional[str]:
    """Convenience function to get transcript text"""
    fetcher = get_transcript_fetcher()
    return fetcher.get_transcript(video_id, max_chars)

def get_full_transcript(video_url: str) -> dict:
    """
    Get full transcript result with metadata.
    Compatible with existing youtube_handler.py usage.
    """
    proxy_base = os.getenv("YOUTUBE_PROXY_URL")
    return fetch_youtube_transcript(video_url, proxy_base, timeout_s=25)