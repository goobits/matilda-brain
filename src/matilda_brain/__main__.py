#!/usr/bin/env python3
"""Make the ttt module executable with python -m ttt."""

import sys

from .cli import main

if __name__ == "__main__":
    # Check if we need to add 'ask' for direct prompt usage
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # If first arg is not a flag and not a known subcommand, treat as direct prompt
        if not first_arg.startswith("-") and first_arg not in [
            "chat",
            "status",
            "models",
            "config",
            "ask",
            "info",
            "export",
            "list",
            "tools",
            "upgrade",
        ]:
            # Insert 'ask' command to make it work as direct prompt
            sys.argv.insert(1, "ask")

    # Run the main CLI
    main()
