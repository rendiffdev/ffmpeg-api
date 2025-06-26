#!/usr/bin/env python3
"""
Rendiff CLI - Unified command-line interface for Rendiff FFmpeg API

Website: https://rendiff.dev
GitHub: https://github.com/rendiffdev/ffmpeg-api
Contact: dev@rendiff.dev
"""
import sys
import os

def main():
    """Main entry point for Rendiff CLI."""
    # Add the project root to sys.path to enable imports
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    # Import and run the unified CLI
    try:
        from rendiff import cli
        cli()
    except ImportError as e:
        print(f"Error: Could not import CLI module: {e}")
        print("Please ensure you're running from the Rendiff project directory")
        print("Alternative: Use the unified CLI script directly: ./rendiff")
        print("Support: https://rendiff.dev | dev@rendiff.dev")
        sys.exit(1)
    except Exception as e:
        print(f"CLI error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
