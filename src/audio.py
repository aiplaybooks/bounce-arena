"""Synthesizes the soundtrack from simulation events (no external audio, no licensing)."""
import wave
import numpy as np

SR = 44100
# Two octaves of a major pentatonic scale per key; bounces walk up and down it.
KEYS = {"C": 261.63, "D": 293.66, "E": 329.63, "G": 392.00, "A": 440.00}
PENTA = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]


def _pluck(freq, dur, bright=1.0):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t * 7.0) * np.minimum(1, t * 400)
    w = np.sin(2 * np.pi * freq * t) + 0.35 * bright * np.sin(4 * np.pi * freq * t) + 0.12 * bright * np.sin(6 * np.pi * freq * t)
    return w * env


def _click(dur=0.03):
    t = np.arange(int(SR * dur)) / SR
    rng = np.random.default_rng(7)
    return rng.standard_normal(t.size) * np.exp(-t * 180) * 0.4


def _add(buf, start, sig, gain):
    i = int(start * SR)
    if i >= buf.size:
        return
    j = min(buf.size, i + sig.size)
    buf[i:j] += sig[: j - i] * gain


def build(events, duration, path, key="C"):
    buf = np.zeros(int(SR * (duration + 1.0)), dtype=np.float64)
    base = KEYS.get(key, 261.63)
    notes = [base * 2 ** (s / 12) for s in PENTA]
    seq = list(range(len(notes))) + list(range(len(notes) - 2, 0, -1))
    k = 0
    last_note = -1.0
    last_clack = -1.0
    for t, kind, team, extra, *_ in events:
        if t > duration:
            break
        if kind == "bounce":
            if t - last_note < 0.05:
                continue
            last_note = t
            _add(buf, t, _pluck(notes[seq[k % len(seq)]], 0.45), 0.32)
            k += 1
        elif kind == "clack":
            if t - last_clack < 0.06:
                continue
            last_clack = t
            _add(buf, t, _click(), 0.5)
        elif kind == "pass":
            for i, s in enumerate((0, 4, 7)):
                _add(buf, t + i * 0.03, _pluck(base * 2 ** ((s + 12) / 12), 0.8, 1.5), 0.25)
        elif kind == "win":
            for i, s in enumerate((0, 4, 7, 12, 16, 19, 24)):
                _add(buf, t + i * 0.08, _pluck(base * 2 ** ((s + 12) / 12), 1.2, 1.6), 0.3)
            for s in (0, 4, 7, 12):
                _add(buf, t + 0.6, _pluck(base * 2 ** ((s + 12) / 12), 2.5, 1.2), 0.18)
    buf = buf[: int(SR * duration)]
    peak = np.max(np.abs(buf)) or 1.0
    # soft limiter keeps dense bounce clusters from clipping
    buf = np.tanh(buf / peak * 1.4) / np.tanh(1.4) * 0.89
    pcm = (buf * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
