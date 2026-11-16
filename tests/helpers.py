"""Shared builders for tests. Nothing here is random."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from prism.enemies import spawn  # noqa: E402
from prism.rules import begin_turn  # noqa: E402
from prism.state import Board, GameState, Player  # noqa: E402


def make_state(enemies=(), walls=(), player_at=(4, 8), hp=None, palette=None, mods=None,
               begin=True):
    """enemies: iterable of (kind, x, y, colour[, hp])."""
    p = Player()
    p.x, p.y = player_at
    if hp is not None:
        p.hp = hp
    if palette:
        p.palette.update(palette)
    if mods:
        p.mods.update(mods)
    s = GameState(Board(walls=walls), p)
    for spec in enemies:
        kind, x, y, color = spec[:4]
        e = spawn(s, kind, x, y, color)
        if len(spec) > 4:
            e.hp = e.max_hp = spec[4]
    if begin:
        begin_turn(s)
    return s


def events(ev, t):
    return [e for e in ev if e["t"] == t]
