"""
Loki Log Handler - Async Batch Log Shipper.

Asynchronous handler that sends logs to Grafana Loki in batches.
Features:
- Batch processing (configurable size and interval)
- Async/non-blocking log shipping
- Graceful degradation (fallback to stdout if Loki unavailable)
- Automatic retry with exponential backoff
- Thread-safe queue

Usage:
    from observability.loki_handler import LokiHandler
    
    handler = LokiHandler(
        loki_url="http://loki:3100",
        job_name="knowledge-router-backend",
        batch_size=100,
        flush_interval=5.0
    )
    logger.addHandler(handler)
"""
import asyncio
import json
import logging
import queue
import threading
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx


class LokiHandler(logging.Handler):
    """
    Async batch log handler for Grafana Loki.
    
    Collects log records in a queue and ships them to Loki in batches
    using a background thread. Falls back to stdout if Loki is unavailable.
    """
    
    def __init__(
        self,
        loki_url: str,
        job_name: str = "knowledge-router-backend",
        batch_size: int = 100,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        timeout: float = 10.0,
    ):
        """
        Initialize Loki handler.
        
        Args:
            loki_url: Loki base URL (e.g., http://loki:3100)
            job_name: Job label for log streams
            batch_size: Number of logs to batch before sending
            flush_interval: Seconds between flushes
            max_retries: Max retry attempts on failure
            timeout: HTTP request timeout
        """
        super().__init__()
        self.loki_url = loki_url
        self.push_url = urljoin(loki_url, "/loki/api/v1/push")
        self.job_name = job_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Thread-safe queue for log records
        self.log_queue: queue.Queue = queue.Queue()
        
        # Background thread for batch shipping
        self.shutdown_event = threading.Event()
        self.shipper_thread = threading.Thread(
            target=self._shipping_loop,
            daemon=True,
            name="LokiShipperThread"
        )
        self.shipper_thread.start()
        
        # HTTP client (reusable)
        self.client = httpx.Client(timeout=timeout)
        
        # Graceful degradation flag
        self.loki_available = True
        self.last_failure_time = 0.0
        self.failure_cooldown = 60.0  # Retry Loki after 60s
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Enqueue log record for batch processing.
        
        Args:
            record: LogRecord instance
        """
        try:
            # Format record (assumes JSONFormatter)
            log_entry = self.format(record)
            
            # Enqueue for batch shipping
            self.log_queue.put_nowait({
                "timestamp": int(time.time() * 1e9),  # nanoseconds
                "line": log_entry,
            })
        except Exception as e:
            # Fallback: print to stderr (avoid infinite loop)
            self.handleError(record)
    
    def _shipping_loop(self) -> None:
        """
        Background thread loop for batch log shipping.
        
        Collects logs from queue and ships to Loki every flush_interval
        or when batch_size is reached.
        """
        batch: List[Dict] = []
        last_flush_time = time.time()
        
        while not self.shutdown_event.is_set():
            try:
                # Check if Loki should be retried
                if not self.loki_available:
                    if time.time() - self.last_failure_time > self.failure_cooldown:
                        self.loki_available = True
                
                # Collect logs from queue (non-blocking)
                try:
                    log_entry = self.log_queue.get(timeout=0.1)
                    batch.append(log_entry)
                except queue.Empty:
                    pass
                
                # Flush conditions: batch size or time interval
                should_flush = (
                    len(batch) >= self.batch_size or
                    (batch and time.time() - last_flush_time >= self.flush_interval)
                )
                
                if should_flush:
                    self._flush_batch(batch)
                    batch.clear()
                    last_flush_time = time.time()
            
            except Exception as e:
                # Log shipping error (print to stderr)
                print(f"[LokiHandler] Shipping error: {e}", flush=True)
        
        # Final flush on shutdown
        if batch:
            self._flush_batch(batch)
    
    def _flush_batch(self, batch: List[Dict]) -> None:
        """
        Send batch of logs to Loki.
        
        Args:
            batch: List of log entries with timestamp and line
        """
        if not batch:
            return
        
        # Skip if Loki marked unavailable
        if not self.loki_available:
            self._fallback_to_stdout(batch)
            return
        
        # Construct Loki push payload
        payload = {
            "streams": [
                {
                    "stream": {
                        "job": self.job_name,
                        "level": "info",  # Can be extracted from log line
                    },
                    "values": [
                        [str(entry["timestamp"]), entry["line"]]
                        for entry in batch
                    ],
                }
            ]
        }
        
        # Send to Loki with retry
        for attempt in range(self.max_retries):
            try:
                response = self.client.post(
                    self.push_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return  # Success
            
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == self.max_retries - 1:
                    # Final attempt failed
                    print(f"[LokiHandler] Failed to ship logs after {self.max_retries} attempts: {e}", flush=True)
                    self.loki_available = False
                    self.last_failure_time = time.time()
                    self._fallback_to_stdout(batch)
                else:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
    
    def _fallback_to_stdout(self, batch: List[Dict]) -> None:
        """
        Fallback: print logs to stdout if Loki unavailable.
        
        Args:
            batch: List of log entries
        """
        for entry in batch:
            print(entry["line"], flush=True)
    
    def close(self) -> None:
        """
        Shutdown handler and flush remaining logs.
        Guard against race conditions during Python shutdown.
        """
        # Signal shutdown first
        self.shutdown_event.set()
        
        # Wait for shipper thread to finish
        if self.shipper_thread.is_alive():
            self.shipper_thread.join(timeout=5.0)
        
        # Suppress httpcore trace logging during close to avoid I/O errors
        # when Python's logging system is shutting down
        import sys
        import os
        
        # Temporarily suppress stderr and disable httpcore logging
        httpcore_logger = logging.getLogger("httpcore")
        original_level = httpcore_logger.level
        httpcore_logger.setLevel(logging.CRITICAL + 1)  # Disable all logging
        
        try:
            # Close with stderr suppressed to avoid "I/O operation on closed file"
            original_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')
            try:
                self.client.close()
            finally:
                sys.stderr.close()
                sys.stderr = original_stderr
        except (ValueError, RuntimeError, OSError):
            # Ignore errors during shutdown (closed file handles, event loop issues)
            pass
        finally:
            httpcore_logger.setLevel(original_level)
        
        super().close()


def create_loki_handler(
    loki_url: str,
    job_name: str = "knowledge-router-backend",
    batch_size: int = 100,
    flush_interval: float = 5.0,
) -> Optional[LokiHandler]:
    """
    Factory function for Loki handler with validation.
    
    Args:
        loki_url: Loki base URL
        job_name: Job label for log streams
        batch_size: Batch size for log shipping
        flush_interval: Flush interval in seconds
    
    Returns:
        LokiHandler instance or None if URL invalid
    """
    if not loki_url or not loki_url.startswith("http"):
        print(f"[LokiHandler] Invalid LOKI_URL: {loki_url}", flush=True)
        return None
    
    try:
        handler = LokiHandler(
            loki_url=loki_url,
            job_name=job_name,
            batch_size=batch_size,
            flush_interval=flush_interval,
        )
        print(f"[LokiHandler] Initialized with URL: {loki_url}", flush=True)
        return handler
    except Exception as e:
        print(f"[LokiHandler] Failed to initialize: {e}", flush=True)
        return None
