import lmdb
import os
from typing import Optional, Union
import json
import pickle
import shutil


class CacheHandler:
    """Simple LMDB-backed cache handler with improved features.

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

    def __init__(
        self,
        cache_path: str = "./lmdb_cache",
        map_size: int = 10 * 1024 * 1024 * 1024,  # 10GB default
        max_dbs: int = 1,
        readonly: bool = False,
        use_existing_cache: bool = True
    ):
        """
        Initialize the cache handler.

        Args:
            cache_path: Path to the LMDB database directory
            map_size: Maximum size of the database (default: 10GB)
            max_dbs: Maximum number of named databases (default: 1)
            readonly: Open in read-only mode (default: False)
            use_existing_cache: If False, ignores and overwrites any
                existing cache. If True, uses existing cache if available.
        """
        self.cache_path = cache_path
        self.readonly = readonly
        self._closed = False

        if not use_existing_cache and os.path.exists(cache_path):
            if os.path.isdir(cache_path):
                shutil.rmtree(cache_path)
            else:
                os.remove(cache_path)

        os.makedirs(cache_path, exist_ok=True)

        # Open environment with configurable map_size
        self.env = lmdb.open(
            cache_path,
            map_size=map_size,
            max_dbs=max_dbs,
            readonly=readonly
        )
        self.db = self.env.open_db()

    # Context manager support -------------------------------------------------
    def __enter__(self) -> "CacheHandler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        self.close()
        return None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # Private helpers ---------------------------------------------------------
    def _ensure_open(self):
        """Ensure the environment is still open."""
        if self._closed or self.env is None:
            raise RuntimeError("Cache is closed. Create a new instance.")
    
    def _to_bytes(self, data: Union[str, bytes]) -> bytes:
        """Convert string to bytes."""
        return data.encode("utf-8") if isinstance(data, str) else data

    # API ---------------------------------------------------------------------
    def check_if_new(self, key: Union[str, bytes]) -> bool:
        """
        Check if a key is new in the cache.
        Returns True if key is NOT found (new), False if found (exists).
        
        Args:
            key: The key to check
            
        Returns:
            bool: True if key doesn't exist (new), False if exists
        """
        self._ensure_open()
        key_bytes = self._to_bytes(key)

        with self.env.begin(self.db) as txn:
            result = txn.get(key_bytes)
            return result is None

    def exists(self, key: Union[str, bytes]) -> bool:
        """
        Check if a key exists in the cache.
        More intuitive naming than check_if_new.
        
        Args:
            key: The key to check
            
        Returns:
            bool: True if key exists, False otherwise
        """
        return not self.check_if_new(key)

    def get(self, key: Union[str, bytes], default: Optional[bytes] = None) -> Optional[bytes]:
        """
        Get a value from the cache.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The value as bytes, or default if not found
        """
        self._ensure_open()
        key_bytes = self._to_bytes(key)

        with self.env.begin(self.db) as txn:
            result = txn.get(key_bytes)
            return result if result is not None else default

    def get_str(self, key: Union[str, bytes], default: Optional[str] = None) -> Optional[str]:
        """
        Get a value from the cache as a string.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist
            
        Returns:
            The value as string, or default if not found
        """
        result = self.get(key)
        if result is None:
            return default
        return result.decode("utf-8")

    def set(self, key: Union[str, bytes], value: Union[str, bytes]) -> bool:
        """
        Store a key-value pair in the cache.
        
        Args:
            key: The key to store
            value: The value to store
            
        Returns:
            bool: True if successful, False otherwise
        """
        self._ensure_open()
        
        if self.readonly:
            raise RuntimeError("Cannot write to a read-only cache")
        
        key_bytes = self._to_bytes(key)
        value_bytes = self._to_bytes(value)

        try:
            with self.env.begin(self.db, write=True) as txn:
                return txn.put(key_bytes, value_bytes)
        except Exception as e:
            print(f"Error setting cache key {key}: {e}")
            return False

    def set_json(self, key: Union[str, bytes], value: dict) -> bool:
        """
        Store a JSON-serializable object in the cache.
        
        Args:
            key: The key to store
            value: The dict/list to store as JSON
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str)
        except (TypeError, ValueError) as e:
            print(f"Error serializing to JSON: {e}")
            return False

    def get_json(self, key: Union[str, bytes], default: Optional[dict] = None) -> Optional[dict]:
        """
        Get a JSON object from the cache.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist or invalid JSON
            
        Returns:
            The deserialized JSON object, or default
        """
        result = self.get_str(key)
        if result is None:
            return default
        
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error deserializing JSON for key {key}: {e}")
            return default

    def set_pickle(self, key: Union[str, bytes], value: any) -> bool:
        """
        Store a Python object using pickle.
        
        Args:
            key: The key to store
            value: Any picklable Python object
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            pickled = pickle.dumps(value)
            return self.set(key, pickled)
        except Exception as e:
            print(f"Error pickling object: {e}")
            return False

    def get_pickle(self, key: Union[str, bytes], default: Optional[any] = None) -> Optional[any]:
        """
        Get a pickled Python object from the cache.
        
        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist or unpickling fails
            
        Returns:
            The unpickled object, or default
        """
        result = self.get(key)
        if result is None:
            return default
        
        try:
            return pickle.loads(result)
        except Exception as e:
            print(f"Error unpickling object for key {key}: {e}")
            return default

    def delete(self, key: Union[str, bytes]) -> bool:
        """
        Delete a key from the cache.
        
        Args:
            key: The key to delete
            
        Returns:
            bool: True if deleted, False if key didn't exist
        """
        self._ensure_open()
        
        if self.readonly:
            raise RuntimeError("Cannot delete from a read-only cache")
        
        key_bytes = self._to_bytes(key)

        try:
            with self.env.begin(self.db, write=True) as txn:
                return txn.delete(key_bytes)
        except Exception as e:
            print(f"Error deleting cache key {key}: {e}")
            return False

    def clear(self) -> bool:
        """
        Clear all entries from the cache.
        
        Returns:
            bool: True if successful
        """
        self._ensure_open()
        
        if self.readonly:
            raise RuntimeError("Cannot clear a read-only cache")
        
        try:
            with self.env.begin(self.db, write=True) as txn:
                # Drop and recreate the database
                txn.drop(self.db)
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False

    def count(self) -> int:
        """
        Get the number of entries in the cache.
        
        Returns:
            int: Number of key-value pairs
        """
        self._ensure_open()
        
        with self.env.begin(self.db) as txn:
            return txn.stat()['entries']

    def keys(self) -> list:
        """
        Get all keys in the cache.
        
        Returns:
            list: List of keys as bytes
        """
        self._ensure_open()
        
        keys = []
        with self.env.begin(self.db) as txn:
            cursor = txn.cursor()
            for key in cursor.iternext(keys=True, values=False):
                keys.append(key)
        return keys

    def items(self) -> list:
        """
        Get all key-value pairs in the cache.
        
        Returns:
            list: List of (key, value) tuples as bytes
        """
        self._ensure_open()
        
        items = []
        with self.env.begin(self.db) as txn:
            cursor = txn.cursor()
            for key, value in cursor:
                items.append((key, value))
        return items

    def close(self):
        """
        Close the LMDB environment.

        Call this when you are finished using the cache. It releases file
        descriptors and removes the lock held by the process.
        """
        if self._closed:
            return
        
        try:
            if hasattr(self, "env") and self.env is not None:
                self.env.close()
        finally:
            self.env = None
            self.db = None
            self._closed = True

    @property
    def is_closed(self) -> bool:
        """Check if the cache is closed."""
        return self._closed


# Example usage
if __name__ == "__main__":
    # Prefer the context-manager form so the environment is closed
    with CacheHandler() as cache:
        # Check if key is new
        print(f"Is 'user_123' new? {cache.check_if_new('user_123')}")  # True
        
        # Store string value
        cache.set("user_123", "John Doe")
        print(f"Is 'user_123' new? {cache.check_if_new('user_123')}")  # False
        print(f"Does 'user_123' exist? {cache.exists('user_123')}")  # True
        
        # Get value
        print(f"Value: {cache.get_str('user_123')}")  # "John Doe"
        
        # Store JSON
        cache.set_json("user_data", {"name": "John", "age": 30})
        print(f"User data: {cache.get_json('user_data')}")
        
        # Store complex object with pickle
        cache.set_pickle("my_list", [1, 2, 3, {"nested": "data"}])
        print(f"My list: {cache.get_pickle('my_list')}")
        
        # Count entries
        print(f"Total entries: {cache.count()}")
        
        # Delete a key
        cache.delete("user_123")
        print(f"After delete, exists? {cache.exists('user_123')}")  # False