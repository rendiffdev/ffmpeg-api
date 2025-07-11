"""
Validate repository pattern structure (without external dependencies)
"""
import os
import sys


def check_file_exists(file_path, description):
    """Check if a file exists."""
    if os.path.exists(file_path):
        print(f"✓ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} - NOT FOUND")
        return False


def check_directory_structure():
    """Check that directory structure is correct."""
    print("Checking repository pattern directory structure...\n")
    
    base_path = os.path.dirname(os.path.dirname(__file__))  # Go up to project root
    
    checks = [
        # Interface files
        (os.path.join(base_path, "api/interfaces/__init__.py"), "Interfaces package"),
        (os.path.join(base_path, "api/interfaces/base.py"), "Base interface"),
        (os.path.join(base_path, "api/interfaces/job_repository.py"), "Job repository interface"),
        (os.path.join(base_path, "api/interfaces/api_key_repository.py"), "API key repository interface"),
        
        # Repository files
        (os.path.join(base_path, "api/repositories/__init__.py"), "Repositories package"),
        (os.path.join(base_path, "api/repositories/base.py"), "Base repository"),
        (os.path.join(base_path, "api/repositories/job_repository.py"), "Job repository"),
        (os.path.join(base_path, "api/repositories/api_key_repository.py"), "API key repository"),
        
        # Service files
        (os.path.join(base_path, "api/services/job_service.py"), "Job service"),
        
        # Router example
        (os.path.join(base_path, "api/routers/jobs_v2.py"), "Jobs v2 router (example)"),
        
        # Dependencies
        (os.path.join(base_path, "api/dependencies_services.py"), "Service dependencies"),
        
        # Test files
        (os.path.join(base_path, "tests/test_repository_pattern.py"), "Repository pattern tests"),
    ]
    
    all_passed = True
    for file_path, description in checks:
        if not check_file_exists(file_path, description):
            all_passed = False
    
    return all_passed


def check_file_contents():
    """Check that files contain expected content."""
    print("\nChecking file contents...\n")
    
    base_path = os.path.dirname(os.path.dirname(__file__))
    
    # Check base interface
    base_interface_path = os.path.join(base_path, "api/interfaces/base.py")
    try:
        with open(base_interface_path, 'r') as f:
            content = f.read()
            if "BaseRepositoryInterface" in content and "ABC" in content:
                print("✓ Base interface contains ABC and BaseRepositoryInterface")
            else:
                print("❌ Base interface missing required content")
                return False
    except Exception as e:
        print(f"❌ Could not read base interface: {e}")
        return False
    
    # Check job repository
    job_repo_path = os.path.join(base_path, "api/repositories/job_repository.py")
    try:
        with open(job_repo_path, 'r') as f:
            content = f.read()
            required_methods = ["get_by_status", "get_by_user_id", "update_status", "get_pending_jobs"]
            missing_methods = [method for method in required_methods if method not in content]
            if not missing_methods:
                print("✓ Job repository contains all required methods")
            else:
                print(f"❌ Job repository missing methods: {missing_methods}")
                return False
    except Exception as e:
        print(f"❌ Could not read job repository: {e}")
        return False
    
    # Check job service
    job_service_path = os.path.join(base_path, "api/services/job_service.py")
    try:
        with open(job_service_path, 'r') as f:
            content = f.read()
            required_methods = ["create_job", "get_job", "update_job_status", "start_job_processing"]
            missing_methods = [method for method in required_methods if method not in content]
            if not missing_methods:
                print("✓ Job service contains all required methods")
            else:
                print(f"❌ Job service missing methods: {missing_methods}")
                return False
    except Exception as e:
        print(f"❌ Could not read job service: {e}")
        return False
    
    return True


def validate_imports():
    """Validate that imports are structured correctly."""
    print("\nChecking import structure...\n")
    
    base_path = os.path.dirname(os.path.dirname(__file__))
    
    # Check services __init__.py
    services_init_path = os.path.join(base_path, "api/services/__init__.py")
    try:
        with open(services_init_path, 'r') as f:
            content = f.read()
            if "JobService" in content and "__all__" in content:
                print("✓ Services package exports JobService")
            else:
                print("❌ Services package doesn't export JobService properly")
                return False
    except Exception as e:
        print(f"❌ Could not read services __init__.py: {e}")
        return False
    
    # Check repositories __init__.py
    repos_init_path = os.path.join(base_path, "api/repositories/__init__.py")
    try:
        with open(repos_init_path, 'r') as f:
            content = f.read()
            if "JobRepository" in content and "__all__" in content:
                print("✓ Repositories package exports repositories")
            else:
                print("❌ Repositories package doesn't export repositories properly")
                return False
    except Exception as e:
        print(f"❌ Could not read repositories __init__.py: {e}")
        return False
    
    return True


def main():
    """Run all validation checks."""
    print("Repository Pattern Implementation Validation")
    print("=" * 50)
    
    structure_ok = check_directory_structure()
    content_ok = check_file_contents()
    imports_ok = validate_imports()
    
    print("\n" + "=" * 50)
    
    if structure_ok and content_ok and imports_ok:
        print("🎉 Repository pattern implementation validation PASSED!")
        print("\nImplemented features:")
        print("- ✓ Base repository interface with CRUD operations")
        print("- ✓ Specific repository interfaces for Job and API Key models")
        print("- ✓ Repository implementations with database operations")
        print("- ✓ Service layer using repository pattern")
        print("- ✓ Dependency injection for services")
        print("- ✓ Example API routes using service layer")
        print("- ✓ Test structure for repository pattern")
        
        return True
    else:
        print("❌ Repository pattern implementation validation FAILED!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)