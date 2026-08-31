"""
Elívea — Character Voice Styler v10
======================================
Advanced DSP styling to match the Elivea / Elivea character voice
from Tensei Shitara Slime Daitaiken:

  - Full, natural feminine register (F0 target ~250 Hz)
  - Calm, measured delivery (gentle compression)
  - Subtle robotic/digital quality (ring modulation + comb resonance)
  - Ethereal "voice inside the soul" quality (chorus + reverb)
  - Minimal vibrato — robotic entities don't waver
  - Low spectral balance boost for warmth and body

This is pure DSP styling over a licensed synthetic voice — NOT voice cloning.
Acoustic targets come from config/raphael_profile.json.
"""
import json
import os
import wave

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_JSON = os.path.join(BASE_DIR, "config", "raphael_profile.json")
SETTINGS_JSON = os.path.join(BASE_DIR, "config", "settings.json")

# Defaults — character acoustic signature
# Tom cheio: voz feminina natural, nem fina nem grossa
_DEFAULT_TARGET_F0 = 250.0  # Hz (registro natural feminino, mais grave = mais encorpado)
_DEFAULT_BALANCE = {"low": 0.45, "mid": 0.32, "high": 0.23}

# Safety limits for pitch shift (±9 semitones)
_MAX_SHIFT = 2.0 ** (9.0 / 12.0)
_MIN_SHIFT = 2.0 ** (-9.0 / 12.0)

# Spectral bands (Hz)
_BAND_LO = 500.0
_BAND_HI = 2000.0
_MAX_BAND_GAIN_DB = 4.0


def _load_targets() -> tuple[float, dict]:
    """Load F0 target and spectral balance from profile/settings."""
    f0 = None
    try:
        with open(SETTINGS_JSON, "r", encoding="utf-8") as f:
            f0 = float(json.load(f).get("voice_f0_hz"))
    except Exception:
        f0 = None
    if not f0:
        try:
            with open(PROFILE_JSON, "r", encoding="utf-8") as f:
                f0 = float(json.load(f).get("f0_median", _DEFAULT_TARGET_F0))
        except Exception:
            f0 = _DEFAULT_TARGET_F0
    f0 = min(max(f0, 160.0), 520.0)

    try:
        with open(PROFILE_JSON, "r", encoding="utf-8") as f:
            bal = json.load(f).get("spectral_balance", _DEFAULT_BALANCE)
    except Exception:
        bal = _DEFAULT_BALANCE
    bal = {k: float(bal.get(k, v)) for k, v in _DEFAULT_BALANCE.items()}
    return f0, bal


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _frames(x: np.ndarray, size: int, hop: int):
    n = 1 + max(0, (len(x) - size)) // hop
    for i in range(n):
        yield x[i * hop: i * hop + size]


def _estimate_f0(x: np.ndarray, sr: int) -> float | None:
    """Median F0 via autocorrelation (voiced frames only)."""
    size, hop = 1024, 512
    min_lag = max(2, int(sr / 520.0))
    max_lag = min(size - 1, int(sr / 120.0))
    rms_all = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    if rms_all < 1e-4:
        return None

    f0s = []
    for fr in _frames(x, size, hop):
        fr = fr - np.mean(fr)
        rms = float(np.sqrt(np.mean(fr ** 2)))
        if rms < rms_all * 0.25:
            continue
        ac = np.correlate(fr, fr, mode="full")[size - 1:]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        seg = ac[min_lag:max_lag + 1]
        peak = int(np.argmax(seg)) + min_lag
        if ac[peak] > 0.35:
            f0s.append(sr / peak)

    if len(f0s) < 5:
        return None
    return float(np.median(f0s))


# ---------------------------------------------------------------------------
# DSP Effects
# ---------------------------------------------------------------------------

