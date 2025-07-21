#!/usr/bin/env python3
"""
Validate Dockerfile syntax and ARG/FROM usage.
This script checks for the specific issue in GitHub Issue #10.
"""
import re
import sys
from pathlib import Path


def validate_dockerfile(dockerfile_path):
    """Validate Dockerfile for ARG/FROM issues."""
    print(f"🔍 Validating: {dockerfile_path}")
    
    if not dockerfile_path.exists():
        print(f"❌ File not found: {dockerfile_path}")
        return False
    
    with open(dockerfile_path, 'r') as f:
        lines = f.readlines()
    
    # Track ARG declarations and their positions
    args_declared = {}
    from_statements = []
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        
        # Find ARG declarations
        if line.startswith('ARG '):
            arg_match = re.match(r'ARG\s+(\w+)(?:=.*)?', line)
            if arg_match:
                arg_name = arg_match.group(1)
                args_declared[arg_name] = i
                print(f"✅ Found ARG declaration: {arg_name} at line {i}")
        
        # Find FROM statements with variables
        if line.startswith('FROM '):
            from_statements.append((i, line))
            
            # Check for variable usage in FROM
            var_match = re.search(r'\$\{(\w+)\}', line)
            if var_match:
                var_name = var_match.group(1)
                print(f"📋 FROM statement at line {i} uses variable: {var_name}")
                
                # Check if ARG was declared before this FROM
                if var_name not in args_declared:
                    print(f"❌ ERROR: Variable {var_name} used in FROM at line {i} but never declared")
                    return False
                elif args_declared[var_name] > i:
                    print(f"❌ ERROR: Variable {var_name} declared at line {args_declared[var_name]} but used in FROM at line {i}")
                    print(f"   FIX: Move 'ARG {var_name}' to before line {i}")
                    return False
                else:
                    print(f"✅ Variable {var_name} properly declared before use")
    
    # Check for the specific issue from GitHub Issue #10
    issue_found = False
    for i, from_line in from_statements:
        if 'runtime-${' in from_line:
            print(f"🎯 Found runtime stage selection at line {i}: {from_line}")
            if 'WORKER_TYPE' in from_line:
                if 'WORKER_TYPE' in args_declared:
                    print(f"✅ WORKER_TYPE properly declared at line {args_declared['WORKER_TYPE']}")
                else:
                    print(f"❌ WORKER_TYPE used but not declared!")
                    issue_found = True
    
    if issue_found:
        print(f"❌ GitHub Issue #10 detected in {dockerfile_path}")
        return False
    
    print(f"✅ Dockerfile validation passed: {dockerfile_path}")
    return True


def main():
    """Main validation function."""
    print("🐳 Docker Dockerfile Validator for GitHub Issue #10")
    print("=" * 60)
    
    # Get repository root
    repo_root = Path(__file__).parent.parent
    
    # List of Dockerfiles to validate
    dockerfiles = [
        repo_root / "docker" / "worker" / "Dockerfile",
        repo_root / "docker" / "worker" / "Dockerfile.genai",
        repo_root / "docker" / "api" / "Dockerfile",
        repo_root / "docker" / "api" / "Dockerfile.genai",
        repo_root / "Dockerfile.genai",
    ]
    
    all_valid = True
    
    for dockerfile in dockerfiles:
        try:
            if not validate_dockerfile(dockerfile):
                all_valid = False
        except Exception as e:
            print(f"❌ Error validating {dockerfile}: {e}")
            all_valid = False
        print()
    
    print("=" * 60)
    if all_valid:
        print("🎉 All Dockerfiles passed validation!")
        print("✅ GitHub Issue #10 has been resolved")
    else:
        print("💥 Some Dockerfiles failed validation")
        print("❌ GitHub Issue #10 may still be present")
        sys.exit(1)


if __name__ == "__main__":
    main()