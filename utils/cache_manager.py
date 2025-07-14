"""
Cache Manager
Handles Redis caching operations for performance optimization
"""

import redis
import json
import logging
import os
from typing import Any, Optional
import pickle

class CacheManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection"""
        try:
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD', None)
            redis_db = int(os.getenv('REDIS_DB', 0))
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            self.logger.info("Redis connection established successfully")
            
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {str(e)}")
            self.logger.warning("Falling back to in-memory cache")
            self.redis_client = None
            self._fallback_cache = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    return pickle.loads(value)
            else:
                # Fallback to in-memory cache
                return self._fallback_cache.get(key)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Cache get failed for key {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """Set value in cache with expiration"""
        try:
            if self.redis_client:
                serialized_value = pickle.dumps(value)
                return self.redis_client.setex(key, expire, serialized_value)
            else:
                # Fallback to in-memory cache (no expiration for simplicity)
                self._fallback_cache[key] = value
                return True
                
        except Exception as e:
            self.logger.error(f"Cache set failed for key {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                if key in self._fallback_cache:
                    del self._fallback_cache[key]
                    return True
                return False
                
        except Exception as e:
            self.logger.error(f"Cache delete failed for key {key}: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            if self.redis_client:
                return bool(self.redis_client.exists(key))
            else:
                return key in self._fallback_cache
                
        except Exception as e:
            self.logger.error(f"Cache exists check failed for key {key}: {str(e)}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter in cache"""
        try:
            if self.redis_client:
                return self.redis_client.incr(key, amount)
            else:
                current = self._fallback_cache.get(key, 0)
                new_value = current + amount
                self._fallback_cache[key] = new_value
                return new_value
                
        except Exception as e:
            self.logger.error(f"Cache increment failed for key {key}: {str(e)}")
            return None

    def get_multiple(self, keys: list) -> dict:
        """Get multiple values from cache"""
        try:
            result = {}
            
            if self.redis_client:
                values = self.redis_client.mget(keys)
                for i, key in enumerate(keys):
                    if values[i]:
                        result[key] = pickle.loads(values[i])
                    else:
                        result[key] = None
            else:
                for key in keys:
                    result[key] = self._fallback_cache.get(key)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Cache get_multiple failed: {str(e)}")
            return {key: None for key in keys}

    def set_multiple(self, mapping: dict, expire: int = 3600) -> bool:
        """Set multiple values in cache"""
        try:
            if self.redis_client:
                pipe = self.redis_client.pipeline()
                for key, value in mapping.items():
                    serialized_value = pickle.dumps(value)
                    pipe.setex(key, expire, serialized_value)
                pipe.execute()
                return True
            else:
                self._fallback_cache.update(mapping)
                return True
                
        except Exception as e:
            self.logger.error(f"Cache set_multiple failed: {str(e)}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # Simple pattern matching for fallback cache
                import fnmatch
                keys_to_delete = [key for key in self._fallback_cache.keys() 
                                if fnmatch.fnmatch(key, pattern)]
                for key in keys_to_delete:
                    del self._fallback_cache[key]
                return len(keys_to_delete)
                
        except Exception as e:
            self.logger.error(f"Cache clear_pattern failed for pattern {pattern}: {str(e)}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics"""
        try:
            if self.redis_client:
                info = self.redis_client.info()
                return {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory': info.get('used_memory', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0)
                }
            else:
                return {
                    'cache_type': 'in_memory',
                    'total_keys': len(self._fallback_cache),
                    'memory_usage': 'unknown'
                }
                
        except Exception as e:
            self.logger.error(f"Cache stats failed: {str(e)}")
            return {}

    def health_check(self) -> dict:
        """Perform cache health check"""
        try:
            if self.redis_client:
                # Test basic operations
                test_key = 'health_check_test'
                test_value = 'test_value'
                
                # Set test value
                self.redis_client.set(test_key, test_value, ex=10)
                
                # Get test value
                retrieved_value = self.redis_client.get(test_key)
                
                # Delete test value
                self.redis_client.delete(test_key)
                
                if retrieved_value and retrieved_value.decode('utf-8') == test_value:
                    return {
                        'status': 'healthy',
                        'cache_type': 'redis',
                        'connection': 'ok'
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'cache_type': 'redis',
                        'connection': 'failed'
                    }
            else:
                return {
                    'status': 'healthy',
                    'cache_type': 'in_memory',
                    'connection': 'ok'
                }
                
        except Exception as e:
            self.logger.error(f"Cache health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'cache_type': 'redis' if self.redis_client else 'in_memory',
                'connection': 'error',
                'error': str(e)
            }

    def flush_all(self) -> bool:
        """Flush all cache data (use with caution)"""
        try:
            if self.redis_client:
                self.redis_client.flushdb()
                return True
            else:
                self._fallback_cache.clear()
                return True
                
        except Exception as e:
            self.logger.error(f"Cache flush_all failed: {str(e)}")
            return False

    # Convenience methods for common caching patterns
    
    def cache_customer_data(self, customer_id: int, data: dict, expire: int = 300):
        """Cache customer data with 5-minute expiration"""
        key = f"customer:{customer_id}"
        return self.set(key, data, expire)

    def get_customer_data(self, customer_id: int) -> Optional[dict]:
        """Get cached customer data"""
        key = f"customer:{customer_id}"
        return self.get(key)

    def cache_issue_analysis(self, issue_id: int, analysis: dict, expire: int = 1800):
        """Cache issue analysis with 30-minute expiration"""
        key = f"issue_analysis:{issue_id}"
        return self.set(key, analysis, expire)

    def get_issue_analysis(self, issue_id: int) -> Optional[dict]:
        """Get cached issue analysis"""
        key = f"issue_analysis:{issue_id}"
        return self.get(key)

    def cache_similar_issues(self, issue_id: int, similar_issues: list, expire: int = 3600):
        """Cache similar issues with 1-hour expiration"""
        key = f"similar_issues:{issue_id}"
        return self.set(key, similar_issues, expire)

    def get_similar_issues(self, issue_id: int) -> Optional[list]:
        """Get cached similar issues"""
        key = f"similar_issues:{issue_id}"
        return self.get(key)

    def cache_template(self, template_key: str, template_data: dict, expire: int = 7200):
        """Cache template data with 2-hour expiration"""
        key = f"template:{template_key}"
        return self.set(key, template_data, expire)

    def get_template(self, template_key: str) -> Optional[dict]:
        """Get cached template data"""
        key = f"template:{template_key}"
        return self.get(key)

    def invalidate_customer_cache(self, customer_id: int):
        """Invalidate all cache entries for a customer"""
        pattern = f"customer:{customer_id}*"
        return self.clear_pattern(pattern)

    def invalidate_issue_cache(self, issue_id: int):
        """Invalidate all cache entries for an issue"""
        patterns = [
            f"issue_analysis:{issue_id}",
            f"similar_issues:{issue_id}",
            f"issue:{issue_id}*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.clear_pattern(pattern)
        
        return total_deleted