def _pitch_shift(x: np.ndarray, ratio: float) -> np.ndarray:
    """Granular OLA: shift pitch by ratio while preserving duration."""
    n = len(x)
    if n < 2048 or abs(ratio - 1.0) < 0.02:
        return x

    idx = np.clip(np.arange(int(np.ceil(n / ratio))) * ratio, 0, n - 1)
    x2 = np.interp(idx, np.arange(n), x)
    l2 = len(x2)

    win_len = 1024
    hop_w = win_len // 2
    hop_r = max(1, int(round(hop_w * l2 / n)))
    window = np.hanning(win_len)
    out = np.zeros(n + win_len, dtype=np.float64)
    wsum = np.zeros_like(out)

    pos_w = 0
    pos_r = 0
    while pos_w < n and pos_r + win_len <= l2:
        out[pos_w: pos_w + win_len] += x2[pos_r: pos_r + win_len] * window
        wsum[pos_w: pos_w + win_len] += window
        pos_w += hop_w
        pos_r += hop_r

    wsum[wsum < 1e-8] = 1.0
    out = out[:n] / wsum[:n]
    return out


def _formant_shift(x: np.ndarray, sr: int, shift_ratio: float = 1.08) -> np.ndarray:
    """Shift formants up slightly for brighter, more feminine character voice.
    
    Uses PSOLA-like approach: pitch-synchronous overlap-add with formant modification.
    A simpler approach: resample at higher rate then time-stretch back.
    """
    n = len(x)
    if n < 4096 or abs(shift_ratio - 1.0) < 0.02:
        return x
    
    # Simple formant shift via resampling + time-stretch
    # 1. Upsample (shifts formants up)
    upsampled = np.interp(
        np.arange(int(n * shift_ratio)),
        np.arange(n),
        x
    )
    
    # 2. Time-stretch back to original duration using OLA
    l2 = len(upsampled)
    win_len = 512
    hop_w = win_len // 2
    hop_r = max(1, int(round(hop_w * l2 / n)))
    window = np.hanning(win_len)
    out = np.zeros(n + win_len, dtype=np.float64)
    wsum = np.zeros_like(out)
    
    pos_w = 0
    pos_r = 0
    while pos_w < n and pos_r + win_len <= l2:
        out[pos_w: pos_w + win_len] += upsampled[pos_r: pos_r + win_len] * window
        wsum[pos_w: pos_w + win_len] += window
        pos_w += hop_w
        pos_r += hop_r
    
    wsum[wsum < 1e-8] = 1.0
    out = out[:n] / wsum[:n]
    return out


def _add_vibrato(x: np.ndarray, sr: int, depth: float = 0.003, rate: float = 5.5) -> np.ndarray:
    """Subtle vibrato for natural anime-character voice quality."""
    n = len(x)
    if n < 2048:
        return x
    t = np.arange(n) / sr
    # Vibrato: slight pitch modulation
    vibrato = 1.0 + depth * np.sin(2 * np.pi * rate * t)
    # Apply via sample-by-sample interpolation
    indices = np.cumsum(vibrato) 
    indices = np.clip(indices * sr, 0, n - 1)
    out = np.interp(indices, np.arange(n), x)
    return out


def _add_breathiness(x: np.ndarray, sr: int, amount: float = 0.03) -> np.ndarray:
    """Add subtle breath/hiss noise for warmth and naturalness."""
    n = len(x)
    if n < 1024:
        return x
    # Generate shaped noise (bandpass filtered)
    noise = np.random.randn(n) * amount
    # Simple bandpass: keep only 2-8 kHz for breath character
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    # Bandpass mask
    mask = np.zeros_like(freqs)
    bp_lo, bp_hi = 2000.0, 8000.0
    in_band = (freqs >= bp_lo) & (freqs <= bp_hi)
    # Smooth transitions
    transition = 500.0
    near_lo = (freqs >= bp_lo - transition) & (freqs < bp_lo)
    near_hi = (freqs > bp_hi) & (freqs <= bp_hi + transition)
    mask[in_band] = 1.0
    mask[near_lo] = (freqs[near_lo] - (bp_lo - transition)) / transition
    mask[near_hi] = 1.0 - (freqs[near_hi] - bp_hi) / transition
    spec *= mask
    breath = np.fft.irfft(spec, n=n)
    # Mix with envelope-following amount (more breath in quiet parts)
    envelope = np.abs(x)
    a = np.exp(-1.0 / (0.05 * sr))
    smooth = np.empty_like(envelope)
    acc = 0.0
    for i, v in enumerate(envelope):
        acc = a * acc + (1 - a) * v
        smooth[i] = acc
    # More breath in quiet segments
    mix = np.clip(1.0 - smooth / (np.max(smooth) + 1e-8), 0, 1) * amount * 2
    return x + breath * mix


