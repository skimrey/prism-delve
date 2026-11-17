"""Sound, synthesized on the spot (no audio files), toy-box style.

The one idea: everything with corners clicks. Every beat of a fight is a
tick; hits are knocks and thuds; knocking a shape loose is a pop. Only
rolling is smooth: a soft continuous hum that swells with speed (the ramp,
the Meadow). Colours each have a note, so a cast sounds like its colour.

Everything is optional: with no audio device, or sound turned off, play()
does nothing. Sounds are built the first time they are used.
"""

import math
import random
from array import array

import pygame

from .settings import SETTINGS

# one note per colour, in rainbow order up a pentatonic-ish scale
NOTE = {"R": 261.6, "Y": 329.6, "G": 392.0, "C": 440.0, "B": 523.3, "M": 587.3}

_cache = {}
_samples = {}                 # computed ahead of time by warm(), turned into Sounds on use
_state = {"ok": None, "roll": None}
NAMES = ("tick", "tock", "ui", "hit", "hurt", "loose", "group", "fanfare", "ascend", "door", "buy",
         "talk", "step", "roll") + tuple("cast:" + c for c in NOTE)


def warm():
    """Compute every sound on a background thread, so none stutters on first use."""
    import threading
    if not available():
        return None

    def work():
        for name in NAMES:
            if name not in _samples:
                try:
                    _samples[name] = _build(name)
                except (pygame.error, TypeError):      # the mixer closed (we're quitting)
                    return
    th = threading.Thread(target=work, daemon=True)
    th.start()
    return th


def init():
    """Open the mixer if we can. Safe to call more than once."""
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(22050, -16, 1, 512)
        _state["ok"] = bool(pygame.mixer.get_init())
    except pygame.error:
        _state["ok"] = False
    return _state["ok"]


def available():
    if _state["ok"] is None:
        try:
            _state["ok"] = bool(pygame.mixer.get_init())
        except pygame.error:
            _state["ok"] = False
    return _state["ok"]


# ---------------------------------------------------------------- synthesis

def _rate():
    return pygame.mixer.get_init()[0]


def _tone(freq, dur, decay=8.0, harmonics=(1.0, 0.3, 0.1), attack=0.004, sweep=None):
    """A plucked/struck tone: a few harmonics, a quick attack, exponential decay.
    `sweep` glides the pitch to that frequency over the note."""
    rate = _rate()
    n = int(dur * rate)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / rate
        f = freq if sweep is None else freq + (sweep - freq) * (i / n)
        phase += f / rate
        env = min(1.0, t / attack) * math.exp(-decay * t)
        out.append(env * sum(a * math.sin(math.tau * phase * (k + 1)) for k, a in enumerate(harmonics)))
    return out


def _noise(dur, decay=30.0, seed=1, smooth=0.0):
    rng = random.Random(seed)
    rate = _rate()
    out, last = [], 0.0
    for i in range(int(dur * rate)):
        v = rng.uniform(-1, 1)
        last = last * smooth + v * (1 - smooth)
        out.append(last * math.exp(-decay * i / rate))
    return out


def _mix(*parts, gaps=None):
    """Lay sounds over each other; `gaps` (seconds) offsets each part."""
    rate = _rate()
    gaps = gaps or [0.0] * len(parts)
    n = max(int(g * rate) + len(p) for p, g in zip(parts, gaps))
    out = [0.0] * n
    for p, g in zip(parts, gaps):
        o = int(g * rate)
        for i, v in enumerate(p):
            out[o + i] += v
    peak = max(1e-6, max(abs(v) for v in out))
    return [v / peak * 0.9 for v in out] if peak > 0.9 else out


def _sound(samples):
    _freq, _fmt, channels = pygame.mixer.get_init()
    data = array("h", (int(max(-1.0, min(1.0, v)) * 30000) for v in samples))
    if channels == 2:
        data = array("h", (v for v in data for _ in (0, 1)))
    return pygame.mixer.Sound(buffer=data.tobytes())


