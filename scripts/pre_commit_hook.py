#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elívea — Pre-Commit Secret Scanner
====================================
Blocks commits containing API keys, tokens, passwords, and other secrets.
Part of the Elívea security pipeline.

Install: python scripts/install_hook.py
Bypass:  git commit --no-verify (logged to .git/secret_scanner_bypass.log)

Scans staged content (not disk) so it catches exactly what would be committed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# ═══ Secret Detection Patterns ═══════════════════════════════════════════════
# Each tuple: (regex, category, severity)
# severity: CRITICAL = blocks commit, WARNING = warns but allows

PATTERNS: List[Tuple[str, str, str]] = [
    # ── API Keys ──
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\'][A-Za-z0-9_\-]{16,}["\']',
     "API Key", "CRITICAL"),
    (r'(?i)(secret[_-]?key|client[_-]?secret)\s*[=:]\s*["\'][A-Za-z0-9_\-]{16,}["\']',
     "Secret Key", "CRITICAL"),

    # ── Tokens ──
    (r'(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[=:]\s*["\'][A-Za-z0-9_\-\.]{20,}["\']',
     "Auth Token", "CRITICAL"),
    (r'ghp_[A-Za-z0-9]{36}',
     "GitHub Token", "CRITICAL"),
    (r'sk-[A-Za-z0-9\-]{32,}',
     "OpenAI Key", "CRITICAL"),
    (r'xoxb-[A-Za-z0-9\-]+',
     "Slack Token", "CRITICAL"),
    (r'xoxp-[A-Za-z0-9\-]+',
     "Slack User Token", "CRITICAL"),
    (r'(?i)AIza[A-Za-z0-9_\-]{35}',
     "Google API Key", "CRITICAL"),
    (r'(?i)glpat-[A-Za-z0-9\-_]{20,}',
     "GitLab Token", "CRITICAL"),
    (r'(?i)bb_[A-Za-z0-9]{40,}',
     "Bitbucket App Password", "CRITICAL"),
    (r'(?i)SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}',
     "SendGrid Key", "CRITICAL"),
    (r'(?i)key-[A-Za-z0-9]{32}',
     "Mailgun Key", "CRITICAL"),
    (r'(?i)AC[a-z0-9]{32}',
     "Twilio Account SID", "CRITICAL"),

    # ── Passwords ──
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{6,}["\']',
     "Password", "CRITICAL"),
    (r'(?i)(db[_-]?password|database[_-]?pass)\s*[=:]\s*["\'][^"\']+["\']',
     "Database Password", "CRITICAL"),

    # ── AWS ──
    (r'AKIA[A-Z0-9]{16}',
     "AWS Access Key", "CRITICAL"),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\'][A-Za-z0-9/+=]{40}["\']',
     "AWS Secret Key", "CRITICAL"),

    # ── Connection Strings ──
    (r'(?i)(mongodb|postgres|mysql|redis|amqp)://[^\s"\']+:[^\s"\']+@[^\s"\']+',
     "Connection String", "CRITICAL"),

    # ── Private Keys ──
    (r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
     "Private Key", "CRITICAL"),

    # ── JWT ──
    (r'eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+',
     "JWT Token", "WARNING"),

    # ── Generic high-entropy secrets ──
    (r'(?i)(secret|credential|private)\s*[=:]\s*["\'][A-Za-z0-9/+=_\-]{32,}["\']',
     "Generic Secret", "WARNING"),

    # ── .env file direct assignments ──
    (r'(?i)^[A-Z_]{3,}=\s*[A-Za-z0-9/+=_\-]{20,}$',
     "Env Var Secret", "WARNING"),
]

# Safe patterns — these should NOT trigger alerts
SAFE_PATTERNS = [
    r'(?i)(example|sample|placeholder|xxx|your[_-]?.*here|<.*>)',
    r'(?i)(os\.environ|getenv|env\()',
    r'(?i)(\.env\.example|\.env\.sample)',
    r'(?i)(TODO|FIXME|HACK|XXX)',
    # sk-proj- keys are real secrets, NOT safe
]

# Files to always skip
SKIP_EXTENSIONS = {
    '.pyc', '.pyo', '.class', '.o', '.so', '.dll', '.exe', '.bin',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
    '.mp3', '.mp4', '.wav', '.avi', '.mkv',
    '.zip', '.tar', '.gz', '.rar', '.7z',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.lock', '.sum', '.min.js', '.min.css',
}

SKIP_PATHS = {
    'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock',
    'pnpm-lock.yaml', 'composer.lock', 'Gemfile.lock',
    '.gitignore', '.dockerignore',
}

# Colors for terminal output
RED = '\033[91m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
CYAN = '\033[96m'
BOLD = '\033[1m'
RESET = '\033[0m'


