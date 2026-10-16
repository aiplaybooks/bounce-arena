"""Synthesizes the soundtrack from simulation events (no external audio, no licensing)."""
import wave
import numpy as np

SR = 44100
# Melody removed (owner: it was headache-inducing). Only soft, low collision pops/ticks.
# `key` still nudges the pop pitch so videos don't all sound identical.
KEYS = {"C": 0.0, "D": 0.06, "E": 0.12, "G": 0.2, "A": 0.26}


def _pop(freq, dur=0.09):
    t = np.arange(int(SR * dur)) / SR
    f = freq * (0.65 + 0.35 * np.exp(-t * 60))  # quick downward pitch bend = "pop"
    env = np.exp(-t * 48) * np.minimum(1, t * 900)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env


def _tick(dur=0.025):
    t = np.arange(int(SR * dur)) / SR
    rng = np.random.default_rng(7)
    n = np.convolve(rng.standard_normal(t.size), np.ones(12) / 12, "same")  # low-passed, not hissy
    return n * np.exp(-t * 220) * 2.0


def _add(buf, start, sig, gain):
    i = int(start * SR)
    if i >= buf.size:
        return
    j = min(buf.size, i + sig.size)
    buf[i:j] += sig[: j - i] * gain


def build(events, duration, path, key="C"):
    buf = np.zeros(int(SR * (duration + 1.0)), dtype=np.float64)
    shift = 2 ** KEYS.get(key, 0.0)
    last_pop = -1.0
    last_tick = -1.0
    last_boom = -1.0
    for t, kind, team, extra, *_ in events:
        if t > duration:
            break
        if kind == "bounce":
            if t - last_pop < 0.07:
                continue
            last_pop = t
            _add(buf, t, _pop(170 * shift * (1 + 0.04 * (sum(map(ord, str(team))) % 5))), 0.35)
        elif kind == "clack":
            if t - last_tick < 0.08:
                continue
            last_tick = t
            _add(buf, t, _tick(), 0.3)
        elif kind == "pass":
            _add(buf, t, _pop(230 * shift, 0.14), 0.5)
        elif kind == "boom":
            if t - last_boom < 0.05:
                continue
            last_boom = t
            _add(buf, t, _pop(150 * shift * (1 + 0.1 * (int(t * 40) % 4)), 0.1), 0.3)
        elif kind == "win":
            for i in range(3):
                _add(buf, t + i * 0.09, _pop((200 + 40 * i) * shift, 0.16), 0.55)
    buf = buf[: int(SR * duration)]
    peak = np.max(np.abs(buf)) or 1.0
    # soft limiter, and a lower ceiling than before so it never sounds harsh
    buf = np.tanh(buf / peak * 1.2) / np.tanh(1.2) * 0.6
    pcm = (buf * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
