"""
Fast, reliable YouTube transcript extraction using yt-dlp.
Based on ChatGPT-5's optimized implementation plan.
"""
from __future__ import annotations
from yt_dlp import YoutubeDL
import io
import json
import os
import random
import re
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import hashlib
import httpx
import webvtt

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Language preferences - prefer English variants
LANG_PREF = ["en", "en-US", "en-GB"]
AUTO_OK = True

def _pick_proxy(base: str | None) -> str | None:
    if not base:
        return None
    sess = random.randint(10_000, 99_999)
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}session={sess}"

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

def _extract_info(url: str, proxy: str | None, left):
    # Try android first, then web if time remains
    clients = ["android", "web"]  # drop "tv" (often slower/blocked)
    last_err=None
    for client in clients:
        if left() < 3:  # not enough time to attempt
            break
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": min(8, max(3, int(left()))),
            "extract_flat": False,
            "cachedir": False,
            "proxy": proxy,
            "subtitleslangs": LANG_PREF + ["en.*"],
            "writesubtitles": True,
            "writeautomaticsub": AUTO_OK,
            "subtitlesformat": "json3/vtt/best",
            "retries": 1,
            "fragment_retries": 0,
            "source_address": "0.0.0.0",  # force IPv4
            "extractor_args": {"youtube": {"player_client": [client], "skip": ["dash","hls"]}},
        }
        try:
            logger.debug(f"Trying client '{client}' with {left():.1f}s remaining, socket_timeout={ydl_opts['socket_timeout']}s")
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            last_err = e
            logger.debug(f"Client '{client}' failed: {e}")
            # rotate proxy session for next attempt
            proxy = _pick_proxy(os.getenv("YOUTUBE_PROXY_URL"))
            continue
    raise RuntimeError(f"Innertube extraction failed: {last_err}")

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

def _download_caption(url: str, proxy: str | None, total_left_s: float) -> tuple[bytes,str]:
    # Strict, total deadline. Fail fast on stalls.
    timeout = httpx.Timeout(connect=5.0, read=min(10.0, max(3.0, total_left_s)), write=5.0, pool=5.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Android 14; Mobile) AppleWebKit/537.36 Chrome/125 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    # One rotate-and-retry on 403/429/empty
    for attempt in (1, 2):
        logger.debug(f"Caption download attempt {attempt}, proxy: {'Yes' if proxy else 'No'}, timeout: {total_left_s:.1f}s")
        client_kwargs = {
            'headers': headers, 
            'timeout': timeout, 
            'follow_redirects': True, 
            'verify': False, 
            'trust_env': False
        }
        if proxy:
            client_kwargs['proxy'] = proxy
            
        with httpx.Client(**client_kwargs) as c:
            r = c.get(url)
            logger.debug(f"Caption response: status={r.status_code}, length={len(r.content)} bytes")
            if r.status_code in (403, 429) or not r.content:
                # rotate proxy and try once more
                proxy = _pick_proxy(os.getenv("YOUTUBE_PROXY_URL"))
                logger.debug(f"Rotating proxy due to status {r.status_code} or empty content")
                continue
            return r.content, ("json3" if "fmt=json3" in url or "json3" in url else "vtt")
    raise RuntimeError(f"Caption fetch failed with status {r.status_code}")

def fetch_youtube_transcript(video_url: str, proxy_base: str | None, timeout_s: int = 25) -> dict:
    left = _deadline(timeout_s)
    proxy = _pick_proxy(proxy_base)

    logger.info(f"Starting transcript extraction with {timeout_s}s budget, proxy: {'Yes' if proxy else 'No'}")
    
    info = _extract_info(video_url, proxy, left)  # ~<= 10–16s worst case
    logger.debug(f"Info extraction completed, {left():.1f}s remaining")

    src, lang, track = _choose_track(info)
    if not track:
        raise RuntimeError("No captions available (manual or auto).")
    
    logger.debug(f"Chosen track: source={src}, lang={lang}, {left():.1f}s remaining")

    if left() < 3:
        raise RuntimeError("Transcript exceeded time budget before download.")

    data, ext = _download_caption(track["url"], proxy, left())
    logger.debug(f"Caption download completed: format={ext}, size={len(data)} bytes, {left():.1f}s remaining")

    segments = _norm_json3(json.loads(data.decode("utf-8", "ignore")).get("events", [])) if ext=="json3" else _norm_vtt(data)
    if not segments:
        raise RuntimeError("Empty caption segments after parsing.")

    if left() <= 0:
        raise RuntimeError("Transcript exceeded time budget after parsing.")

    logger.info(f"✅ Transcript extracted: {len(segments)} segments, {src} {lang} in {timeout_s - left():.1f}s")
    
    return {
        "source": src,
        "lang": lang,
        "segments": segments,
        "raw": {"id": info.get("id"), "title": info.get("title")},
    }

def segments_to_text(segments: List[dict], max_chars: int = None) -> str:
    """
    Convert segments to plain text for sentiment analysis.
    Optionally limit to max_chars for token management.
    """
    if not segments:
        return ""
    
    text = " ".join(segment["text"].strip() for segment in segments if segment.get("text"))
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    
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
    
    def get_transcript(self, video_id: str, max_chars: int = None, timeout_s: int = 25) -> Optional[str]:
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