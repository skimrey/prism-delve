"""Beam-search solver.

It exists for two reasons: tests use it to PROVE that a generated fight has
more than one way to win (by banning different tools and checking it is still
winnable), and a bot can use it to play whole runs headlessly.

The search never mutates the state it is given.
"""

from dataclasses import dataclass, field

from .consts import COMPONENTS, COLORS, ORTH, PRIMARIES, SHAPES
from .rules import (begin_turn, can_afford, end_turn, resolve_beat, shape_range,
                    shape_tiles, validate_action)
from .state import cast, move, wait

CONSTRAINTS = {
    "any": None,
    "no_mix": lambda shape, color: color in PRIMARIES,
    "no_red": lambda shape, color: "R" not in COMPONENTS[color],
    "no_square": lambda shape, color: shape != "square",
    "no_triangle": lambda shape, color: shape != "triangle",
    "no_circle": lambda shape, color: shape != "circle",
}


@dataclass
class SolveResult:
    won: bool
    turns: int = 0
    plan: list = field(default_factory=list)     # list of turns, each a list of Actions
    hp_left: int = 0

    def used(self):
        """(shapes, colours) the winning plan cast with."""
        shapes, colors = set(), set()
        for turn in self.plan:
            for a in turn:
                if a.kind == "cast":
                    shapes.add(a.shape)
                    colors.add(a.color)
        return shapes, colors


def candidate_actions(state, allow=None, per_shape=4):
    """A pruned but varied set of legal actions for the next beat."""
    p = state.player
    acts = [wait()]
    for dx, dy in ORTH:
        a = move(dx, dy)
        if validate_action(state, a)[0]:
            acts.append(a)
    rng = shape_range(state)
    for shape in SHAPES:
        seen = {}
        for tx in range(p.x - rng, p.x + rng + 1):
            for ty in range(p.y - rng, p.y + rng + 1):
                tiles = shape_tiles(state, shape, tx, ty)
                if not tiles:
                    continue
                key = frozenset(tiles)
                hits = sum(1 for t in tiles if state.enemy_at(*t))
                if hits and (key not in seen or seen[key][0] < hits):
                    seen[key] = (hits, tx, ty)
        best = sorted(seen.values(), key=lambda h: -h[0])[:per_shape]
        for color in COLORS:
            if allow and not allow(shape, color):
                continue
            if not can_afford(p, color):
                continue
            for _, tx, ty in best:
                acts.append(cast(shape, color, tx, ty))
    if (allow is None or allow("circle", "B")) and can_afford(p, "B"):
        acts.append(cast("circle", "B", p.x, p.y))      # pure defence: a shield
    return acts


def score(state):
    if state.outcome == "victory":
        return 1e6
    p = state.player
    threat = 0
    for e in state.enemies:
        effective = max(0, e.hp + e.shield - min(e.burn, e.hp))
        threat += 7 * effective + 9 + (-3 if e.stun else 0)
    return 10 * p.hp + 4 * p.shield - threat + 0.5 * sum(p.palette.values())


def _signature(s):
    p = s.player
    return (p.x, p.y, p.hp, p.shield, tuple(sorted(p.palette.items())), p.chain,
            p.last_shape,
            tuple((e.id, e.x, e.y, e.hp, e.shield, e.stun, e.burn, e.color)
                  for e in s.enemies))


def solve(state, allow=None, max_turns=4, beat_beam=10, turn_beam=5):
    """Search for a winning plan within max_turns. Returns a SolveResult."""
    frontier = [(state.clone(), [])]
    for turn in range(max_turns):
        cur = [(s, plan, []) for s, plan in frontier]
        for beat in range(4):
            nxt = {}
            for s, plan, acts in cur:
                for a in candidate_actions(s, allow):
                    s2 = s.clone()
                    resolve_beat(s2, a, beat)
                    if s2.outcome == "defeat":
                        continue
                    if s2.outcome == "victory":
                        full = plan + [acts + [a]]
                        return SolveResult(True, turn + 1, full, s2.player.hp)
                    key = _signature(s2)
                    sc = score(s2)
                    if key not in nxt or nxt[key][0] < sc:
                        nxt[key] = (sc, s2, plan, acts + [a])
            ranked = sorted(nxt.values(), key=lambda v: -v[0])[:beat_beam]
            cur = [(s2, plan, acts) for _, s2, plan, acts in ranked]
            if not cur:
                break
        finals = {}
        for s, plan, acts in cur:
            end_turn(s)
            if s.outcome == "defeat":
                continue
            if s.outcome == "victory":
                return SolveResult(True, turn + 1, plan + [acts], s.player.hp)
            begin_turn(s)
            key = _signature(s)
            sc = score(s)
            if key not in finals or finals[key][0] < sc:
                finals[key] = (sc, s, plan + [acts])
        ranked = sorted(finals.values(), key=lambda v: -v[0])[:turn_beam]
        frontier = [(s, plan) for _, s, plan in ranked]
        if not frontier:
            break
    return SolveResult(False)


def count_paths(state, names=None, **kw):
    """Solve under each named constraint. Returns {name: SolveResult}."""
    names = names or [n for n in CONSTRAINTS if n != "any"]
    return {n: solve(state, CONSTRAINTS[n], **kw) for n in names}
