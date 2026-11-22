"""Procedural sound synthesis with NumPy, written as 16-bit PCM mono .wav.

Every sound is generated from maths (sines, filtered noise, envelopes), so
the project ships no third-party audio. Run this module directly to
regenerate all files:  python -m sfx.synth
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100
_rng = np.random.default_rng(1337)   # fixed seed: identical files every build


# ---------------------------------------------------------------- helpers
def _t(seconds: float) -> np.ndarray:
    return np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE


def _fade(sig: np.ndarray, fade_in: float = 0.005, fade_out: float = 0.01) -> np.ndarray:
    out = sig.copy()
    n_in, n_out = int(SAMPLE_RATE * fade_in), int(SAMPLE_RATE * fade_out)
    if n_in:
        out[:n_in] *= np.linspace(0.0, 1.0, n_in)
    if n_out:
        out[-n_out:] *= np.linspace(1.0, 0.0, n_out)
    return out


def _lowpass(sig: np.ndarray, window: int) -> np.ndarray:
    """Cheap moving-average low-pass filter."""
    kernel = np.ones(window) / window
    return np.convolve(sig, kernel, mode="same")


def _normalise(sig: np.ndarray, peak: float = 0.85) -> np.ndarray:
    m = np.max(np.abs(sig))
    return sig if m == 0 else sig * (peak / m)


def write_wav(path: Path, sig: np.ndarray) -> None:
    data = (np.clip(sig, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(data.tobytes())


# ---------------------------------------------------------------- sounds
def ambient_drone() -> np.ndarray:
    """8 s seamless loop. Every frequency completes a whole number of cycles
    in 8 s, so the end joins the start without a click."""
    dur = 8.0
    t = _t(dur)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)          # 2 cycles per loop
    lfo2 = 0.5 + 0.5 * np.sin(2 * np.pi * 0.125 * t + 1.0)  # 1 cycle per loop
    sig = (0.50 * np.sin(2 * np.pi * 55.0 * t)
           + 0.30 * np.sin(2 * np.pi * 82.5 * t) * lfo
           + 0.18 * np.sin(2 * np.pi * 110.25 * t) * lfo2
           + 0.10 * np.sin(2 * np.pi * 164.875 * t) * (1 - lfo2)   # eerie upper partial
           + 0.06 * np.sin(2 * np.pi * 233.125 * t) * lfo)         # dissonant shimmer
    # Breath of wind: low-passed noise, made periodic by tiling one period.
    # Generate extra samples past the loop end and crossfade them into the
    # start, so sample 0 continues smoothly from the last sample.
    n, edge = len(t), int(SAMPLE_RATE * 0.5)
    raw = _lowpass(_rng.standard_normal(n + edge), 400)
    raw = raw / (np.max(np.abs(raw)) + 1e-9)
    ramp = np.linspace(0, 1, edge)
    noise = raw[:n].copy()
    noise[:edge] = raw[:edge] * ramp + raw[n:n + edge] * (1 - ramp)
    sig = sig + 0.12 * noise * lfo2
    return _normalise(sig, 0.55)


def heartbeat() -> np.ndarray:
    """Lub-dub: two low thumps with a falling pitch."""
    def thump(dur: float, f0: float, f1: float, amp: float) -> np.ndarray:
        t = _t(dur)
        freq = f1 + (f0 - f1) * np.exp(-t * 25)
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        env = np.exp(-t * 18) * (1 - np.exp(-t * 400))
        return amp * np.sin(phase) * env

    out = np.zeros(int(SAMPLE_RATE * 0.55))
    lub = thump(0.25, 95, 45, 1.0)
    dub = thump(0.22, 85, 40, 0.7)
    out[: len(lub)] += lub
    start = int(SAMPLE_RATE * 0.17)
    out[start: start + len(dub)] += dub
    return _fade(_normalise(out, 0.9), 0.001, 0.02)


def step() -> np.ndarray:
    """Soft footstep: short burst of filtered noise with a low knock."""
    t = _t(0.09)
    noise = _lowpass(_rng.standard_normal(len(t)), 12) * np.exp(-t * 70)
    knock = np.sin(2 * np.pi * 120 * t) * np.exp(-t * 60)
    return _fade(_normalise(0.6 * noise + 0.5 * knock, 0.5), 0.001, 0.01)


def radar_ping() -> np.ndarray:
    """Sonar pulse with a fading echo."""
    t = _t(1.2)
    def ping(delay: float, amp: float) -> np.ndarray:
        td = np.clip(t - delay, 0, None)
        gate = (t >= delay).astype(float)
        tone = np.sin(2 * np.pi * 1400 * td) + 0.3 * np.sin(2 * np.pi * 2800 * td)
        return amp * gate * tone * np.exp(-td * 7)
    sig = ping(0.0, 1.0) + ping(0.28, 0.35) + ping(0.56, 0.12)
    return _fade(_normalise(sig, 0.6), 0.002, 0.05)


def hint_chime() -> np.ndarray:
    """Spectral bell: slightly inharmonic partials with long decays."""
    t = _t(1.6)
    partials = [(660, 1.0, 3.0), (990, 0.6, 4.0), (1325, 0.4, 5.0), (1780, 0.25, 7.0), (2490, 0.12, 9.0)]
    sig = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in partials)
    shimmer = 1 + 0.15 * np.sin(2 * np.pi * 6 * t)
    return _fade(_normalise(sig * shimmer, 0.55), 0.003, 0.1)


def catch_stinger() -> np.ndarray:
    """Dissonant shock chord (minor seconds + tritone) over a noise slam."""
    dur = 2.4
    t = _t(dur)
    freqs = [110, 116.5, 155.6, 220, 233.1, 311.1, 466.2]
    chord = np.zeros_like(t)
    for i, f in enumerate(freqs):
        detune = 1 + 0.003 * np.sin(2 * np.pi * (0.5 + i * 0.2) * t)
        phase = 2 * np.pi * f * detune * t
        chord += np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.15 * np.sin(3 * phase)
    env = (1 - np.exp(-t * 30)) * np.exp(-t * 1.4)
    slam = _lowpass(_rng.standard_normal(len(t)), 6) * np.exp(-t * 9)
    sig = chord * env / len(freqs) + 0.8 * slam
    return _fade(_normalise(sig, 0.9), 0.001, 0.2)


SOUNDS = {
    "ambient_drone.wav": ambient_drone,
    "heartbeat.wav": heartbeat,
    "step.wav": step,
    "radar_ping.wav": radar_ping,
    "hint_chime.wav": hint_chime,
    "catch_stinger.wav": catch_stinger,
}


def generate_all(out_dir: Path, force: bool = False) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in SOUNDS.items():
        path = out_dir / name
        if force or not path.exists():
            write_wav(path, fn())
            written.append(path)
    return written


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from config import AUDIO_DIR
    for p in generate_all(AUDIO_DIR, force=True):
        print("wrote", p)
