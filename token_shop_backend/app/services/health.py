# app/services/health.py
"""
Health check và monitoring utilities cho bot
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any
from app.services.storage import MemoryStorage
from app.services.cache import products_cache

log = logging.getLogger("health")


class HealthMonitor:
    """Monitor health và performance của bot"""
    
    def __init__(self, storage: MemoryStorage):
        self.storage = storage
        self.start_time = datetime.now()
        self._stats_history = []
    
    def get_health_status(self) -> Dict[str, Any]:
        """Lấy health status hiện tại"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        storage_stats = self.storage.get_stats()
        cache_stats = products_cache.get_stats()
        
        return {
            "status": "healthy",
            "uptime_seconds": int(uptime),
            "uptime_hours": round(uptime / 3600, 2),
            "uptime_days": round(uptime / 86400, 2),
            "storage": storage_stats,
            "cache": cache_stats,
            "timestamp": datetime.now().isoformat(),
        }
    
    def log_health_status(self):
        """Log health status định kỳ"""
        status = self.get_health_status()
        log.info(
            f"Health check - Uptime: {status['uptime_days']:.2f} days | "
            f"Storage: {status['storage']['total_sessions']} sessions | "
            f"Cache: {status['cache']['active_entries']} entries"
        )
    
    def start_periodic_logging(self, interval_hours: int = 24):
        """Bắt đầu log health status định kỳ"""
        async def _log_loop():
            while True:
                try:
                    await asyncio.sleep(interval_hours * 3600)
                    self.log_health_status()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"Error in health logging: {e}", exc_info=True)
        
        return asyncio.create_task(_log_loop())

