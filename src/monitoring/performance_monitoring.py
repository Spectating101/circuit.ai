"""
Advanced Performance Monitoring

Features:
- Real-time performance metrics
- Application Performance Monitoring (APM)
- User experience tracking
- Database query analysis
- Memory profiling
- Distributed tracing
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import time
import functools
import asyncio
from collections import defaultdict
from loguru import logger


class MetricType(Enum):
    """Performance metric types."""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    DATABASE_QUERY_TIME = "db_query_time"
    CACHE_HIT_RATE = "cache_hit_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    metric_type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str]


@dataclass
class TraceSpan:
    """Distributed tracing span."""
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[float]
    tags: Dict[str, Any]
    status: str  # success, error


class PerformanceMonitor:
    """Performance monitoring and tracking."""

    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: List[PerformanceMetric] = []
        self.traces: Dict[str, List[TraceSpan]] = {}  # trace_id -> spans
        self.endpoint_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "min_time": float('inf'),
            "max_time": 0.0,
            "errors": 0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "recent_times": []
        })
        logger.info("PerformanceMonitor initialized")

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Record performance metric.

        Args:
            metric_type: Type of metric
            value: Metric value
            tags: Additional tags
        """
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )

        self.metrics.append(metric)

        # Keep only last 1 hour
        cutoff = datetime.utcnow() - timedelta(hours=1)
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff]

    def track_request(
        self,
        endpoint: str,
        duration_ms: float,
        status_code: int
    ):
        """
        Track HTTP request performance.

        Args:
            endpoint: Endpoint path
            duration_ms: Response time in milliseconds
            status_code: HTTP status code
        """
        stats = self.endpoint_stats[endpoint]

        stats["count"] += 1
        stats["total_time"] += duration_ms
        stats["min_time"] = min(stats["min_time"], duration_ms)
        stats["max_time"] = max(stats["max_time"], duration_ms)

        if status_code >= 400:
            stats["errors"] += 1

        # Keep recent times for percentile calculation
        stats["recent_times"].append(duration_ms)
        if len(stats["recent_times"]) > 1000:
            stats["recent_times"] = stats["recent_times"][-1000:]

        # Update percentiles
        if stats["recent_times"]:
            sorted_times = sorted(stats["recent_times"])
            count = len(sorted_times)

            stats["p50"] = sorted_times[int(count * 0.50)]
            stats["p95"] = sorted_times[int(count * 0.95)]
            stats["p99"] = sorted_times[int(count * 0.99)]

        # Record metric
        self.record_metric(
            MetricType.RESPONSE_TIME,
            duration_ms,
            tags={"endpoint": endpoint}
        )

    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """
        Get performance statistics for endpoint.

        Args:
            endpoint: Endpoint path

        Returns:
            Performance statistics
        """
        stats = self.endpoint_stats.get(endpoint)

        if not stats or stats["count"] == 0:
            return {}

        avg_time = stats["total_time"] / stats["count"]
        error_rate = (stats["errors"] / stats["count"]) * 100

        return {
            "endpoint": endpoint,
            "request_count": stats["count"],
            "avg_response_time_ms": avg_time,
            "min_response_time_ms": stats["min_time"],
            "max_response_time_ms": stats["max_time"],
            "p50_response_time_ms": stats["p50"],
            "p95_response_time_ms": stats["p95"],
            "p99_response_time_ms": stats["p99"],
            "error_count": stats["errors"],
            "error_rate_percent": error_rate
        }

    def get_all_endpoints_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all endpoints."""
        return [
            self.get_endpoint_stats(endpoint)
            for endpoint in self.endpoint_stats.keys()
        ]

    def get_slow_endpoints(self, threshold_ms: float = 1000) -> List[Dict[str, Any]]:
        """
        Get endpoints with slow response times.

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            List of slow endpoints
        """
        slow_endpoints = []

        for endpoint in self.endpoint_stats.keys():
            stats = self.get_endpoint_stats(endpoint)

            if stats.get("p95_response_time_ms", 0) > threshold_ms:
                slow_endpoints.append(stats)

        # Sort by p95 time
        slow_endpoints.sort(key=lambda x: x["p95_response_time_ms"], reverse=True)

        return slow_endpoints

    def get_error_prone_endpoints(self, threshold_percent: float = 5.0) -> List[Dict[str, Any]]:
        """
        Get endpoints with high error rates.

        Args:
            threshold_percent: Error rate threshold

        Returns:
            List of error-prone endpoints
        """
        error_endpoints = []

        for endpoint in self.endpoint_stats.keys():
            stats = self.get_endpoint_stats(endpoint)

            if stats.get("error_rate_percent", 0) > threshold_percent:
                error_endpoints.append(stats)

        # Sort by error rate
        error_endpoints.sort(key=lambda x: x["error_rate_percent"], reverse=True)

        return error_endpoints

    def start_trace(self, trace_id: str, operation: str) -> TraceSpan:
        """
        Start distributed trace.

        Args:
            trace_id: Unique trace ID
            operation: Operation name

        Returns:
            Trace span
        """
        import uuid

        span = TraceSpan(
            span_id=str(uuid.uuid4()),
            parent_span_id=None,
            operation_name=operation,
            start_time=datetime.utcnow(),
            end_time=None,
            duration_ms=None,
            tags={},
            status="started"
        )

        if trace_id not in self.traces:
            self.traces[trace_id] = []

        self.traces[trace_id].append(span)

        return span

    def end_trace(
        self,
        trace_id: str,
        span: TraceSpan,
        status: str = "success",
        tags: Optional[Dict[str, Any]] = None
    ):
        """
        End trace span.

        Args:
            trace_id: Trace ID
            span: Span to end
            status: Status (success/error)
            tags: Additional tags
        """
        span.end_time = datetime.utcnow()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status

        if tags:
            span.tags.update(tags)

    def get_trace(self, trace_id: str) -> List[TraceSpan]:
        """Get complete trace."""
        return self.traces.get(trace_id, [])


class PerformanceDecorator:
    """Decorators for automatic performance tracking."""

    def __init__(self, monitor: PerformanceMonitor):
        """Initialize decorator."""
        self.monitor = monitor

    def track_performance(self, operation_name: Optional[str] = None):
        """
        Decorator to track function performance.

        Args:
            operation_name: Name of operation (defaults to function name)

        Example:
            @performance_decorator.track_performance("analyze_pcb")
            async def analyze_pcb(image):
                ...
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                op_name = operation_name or func.__name__

                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)
                    status = "success"
                    return result

                except Exception as e:
                    status = "error"
                    raise

                finally:
                    duration_ms = (time.time() - start_time) * 1000

                    self.monitor.record_metric(
                        MetricType.RESPONSE_TIME,
                        duration_ms,
                        tags={"operation": op_name, "status": status}
                    )

                    logger.debug(f"{op_name} completed in {duration_ms:.2f}ms ({status})")

            return wrapper

        return decorator

    def track_database_query(self):
        """Decorator to track database query performance."""
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)
                    return result

                finally:
                    duration_ms = (time.time() - start_time) * 1000

                    self.monitor.record_metric(
                        MetricType.DATABASE_QUERY_TIME,
                        duration_ms,
                        tags={"query": func.__name__}
                    )

                    if duration_ms > 100:  # Slow query threshold
                        logger.warning(f"Slow database query: {func.__name__} took {duration_ms:.2f}ms")

            return wrapper

        return decorator


