# src/config/__init__.py
"""
Configuration module for DriveShop Clip Tracking System.

Provides centralized environment variable management that works
with or without .env files (dev vs production deployment).
"""

from .env import (
    init_environment,
    getenv_any,
    apify_token,
    apify_actor_or_task, 
    cookiefile_path,
    youtube_proxy_url,
    apify_timeout,
    is_apify_enabled,
    should_force_apify,
    validate_apify_config
)

__all__ = [
    'init_environment',
    'getenv_any', 
    'apify_token',
    'apify_actor_or_task',
    'cookiefile_path',
    'youtube_proxy_url', 
    'apify_timeout',
    'is_apify_enabled',
    'should_force_apify',
    'validate_apify_config'
]