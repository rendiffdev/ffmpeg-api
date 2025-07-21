#!/bin/bash

# Interactive wrapper for version controller in git hooks
# This script properly handles terminal input/output for git hooks

# Check if we're in a git hook environment
if [ -t 0 ] && [ -t 1 ]; then
    # We have a proper terminal, run directly
    exec "$(dirname "$0")/versionController.sh"
else
    # We're in a git hook, need to use terminal properly
    exec < /dev/tty > /dev/tty 2>&1
    "$(dirname "$0")/versionController.sh"
fi