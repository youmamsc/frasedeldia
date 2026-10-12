"""Original music identity for Frase del Día.

Procedurally synthesized nylon-string-like plucks and castanet-style clicks.
No loops, samples, third-party recordings, or music-library licences.
"""
from __future__ import annotations

import numpy as np
from pydub import AudioSegment

RATE = 44100


def make_jingle(outro: bool = False) -> AudioSegment:
    seconds = 1.35 if outro else 3.20
    count = int(RATE * seconds)
    mix = np.zeros(count, dtype=np.float64)

    def pluck(freq: float, at: float, duration: float = .75,
              volume: float = .25) -> None:
        start = int(at * RATE)
        end = min(count, start + int(duration * RATE))
        t = np.arange(end - start) / RATE
        harmonics = [(1, 1.), (2, .42), (3, .24), (4, .12), (5, .05)]
        tone = sum(a * np.sin(2 * np.pi * freq * n * t + .11 * n) / n ** .2
                   for n, a in harmonics)
        envelope = (1 - np.exp(-220 * t)) * np.exp(-3.5 * t)
        mix[start:end] += volume * tone * envelope

    def palm(at: float, volume: float = .055) -> None:
        start = int(at * RATE)
        end = min(count, start + int(.075 * RATE))
        t = np.arange(end - start) / RATE
        noise = np.random.default_rng(1024 + start).normal(size=len(t))
        mix[start:end] += volume * noise * np.exp(-70 * t) * (
            1 - np.exp(-1000 * t)
        )

    def chord(at: float, notes: list[float], volume: float = .17) -> None:
        for index, frequency in enumerate(notes):
            pluck(frequency, at + .008 * index, 1.2,
                  volume * (1 - .12 * index))

    if outro:
        for note, at in [(392., 0), (349.23, .18), (329.63, .36)]:
            pluck(note, at, .55, .25)
        chord(.60, [164.81, 246.94, 329.63], .12)
        for at in [0, .16, .42, .57]:
            palm(at, .035)
    else:
        # Original four-note flamenco-flavoured station identity: A-G-F-E.
        for note, at in [(440., .15), (392., .60), (349.23, 1.06),
                         (329.63, 1.52)]:
            pluck(note, at, .73, .33)
        chord(2.06, [164.81, 246.94, 329.63], .22)
        for at in [0, .23, .50, .73, .99, 1.23, 1.50, 1.73, 2., 2.22]:
            palm(at, .042 if int(at * 4) % 2 else .068)

    # A tiny self-produced room reflection makes the ident warmer.
    reflection = int(.093 * RATE)
    mix[reflection:] += mix[:-reflection].copy() * .14
    mix = np.tanh(mix * 1.3) * .60
    tail = int((.23 if outro else .38) * RATE)
    mix[-tail:] *= np.linspace(1, 0, tail)
    data = (np.clip(mix, -.98, .98) * 32767).astype(np.int16)
    return AudioSegment(data.tobytes(), frame_rate=RATE,
                        sample_width=2, channels=1).set_channels(2)
