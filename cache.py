import lmdb
import os
from typing import Optional


class CacheHandler:
    """Simple LMDB-backed cache handler.

    Notes on closing:
    - It's best to explicitly call ``close()`` when you're done with the cache
      to release file handles and locks promptly.
    - You can instead use this class as a context manager (``with``) which
      will automatically close the environment on exit.
    - A ``__del__`` method is provided as a last-resort attempt to close the
      environment when the instance is garbage-collected, but ``__del__`` is
      not guaranteed to run in all interpreter shutdown scenarios so prefer
      explicit close or the context manager.
    """

    __cache_path: str = "./lmdb_cache"

    def __init__(self, ignore: bool = False, cache_path: str = "./lmdb_cache"):
        self.cache_path = cache_path
        os.makedirs(cache_path, exist_ok=True)
        # Open environment; default DB (None) is fine for a single DB use.
        self.env = lmdb.open(cache_path, max_dbs=1)
        self.db = self.env.open_db()

    # Context manager support -------------------------------------------------
    def __enter__(self) -> "CacheHandler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        # Always try to close; ignore errors during interpreter shutdown.
        try:
            self.close()
        except Exception:
            pass
        # don't suppress exceptions
        return None

    def __del__(self):
        # Best-effort cleanup. __del__ may not be called reliably during
        # interpreter shutdown, so don't rely on it as the primary cleanup.
        try:
            self.close()
        except Exception:
            pass

    # API ---------------------------------------------------------------------
    def check_if_new(self, key):
        """
        Check if a key is new in the cache.
        Returns True if key is NOT found (new), False if found (exists).
        """
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key

        with self.env.begin(self.db) as txn:
            result = txn.get(key_bytes)
            return result is None  # True if new (not found), False if exists

    def set(self, key, value):
        """Store a key-value pair in the cache."""
        key_bytes = key.encode("utf-8") if isinstance(key, str) else key
        value_bytes = value.encode("utf-8") if isinstance(value, str) else value

        with self.env.begin(self.db, write=True) as txn:
            txn.put(key_bytes, value_bytes)

    def close(self):
        """Close the LMDB environment.

        Call this when you are finished using the cache. It releases file
        descriptors and removes the lock held by the process.
        """
        try:
            if hasattr(self, "env") and self.env is not None:
                self.env.close()
        finally:
            # Avoid leaving a dangling reference
            self.env = None
            self.db = None


# Example usage
if __name__ == "__main__":
    # Prefer the context-manager form so the environment is closed
    with CacheHandler() as cache:
        # Check if key is new
        print(cache.check_if_new("user_123"))  # True (new)

    
    # Store the key
    cache.set("user_123", "data")

    # Check again
    print(cache.check_if_new("user_123"))  # False (exists)