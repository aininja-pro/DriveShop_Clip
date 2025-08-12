"""
OpenAI API Semaphore for controlling concurrent requests
Prevents hitting burst limits when multiple processes are running
"""

import threading
import asyncio
from contextlib import contextmanager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class OpenAISemaphore:
    """
    Singleton semaphore to limit concurrent OpenAI API calls across the application
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Limit concurrent OpenAI calls
        # With 5 workers, limit to 3 concurrent API calls to avoid burst issues
        self.max_concurrent = 3
        self.semaphore = threading.Semaphore(self.max_concurrent)
        self.async_semaphore = asyncio.Semaphore(self.max_concurrent)
        self._initialized = True
        
        logger.info(f"OpenAI Semaphore initialized with max {self.max_concurrent} concurrent requests")
    
    @contextmanager
    def acquire(self):
        """
        Context manager for synchronous code
        """
        logger.debug("Waiting for OpenAI semaphore...")
        self.semaphore.acquire()
        logger.debug("OpenAI semaphore acquired")
        try:
            yield
        finally:
            self.semaphore.release()
            logger.debug("OpenAI semaphore released")
    
    async def async_acquire(self):
        """
        Context manager for async code
        """
        logger.debug("Waiting for async OpenAI semaphore...")
        async with self.async_semaphore:
            logger.debug("Async OpenAI semaphore acquired")
            yield
            logger.debug("Async OpenAI semaphore released")

# Global singleton instance
openai_semaphore = OpenAISemaphore()