def _match_spectral_balance(x: np.ndarray, sr: int, target: dict) -> np.ndarray:
    """Gentle EQ to match the target low/mid/high balance."""
    n = len(x)
    if n < 4096:
        return x
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    mag = np.abs(spec)

    def band_energy(lo, hi):
        m = (freqs >= lo) & (freqs < hi)
        e = float(np.sqrt(np.mean(mag[m] ** 2))) if np.any(m) else 1e-9
        return max(e, 1e-9)

    cur = {
        "low": band_energy(0, _BAND_LO),
        "mid": band_energy(_BAND_LO, _BAND_HI),
        "high": band_energy(_BAND_HI, np.inf),
    }
    total = sum(cur.values())
    cur = {k: v / total for k, v in cur.items()}

    cap = 10.0 ** (_MAX_BAND_GAIN_DB / 20.0)
    floor = 1.0 / cap
    gain = {
        "low": float(np.clip(np.sqrt(target["low"] / max(cur["low"], 1e-6)), floor, cap)),
        "mid": float(np.clip(np.sqrt(target["mid"] / max(cur["mid"], 1e-6)), floor, cap)),
        "high": float(np.clip(np.sqrt(target["high"] / max(cur["high"], 1e-6)), floor, cap)),
    }

    anchor_f = np.array([0.0, _BAND_LO * 0.7, _BAND_LO, _BAND_HI, _BAND_HI * 1.4, freqs[-1]])
    anchor_g = np.array([gain["low"], gain["low"], gain["mid"], gain["mid"], gain["high"], gain["high"]])
    anchor_f = np.clip(anchor_f, 0, freqs[-1])
    mask = np.interp(freqs, anchor_f, anchor_g)
    return np.fft.irfft(spec * mask, n=n)


def _add_chorus(samples, sr, delay_ms=20, depth=0.12, rate=0.25):
    """Dual chorus for ethereal 'voice inside the head' quality."""
    delay_samples = int(sr * delay_ms / 1000)
    n = len(samples)
    t = np.arange(n) / sr
    
    # Primary chorus
    lfo1 = 1.0 + depth * 0.5 * np.sin(2 * np.pi * rate * t)
    output = samples.copy()
    delayed1 = np.zeros(n)
    delayed1[delay_samples:] = samples[:-delay_samples]
    output += delayed1 * lfo1 * depth
    
    # Secondary chorus (slightly different rate for richness)
    delay2 = int(sr * (delay_ms * 0.7) / 1000)
    lfo2 = 1.0 + depth * 0.3 * np.sin(2 * np.pi * (rate * 1.3) * t)
    delayed2 = np.zeros(n)
    delayed2[delay2:] = samples[:-delay2]
    output += delayed2 * lfo2 * depth * 0.6
    
    return output


def _ring_modulate(x: np.ndarray, sr: int, freq: float = 90.0, depth: float = 0.08) -> np.ndarray:
    """Subtle ring modulation for robotic/digital quality (Elivea flavor).
    
    Very light modulation at a low frequency adds a slight mechanical
    shimmer without making it sound like a broken robot.
    """
    n = len(x)
    if n < 2048 or depth < 0.001:
        return x
    t = np.arange(n) / sr
    modulator = 1.0 - depth + depth * np.sin(2 * np.pi * freq * t)
    return x * modulator


