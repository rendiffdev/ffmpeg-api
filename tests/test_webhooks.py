"""
Tests for webhook service functionality
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from worker.webhooks import WebhookService, WebhookDelivery, WebhookStatus


class TestWebhookService:
    """Test webhook service functionality."""
    
    @pytest.fixture
    def webhook_service(self):
        """Create webhook service instance."""
        return WebhookService()
    
    @pytest.fixture
    def sample_delivery(self):
        """Create sample webhook delivery."""
        return WebhookDelivery(
            job_id="test-job-123",
            event="completed",
            webhook_url="https://api.example.com/webhook",
            payload={"status": "completed", "job_id": "test-job-123"}
        )
    
    def test_webhook_service_initialization(self, webhook_service):
        """Test webhook service initialization."""
        assert webhook_service.max_retries == 5
        assert webhook_service.timeout_seconds == 30
        assert len(webhook_service.retry_delays) == 5
        assert webhook_service.retry_delays == [60, 300, 900, 3600, 7200]
        assert webhook_service.deliveries == {}
    
    def test_webhook_delivery_initialization(self, sample_delivery):
        """Test webhook delivery initialization."""
        assert sample_delivery.job_id == "test-job-123"
        assert sample_delivery.event == "completed"
        assert sample_delivery.webhook_url == "https://api.example.com/webhook"
        assert sample_delivery.attempt == 1
        assert sample_delivery.status == WebhookStatus.PENDING
        assert isinstance(sample_delivery.created_at, datetime)
    
    def test_validate_webhook_url_valid(self, webhook_service):
        """Test webhook URL validation with valid URLs."""
        valid_urls = [
            "https://api.example.com/webhook",
            "http://localhost:8000/webhook",
            "https://webhook.site/12345",
            "http://192.168.1.100:3000/hook",
        ]
        
        for url in valid_urls:
            assert webhook_service.validate_webhook_url(url) is True
    
    def test_validate_webhook_url_invalid(self, webhook_service):
        """Test webhook URL validation with invalid URLs."""
        invalid_urls = [
            "ftp://example.com/webhook",
            "not-a-url",
            "",
            "http://",
            "https://",
            "javascript:alert('xss')",
        ]
        
        for url in invalid_urls:
            assert webhook_service.validate_webhook_url(url) is False
    
    @patch('worker.webhooks.settings')
    def test_validate_webhook_url_production_security(self, mock_settings, webhook_service):
        """Test webhook URL validation blocks internal URLs in production."""
        mock_settings.ENVIRONMENT = 'production'
        
        blocked_urls = [
            "http://localhost:8000/webhook",
            "http://127.0.0.1:3000/hook",
            "http://10.0.0.1/webhook",
            "http://192.168.1.100/hook",
            "http://172.16.0.1/webhook",
        ]
        
        for url in blocked_urls:
            assert webhook_service.validate_webhook_url(url) is False
    
    def test_calculate_retry_delay(self, webhook_service):
        """Test retry delay calculation."""
        # Test predefined delays
        assert webhook_service._calculate_retry_delay(1) == 60
        assert webhook_service._calculate_retry_delay(2) == 300
        assert webhook_service._calculate_retry_delay(3) == 900
        assert webhook_service._calculate_retry_delay(4) == 3600
        assert webhook_service._calculate_retry_delay(5) == 7200
        
        # Test exponential backoff beyond predefined delays
        delay_6 = webhook_service._calculate_retry_delay(6)
        assert delay_6 > 7200
        assert delay_6 <= 86400  # Max 24 hours
    
    def test_should_retry_logic(self, webhook_service):
        """Test retry decision logic."""
        # Should retry on server errors
        assert webhook_service._should_retry(500, 1) is True
        assert webhook_service._should_retry(502, 2) is True
        assert webhook_service._should_retry(503, 3) is True
        assert webhook_service._should_retry(429, 1) is True  # Rate limiting
        
        # Should not retry on client errors (except 429)
        assert webhook_service._should_retry(400, 1) is False
        assert webhook_service._should_retry(401, 1) is False
        assert webhook_service._should_retry(404, 1) is False
        
        # Should retry on network errors (None status)
        assert webhook_service._should_retry(None, 1) is True
        
        # Should not retry after max attempts
        assert webhook_service._should_retry(500, 5) is False
        assert webhook_service._should_retry(None, 6) is False
    
    @pytest.mark.asyncio
    @patch('worker.webhooks.HTTP_CLIENT', 'httpx')
    @patch('httpx.AsyncClient')
    async def test_send_http_request_httpx_success(self, mock_client_class, webhook_service, sample_delivery):
        """Test successful HTTP request with httpx."""
        # Mock httpx client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        webhook_service._http_client = mock_client
        
        status, body, error = await webhook_service._send_http_request(sample_delivery)
        
        assert status == 200
        assert body == "OK"
        assert error is None
        
        # Verify client was called correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[1]['json'] == sample_delivery.payload
        assert 'X-Webhook-Event' in call_args[1]['headers']
        assert 'X-Job-ID' in call_args[1]['headers']
    
    @pytest.mark.asyncio
    @patch('worker.webhooks.settings')
    @patch('worker.webhooks.HTTP_CLIENT', 'httpx')
    @patch('httpx.AsyncClient')
    async def test_send_http_request_with_signature(self, mock_client_class, mock_settings, webhook_service, sample_delivery):
        """Test HTTP request with webhook signature."""
        mock_settings.WEBHOOK_SECRET = "test-secret"
        
        # Mock httpx client
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        webhook_service._http_client = mock_client
        
        status, body, error = await webhook_service._send_http_request(sample_delivery)
        
        assert status == 200
        
        # Verify signature was added
        call_args = mock_client.post.call_args
        headers = call_args[1]['headers']
        assert 'X-Webhook-Signature' in headers
        assert headers['X-Webhook-Signature'].startswith('sha256=')
    
    @pytest.mark.asyncio
    @patch('worker.webhooks.HTTP_CLIENT', 'httpx')
    @patch('httpx.AsyncClient')
    async def test_send_http_request_timeout(self, mock_client_class, webhook_service, sample_delivery):
        """Test HTTP request timeout handling."""
        # Mock httpx client to raise timeout
        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError()
        mock_client_class.return_value = mock_client
        
        webhook_service._http_client = mock_client
        
        status, body, error = await webhook_service._send_http_request(sample_delivery)
        
        assert status is None
        assert body is None
        assert error == "Request timeout"
    
    @pytest.mark.asyncio
    async def test_attempt_delivery_success(self, webhook_service, sample_delivery):
        """Test successful webhook delivery attempt."""
        with patch.object(webhook_service, '_send_http_request', return_value=(200, "OK", None)):
            success = await webhook_service._attempt_delivery(sample_delivery)
        
        assert success is True
        assert sample_delivery.status == WebhookStatus.SENT
        assert sample_delivery.response_status == 200
        assert sample_delivery.response_body == "OK"
        assert sample_delivery.last_attempt_at is not None
    
    @pytest.mark.asyncio
    async def test_attempt_delivery_failure(self, webhook_service, sample_delivery):
        """Test failed webhook delivery attempt."""
        with patch.object(webhook_service, '_send_http_request', return_value=(500, "Server Error", None)):
            success = await webhook_service._attempt_delivery(sample_delivery)
        
        assert success is False
        assert sample_delivery.status == WebhookStatus.FAILED
        assert sample_delivery.response_status == 500
        assert sample_delivery.response_body == "Server Error"
        assert sample_delivery.last_attempt_at is not None
    
    @pytest.mark.asyncio
    async def test_send_webhook_invalid_url(self, webhook_service):
        """Test sending webhook with invalid URL."""
        success = await webhook_service.send_webhook(
            job_id="test-job",
            event="test",
            webhook_url="invalid-url",
            payload={"test": "data"},
            retry=False
        )
        
        assert success is False
        assert "test-job" not in webhook_service.deliveries
    
    @pytest.mark.asyncio
    async def test_send_webhook_success_no_retry(self, webhook_service):
        """Test successful webhook without retry."""
        with patch.object(webhook_service, '_attempt_delivery', return_value=True):
            success = await webhook_service.send_webhook(
                job_id="test-job",
                event="test",
                webhook_url="https://api.example.com/webhook",
                payload={"test": "data"},
                retry=False
            )
        
        assert success is True
        assert "test-job" in webhook_service.deliveries
        assert len(webhook_service.deliveries["test-job"]) == 1
    
    @pytest.mark.asyncio
    async def test_send_webhook_failure_with_retry(self, webhook_service):
        """Test failed webhook with retry scheduling."""
        with patch.object(webhook_service, '_attempt_delivery', return_value=False):
            with patch.object(webhook_service, '_schedule_retry') as mock_schedule:
                success = await webhook_service.send_webhook(
                    job_id="test-job",
                    event="test",
                    webhook_url="https://api.example.com/webhook",
                    payload={"test": "data"},
                    retry=True
                )
        
        assert success is False
        mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_schedule_retry_max_attempts(self, webhook_service, sample_delivery):
        """Test retry scheduling with max attempts reached."""
        sample_delivery.attempt = 5  # Max retries
        sample_delivery.response_status = 500
        
        await webhook_service._schedule_retry(sample_delivery)
        
        assert sample_delivery.status == WebhookStatus.ABANDONED
        assert sample_delivery.next_retry_at is None
    
    @pytest.mark.asyncio
    async def test_schedule_retry_valid(self, webhook_service, sample_delivery):
        """Test valid retry scheduling."""
        sample_delivery.attempt = 1
        sample_delivery.response_status = 500
        
        with patch.object(webhook_service, '_delayed_retry') as mock_delayed:
            await webhook_service._schedule_retry(sample_delivery)
        
        assert sample_delivery.status == WebhookStatus.RETRYING
        assert sample_delivery.next_retry_at is not None
        mock_delayed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_retry_execution(self, webhook_service, sample_delivery):
        """Test delayed retry execution."""
        webhook_service.deliveries["test-job-123"] = [sample_delivery]
        
        with patch.object(webhook_service, '_attempt_delivery', return_value=True):
            with patch('asyncio.sleep'):  # Skip actual delay
                await webhook_service._delayed_retry(sample_delivery, 60)
        
        # Should have created a new delivery attempt
        assert len(webhook_service.deliveries["test-job-123"]) == 2
        retry_delivery = webhook_service.deliveries["test-job-123"][1]
        assert retry_delivery.attempt == 2
    
    def test_get_delivery_status_empty(self, webhook_service):
        """Test getting delivery status for non-existent job."""
        status = webhook_service.get_delivery_status("non-existent-job")
        assert status == []
    
    def test_get_delivery_status_with_deliveries(self, webhook_service, sample_delivery):
        """Test getting delivery status with existing deliveries."""
        webhook_service.deliveries["test-job-123"] = [sample_delivery]
        
        status = webhook_service.get_delivery_status("test-job-123")
        
        assert len(status) == 1
        assert status[0]["event"] == "completed"
        assert status[0]["attempt"] == 1
        assert status[0]["status"] == "pending"
        assert "created_at" in status[0]
    
    def test_get_statistics_empty(self, webhook_service):
        """Test statistics with no deliveries."""
        stats = webhook_service.get_statistics()
        
        assert stats["total_deliveries"] == 0
        assert stats["successful_deliveries"] == 0
        assert stats["failed_deliveries"] == 0
        assert stats["success_rate"] == 0.0
    
    def test_get_statistics_with_deliveries(self, webhook_service):
        """Test statistics with mixed delivery results."""
        # Create some test deliveries
        delivery1 = WebhookDelivery("job1", "event1", "url1", {})
        delivery1.status = WebhookStatus.SENT
        
        delivery2 = WebhookDelivery("job2", "event2", "url2", {})
        delivery2.status = WebhookStatus.FAILED
        
        delivery3 = WebhookDelivery("job3", "event3", "url3", {})
        delivery3.status = WebhookStatus.SENT
        
        webhook_service.deliveries = {
            "job1": [delivery1],
            "job2": [delivery2],
            "job3": [delivery3]
        }
        
        stats = webhook_service.get_statistics()
        
        assert stats["total_deliveries"] == 3
        assert stats["successful_deliveries"] == 2
        assert stats["failed_deliveries"] == 1
        assert abs(stats["success_rate"] - 66.67) < 0.1
    
    def test_cleanup_old_deliveries(self, webhook_service):
        """Test cleanup of old delivery records."""
        # Create old and recent deliveries
        old_delivery = WebhookDelivery("old-job", "event", "url", {})
        old_delivery.created_at = datetime.utcnow() - timedelta(days=10)
        
        recent_delivery = WebhookDelivery("recent-job", "event", "url", {})
        recent_delivery.created_at = datetime.utcnow() - timedelta(hours=1)
        
        webhook_service.deliveries = {
            "old-job": [old_delivery],
            "recent-job": [recent_delivery]
        }
        
        webhook_service.cleanup_old_deliveries(days=7)
        
        # Old delivery should be removed, recent should remain
        assert "old-job" not in webhook_service.deliveries
        assert "recent-job" in webhook_service.deliveries
    
    @pytest.mark.asyncio
    async def test_cleanup_http_client(self, webhook_service):
        """Test HTTP client cleanup."""
        # Mock HTTP client
        mock_client = AsyncMock()
        webhook_service._http_client = mock_client
        
        with patch('worker.webhooks.HTTP_CLIENT', 'httpx'):
            await webhook_service.cleanup()
        
        mock_client.aclose.assert_called_once()
        assert webhook_service._http_client is None


class TestWebhookIntegration:
    """Integration tests for webhook functionality."""
    
    @pytest.mark.asyncio
    async def test_full_webhook_delivery_flow(self):
        """Test complete webhook delivery flow."""
        webhook_service = WebhookService()
        
        # Mock successful HTTP response
        with patch.object(webhook_service, '_send_http_request', return_value=(200, "OK", None)):
            success = await webhook_service.send_webhook(
                job_id="integration-test",
                event="completed",
                webhook_url="https://api.example.com/webhook",
                payload={"status": "completed", "result": "success"}
            )
        
        assert success is True
        
        # Check delivery status
        status = webhook_service.get_delivery_status("integration-test")
        assert len(status) == 1
        assert status[0]["status"] == "sent"
        
        # Check statistics
        stats = webhook_service.get_statistics()
        assert stats["total_deliveries"] == 1
        assert stats["successful_deliveries"] == 1
        assert stats["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_webhook_retry_flow(self):
        """Test webhook retry flow with eventual success."""
        webhook_service = WebhookService()
        
        # Mock first attempt fails, second succeeds
        responses = [(500, "Server Error", None), (200, "OK", None)]
        
        with patch.object(webhook_service, '_send_http_request', side_effect=responses):
            with patch('asyncio.sleep'):  # Skip actual delays
                # First attempt
                success = await webhook_service.send_webhook(
                    job_id="retry-test",
                    event="completed",
                    webhook_url="https://api.example.com/webhook",
                    payload={"status": "completed"}
                )
                
                # Should fail initially
                assert success is False
                
                # Manually trigger retry
                delivery = webhook_service.deliveries["retry-test"][0]
                retry_delivery = WebhookDelivery(
                    delivery.job_id, delivery.event, delivery.webhook_url, 
                    delivery.payload, attempt=2
                )
                
                success = await webhook_service._attempt_delivery(retry_delivery)
                assert success is True
        
        # Check final statistics
        stats = webhook_service.get_statistics()
        assert stats["total_deliveries"] == 1  # Original delivery count
        assert stats["failed_deliveries"] == 1