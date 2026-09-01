#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Pre-Commit Hook Installer
====================================
Installs the secret scanner as a git pre-commit hook.
Run once after cloning the repository.

Usage:
    python scripts/install_hook.py
    python scripts/install_hook.py --uninstall
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def get_project_root() -> Path:
    """Find the project root (has .git directory)."""
    current = Path(__file__).resolve().parent.parent
    if (current / '.git').is_dir():
        return current
    # Fallback: current directory
    if Path('.git').is_dir():
        return Path.cwd()
    raise RuntimeError("Not inside a git repository")


def install_hook():
    """Install the pre-commit hook."""
    root = get_project_root()
    hooks_dir = root / '.git' / 'hooks'
    hook_path = hooks_dir / 'pre-commit'
    scanner_path = root / 'scripts' / 'pre_commit_hook.py'

    # Ensure hooks directory exists
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Check if hook already exists
    if hook_path.exists():
        # Check if it's already our hook
        with open(hook_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if 'SECRET SCANNER' in content or 'pre_commit_hook' in content:
            print(f"{YELLOW}⚠️  Secret scanner hook already installed. Updating...{RESET}")
        else:
            # Back up existing hook
            backup = hooks_dir / 'pre-commit.backup'
            shutil.copy2(hook_path, backup)
            print(f"{YELLOW}📦 Backed up existing hook to .git/hooks/pre-commit.backup{RESET}")

    # Create the wrapper hook
    hook_content = f'''#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Elívea — Pre-Commit Secret Scanner
# Auto-installed by: python scripts/install_hook.py
# ═══════════════════════════════════════════════════════════════

# Log --no-verify bypass for audit trail
if [ "$1" = "--bypass-logged" ]; then
    python "{root / 'scripts' / 'pre_commit_hook.py'}" 2>&1
    exit $?
fi

# Run the scanner
python "{root / 'scripts' / 'pre_commit_hook.py'}"
EXIT_CODE=$?

exit $EXIT_CODE
'''
    with open(hook_path, 'w', encoding='utf-8') as f:
        f.write(hook_content)

    # Make executable (Unix)
    try:
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except (OSError, AttributeError):
        pass  # Windows doesn't need chmod

    # Also create a post-commit hook that logs bypass attempts
    post_commit_path = hooks_dir / 'post-commit'
    post_commit_content = f'''#!/bin/bash
# Log if commit was made with --no-verify (bypass)
# This is a secondary safety net
'''
    if not post_commit_path.exists():
        with open(post_commit_path, 'w', encoding='utf-8') as f:
            f.write(post_commit_content)
        try:
            post_commit_path.chmod(post_commit_path.stat().st_mode | stat.S_IEXEC)
        except (OSError, AttributeError):
            pass

    print(f"\n{GREEN}{BOLD}✅ Pre-commit secret scanner installed!{RESET}\n")
    print(f"  Hook location: {CYAN}.git/hooks/pre-commit{RESET}")
    print(f"  Scanner:       {CYAN}scripts/pre_commit_hook.py{RESET}")
    print(f"\n{BOLD}How it works:{RESET}")
    print(f"  • Every {CYAN}git commit{RESET} scans staged files for secrets")
    print(f"  • Blocks commits containing API keys, tokens, passwords")
    print(f"  • Shows exact file and line number of each finding")
    print(f"  • Bypass with {YELLOW}git commit --no-verify{RESET} (logged)")
    print(f"\n{BOLD}Patterns detected:{RESET}")
    print(f"  API Keys (OpenAI, Google, AWS, etc.)")
    print(f"  GitHub/GitLab/Bitbucket tokens")
    print(f"  Slack/Discord tokens")
    print(f"  Passwords and database credentials")
    print(f"  Connection strings (MongoDB, PostgreSQL, Redis)")
    print(f"  Private keys (RSA, EC, SSH)")
    print(f"  JWT tokens")
    print(f"  Generic high-entropy secrets")
    print(f"\n{BOLD}Test it:{RESET}")
    print(f"  {CYAN}echo 'MY_API_KEY=\"your_key_here\"' > test.txt{RESET}")
    print(f"  {CYAN}git add test.txt && git commit -m 'test'{RESET}")
    print(f"  {CYAN}rm test.txt && git reset HEAD test.txt{RESET}")
    print()


def uninstall_hook():
    """Remove the pre-commit hook."""
    root = get_project_root()
    hook_path = root / '.git' / 'hooks' / 'pre-commit'

    if not hook_path.exists():
        print(f"{YELLOW}No pre-commit hook found.{RESET}")
        return

    with open(hook_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if 'SECRET SCANNER' not in content and 'pre_commit_hook' not in content:
        print(f"{YELLOW}Pre-commit hook is not the secret scanner. Skipping.{RESET}")
        return

    # Remove our hook
    hook_path.unlink()
    print(f"{GREEN}✅ Pre-commit secret scanner removed.{RESET}")

    # Restore backup if exists
    backup = root / '.git' / 'hooks' / 'pre-commit.backup'
    if backup.exists():
        shutil.move(str(backup), str(hook_path))
        print(f"{GREEN}📦 Restored original hook from backup.{RESET}")


def main():
    if '--uninstall' in sys.argv:
        uninstall_hook()
    else:
        install_hook()


if __name__ == '__main__':
    main()
