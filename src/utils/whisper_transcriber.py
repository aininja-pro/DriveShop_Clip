"""
Whisper API transcription handler for YouTube videos
Uses OpenAI's Whisper API to transcribe videos when YouTube captions are unavailable
"""

import os
import tempfile
import subprocess
from typing import Optional, Dict, Any
import hashlib
import json
from datetime import datetime, timedelta

from openai import OpenAI
import yt_dlp

from src.utils.logger import setup_logger
from src.utils.rate_limiter import rate_limiter

logger = setup_logger(__name__)

class WhisperTranscriber:
    """
    Handles audio transcription using OpenAI's Whisper API
    Includes caching to avoid re-transcribing the same videos
    """
    
    def __init__(self, cache_dir: str = ".whisper_cache"):
        """
        Initialize the Whisper transcriber
        
        Args:
            cache_dir: Directory to store transcription cache
        """
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("No OpenAI API key found - Whisper transcription disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=self.api_key)
        
        # Create cache directory
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Choose a persistent tmp directory to avoid ephemeral /tmp cleanup
        self.tmp_dir = os.environ.get('TMPDIR', '/app/data/tmp')
        try:
            os.makedirs(self.tmp_dir, exist_ok=True)
        except Exception:
            # Fallback to /var/tmp if /app/data/tmp is unavailable
            self.tmp_dir = '/var/tmp'
            os.makedirs(self.tmp_dir, exist_ok=True)

        # Audio download settings (stable writes, no fragmented parts, no proxy)
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(self.tmp_dir, '%(id)s.%(ext)s'),
            'paths': { 'home': self.tmp_dir, 'temp': self.tmp_dir },
            'nopart': True,                 # write final files directly (no .part-Frag)
            'concurrent_fragment_downloads': 1,
            'retries': 5,
            'fragment_retries': 3,
            'proxy': '',                    # disable any proxy usage
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
    
    def _get_cache_path(self, video_id: str) -> str:
        """Get cache file path for a video ID"""
        return os.path.join(self.cache_dir, f"{video_id}_transcript.json")
    
    def _load_from_cache(self, video_id: str) -> Optional[str]:
        """
        Load transcript from cache if available and not expired
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Cached transcript or None
        """
        cache_path = self._get_cache_path(video_id)
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (30 days)
                cached_date = datetime.fromisoformat(cache_data['timestamp'])
                if datetime.now() - cached_date < timedelta(days=30):
                    logger.info(f"Found valid cached transcript for {video_id}")
                    return cache_data['transcript']
                else:
                    logger.info(f"Cache expired for {video_id}")
                    
            except Exception as e:
                logger.warning(f"Error loading cache for {video_id}: {e}")
        
        return None
    
    def _save_to_cache(self, video_id: str, transcript: str):
        """Save transcript to cache"""
        cache_path = self._get_cache_path(video_id)
        
        try:
            cache_data = {
                'video_id': video_id,
                'transcript': transcript,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
                
            logger.info(f"Saved transcript to cache for {video_id}")
        except Exception as e:
            logger.warning(f"Error saving cache for {video_id}: {e}")
    
    def download_audio(self, video_url: str, video_id: str) -> Optional[str]:
        """
        Download audio from YouTube video
        
        Args:
            video_url: Full YouTube URL
            video_id: YouTube video ID
            
        Returns:
            Path to downloaded audio file or None if failed
        """
        try:
            # Ensure temp dir exists and set specific output template
            os.makedirs(self.tmp_dir, exist_ok=True)
            output_path = os.path.join(self.tmp_dir, f"{video_id}.mp3")

            # Clone ydl options (avoid mutating shared dict)
            ydl_opts = dict(self.ydl_opts)
            ydl_opts['outtmpl'] = os.path.join(self.tmp_dir, f"{video_id}.%(ext)s")
            
            logger.info(f"Downloading audio for video {video_id}...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Apply rate limiting
                rate_limiter.wait_if_needed('youtube.com')
                
                # Download the video
                info = ydl.extract_info(video_url, download=True)
                
                # Get video duration
                duration = info.get('duration', 0)
                
                # Check duration limit (e.g., 30 minutes max to control costs)
                max_duration = 1800  # 30 minutes
                if duration > max_duration:
                    logger.warning(f"Video too long ({duration}s > {max_duration}s) - skipping transcription")
                    return None
                
                # The file might have a different extension after processing
                # Look for the actual output file
                for ext in ['.mp3', '.m4a', '.wav']:
                    potential_path = output_path.replace('.mp3', ext)
                    if os.path.exists(potential_path):
                        logger.info(f"Audio downloaded successfully: {potential_path}")
                        return potential_path
                
                # If no file found, check temp directory
                files = os.listdir(self.tmp_dir)
                audio_files = [f for f in files if f.startswith(video_id) and f.endswith(('.mp3', '.m4a', '.wav'))]
                
                if audio_files:
                    audio_path = os.path.join(self.tmp_dir, audio_files[0])
                    logger.info(f"Audio downloaded successfully: {audio_path}")
                    return audio_path
                else:
                    logger.error(f"No audio file found after download")
                    return None
                
        except Exception as e:
            logger.error(f"Error downloading audio for {video_id}: {e}")
            return None
    
    def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio file using Whisper API
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text or None if failed
        """
        if not self.client:
            logger.error("No OpenAI client available - API key missing")
            return None
        
        try:
            logger.info(f"Transcribing audio file: {audio_path}")
            
            # Check file size (Whisper API limit is 25MB)
            file_size = os.path.getsize(audio_path)
            max_size = 25 * 1024 * 1024  # 25MB
            
            if file_size > max_size:
                logger.warning(f"Audio file too large ({file_size / 1024 / 1024:.1f}MB > 25MB)")
                # Could implement audio splitting here if needed
                return None
            
            # Apply rate limiting
            rate_limiter.wait_if_needed('api.openai.com')
            
            # Open and transcribe the audio file
            with open(audio_path, 'rb') as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text",
                    language="en"  # Specify English for better accuracy
                )
            
            # The response is the transcribed text
            transcript = response.strip()
            
            logger.info(f"Transcription successful: {len(transcript)} characters")
            return transcript
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None
    
    def cleanup_temp_files(self, audio_path: str):
        """Clean up temporary audio files"""
        try:
            if audio_path and os.path.exists(audio_path):
                # Remove the audio file
                os.remove(audio_path)
                
                # Do not remove the persistent tmp dir; only remove file
                    
                logger.info("Cleaned up temporary files")
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")
    
    def transcribe_youtube_video(self, video_url: str, video_id: str) -> Optional[str]:
        """
        Main method to transcribe a YouTube video
        
        Args:
            video_url: Full YouTube URL
            video_id: YouTube video ID
            
        Returns:
            Transcribed text or None if failed
        """
        # Check cache first
        cached_transcript = self._load_from_cache(video_id)
        if cached_transcript:
            return cached_transcript
        
        # Check if we have API access
        if not self.client:
            logger.warning("Whisper transcription unavailable - no API key")
            return None
        
        audio_path = None
        
        try:
            # Download audio
            audio_path = self.download_audio(video_url, video_id)
            if not audio_path:
                return None
            
            # Transcribe
            transcript = self.transcribe_audio(audio_path)
            
            if transcript:
                # Save to cache
                self._save_to_cache(video_id, transcript)
                return transcript
            else:
                return None
                
        finally:
            # Always clean up temp files
            if audio_path:
                self.cleanup_temp_files(audio_path)


# Global instance for easy access
_whisper_instance = None

def get_whisper_transcriber() -> WhisperTranscriber:
    """Get or create the global Whisper transcriber instance"""
    global _whisper_instance
    if _whisper_instance is None:
        _whisper_instance = WhisperTranscriber()
    return _whisper_instance


def transcribe_youtube_video(video_url: str, video_id: str) -> Optional[str]:
    """
    Convenience function to transcribe a YouTube video
    
    Args:
        video_url: Full YouTube URL
        video_id: YouTube video ID
        
    Returns:
        Transcribed text or None if failed
    """
    transcriber = get_whisper_transcriber()
    return transcriber.transcribe_youtube_video(video_url, video_id)