#!/usr/bin/env python3
"""
Script to create the first admin API key
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.models.database import init_db, AsyncSessionLocal
from api.models.api_key import ApiKeyCreate
from api.services.api_key import ApiKeyService


async def create_admin_key():
    """Create the first admin API key."""
    print("Creating first admin API key...")
    
    # Initialize database
    await init_db()
    
    # Create API key
    async with AsyncSessionLocal() as db:
        service = ApiKeyService(db)
        
        # Create admin key
        request = ApiKeyCreate(
            name="Initial Admin Key",
            owner_name="System Administrator",
            role="admin",
            max_concurrent_jobs=50,
            monthly_quota_minutes=100000,
        )
        
        try:
            api_key, full_key = await service.create_api_key(
                request=request,
                created_by="system",
            )
            
            print(f"✅ Admin API key created successfully!")
            print(f"🔑 API Key: {full_key}")
            print(f"📋 Key ID: {api_key.id}")
            print(f"🏷️  Prefix: {api_key.prefix}")
            print(f"👑 Role: {api_key.role}")
            print(f"⚡ Max Concurrent Jobs: {api_key.max_concurrent_jobs}")
            print(f"⏰ Monthly Quota: {api_key.monthly_quota_minutes} minutes")
            print()
            print("🚨 IMPORTANT: Save this key securely! It will not be shown again.")
            print("🔒 You can use this key to access admin endpoints and create other API keys.")
            print()
            print("💡 Example usage:")
            print(f"   curl -H 'X-API-Key: {full_key}' https://your-domain/api/v1/admin/api-keys")
            print(f"   curl -H 'Authorization: Bearer {full_key}' https://your-domain/api/v1/admin/api-keys")
            
        except Exception as e:
            print(f"❌ Failed to create admin key: {e}")
            return False
    
    return True


if __name__ == "__main__":
    if asyncio.run(create_admin_key()):
        print("\n✅ Setup complete! You can now use the admin API key to manage other keys.")
        sys.exit(0)
    else:
        print("\n❌ Setup failed!")
        sys.exit(1)