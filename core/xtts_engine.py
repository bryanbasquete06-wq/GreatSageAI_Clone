"""
XTTS v2 Voice Engine — Persistent server with safety guards.

- Single Python 3.11 process, no terminal windows
- Global lock prevents concurrent XTTS calls
- Timeout protection prevents hangs
- Automatic restart on crash
- Mutex file prevents multiple server instances
"""
import os, subprocess, tempfile, threading, json, time, sys, shutil, glob

def _find_python311():
    """Find Python 3.11 executable."""
    # Check common locations
    candidates = [
        shutil.which("python3.11"),
        shutil.which("python3"),
    ]
    # Also search AppData\Local\Python
    local_python = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Python")
    if os.path.isdir(local_python):
        for d in glob.glob(os.path.join(local_python, "pythoncore-3.11-*")):
            exe = os.path.join(d, "python.exe")
            if os.path.isfile(exe):
                candidates.append(exe)
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return "python"  # fallback

PYTHON311 = _find_python311()
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_WAV = os.path.join(BASE_DIR, "config", "gs_01_11_to_02_09.wav")

# Multiple reference segments for voice variety
REF_SEGMENTS = [
    os.path.join(BASE_DIR, "config", "gs_calm_analytical.wav"),
    os.path.join(BASE_DIR, "config", "gs_authoritative.wav"),
    os.path.join(BASE_DIR, "config", "gs_emotional.wav"),
    os.path.join(BASE_DIR, "config", "gs_rapid_speech.wav"),
    os.path.join(BASE_DIR, "config", "gs_warm.wav"),
]

# Filter to only existing files
REF_SEGMENTS = [r for r in REF_SEGMENTS if os.path.exists(r)]
if not REF_SEGMENTS and os.path.exists(REF_WAV):
    REF_SEGMENTS = [REF_WAV]

MUTEX_FILE = os.path.join(tempfile.gettempdir(), "xtts_server_running.txt")

# Global lock — only ONE XTTS call at a time
_xtts_lock = threading.Lock()
_server = None
_server_lock = threading.Lock()

# Cleanup mutex on exit
import atexit
def _cleanup_mutex():
    try:
        if os.path.exists(MUTEX_FILE):
            os.remove(MUTEX_FILE)
    except Exception:
        pass
atexit.register(_cleanup_mutex)

_SERVER_SCRIPT = r'''
import os, sys, json, tempfile
os.environ["COQUI_TOS_AGREED"] = "1"

import torch
_orig_load = torch.load
def _patched_load(*a, **kw):
    kw.setdefault("weights_only", False)
    return _orig_load(*a, **kw)
torch.load = _patched_load

import torchaudio
import soundfile as sf
import numpy as np

def _sf_load(uri, **kwargs):
    data, sr = sf.read(uri, dtype='float32')
    if data.ndim == 1:
        data = data[np.newaxis, :]
    else:
        data = data.T
    return torch.from_numpy(data), sr

torchaudio.load = _sf_load

print("Loading XTTS v2 model...", flush=True)
from TTS.api import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
print("READY", flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
        text = req["text"]
        ref = req["ref"]
        out = req["out"]
        # Character voice parameters for Great Sage
        # Lower temperature = more stable, consistent voice
        # Higher repetition_penalty = less repetition artifacts
        kwargs = {
            "text": text,
            "file_path": out,
            "speaker_wav": ref,
            "language": "pt",
            "temperature": 0.3,        # Low temp for stable, analytical voice
            "repetition_penalty": 10.0, # High to prevent stuttering
            "top_k": 30,               # Narrow sampling for consistency
            "top_p": 0.85,             # Focused nucleus sampling
            "speed": 0.95,             # Slightly slower for measured delivery
        }
        tts.tts_to_file(**kwargs)
        size = os.path.getsize(out) if os.path.exists(out) else 0
        print(json.dumps({"ok": True, "size": size}), flush=True)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), flush=True)
'''


class _XttsServer:
    def __init__(self):
        self._proc = None
        self._ready = False

    def start(self):
        if not os.path.exists(PYTHON311) or not os.path.exists(REF_WAV):
            print("[XTTS] Missing Python 3.11 or reference audio")
            return False

        # Check if another instance is already running
        if os.path.exists(MUTEX_FILE):
            try:
                with open(MUTEX_FILE, 'r') as f:
                    pid = int(f.read().strip())
                # Check if process is still alive
                import psutil
                if psutil.pid_exists(pid):
                    print("[XTTS] Another instance already running")
                    return False
            except Exception:
                pass
            # Stale mutex, remove it
            try:
                os.remove(MUTEX_FILE)
            except Exception:
                pass

        # Write mutex file with our PID
        try:
            with open(MUTEX_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

        script_path = os.path.join(tempfile.gettempdir(), "xtts_server.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(_SERVER_SCRIPT)

        try:
            self._proc = subprocess.Popen(
                [PYTHON311, "-u", script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
                text=True,
                bufsize=1,
            )
            # Wait for model to load (timeout 120s)
            start = time.time()
            for line in self._proc.stdout:
                if "READY" in line:
                    self._ready = True
                    print("[XTTS] Server ready")
                    return True
                if time.time() - start > 120:
                    print("[XTTS] Server startup timeout")
                    break
                if "Error" in line or "Traceback" in line:
                    print(f"[XTTS] Server error: {line.strip()}")
                    break
        except Exception as e:
            print(f"[XTTS] Failed to start: {e}")
        return False

    def synthesize(self, text, ref_wav, output_path):
        if not self._ready or not self._proc:
            return False
        try:
            req = json.dumps({"text": text, "ref": ref_wav, "out": output_path})
            self._proc.stdin.write(req + "\n")
            self._proc.stdin.flush()

            # Read response with timeout
            start = time.time()
            for line in self._proc.stdout:
                if time.time() - start > 90:
                    print("[XTTS] Synth timeout")
                    return False
                resp = json.loads(line.strip())
                return resp.get("ok", False)
        except Exception as e:
            print(f"[XTTS] Synth error: {e}")
            self._ready = False
        return False

    def shutdown(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
            self._ready = False
            # Remove mutex file
            try:
                if os.path.exists(MUTEX_FILE):
                    os.remove(MUTEX_FILE)
            except Exception:
                pass


def _get_server():
    global _server
    with _server_lock:
        if _server is None or not _server._ready:
            if _server:
                _server.shutdown()
            _server = _XttsServer()
            _server.start()
        return _server


def synthesize(text: str, output_path: str) -> bool:
    """Synthesize text using XTTS v2 with Great Sage voice cloning.

    Thread-safe: only one XTTS call at a time.
    Uses random reference segment for natural variety.
    """
    if not os.path.exists(PYTHON311) or not REF_SEGMENTS:
        return False

    # Only one XTTS call at a time
    if not _xtts_lock.acquire(blocking=False):
        print("[XTTS] Already busy, skipping")
        return False

    try:
        # Randomly select reference segment for variety
        import random
        ref = random.choice(REF_SEGMENTS)
        server = _get_server()
        return server.synthesize(text, ref, output_path)
    finally:
        _xtts_lock.release()


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "Entendido, Mestre."
    out = os.path.join(tempfile.gettempdir(), "xtts_test.wav")
    ok = synthesize(text, out)
    print(f"Result: {ok}, Size: {os.path.getsize(out) if ok else 0}")
