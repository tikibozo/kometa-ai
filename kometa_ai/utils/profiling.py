"""
Performance profiling utilities for Kometa-AI.

This module provides tools for measuring and analyzing performance metrics
such as memory usage, execution time, and API call efficiency.
"""

import time
import logging
import tracemalloc
import functools
from typing import Dict, Any, Optional, Callable, TypeVar, cast
from datetime import datetime, UTC
import gc
import os
import json

# Mock psutil if not available
try:
    import psutil  # type: ignore
except ImportError:
    # Create a mock psutil for testing
    class MockProcess:
        def __init__(self):
            pass

        def memory_info(self):
            class MemInfo:
                def __init__(self):
                    self.rss = 0
                    self.vms = 0
                    self.shared = 0
                    self.text = 0
                    self.data = 0
            return MemInfo()

    class MockPsutil:
        @staticmethod
        def Process(pid=None):
            return MockProcess()

    psutil = MockPsutil()

logger = logging.getLogger(__name__)

# Type variable for function return types
T = TypeVar('T')


class PerformanceProfiler:
    """Utility class for profiling performance metrics."""

    def __init__(self, enabled: bool = True):
        """Initialize the performance profiler.

        Args:
            enabled: Whether profiling is enabled
        """
        self.enabled = enabled
        self.active = False
        self.metrics: Dict[str, Any] = {
            'memory': {},
            'timing': {},
            'api_calls': {},
            'batch_efficiency': {}
        }
        self._start_time: Optional[float] = None
        self._start_memory: Optional[Dict[str, Any]] = None
        self._collection_start_times: Dict[str, float] = {}
        self._memory_snapshots: Dict[str, Any] = {}
        self._last_snapshot: Optional[tracemalloc.Snapshot] = None

    def start(self) -> None:
        """Start performance profiling."""
        if not self.enabled:
            return

        if self.active:
            logger.warning("Performance profiler already started")
            return

        self.active = True
        self._start_time = time.time()
        self._start_memory = self._get_memory_usage()

        # Start memory tracing
        tracemalloc.start()
        self._last_snapshot = tracemalloc.take_snapshot()

        logger.info("Performance profiling started")

    def stop(self) -> Dict[str, Any]:
        """Stop performance profiling and return metrics.

        Returns:
            Dictionary with performance metrics
        """
        if not self.enabled or not self.active:
            return self.metrics

        end_time = time.time()
        end_memory = self._get_memory_usage()

        # Calculate overall metrics
        duration = end_time - cast(float, self._start_time)

        # Calculate memory diff properly
        memory_diff: Dict[str, Any] = {}
        if isinstance(self._start_memory, dict) and isinstance(end_memory, dict):
            for key in end_memory:
                if key in self._start_memory:
                    memory_diff[key] = end_memory[key] - self._start_memory[key]

        self.metrics['timing']['total_duration'] = duration
        self.metrics['memory']['peak'] = self._get_peak_memory()
        self.metrics['memory']['diff'] = memory_diff
        self.metrics['memory']['current'] = end_memory
        self.metrics['timestamp'] = datetime.now(UTC).isoformat()

        # Capture final memory snapshot and compare
        if tracemalloc.is_tracing():
            new_snapshot = tracemalloc.take_snapshot()
            if self._last_snapshot:
                top_stats = new_snapshot.compare_to(self._last_snapshot, 'lineno')
                # Handle different traceback formats
                top_allocations = []
                for stat in top_stats[:10]:  # Top 10 allocations
                    try:
                        # For newer versions of tracemalloc
                        # Get the first frame if it's a traceback collection
                        frame = stat.traceback[0] if hasattr(stat.traceback, '__getitem__') else stat.traceback
                        allocation = {
                            'file': str(frame.filename) if hasattr(frame, 'filename') else str(stat),
                            'line': frame.lineno if hasattr(frame, 'lineno') else 0,
                            'size': stat.size,
                            'size_diff': stat.size_diff
                        }
                    except AttributeError:
                        # Fall back to a simpler format if traceback structure is different
                        allocation = {
                            'info': str(stat.traceback),
                            'size': stat.size,
                            'size_diff': stat.size_diff
                        }
                    top_allocations.append(allocation)

                self.metrics['memory']['top_allocations'] = top_allocations
            tracemalloc.stop()

        self.active = False
        logger.info(f"Performance profiling stopped. Duration: {duration:.2f}s")
        return self.metrics

    def mark_collection_start(self, collection_name: str) -> None:
        """Mark the start of processing a collection.

        Args:
            collection_name: Name of the collection
        """
        if not self.enabled or not self.active:
            return

        self._collection_start_times[collection_name] = time.time()
        self._memory_snapshots[collection_name] = tracemalloc.take_snapshot()
        logger.debug(f"Marked start of collection '{collection_name}'")

    def mark_collection_end(self, collection_name: str, stats: Dict[str, Any]) -> None:
        """Mark the end of processing a collection and record metrics.

        Args:
            collection_name: Name of the collection
            stats: Statistics from processing the collection
        """
        if not self.enabled or not self.active:
            return

        if collection_name not in self._collection_start_times:
            logger.warning(f"No start time recorded for collection '{collection_name}'")
            return

        duration = time.time() - self._collection_start_times[collection_name]

        # Take memory snapshot and compare
        if tracemalloc.is_tracing() and collection_name in self._memory_snapshots:
            new_snapshot = tracemalloc.take_snapshot()
            collection_diff = new_snapshot.compare_to(
                self._memory_snapshots[collection_name], 'lineno'
            )
            memory_diff = sum(stat.size_diff for stat in collection_diff)
        else:
            memory_diff = 0

        # Record collection metrics
        collection_metrics = {
            'duration': duration,
            'memory_diff': memory_diff,
            'movies_processed': stats.get('processed_movies', 0),
            'from_cache': stats.get('from_cache', 0),
            'api_calls': stats.get('requests', 0),
            'batches': stats.get('batches', 0),
            'tokens': {
                'input': stats.get('total_input_tokens', 0),
                'output': stats.get('total_output_tokens', 0)
            }
        }

        # Calculate efficiency metrics
        if collection_metrics['batches'] > 0:
            collection_metrics['movies_per_batch'] = (
                collection_metrics['movies_processed'] / collection_metrics['batches']
            )
        else:
            collection_metrics['movies_per_batch'] = 0

        if collection_metrics['api_calls'] > 0:
            collection_metrics['movies_per_api_call'] = (
                collection_metrics['movies_processed'] / collection_metrics['api_calls']
            )
        else:
            collection_metrics['movies_per_api_call'] = 0

        # Store in metrics dictionary
        if 'collections' not in self.metrics:
            self.metrics['collections'] = {}

        self.metrics['collections'][collection_name] = collection_metrics
        logger.debug(f"Recorded metrics for collection '{collection_name}'")

    def record_api_call(self, endpoint: str, tokens: Dict[str, int]) -> None:
        """Record metrics for an API call.

        Args:
            endpoint: API endpoint called
            tokens: Token usage {'input': count, 'output': count}
        """
        if not self.enabled or not self.active:
            return

        if endpoint not in self.metrics['api_calls']:
            self.metrics['api_calls'][endpoint] = {
                'count': 0,
                'input_tokens': 0,
                'output_tokens': 0
            }

        self.metrics['api_calls'][endpoint]['count'] += 1
        self.metrics['api_calls'][endpoint]['input_tokens'] += tokens.get('input', 0)
        self.metrics['api_calls'][endpoint]['output_tokens'] += tokens.get('output', 0)

    def record_batch_efficiency(self, batch_size: int, actual_size: int) -> None:
        """Record batch efficiency metrics.

        Args:
            batch_size: Configured batch size
            actual_size: Actual number of items processed
        """
        if not self.enabled or not self.active:
            return

        if batch_size not in self.metrics['batch_efficiency']:
            self.metrics['batch_efficiency'][batch_size] = {
                'count': 0,
                'total_items': 0,
                'efficiency': 0
            }

        self.metrics['batch_efficiency'][batch_size]['count'] += 1
        self.metrics['batch_efficiency'][batch_size]['total_items'] += actual_size

        # Calculate average efficiency
        count = self.metrics['batch_efficiency'][batch_size]['count']
        total = self.metrics['batch_efficiency'][batch_size]['total_items']
        efficiency = (total / (count * batch_size)) if count > 0 else 0

        self.metrics['batch_efficiency'][batch_size]['efficiency'] = efficiency

    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage.

        Returns:
            Dictionary with memory metrics
        """
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()

        return {
            'rss': mem_info.rss,  # Resident Set Size
            'vms': mem_info.vms,  # Virtual Memory Size
            'shared': getattr(mem_info, 'shared', 0),  # Shared memory
            'text': getattr(mem_info, 'text', 0),  # Text (code)
            'data': getattr(mem_info, 'data', 0),  # Data + stack
        }

    def _get_peak_memory(self) -> Dict[str, Any]:
        """Get peak memory usage.

        Returns:
            Dictionary with peak memory metrics
        """
        # Force garbage collection to get accurate measurements
        gc.collect()

        process = psutil.Process(os.getpid())
        return {
            'rss_peak': process.memory_info().rss,
            'vms_peak': process.memory_info().vms
        }

    def save_metrics(self, filepath: str) -> None:
        """Save metrics to a file.

        Args:
            filepath: Path to save metrics
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.metrics, f, indent=2)
            logger.info(f"Performance metrics saved to {filepath}")
        except Exception as e:
            logger.error(f"Error saving performance metrics: {e}")


# Decorator for function timing
def profile_time(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to profile execution time of a function.

    Args:
        func: Function to profile

    Returns:
        Wrapped function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time

        # Log execution time
        logger.debug(f"Function {func.__name__} took {duration:.4f}s to execute")

        return result

    return wrapper


# Decorator for memory profiling
def profile_memory(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to profile memory usage of a function.

    Args:
        func: Function to profile

    Returns:
        Wrapped function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Start tracking
        gc.collect()
        tracemalloc.start()
        start_snapshot = tracemalloc.take_snapshot()

        result = func(*args, **kwargs)

        # Measure memory usage
        gc.collect()
        end_snapshot = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Compare snapshots
        stats = end_snapshot.compare_to(start_snapshot, 'lineno')

        # Log memory usage
        top_stats = stats[:10]
        logger.debug(f"Memory usage for {func.__name__}:")
        for stat in top_stats:
            logger.debug(f"  {stat}")

        return result

    return wrapper


# Global profiler instance
profiler = PerformanceProfiler(enabled=True)