def _build(name):
    if name == "tick":                                         # a corner clicking on the beat
        return _mix(_tone(1400, 0.05, 70, (1.0, 0.2)), _noise(0.02, 200, 2))
    if name == "tock":                                         # beat one of a turn
        return _mix(_tone(900, 0.07, 50, (1.0, 0.3)), _noise(0.02, 200, 3))
    if name == "ui":
        return _tone(660, 0.07, 40, (1.0, 0.2), sweep=880)
    if name.startswith("cast:"):                               # each colour has its note
        f = NOTE.get(name[5:], 440.0)
        return _mix(_tone(f, 0.35, 9, (1.0, 0.4, 0.2, 0.1)), _tone(f * 2, 0.2, 14, (0.4,)))
    if name == "hit":
        return _mix(_tone(150, 0.14, 25, (1.0, 0.5)), _noise(0.06, 60, 4, 0.6))
    if name == "hurt":
        return _tone(180, 0.22, 12, (1.0, 0.6, 0.3), sweep=80)
    if name == "loose":                                        # a pop, and the edges tinkling off
        return _mix(_noise(0.05, 80, 5), _tone(900, 0.1, 25, sweep=1500),
                    _tone(1500, 0.1, 25, sweep=2200), gaps=[0, 0.03, 0.09])
    if name == "group":
        notes = (NOTE["R"] * 2, NOTE["G"] * 2, NOTE["B"] * 2)
        return _mix(*[_tone(f, 0.3, 10, (1.0, 0.3)) for f in notes], gaps=[0, 0.06, 0.12])
    if name == "fanfare":                                      # a clean sort
        notes = [NOTE[c] * 2 for c in ("R", "Y", "G", "C", "B", "M")]
        return _mix(*[_tone(f, 0.5, 5, (1.0, 0.3, 0.1)) for f in notes],
                    gaps=[i * 0.07 for i in range(len(notes))])
    if name == "ascend":                                       # growing a side
        return _mix(*[_tone(f, 1.1, 3, (1.0, 0.2), sweep=f * 1.5) for f in (262, 330, 392)])
    if name == "door":                                         # the Round Door, humming open
        return _mix(*[_tone(f, 1.8, 1.4, (1.0, 0.15), attack=0.4) for f in (392, 494, 587, 784)])
    if name == "buy":
        return _mix(_tone(1318, 0.12, 20, (1.0,)), _tone(1760, 0.18, 16, (1.0,)), gaps=[0, 0.06])
    if name == "talk":
        return _tone(700 + random.Random(len(_cache)).uniform(-80, 80), 0.06, 30, (1.0, 0.2),
                     sweep=900)
    if name == "step":
        return _tone(320, 0.05, 60, (1.0, 0.3))
    if name == "roll":                                         # the only smooth sound there is
        base = _noise(1.0, 0.0, 6, 0.985)
        hum = _tone(110, 1.0, 0.0, (0.3, 0.1), attack=0.001)
        return _mix(base, hum)
    return [0.0]


def get(name):
    snd = _cache.get(name)
    if snd is None:
        samples = _samples.get(name) or _build(name)
        snd = _cache[name] = _sound(samples)
    return snd


def play(name, gain=1.0):
    """Play a sound once (if sound is on and there is somewhere to play it)."""
    if not SETTINGS["sound"] or not available():
        return
    try:
        snd = get(name)
        snd.set_volume(max(0.0, min(1.0, SETTINGS["volume"] * gain)))
        snd.play()
    except pygame.error:
        pass


def roll(level):
    """The rolling hum: level 0..1 (0 stops it)."""
    if not available():
        return
    try:
        ch = _state["roll"]
        if level <= 0 or not SETTINGS["sound"]:
            if ch is not None:
                ch.stop()
                _state["roll"] = None
            return
        if ch is None or not ch.get_busy():
            ch = _state["roll"] = get("roll").play(loops=-1)
        if ch is not None:
            ch.set_volume(min(1.0, level) * SETTINGS["volume"] * 0.5)
    except pygame.error:
        pass