def _add_digital_resonance(x: np.ndarray, sr: int) -> np.ndarray:
    """Subtle metallic resonance for the 'voice of a being inside the soul' quality.
    
    Adds a very gentle comb filter that creates a slight metallic ring,
    characteristic of an AI/spirit entity speaking from within.
    """
    n = len(x)
    if n < 4096:
        return x
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    # Gentle comb: slight notches at 120 Hz intervals (mains harmonic = digital feel)
    comb = np.ones_like(freqs)
    for h in range(1, 8):
        notch_f = 120.0 * h
        if notch_f < freqs[-1]:
            mask = np.exp(-((freqs - notch_f) ** 2) / (2 * (8.0 ** 2)))
            comb *= (1.0 - 0.04 * mask)
    return np.fft.irfft(spec * comb, n=n)


def _add_reverb(samples, sr, delay_ms=15, decay=0.15, iterations=3):
    """Short room reverb for spatial presence."""
    output = samples.copy()
    for i in range(iterations):
        delay_samples = int(sr * delay_ms * (i + 1) / 1000)
        gain = decay ** (i + 1)
        if delay_samples < len(samples):
            output[delay_samples:] += samples[:-delay_samples] * gain
    return output


def _compress(x: np.ndarray, threshold=0.25, ratio=2.5) -> np.ndarray:
    """Gentle compression for measured, controlled delivery."""
    env = np.abs(x)
    a = np.exp(-1.0 / (0.02 * 24000))
    smooth = np.empty_like(env)
    acc = 0.0
    for i, v in enumerate(env):
        acc = a * acc + (1 - a) * v
        smooth[i] = acc
    over = smooth > threshold
    gain = np.ones_like(smooth)
    gain[over] = (threshold + (smooth[over] - threshold) / ratio) / smooth[over]
    y = x * gain
    peak = float(np.max(np.abs(y)))
    if peak > 1e-8 and peak < 0.5:
        y = y * (0.5 / peak)
    return y


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def convert_voice(input_wav: str, output_wav: str) -> bool:
    """Apply character styling to a mono 16-bit WAV.
    
    Chain: F0 alignment -> formant shift -> vibrato -> breathiness -> 
           spectral EQ -> dual chorus -> reverb -> compression -> normalize
    """
    try:
        with wave.open(input_wav, "r") as wf:
            sr = wf.getframerate()
            nch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
        if nch > 1:
            samples = samples.reshape(-1, nch).mean(axis=1)
    except Exception as e:
        print(f"[VoiceStyler] read error: {e}")
        return False

    if len(samples) < 1024:
        return False

    target_f0, balance = _load_targets()

    # 1. F0 alignment (measured -> target)
    measured = _estimate_f0(samples, sr)
    if measured and 100.0 < measured < 600.0:
        ratio = float(np.clip(target_f0 / measured, _MIN_SHIFT, _MAX_SHIFT))
        samples = _pitch_shift(samples, ratio)

    # 2. Formant shift leve para voz mais natural (antes 0.92 deixava grave demais)
    samples = _formant_shift(samples, sr, shift_ratio=0.97)

    # 3. Vibrato quase imperceptível — mais humano
    samples = _add_vibrato(samples, sr, depth=0.00015, rate=4.5)

    # 4. Breathiness sutil para calor humano
    samples = _add_breathiness(samples, sr, amount=0.004)

    # 5. Spectral balance EQ — leve
    samples = _match_spectral_balance(samples, sr, balance)

    # 6. Ring modulation DESATIVADO para voz natural (antes 0.06 deixava robótico)
    # samples = _ring_modulate(samples, sr, freq=85.0, depth=0.06)

    # 7. Digital resonance DESATIVADO (metálico)
    # samples = _add_digital_resonance(samples, sr)

    # 8. Chorus muito sutil para presença (antes 0.10 era etéreo demais)
    samples = _add_chorus(samples, sr, depth=0.035)

    # 9. Room reverb
    samples = _add_reverb(samples, sr)

    # 10. Gentle compression
    samples = _compress(samples)

    # 11. Final normalization
    peak = float(np.max(np.abs(samples)))
    if peak > 0:
        samples = samples / peak * 0.92

    out = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    try:
        with wave.open(output_wav, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(out.tobytes())
        return True
    except Exception as e:
        print(f"[VoiceStyler] write error: {e}")
        return False


if __name__ == "__main__":
    print("Elivea Voice Styler v10")
    print(f"Profile: {PROFILE_JSON}")
