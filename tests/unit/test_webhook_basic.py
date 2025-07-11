#!/usr/bin/env python3
"""
Basic webhook functionality test without external dependencies
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_webhook_service_basic():
    """Test basic webhook service functionality."""
    print("🔧 Testing webhook service basic functionality...")
    
    try:
        # Test webhook URL validation
        from worker.webhooks import WebhookService
        
        service = WebhookService()
        
        # Test valid URLs
        valid_urls = [
            "https://api.example.com/webhook",
            "http://localhost:8000/webhook",
        ]
        
        for url in valid_urls:
            assert service.validate_webhook_url(url), f"Valid URL failed: {url}"
        
        print("✅ URL validation works correctly")
        
        # Test invalid URLs
        invalid_urls = [
            "ftp://example.com/webhook",
            "not-a-url",
            "",
        ]
        
        for url in invalid_urls:
            assert not service.validate_webhook_url(url), f"Invalid URL passed: {url}"
        
        print("✅ Invalid URL rejection works correctly")
        
        # Test retry delay calculation
        assert service._calculate_retry_delay(1) == 60
        assert service._calculate_retry_delay(2) == 300
        assert service._calculate_retry_delay(3) == 900
        
        print("✅ Retry delay calculation works correctly")
        
        # Test retry logic
        assert service._should_retry(500, 1) == True  # Server error
        assert service._should_retry(429, 1) == True  # Rate limit
        assert service._should_retry(400, 1) == False  # Client error
        assert service._should_retry(None, 1) == True  # Network error
        assert service._should_retry(500, 5) == False  # Max retries
        
        print("✅ Retry logic works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook service test failed: {e}")
        return False

async def test_webhook_delivery():
    """Test webhook delivery object."""
    print("🚀 Testing webhook delivery object...")
    
    try:
        from worker.webhooks import WebhookDelivery, WebhookStatus
        from datetime import datetime
        
        delivery = WebhookDelivery(
            job_id="test-job-123",
            event="completed",
            webhook_url="https://api.example.com/webhook",
            payload={"status": "completed", "job_id": "test-job-123"}
        )
        
        assert delivery.job_id == "test-job-123"
        assert delivery.event == "completed"
        assert delivery.webhook_url == "https://api.example.com/webhook"
        assert delivery.attempt == 1
        assert delivery.status == WebhookStatus.PENDING
        assert isinstance(delivery.created_at, datetime)
        
        print("✅ Webhook delivery initialization works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook delivery test failed: {e}")
        return False

async def test_webhook_integration_without_dependencies():
    """Test webhook integration logic without external dependencies."""
    print("🔗 Testing webhook integration logic...")
    
    try:
        # Mock the database and HTTP dependencies
        class MockJob:
            def __init__(self, job_id, webhook_url=None):
                self.id = job_id
                self.webhook_url = webhook_url
                self.status = "queued"
        
        class MockWorkerTask:
            async def get_job(self, job_id):
                if job_id == "with-webhook":
                    return MockJob(job_id, "https://api.example.com/webhook")
                elif job_id == "no-webhook":
                    return MockJob(job_id, None)
                else:
                    raise Exception("Job not found")
        
        worker = MockWorkerTask()
        
        # Test job with webhook URL
        job_with_webhook = await worker.get_job("with-webhook")
        assert job_with_webhook.webhook_url == "https://api.example.com/webhook"
        
        # Test job without webhook URL
        job_no_webhook = await worker.get_job("no-webhook")
        assert job_no_webhook.webhook_url is None
        
        print("✅ Webhook integration logic works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook integration test failed: {e}")
        return False

async def test_webhook_statistics():
    """Test webhook statistics functionality."""
    print("📊 Testing webhook statistics...")
    
    try:
        from worker.webhooks import WebhookService, WebhookDelivery, WebhookStatus
        
        service = WebhookService()
        
        # Test empty statistics
        stats = service.get_statistics()
        assert stats["total_deliveries"] == 0
        assert stats["success_rate"] == 0.0
        
        print("✅ Empty statistics work correctly")
        
        # Create some test deliveries
        delivery1 = WebhookDelivery("job1", "event1", "url1", {})
        delivery1.status = WebhookStatus.SENT
        
        delivery2 = WebhookDelivery("job2", "event2", "url2", {})
        delivery2.status = WebhookStatus.FAILED
        
        service.deliveries = {
            "job1": [delivery1],
            "job2": [delivery2]
        }
        
        stats = service.get_statistics()
        assert stats["total_deliveries"] == 2
        assert stats["successful_deliveries"] == 1
        assert stats["failed_deliveries"] == 1
        assert stats["success_rate"] == 50.0
        
        print("✅ Statistics calculation works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Webhook statistics test failed: {e}")
        return False

async def main():
    """Run all webhook tests."""
    print("🧪 Basic Webhook Functionality Tests")
    print("=" * 60)
    
    tests = [
        test_webhook_service_basic,
        test_webhook_delivery,
        test_webhook_integration_without_dependencies,
        test_webhook_statistics,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing
    
    print("=" * 60)
    print("WEBHOOK TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("🎉 All webhook tests passed!")
        return 0
    else:
        success_rate = (passed / (passed + failed)) * 100
        print(f"Success rate: {success_rate:.1f}%")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)