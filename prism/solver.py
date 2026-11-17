"""Beam-search solver.

It exists for two reasons: tests use it to PROVE that a generated fight has
more than one way to win (by banning different tools and checking it is still
winnable), and a bot can use it to play whole runs headlessly.

The search never mutates the state it is given.
"""

from dataclasses import dataclass, field

from .consts import COLORS, COMPONENTS, ORTH, PATTERN_ORDER, PRIMARIES
from .rules import (begin_turn, can_afford, end_turn, fitting_targets, pattern_aims,
                    pattern_tiles, resolve_beat, set_boss_shapes, validate_action)
from .state import cast, move, wait

# A constraint is allow(pattern, colour) -> bool. "Styles" of winning are
# proven distinct by winning with one tool banned at a time.
CONSTRAINTS = {
    "any": None,
    "no_mix": lambda pattern, color: color in PRIMARIES,
    "no_red": lambda pattern, color: "R" not in COMPONENTS[color],
}
for _pat in PATTERN_ORDER:
    CONSTRAINTS["no_" + _pat] = (lambda banned: lambda pattern, color: pattern != banned)(_pat)


def constraints_for(player):
    """The bans that mean something for this player: no point banning a
    pattern they don't know."""
    return [n for n in CONSTRAINTS
            if n != "any" and (n[3:] not in PATTERN_ORDER or n[3:] in player.patterns)]


@dataclass
class SolveResult:
    won: bool
    turns: int = 0
    plan: list = field(default_factory=list)     # list of turns, each a list of Actions
    hp_left: int = 0

    def used(self):
        """(patterns, colours) the winning plan cast with."""
        patterns, colors = set(), set()
        for turn in self.plan:
            for a in turn:
                if a.kind == "cast":
                    patterns.add(a.pattern)
                    colors.add(a.color)
        return patterns, colors


def candidate_actions(state, allow=None):
    """A pruned but varied set of legal actions for the next beat: every
    move, and every cast that lands on something, once per distinct set of
    enemies it would land on."""
    p = state.player
    acts = [wait()]
    for dx, dy in ORTH:
        a = move(dx, dy)
        if validate_action(state, a)[0]:
            acts.append(a)
    seen = set()
    for pattern in p.patterns:
        if pattern in p.used:
            continue
        for dx, dy in pattern_aims(pattern):
            tiles = pattern_tiles(state, pattern, dx, dy)
            if not tiles:
                continue
            shapes = {e.shape for e in (state.enemy_at(*t) for t in tiles) if e is not None}
            for shape in shapes:
                ids = frozenset(e.id for e in fitting_targets(state, tiles, shape))
                for color in COLORS:
                    if allow and not allow(pattern, color):
                        continue
                    if not can_afford(p, color) or (ids, color) in seen:
                        continue
                    seen.add((ids, color))
                    acts.append(cast(pattern, shape, color, dx, dy))
    # pure defence: blue light that lands on nothing still shields you
    if "halo" in p.patterns and "halo" not in p.used and can_afford(p, "B") \
            and (allow is None or allow("halo", "B")) and pattern_tiles(state, "halo"):
        acts.append(cast("halo", "triangle", "B"))
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
    return (p.x, p.y, p.hp, p.shield, tuple(sorted(p.palette.items())), p.used,
            tuple((e.id, e.x, e.y, e.hp, e.shield, e.stun, e.burn, e.color, e.shape)
                  for e in s.enemies))


def solve(state, allow=None, max_turns=4, beat_beam=10, turn_beam=5):
    """Search for a winning plan within max_turns. Returns a SolveResult."""
    frontier = [(state.clone(), [])]
    for turn in range(max_turns):
        cur = [(s, plan, []) for s, plan in frontier]
        for beat in range(4):
            nxt = {}
            for s, plan, acts in cur:
                set_boss_shapes(s, beat)     # a Keeper's shape this beat decides what fits it
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
    names = names or constraints_for(state.player)
    return {n: solve(state, CONSTRAINTS[n], **kw) for n in names}
