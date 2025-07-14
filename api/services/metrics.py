"""
Custom business metrics service for Rendiff FFmpeg API

Provides application-specific metrics for monitoring business KPIs:
- Job processing metrics
- API usage patterns
- Performance indicators
- Business health metrics
"""
import time
from typing import Dict, Any, Optional
from enum import Enum
import structlog

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary, Info,
        generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from api.config import settings

logger = structlog.get_logger()


class MetricType(str, Enum):
    """Metric types for business monitoring."""
    COUNTER = "counter"
    HISTOGRAM = "histogram" 
    GAUGE = "gauge"
    SUMMARY = "summary"
    INFO = "info"


class BusinessMetricsService:
    """Service for collecting and exposing business metrics."""
    
    def __init__(self):
        self.registry = CollectorRegistry() if PROMETHEUS_AVAILABLE else None
        self.enabled = PROMETHEUS_AVAILABLE and getattr(settings, 'ENABLE_METRICS', True)
        
        if self.enabled:
            self._initialize_metrics()
        
        logger.info("Business metrics service initialized", enabled=self.enabled)
    
    def _initialize_metrics(self):
        """Initialize all business metrics."""
        if not self.enabled:
            return
        
        # Job Processing Metrics
        self.jobs_total = Counter(
            'rendiff_jobs_total',
            'Total number of jobs by status',
            ['status', 'job_type'],
            registry=self.registry
        )
        
        self.jobs_completed_total = Counter(
            'rendiff_jobs_completed_total',
            'Total number of completed jobs',
            ['job_type'],
            registry=self.registry
        )
        
        self.jobs_failed_total = Counter(
            'rendiff_jobs_failed_total',
            'Total number of failed jobs',
            ['job_type', 'error_type'],
            registry=self.registry
        )
        
        self.job_duration_seconds = Histogram(
            'rendiff_job_duration_seconds',
            'Job processing duration in seconds',
            ['job_type', 'worker_type'],
            buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600],
            registry=self.registry
        )
        
        self.job_file_size_bytes = Histogram(
            'rendiff_job_file_size_bytes',
            'Input file size for jobs in bytes',
            ['job_type'],
            buckets=[1e6, 10e6, 100e6, 500e6, 1e9, 5e9, 10e9],
            registry=self.registry
        )
        
        self.job_output_size_bytes = Histogram(
            'rendiff_job_output_size_bytes',
            'Output file size for jobs in bytes',
            ['job_type'],
            buckets=[1e6, 10e6, 100e6, 500e6, 1e9, 5e9, 10e9],
            registry=self.registry
        )
        
        # Queue Metrics
        self.queue_depth = Gauge(
            'rendiff_queue_depth',
            'Number of jobs waiting in queue',
            ['queue'],
            registry=self.registry
        )
        
        self.queue_processing_time = Summary(
            'rendiff_queue_wait_time_seconds',
            'Time jobs wait in queue before processing',
            ['queue'],
            registry=self.registry
        )
        
        # Worker Metrics
        self.workers_active = Gauge(
            'rendiff_workers_active',
            'Number of active workers',
            ['worker_type'],
            registry=self.registry
        )
        
        self.worker_utilization = Gauge(
            'rendiff_worker_utilization_percent',
            'Worker utilization percentage',
            ['worker_type'],
            registry=self.registry
        )
        
        # API Metrics
        self.api_requests_total = Counter(
            'rendiff_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'rendiff_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint'],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry
        )
        
        # Authentication Metrics
        self.api_key_validation_total = Counter(
            'rendiff_api_key_validation_total',
            'API key validation attempts',
            ['status'],
            registry=self.registry
        )
        
        self.api_key_validation_failures_total = Counter(
            'rendiff_api_key_validation_failures_total',
            'Failed API key validations',
            ['failure_reason'],
            registry=self.registry
        )
        
        # Cache Metrics
        self.cache_operations_total = Counter(
            'rendiff_cache_operations_total',
            'Cache operations',
            ['operation', 'result'],
            registry=self.registry
        )
        
        self.cache_hits_total = Counter(
            'rendiff_cache_hits_total',
            'Cache hits',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_misses_total = Counter(
            'rendiff_cache_misses_total',
            'Cache misses',
            ['cache_type'],
            registry=self.registry
        )
        
        self.cache_connection_errors_total = Counter(
            'rendiff_cache_connection_errors_total',
            'Cache connection errors',
            registry=self.registry
        )
        
        # Webhook Metrics
        self.webhook_attempts_total = Counter(
            'rendiff_webhook_attempts_total',
            'Webhook delivery attempts',
            ['event_type'],
            registry=self.registry
        )
        
        self.webhook_successes_total = Counter(
            'rendiff_webhook_successes_total',
            'Successful webhook deliveries',
            ['event_type'],
            registry=self.registry
        )
        
        self.webhook_failures_total = Counter(
            'rendiff_webhook_failures_total',
            'Failed webhook deliveries',
            ['event_type', 'failure_reason'],
            registry=self.registry
        )
        
        self.webhook_duration_seconds = Histogram(
            'rendiff_webhook_duration_seconds',
            'Webhook delivery duration',
            ['event_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        # Business KPI Metrics
        self.revenue_total = Counter(
            'rendiff_revenue_total',
            'Total revenue (if applicable)',
            ['currency'],
            registry=self.registry
        )
        
        self.active_users = Gauge(
            'rendiff_active_users',
            'Number of active users',
            ['period'],
            registry=self.registry
        )
        
        self.storage_usage_bytes = Gauge(
            'rendiff_storage_usage_bytes',
            'Storage usage in bytes',
            ['storage_type'],
            registry=self.registry
        )
        
        # Quality Metrics
        self.job_quality_score = Histogram(
            'rendiff_job_quality_score',
            'Quality scores for processed jobs',
            ['metric_type'],
            buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99],
            registry=self.registry
        )
        
        # Error Metrics
        self.job_errors_total = Counter(
            'rendiff_job_errors_total',
            'Job processing errors',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        self.system_errors_total = Counter(
            'rendiff_system_errors_total',
            'System-level errors',
            ['error_type', 'component'],
            registry=self.registry
        )
        
        # Service Info
        self.service_info = Info(
            'rendiff_service_info',
            'Service information',
            registry=self.registry
        )
        
        # Set service info
        self.service_info.info({
            'version': getattr(settings, 'VERSION', 'unknown'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'build_date': getattr(settings, 'BUILD_DATE', 'unknown'),
            'git_commit': getattr(settings, 'GIT_COMMIT', 'unknown'),
        })
    
    # Job Processing Methods
    def record_job_started(self, job_type: str, status: str = "processing"):
        """Record a job start."""
        if self.enabled:
            self.jobs_total.labels(status=status, job_type=job_type).inc()
    
    def record_job_completed(self, job_type: str, duration_seconds: float, worker_type: str = "cpu"):
        """Record a job completion."""
        if self.enabled:
            self.jobs_completed_total.labels(job_type=job_type).inc()
            self.job_duration_seconds.labels(job_type=job_type, worker_type=worker_type).observe(duration_seconds)
    
    def record_job_failed(self, job_type: str, error_type: str):
        """Record a job failure."""
        if self.enabled:
            self.jobs_failed_total.labels(job_type=job_type, error_type=error_type).inc()
    
    def record_job_file_sizes(self, job_type: str, input_size: int, output_size: int):
        """Record job file sizes."""
        if self.enabled:
            self.job_file_size_bytes.labels(job_type=job_type).observe(input_size)
            self.job_output_size_bytes.labels(job_type=job_type).observe(output_size)
    
    def record_job_quality(self, metric_type: str, score: float):
        """Record job quality metrics."""
        if self.enabled:
            self.job_quality_score.labels(metric_type=metric_type).observe(score)
    
    # Queue Methods
    def update_queue_depth(self, queue_name: str, depth: int):
        """Update queue depth."""
        if self.enabled:
            self.queue_depth.labels(queue=queue_name).set(depth)
    
    def record_queue_wait_time(self, queue_name: str, wait_time_seconds: float):
        """Record queue wait time."""
        if self.enabled:
            self.queue_processing_time.labels(queue=queue_name).observe(wait_time_seconds)
    
    # Worker Methods
    def update_active_workers(self, worker_type: str, count: int):
        """Update active worker count."""
        if self.enabled:
            self.workers_active.labels(worker_type=worker_type).set(count)
    
    def update_worker_utilization(self, worker_type: str, utilization_percent: float):
        """Update worker utilization."""
        if self.enabled:
            self.worker_utilization.labels(worker_type=worker_type).set(utilization_percent)
    
    # API Methods
    def record_api_request(self, method: str, endpoint: str, status_code: int, duration_seconds: float):
        """Record API request metrics."""
        if self.enabled:
            self.api_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            self.api_request_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)
    
    # Authentication Methods
    def record_api_key_validation(self, status: str):
        """Record API key validation."""
        if self.enabled:
            self.api_key_validation_total.labels(status=status).inc()
    
    def record_api_key_validation_failure(self, failure_reason: str):
        """Record API key validation failure."""
        if self.enabled:
            self.api_key_validation_failures_total.labels(failure_reason=failure_reason).inc()
    
    # Cache Methods
    def record_cache_operation(self, operation: str, result: str):
        """Record cache operation."""
        if self.enabled:
            self.cache_operations_total.labels(operation=operation, result=result).inc()
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit."""
        if self.enabled:
            self.cache_hits_total.labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss."""
        if self.enabled:
            self.cache_misses_total.labels(cache_type=cache_type).inc()
    
    def record_cache_connection_error(self):
        """Record cache connection error."""
        if self.enabled:
            self.cache_connection_errors_total.inc()
    
    # Webhook Methods
    def record_webhook_attempt(self, event_type: str):
        """Record webhook attempt."""
        if self.enabled:
            self.webhook_attempts_total.labels(event_type=event_type).inc()
    
    def record_webhook_success(self, event_type: str, duration_seconds: float):
        """Record webhook success."""
        if self.enabled:
            self.webhook_successes_total.labels(event_type=event_type).inc()
            self.webhook_duration_seconds.labels(event_type=event_type).observe(duration_seconds)
    
    def record_webhook_failure(self, event_type: str, failure_reason: str):
        """Record webhook failure."""
        if self.enabled:
            self.webhook_failures_total.labels(event_type=event_type, failure_reason=failure_reason).inc()
    
    # Business KPI Methods
    def record_revenue(self, amount: float, currency: str = "USD"):
        """Record revenue."""
        if self.enabled:
            self.revenue_total.labels(currency=currency).inc(amount)
    
    def update_active_users(self, period: str, count: int):
        """Update active user count."""
        if self.enabled:
            self.active_users.labels(period=period).set(count)
    
    def update_storage_usage(self, storage_type: str, bytes_used: int):
        """Update storage usage."""
        if self.enabled:
            self.storage_usage_bytes.labels(storage_type=storage_type).set(bytes_used)
    
    # Error Methods
    def record_job_error(self, error_type: str, component: str):
        """Record job error."""
        if self.enabled:
            self.job_errors_total.labels(error_type=error_type, component=component).inc()
    
    def record_system_error(self, error_type: str, component: str):
        """Record system error."""
        if self.enabled:
            self.system_errors_total.labels(error_type=error_type, component=component).inc()
    
    # Utility Methods
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        if not self.enabled:
            return "# Metrics not enabled\n"
        
        return generate_latest(self.registry).decode('utf-8')
    
    def get_content_type(self) -> str:
        """Get metrics content type."""
        return CONTENT_TYPE_LATEST
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for health checks."""
        if not self.enabled:
            return {"enabled": False}
        
        # This is a simplified summary - in production you might want
        # to collect actual values from the registry
        return {
            "enabled": True,
            "registry_collectors": len(list(self.registry._collector_to_names.keys())),
            "total_metrics": len([m for m in self.registry._collector_to_names.values()]),
        }


# Global metrics service instance
business_metrics = BusinessMetricsService()


def get_business_metrics() -> BusinessMetricsService:
    """Get business metrics service instance."""
    return business_metrics


# Convenience function for timing operations
class MetricsTimer:
    """Context manager for timing operations."""
    
    def __init__(self, metrics_service: BusinessMetricsService, metric_method: str, *args, **kwargs):
        self.metrics_service = metrics_service
        self.metric_method = metric_method
        self.args = args
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            method = getattr(self.metrics_service, self.metric_method)
            method(*self.args, duration, **self.kwargs)


def time_operation(metrics_service: BusinessMetricsService, metric_method: str, *args, **kwargs):
    """Decorator for timing operations."""
    def decorator(func):
        def wrapper(*func_args, **func_kwargs):
            with MetricsTimer(metrics_service, metric_method, *args, **kwargs):
                return func(*func_args, **func_kwargs)
        return wrapper
    return decorator