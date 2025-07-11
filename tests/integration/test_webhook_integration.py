"""
Tests for webhook integration with BaseWorkerTask
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from worker.base import BaseWorkerTask
from api.models.job import Job, JobStatus


class TestWebhookIntegration:
    """Test webhook integration with worker tasks."""
    
    @pytest.fixture
    def worker_task(self):
        """Create worker task instance."""
        return BaseWorkerTask()
    
    @pytest.fixture
    def mock_job(self):
        """Create mock job with webhook URL."""
        job = MagicMock(spec=Job)
        job.id = "test-job-123"
        job.webhook_url = "https://api.example.com/webhook"
        job.status = JobStatus.QUEUED
        job.started_at = datetime.utcnow()
        return job
    
    @pytest.fixture
    def mock_job_no_webhook(self):
        """Create mock job without webhook URL."""
        job = MagicMock(spec=Job)
        job.id = "test-job-456"
        job.webhook_url = None
        job.status = JobStatus.QUEUED
        return job
    
    @pytest.mark.asyncio
    async def test_send_webhook_with_url(self, worker_task, mock_job):
        """Test sending webhook when job has webhook URL."""
        with patch.object(worker_task, 'get_job', return_value=mock_job):
            with patch('worker.webhooks.webhook_service.send_webhook', return_value=True) as mock_send:
                await worker_task.send_webhook("test-job-123", "completed", {"status": "success"})
        
        # Verify webhook service was called correctly
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[1]['job_id'] == "test-job-123"
        assert call_args[1]['event'] == "completed"
        assert call_args[1]['webhook_url'] == "https://api.example.com/webhook"
        assert call_args[1]['retry'] is True
        
        # Check payload structure
        payload = call_args[1]['payload']
        assert payload['event'] == "completed"
        assert payload['job_id'] == "test-job-123"
        assert payload['status'] == "success"
        assert 'timestamp' in payload
    
    @pytest.mark.asyncio
    async def test_send_webhook_no_url(self, worker_task, mock_job_no_webhook):
        """Test sending webhook when job has no webhook URL."""
        with patch.object(worker_task, 'get_job', return_value=mock_job_no_webhook):
            with patch('worker.webhooks.webhook_service.send_webhook') as mock_send:
                await worker_task.send_webhook("test-job-456", "completed", {"status": "success"})
        
        # Webhook service should not be called
        mock_send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_webhook_service_failure(self, worker_task, mock_job):
        """Test webhook sending when service fails."""
        with patch.object(worker_task, 'get_job', return_value=mock_job):
            with patch('worker.webhooks.webhook_service.send_webhook', side_effect=Exception("Service error")):
                # Should not raise exception, just log error
                await worker_task.send_webhook("test-job-123", "completed", {"status": "success"})
    
    @pytest.mark.asyncio
    async def test_send_webhook_job_not_found(self, worker_task):
        """Test webhook sending when job not found."""
        with patch.object(worker_task, 'get_job', side_effect=Exception("Job not found")):
            # Should not raise exception, just log error
            await worker_task.send_webhook("non-existent-job", "completed", {"status": "success"})
    
    @pytest.mark.asyncio
    async def test_handle_job_error_sends_webhook(self, worker_task, mock_job):
        """Test that handling job error sends error webhook."""
        with patch.object(worker_task, 'get_job', return_value=mock_job):
            with patch.object(worker_task, 'update_job_status') as mock_update:
                with patch.object(worker_task, 'send_webhook') as mock_webhook:
                    error = Exception("Processing failed")
                    await worker_task.handle_job_error("test-job-123", error)
        
        # Verify job status was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][1] == JobStatus.FAILED  # status argument
        assert call_args[1]['error_message'] == "Processing failed"
        
        # Verify error webhook was sent
        mock_webhook.assert_called_once()
        webhook_args = mock_webhook.call_args
        assert webhook_args[0][1] == "error"  # event
        webhook_data = webhook_args[0][2]  # data
        assert webhook_data['status'] == "failed"
        assert webhook_data['error'] == "Processing failed"
    
    @pytest.mark.asyncio
    async def test_complete_job_processing_sends_webhook(self, worker_task, mock_job):
        """Test that completing job sends completion webhook."""
        result = {
            "vmaf_score": 95.5,
            "psnr_score": 42.3,
            "metrics": {"quality": "high"}
        }
        
        with patch.object(worker_task, 'get_job', return_value=mock_job):
            with patch.object(worker_task, 'update_job_status') as mock_update:
                with patch.object(worker_task, 'send_webhook') as mock_webhook:
                    await worker_task.complete_job_processing("test-job-123", result)
        
        # Verify job status was updated
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][1] == JobStatus.COMPLETED  # status argument
        
        # Verify completion webhook was sent
        mock_webhook.assert_called_once()
        webhook_args = mock_webhook.call_args
        assert webhook_args[0][1] == "complete"  # event
        webhook_data = webhook_args[0][2]  # data
        assert webhook_data['status'] == "completed"
        assert webhook_data['metrics'] == {"quality": "high"}
    
    @pytest.mark.asyncio
    async def test_get_webhook_delivery_status(self, worker_task):
        """Test getting webhook delivery status."""
        mock_status = [
            {
                "event": "completed",
                "attempt": 1,
                "status": "sent",
                "created_at": "2025-07-10T10:00:00",
                "response_status": 200
            }
        ]
        
        with patch('worker.webhooks.webhook_service.get_delivery_status', return_value=mock_status):
            status = await worker_task.get_webhook_delivery_status("test-job-123")
        
        assert status == mock_status
    
    @pytest.mark.asyncio
    async def test_get_webhook_delivery_status_error(self, worker_task):
        """Test getting webhook delivery status when service fails."""
        with patch('worker.webhooks.webhook_service.get_delivery_status', side_effect=Exception("Service error")):
            status = await worker_task.get_webhook_delivery_status("test-job-123")
        
        # Should return empty list on error
        assert status == []
    
    @pytest.mark.asyncio
    async def test_cleanup_webhook_resources(self, worker_task):
        """Test webhook resource cleanup."""
        with patch('worker.webhooks.webhook_service.cleanup') as mock_cleanup:
            await worker_task.cleanup_webhook_resources()
        
        mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_webhook_resources_error(self, worker_task):
        """Test webhook resource cleanup when service fails."""
        with patch('worker.webhooks.webhook_service.cleanup', side_effect=Exception("Cleanup error")):
            # Should not raise exception, just log error
            await worker_task.cleanup_webhook_resources()
    
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_includes_webhook_cleanup(self, worker_task):
        """Test that task execution includes webhook cleanup."""
        async def mock_processing_func(job):
            return {"result": "success"}
        
        mock_job = MagicMock(spec=Job)
        mock_job.id = "test-job-123"
        
        with patch.object(worker_task, 'start_job_processing', return_value=mock_job):
            with patch.object(worker_task, 'complete_job_processing'):
                with patch.object(worker_task, 'cleanup_webhook_resources') as mock_cleanup:
                    result = await worker_task.execute_with_error_handling(
                        "test-job-123", mock_processing_func
                    )
        
        # Verify cleanup was called
        mock_cleanup.assert_called_once()
        assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_execute_with_error_handling_cleanup_on_error(self, worker_task):
        """Test that webhook cleanup happens even when processing fails."""
        async def mock_processing_func(job):
            raise Exception("Processing error")
        
        mock_job = MagicMock(spec=Job)
        mock_job.id = "test-job-123"
        
        with patch.object(worker_task, 'start_job_processing', return_value=mock_job):
            with patch.object(worker_task, 'handle_job_error'):
                with patch.object(worker_task, 'cleanup_webhook_resources') as mock_cleanup:
                    with pytest.raises(Exception, match="Processing error"):
                        await worker_task.execute_with_error_handling(
                            "test-job-123", mock_processing_func
                        )
        
        # Cleanup should still be called even on error
        mock_cleanup.assert_called_once()


class TestWebhookServiceConfiguration:
    """Test webhook service configuration and settings."""
    
    @pytest.mark.asyncio
    async def test_webhook_service_with_custom_settings(self):
        """Test webhook service with custom configuration."""
        from worker.webhooks import WebhookService
        
        with patch('worker.webhooks.settings') as mock_settings:
            mock_settings.WEBHOOK_MAX_RETRIES = 3
            mock_settings.WEBHOOK_TIMEOUT_SECONDS = 15
            mock_settings.VERSION = "2.0.0"
            
            service = WebhookService()
            
            assert service.max_retries == 3
            assert service.timeout_seconds == 15
            assert "2.0.0" in service.user_agent
    
    @pytest.mark.asyncio
    async def test_webhook_service_with_secret(self):
        """Test webhook service signature generation with secret."""
        from worker.webhooks import WebhookService, WebhookDelivery
        
        with patch('worker.webhooks.settings') as mock_settings:
            mock_settings.WEBHOOK_SECRET = "test-secret-key"
            
            service = WebhookService()
            delivery = WebhookDelivery(
                "test-job", "completed", "https://example.com/hook", 
                {"status": "completed"}
            )
            
            with patch('worker.webhooks.HTTP_CLIENT', 'httpx'):
                with patch('httpx.AsyncClient') as mock_client_class:
                    mock_client = AsyncMock()
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.text = "OK"
                    mock_client.post.return_value = mock_response
                    mock_client_class.return_value = mock_client
                    
                    service._http_client = mock_client
                    
                    await service._send_http_request(delivery)
                    
                    # Verify signature was included in headers
                    call_args = mock_client.post.call_args
                    headers = call_args[1]['headers']
                    assert 'X-Webhook-Signature' in headers
                    assert headers['X-Webhook-Signature'].startswith('sha256=')


class TestWebhookErrorScenarios:
    """Test various webhook error scenarios."""
    
    @pytest.mark.asyncio
    async def test_webhook_timeout_scenario(self):
        """Test webhook timeout handling."""
        from worker.webhooks import WebhookService, WebhookDelivery
        
        service = WebhookService()
        delivery = WebhookDelivery(
            "timeout-job", "completed", "https://slow.example.com/hook",
            {"status": "completed"}
        )
        
        with patch.object(service, '_send_http_request', return_value=(None, None, "Request timeout")):
            success = await service._attempt_delivery(delivery)
        
        assert success is False
        assert delivery.response_status is None
        assert delivery.error_message == "Request timeout"
    
    @pytest.mark.asyncio
    async def test_webhook_network_error_scenario(self):
        """Test webhook network error handling."""
        from worker.webhooks import WebhookService, WebhookDelivery
        
        service = WebhookService()
        delivery = WebhookDelivery(
            "network-job", "completed", "https://unreachable.example.com/hook",
            {"status": "completed"}
        )
        
        with patch.object(service, '_send_http_request', return_value=(None, None, "Connection refused")):
            success = await service._attempt_delivery(delivery)
        
        assert success is False
        assert delivery.response_status is None
        assert delivery.error_message == "Connection refused"
    
    @pytest.mark.asyncio
    async def test_webhook_rate_limit_retry(self):
        """Test webhook rate limit handling with retry."""
        from worker.webhooks import WebhookService, WebhookDelivery
        
        service = WebhookService()
        delivery = WebhookDelivery(
            "rate-limit-job", "completed", "https://api.example.com/hook",
            {"status": "completed"}
        )
        delivery.response_status = 429  # Rate limited
        delivery.attempt = 1
        
        # Should retry on rate limit
        assert service._should_retry(429, 1) is True
        
        with patch.object(service, '_delayed_retry') as mock_retry:
            await service._schedule_retry(delivery)
        
        assert delivery.status.value == "retrying"
        mock_retry.assert_called_once()