"""Enhanced caching system for DOI lookups."""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import platformdirs

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages file-based caching with expiration and statistics."""

    def __init__(self, app_name: str = "oscapify", cache_name: str = "doi_cache"):
        self.cache_dir = Path(platformdirs.user_cache_dir(app_name, app_name))
        self.cache_file = self.cache_dir / f"{cache_name}.json"
        self.stats_file = self.cache_dir / f"{cache_name}_stats.json"

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load cache and stats
        self.cache = self._load_json(self.cache_file, default={})
        self.stats = self._load_json(
            self.stats_file, default={"hits": 0, "misses": 0, "errors": 0, "last_cleanup": None}
        )

    def _load_json(self, file_path: Path, default: Any = None) -> Any:
        """Load JSON file with error handling."""
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load {file_path}: {e}")
                # Backup corrupted file
                backup_path = file_path.with_suffix(f".{datetime.now():%Y%m%d_%H%M%S}.bak")
                try:
                    file_path.rename(backup_path)
                    logger.info(f"Backed up corrupted file to {backup_path}")
                except Exception:
                    pass
        return default if default is not None else {}

    def _save_json(self, data: Any, file_path: Path) -> None:
        """Save JSON file with atomic write."""
        temp_file = file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2, sort_keys=True)
            temp_file.replace(file_path)
        except IOError as e:
            logger.error(f"Could not save {file_path}: {e}")
            if temp_file.exists():
                temp_file.unlink()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if key in self.cache:
            entry = self.cache[key]

            # Check expiration if set
            if "expires" in entry:
                expires = datetime.fromisoformat(entry["expires"])
                if datetime.now() > expires:
                    del self.cache[key]
                    return None

            self.stats["hits"] += 1
            self._save_stats()
            return entry.get("value")

        self.stats["misses"] += 1
        self._save_stats()
        return None

    def set(self, key: str, value: Any, expire_days: Optional[int] = None) -> None:
        """Set value in cache with optional expiration."""
        entry = {
            "value": value,
            "created": datetime.now().isoformat(),
        }

        if expire_days:
            entry["expires"] = (datetime.now() + timedelta(days=expire_days)).isoformat()

        self.cache[key] = entry
        self._save_cache()

    def _save_cache(self) -> None:
        """Save cache to file."""
        self._save_json(self.cache, self.cache_file)

    def _save_stats(self) -> None:
        """Save statistics to file."""
        self._save_json(self.stats, self.stats_file)

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache."""
        initial_size = len(self.cache)
        now = datetime.now()

        expired_keys = []
        for key, entry in self.cache.items():
            if "expires" in entry:
                expires = datetime.fromisoformat(entry["expires"])
                if now > expires:
                    expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            self._save_cache()

        self.stats["last_cleanup"] = now.isoformat()
        self._save_stats()

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_size": len(self.cache),
            "total_requests": total_requests,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "hit_rate": f"{hit_rate:.1f}%",
            "last_cleanup": self.stats.get("last_cleanup"),
            "cache_file": str(self.cache_file),
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")


def cached_function(
    cache_manager: CacheManager, expire_days: Optional[int] = None, key_prefix: str = ""
) -> Callable:
    """
    Decorator for caching function results.

    Args:
        cache_manager: CacheManager instance
        expire_days: Days until cache entry expires
        key_prefix: Prefix for cache keys
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function arguments
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))

            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()

            # Try to get from cache
            cached_value = cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__} with key {cache_key}")
                return cached_value

            # Call function and cache result
            try:
                result = func(*args, **kwargs)
                cache_manager.set(cache_key, result, expire_days)
                return result
            except Exception as e:
                cache_manager.stats["errors"] += 1
                cache_manager._save_stats()
                raise

        # Add cache control methods
        wrapper.cache_manager = cache_manager
        wrapper.clear_cache = lambda: cache_manager.clear()
        wrapper.get_cache_stats = lambda: cache_manager.get_stats()

        return wrapper

    return decorator