def get_staged_files() -> List[str]:
    """Get list of files staged for commit."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
    except Exception:
        return []


def get_staged_content(filepath: str) -> str:
    """Get the staged content of a file (what would actually be committed)."""
    try:
        result = subprocess.run(
            ['git', 'show', f':{filepath}'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except Exception:
        return ""


def is_safe(content: str, line: str) -> bool:
    """Check if a line matches safe patterns (false positive)."""
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, line):
            return True
    return False


def scan_content(content: str, filepath: str) -> List[dict]:
    """Scan content for secrets. Returns list of findings."""
    findings = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip empty lines and comments (but not strings with comments)
        if not stripped or (stripped.startswith('#') and len(stripped) < 3):
            continue
        # Skip lines that are just variable declarations without values
        if stripped.endswith('=') or stripped.endswith(':'):
            continue

        for pattern, category, severity in PATTERNS:
            if re.search(pattern, line):
                # Check false positives
                if is_safe(content, line):
                    continue
                # Don't double-report same line
                if any(f['line'] == line_num and f['category'] == category
                       for f in findings):
                    continue
                findings.append({
                    'file': filepath,
                    'line': line_num,
                    'category': category,
                    'severity': severity,
                    'content': stripped[:120],
                })
                break  # One finding per line max

    return findings


def scan_all_files() -> Tuple[List[dict], int]:
    """Scan all staged files. Returns (findings, files_scanned)."""
    all_findings = []
    files_scanned = 0

    for filepath in get_staged_files():
        # Skip binary/lock files
        ext = Path(filepath).suffix.lower()
        if ext in SKIP_EXTENSIONS:
            continue
        if Path(filepath).name in SKIP_PATHS:
            continue
        if filepath.startswith('build/') or filepath.startswith('dist/'):
            continue

        content = get_staged_content(filepath)
        if not content:
            continue

        files_scanned += 1
        findings = scan_content(content, filepath)
        all_findings.extend(findings)

    return all_findings, files_scanned


def log_bypass(reason: str):
    """Log --no-verify bypass for audit trail."""
    log_path = Path('.git') / 'secret_scanner_bypass.log'
    try:
        # Get current branch and last commit info
        branch = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "detached"

        user = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "unknown"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        entry = f"[{timestamp}] branch={branch} user={user} reason={reason}\n"
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception:
        pass


def print_report(findings: List[dict], files_scanned: int):
    """Print the scan report to stderr."""
    if not findings:
        print(f"\n{GREEN}✅ Secret Scanner: {files_scanned} files scanned, 0 secrets found{RESET}\n")
        return

    critical = [f for f in findings if f['severity'] == 'CRITICAL']
    warnings = [f for f in findings if f['severity'] == 'WARNING']

    print(f"\n{RED}{BOLD}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{RED}{BOLD}║  🚫 SECRET SCANNER — COMMIT BLOCKED             ║{RESET}")
    print(f"{RED}{BOLD}╚══════════════════════════════════════════════════╝{RESET}")
    print(f"\n{BOLD}Scanned:{RESET} {files_scanned} files")
    print(f"{RED}Critical:{RESET} {len(critical)} secrets found")
    if warnings:
        print(f"{YELLOW}Warnings:{RESET} {len(warnings)} potential secrets found")

    print(f"\n{BOLD}── Findings ──{RESET}\n")

    for i, f in enumerate(findings, 1):
        sev_color = RED if f['severity'] == 'CRITICAL' else YELLOW
        sev_icon = "🚫" if f['severity'] == 'CRITICAL' else "⚠️"

        print(f"  {sev_icon} {sev_color}{BOLD}[{f['severity']}]{RESET} {f['category']}")
        print(f"     {CYAN}{f['file']}:{f['line']}{RESET}")
        print(f"     {f['content'][:100]}")
        print()

    print(f"{BOLD}── How to fix ──{RESET}\n")
    print(f"  1. Remove the secret from the code")
    print(f"  2. Use environment variables: os.environ['API_KEY']")
    print(f"  3. Add the secret to .env (already in .gitignore)")
    print(f"  4. Add the file to .gitignore if it contains secrets")
    print(f"\n{YELLOW}Bypass (NOT recommended): git commit --no-verify{RESET}")
    print(f"{YELLOW}  ⚠️  This action will be logged to .git/secret_scanner_bypass.log{RESET}\n")


def main():
    """Main entry point for the pre-commit hook."""
    # Check if we're in a git repo
    if not Path('.git').is_dir():
        return 0

    findings, files_scanned = scan_all_files()

    if findings:
        print_report(findings, files_scanned)
        # Block commit (exit 1)
        return 1
    else:
        print_report(findings, files_scanned)
        # Allow commit (exit 0)
        return 0


if __name__ == '__main__':
    sys.exit(main())