class PerformanceAnalyzer:
    """Analyze performance data and provide insights."""

    def __init__(self, monitor: PerformanceMonitor):
        """Initialize analyzer."""
        self.monitor = monitor

    def analyze_trends(
        self,
        metric_type: MetricType,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze performance trends.

        Args:
            metric_type: Metric to analyze
            hours: Hours of data to analyze

        Returns:
            Trend analysis
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Filter metrics
        metrics = [
            m for m in self.monitor.metrics
            if m.metric_type == metric_type and m.timestamp > cutoff
        ]

        if not metrics:
            return {
                "metric_type": metric_type.value,
                "data_points": 0,
                "trend": "no_data"
            }

        values = [m.value for m in metrics]

        # Calculate statistics
        avg = sum(values) / len(values)
        min_val = min(values)
        max_val = max(values)

        # Calculate trend (simple moving average)
        recent_values = values[-100:]  # Last 100 points
        older_values = values[:-100] if len(values) > 100 else values

        recent_avg = sum(recent_values) / len(recent_values)
        older_avg = sum(older_values) / len(older_values) if older_values else recent_avg

        if recent_avg > older_avg * 1.1:
            trend = "increasing"
        elif recent_avg < older_avg * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"

        return {
            "metric_type": metric_type.value,
            "data_points": len(metrics),
            "average": avg,
            "min": min_val,
            "max": max_val,
            "recent_average": recent_avg,
            "trend": trend,
            "change_percent": ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        }

    def get_performance_score(self) -> Dict[str, Any]:
        """
        Calculate overall performance score (0-100).

        Returns:
            Performance score and breakdown
        """
        score = 100.0
        deductions = []

        # Check response times
        all_stats = self.monitor.get_all_endpoints_stats()

        if all_stats:
            avg_p95 = sum(s["p95_response_time_ms"] for s in all_stats) / len(all_stats)

            if avg_p95 > 2000:  # > 2 seconds
                deduction = 30
                score -= deduction
                deductions.append(f"-{deduction}: Slow response times (avg p95: {avg_p95:.0f}ms)")
            elif avg_p95 > 1000:  # > 1 second
                deduction = 15
                score -= deduction
                deductions.append(f"-{deduction}: Moderate response times (avg p95: {avg_p95:.0f}ms)")

        # Check error rates
        slow_endpoints = self.monitor.get_slow_endpoints(threshold_ms=1000)
        if len(slow_endpoints) > 5:
            deduction = 20
            score -= deduction
            deductions.append(f"-{deduction}: {len(slow_endpoints)} slow endpoints detected")

        error_endpoints = self.monitor.get_error_prone_endpoints(threshold_percent=5.0)
        if error_endpoints:
            deduction = 25
            score -= deduction
            deductions.append(f"-{deduction}: {len(error_endpoints)} endpoints with high error rates")

        score = max(0, score)

        # Rating
        if score >= 90:
            rating = "Excellent"
        elif score >= 75:
            rating = "Good"
        elif score >= 50:
            rating = "Fair"
        else:
            rating = "Poor"

        return {
            "score": score,
            "rating": rating,
            "deductions": deductions,
            "recommendations": self._get_recommendations(deductions)
        }

    def _get_recommendations(self, deductions: List[str]) -> List[str]:
        """Get performance improvement recommendations."""
        recommendations = []

        for deduction in deductions:
            if "Slow response times" in deduction:
                recommendations.append("Optimize database queries with indexes")
                recommendations.append("Implement caching layer")
                recommendations.append("Scale up compute resources")

            elif "slow endpoints" in deduction:
                recommendations.append("Profile slow endpoints to identify bottlenecks")
                recommendations.append("Consider async processing for heavy operations")

            elif "error rates" in deduction:
                recommendations.append("Review error logs and fix common issues")
                recommendations.append("Add better input validation")
                recommendations.append("Implement circuit breakers for external dependencies")

        return recommendations


# Singleton instances
performance_monitor = PerformanceMonitor()
performance_decorator = PerformanceDecorator(performance_monitor)
performance_analyzer = PerformanceAnalyzer(performance_monitor)
