# -*- coding: utf-8 -*-
"""
Silent Run — Drop-in replacement for os.system() that never opens windows.

On Windows, os.system() opens a new cmd.exe/PowerShell window for EVERY call.
This module provides run_silent() which uses subprocess with CREATE_NO_WINDOW.

Usage:
    from core.silent_run import run_silent
    run_silent("start notepad.exe")
    run_silent("shutdown /s /t 30")
"""

import subprocess
import os
import sys


def run_silent(cmd: str, timeout: int = 30) -> int:
    """Execute a shell command silently — no window pops up.
    
    Returns the exit code (0 = success).
    """
    try:
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
            creationflags=creation_flags,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        return 1
    except Exception:
        return 1


def patch_os_system():
    """Monkey-patch os.system AND subprocess to run silently (no windows).
    
    Call this once at app startup:
        from core.silent_run import patch_os_system
        patch_os_system()
    """
    _original_system = os.system
    
    def _silent_system(cmd):
        return run_silent(cmd)
    
    os.system = _silent_system

    # Also patch subprocess.run to always use CREATE_NO_WINDOW
    _original_run = subprocess.run
    _original_popen = subprocess.Popen

    def _silent_run(*args, **kwargs):
        if sys.platform == 'win32':
            kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
        return _original_run(*args, **kwargs)

    # Must be a CLASS (not function) so asyncio can subclass it:
    #   class Popen(subprocess.Popen): ...
    class _SilentPopen(_original_popen):
        """Subclass of Popen that defaults to CREATE_NO_WINDOW on Windows."""
        def __new__(cls, *args, **kwargs):
            if sys.platform == 'win32':
                kwargs.setdefault('creationflags', subprocess.CREATE_NO_WINDOW)
            return _original_popen(*args, **kwargs)

        def __init__(self, *args, **kwargs):
            # __new__ already created the real Popen; nothing to init
            pass

    subprocess.run = _silent_run
    subprocess.Popen = _SilentPopen
