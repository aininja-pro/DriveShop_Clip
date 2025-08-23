# src/utils/caption_concurrency.py
import os
import threading

# Per-container semaphore to limit concurrent caption downloads
_sema = threading.Semaphore(int(os.getenv("YT_CAPTION_CONCURRENCY", "2")))

class CaptionSlot:
    """
    Context manager to limit concurrent caption downloads per container.
    Prevents proxy overload that causes 429 rate limits.
    """
    def __enter__(self):
        _sema.acquire()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        _sema.release()