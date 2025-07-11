#!/usr/bin/env python3
"""
Generate secure API keys for the FFmpeg API service.
"""
import secrets
import string
import argparse


def generate_api_key(length: int = 32) -> str:
    """Generate a secure random API key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description='Generate secure API keys')
    parser.add_argument(
        '-n', '--number',
        type=int,
        default=1,
        help='Number of API keys to generate (default: 1)'
    )
    parser.add_argument(
        '-l', '--length',
        type=int,
        default=32,
        help='Length of each API key (default: 32)'
    )
    parser.add_argument(
        '--admin',
        action='store_true',
        help='Generate admin API keys format for .env file'
    )
    
    args = parser.parse_args()
    
    keys = [generate_api_key(args.length) for _ in range(args.number)]
    
    if args.admin:
        print("# Add this to your .env file:")
        print(f"ADMIN_API_KEYS={','.join(keys)}")
    else:
        print("Generated API keys:")
        for i, key in enumerate(keys, 1):
            print(f"{i}. {key}")


if __name__ == '__main__':
    main()