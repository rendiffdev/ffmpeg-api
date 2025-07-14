"""
Webhook service for sending HTTP notifications about job events
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
# Use structlog if available, fall back to standard logging
try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Use httpx for async HTTP requests, fall back to aiohttp if needed
try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    try:
        import aiohttp
        HTTP_CLIENT = "aiohttp"
    except ImportError:
        HTTP_CLIENT = None

try:
    from api.config import settings
except ImportError:
    # Mock settings for testing without dependencies
    class MockSettings:
        WEBHOOK_MAX_RETRIES = 5
        WEBHOOK_TIMEOUT_SECONDS = 30
        VERSION = "1.0.0"
        ENVIRONMENT = "development"
        WEBHOOK_SECRET = None
    
    settings = MockSettings()


class WebhookStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    ABANDONED = "abandoned"


class WebhookDelivery:
    """Represents a webhook delivery attempt."""
    
    def __init__(
        self,
        job_id: str,
        event: str,
        webhook_url: str,
        payload: Dict[str, Any],
        attempt: int = 1
    ):
        self.job_id = job_id
        self.event = event
        self.webhook_url = webhook_url
        self.payload = payload
        self.attempt = attempt
        self.status = WebhookStatus.PENDING
        self.created_at = datetime.utcnow()
        self.last_attempt_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
        self.response_status: Optional[int] = None
        self.response_body: Optional[str] = None
        self.error_message: Optional[str] = None


class WebhookService:
    """Service for sending webhook notifications with retry logic."""
    
    def __init__(self):
        self.max_retries = getattr(settings, 'WEBHOOK_MAX_RETRIES', 5)
        self.timeout_seconds = getattr(settings, 'WEBHOOK_TIMEOUT_SECONDS', 30)
        self.retry_delays = [60, 300, 900, 3600, 7200]  # 1m, 5m, 15m, 1h, 2h
        self.user_agent = f"Rendiff-FFmpeg-API/{getattr(settings, 'VERSION', '1.0.0')}"
        self.deliveries: Dict[str, List[WebhookDelivery]] = {}
        
        # Initialize HTTP client
        self._http_client = None
        self._client_session = None
    
    async def _get_http_client(self):
        """Get or create HTTP client."""
        if HTTP_CLIENT is None:
            raise RuntimeError("No HTTP client available. Install httpx or aiohttp.")
        
        if self._http_client is None:
            if HTTP_CLIENT == "httpx":
                self._http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds),
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True
                )
            elif HTTP_CLIENT == "aiohttp":
                import aiohttp
                timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
                self._http_client = aiohttp.ClientSession(
                    timeout=timeout,
                    headers={"User-Agent": self.user_agent}
                )
        
        return self._http_client
    
    async def cleanup(self):
        """Clean up HTTP client resources."""
        if self._http_client:
            if HTTP_CLIENT == "httpx":
                await self._http_client.aclose()
            elif HTTP_CLIENT == "aiohttp":
                await self._http_client.close()
            self._http_client = None
    
    def validate_webhook_url(self, url: str) -> bool:
        """Validate webhook URL format and security."""
        try:
            parsed = urlparse(url)
            
            # Must be HTTP or HTTPS
            if parsed.scheme not in ["http", "https"]:
                return False
            
            # Must have a host
            if not parsed.netloc:
                return False
            
            # Security: Block internal/localhost URLs in production
            if hasattr(settings, 'ENVIRONMENT') and settings.ENVIRONMENT == 'production':
                hostname = parsed.hostname
                if hostname in ['localhost', '127.0.0.1', '::1']:
                    return False
                
                # Block private IP ranges
                if hostname and (
                    hostname.startswith('10.') or
                    hostname.startswith('192.168.') or
                    hostname.startswith('172.')
                ):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _calculate_retry_delay(self, attempt: int) -> int:
        """Calculate retry delay with exponential backoff."""
        if attempt <= len(self.retry_delays):
            return self.retry_delays[attempt - 1]
        else:
            # For attempts beyond our predefined delays, use exponential backoff
            return min(self.retry_delays[-1] * (2 ** (attempt - len(self.retry_delays))), 86400)  # Max 24h
    
    def _should_retry(self, status_code: Optional[int], attempt: int) -> bool:
        """Determine if webhook should be retried."""
        if attempt >= self.max_retries:
            return False
        
        if status_code is None:  # Network error
            return True
        
        # Retry on server errors and rate limiting
        if status_code >= 500 or status_code == 429:
            return True
        
        # Don't retry on client errors (4xx except 429)
        return False
    
    async def _send_http_request(self, delivery: WebhookDelivery) -> tuple[Optional[int], Optional[str], Optional[str]]:
        """Send the actual HTTP request."""
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery.event,
            "X-Job-ID": delivery.job_id,
            "X-Delivery-Attempt": str(delivery.attempt),
            "X-Webhook-Timestamp": delivery.created_at.isoformat(),
        }
        
        # Add signature if configured
        if hasattr(settings, 'WEBHOOK_SECRET') and settings.WEBHOOK_SECRET:
            import hashlib
            import hmac
            
            payload_bytes = json.dumps(delivery.payload, sort_keys=True).encode()
            signature = hmac.new(
                settings.WEBHOOK_SECRET.encode(),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
        
        try:
            client = await self._get_http_client()
            
            if HTTP_CLIENT == "httpx":
                response = await client.post(
                    delivery.webhook_url,
                    json=delivery.payload,
                    headers=headers
                )
                return response.status_code, response.text, None
                
            elif HTTP_CLIENT == "aiohttp":
                async with client.post(
                    delivery.webhook_url,
                    json=delivery.payload,
                    headers=headers
                ) as response:
                    body = await response.text()
                    return response.status, body, None
            
        except asyncio.TimeoutError:
            return None, None, "Request timeout"
        except Exception as e:
            return None, None, str(e)
    
    async def send_webhook(
        self, 
        job_id: str, 
        event: str, 
        webhook_url: str, 
        payload: Dict[str, Any],
        retry: bool = True
    ) -> bool:
        """Send a webhook notification."""
        # Validate URL
        if not self.validate_webhook_url(webhook_url):
            logger.warning(
                "Invalid webhook URL",
                job_id=job_id,
                event=event,
                url=webhook_url
            )
            return False
        
        # Create delivery record
        delivery = WebhookDelivery(job_id, event, webhook_url, payload)
        
        # Store delivery for tracking
        if job_id not in self.deliveries:
            self.deliveries[job_id] = []
        self.deliveries[job_id].append(delivery)
        
        # Attempt delivery
        success = await self._attempt_delivery(delivery)
        
        if not success and retry:
            # Schedule retry
            await self._schedule_retry(delivery)
        
        return success
    
    async def _attempt_delivery(self, delivery: WebhookDelivery) -> bool:
        """Attempt to deliver a webhook."""
        delivery.last_attempt_at = datetime.utcnow()
        delivery.status = WebhookStatus.PENDING
        
        logger.info(
            "Sending webhook",
            job_id=delivery.job_id,
            event=delivery.event,
            url=delivery.webhook_url,
            attempt=delivery.attempt
        )
        
        status_code, response_body, error = await self._send_http_request(delivery)
        
        delivery.response_status = status_code
        delivery.response_body = response_body[:1000] if response_body else None  # Truncate
        delivery.error_message = error
        
        # Determine success
        if status_code and 200 <= status_code < 300:
            delivery.status = WebhookStatus.SENT
            logger.info(
                "Webhook delivered successfully",
                job_id=delivery.job_id,
                event=delivery.event,
                status_code=status_code,
                attempt=delivery.attempt
            )
            return True
        else:
            delivery.status = WebhookStatus.FAILED
            logger.warning(
                "Webhook delivery failed",
                job_id=delivery.job_id,
                event=delivery.event,
                status_code=status_code,
                error=error,
                attempt=delivery.attempt
            )
            return False
    
    async def _schedule_retry(self, delivery: WebhookDelivery):
        """Schedule a retry for failed webhook delivery."""
        if not self._should_retry(delivery.response_status, delivery.attempt):
            delivery.status = WebhookStatus.ABANDONED
            logger.warning(
                "Webhook abandoned after max retries",
                job_id=delivery.job_id,
                event=delivery.event,
                final_attempt=delivery.attempt
            )
            return
        
        # Calculate next retry time
        retry_delay = self._calculate_retry_delay(delivery.attempt)
        delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
        delivery.status = WebhookStatus.RETRYING
        
        logger.info(
            "Webhook retry scheduled",
            job_id=delivery.job_id,
            event=delivery.event,
            next_attempt=delivery.attempt + 1,
            retry_in_seconds=retry_delay,
            retry_at=delivery.next_retry_at.isoformat()
        )
        
        # Schedule the retry (in a real implementation, this would use a task queue)
        asyncio.create_task(self._delayed_retry(delivery, retry_delay))
    
    async def _delayed_retry(self, delivery: WebhookDelivery, delay_seconds: int):
        """Execute a delayed retry."""
        await asyncio.sleep(delay_seconds)
        
        # Create new delivery attempt
        retry_delivery = WebhookDelivery(
            delivery.job_id,
            delivery.event,
            delivery.webhook_url,
            delivery.payload,
            delivery.attempt + 1
        )
        
        # Store retry delivery
        if delivery.job_id in self.deliveries:
            self.deliveries[delivery.job_id].append(retry_delivery)
        
        # Attempt delivery
        success = await self._attempt_delivery(retry_delivery)
        
        if not success:
            # Schedule another retry if needed
            await self._schedule_retry(retry_delivery)
    
    def get_delivery_status(self, job_id: str) -> List[Dict[str, Any]]:
        """Get webhook delivery status for a job."""
        if job_id not in self.deliveries:
            return []
        
        return [
            {
                "event": d.event,
                "attempt": d.attempt,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
                "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
                "next_retry_at": d.next_retry_at.isoformat() if d.next_retry_at else None,
                "response_status": d.response_status,
                "error_message": d.error_message
            }
            for d in self.deliveries[job_id]
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get webhook delivery statistics."""
        all_deliveries = []
        for deliveries in self.deliveries.values():
            all_deliveries.extend(deliveries)
        
        if not all_deliveries:
            return {
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "pending_deliveries": 0,
                "success_rate": 0.0
            }
        
        status_counts = {}
        for delivery in all_deliveries:
            status = delivery.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        total = len(all_deliveries)
        successful = status_counts.get(WebhookStatus.SENT.value, 0)
        
        return {
            "total_deliveries": total,
            "successful_deliveries": successful,
            "failed_deliveries": status_counts.get(WebhookStatus.FAILED.value, 0),
            "pending_deliveries": status_counts.get(WebhookStatus.PENDING.value, 0),
            "retrying_deliveries": status_counts.get(WebhookStatus.RETRYING.value, 0),
            "abandoned_deliveries": status_counts.get(WebhookStatus.ABANDONED.value, 0),
            "success_rate": (successful / total * 100) if total > 0 else 0.0,
            "status_breakdown": status_counts
        }
    
    def cleanup_old_deliveries(self, days: int = 7):
        """Clean up old delivery records."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        for job_id in list(self.deliveries.keys()):
            # Keep only recent deliveries
            recent_deliveries = [
                d for d in self.deliveries[job_id]
                if d.created_at > cutoff_date
            ]
            
            if recent_deliveries:
                self.deliveries[job_id] = recent_deliveries
            else:
                del self.deliveries[job_id]


# Global webhook service instance
webhook_service = WebhookService()