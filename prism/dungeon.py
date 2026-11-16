"""Room generation (combat boards) and the branching route map."""

import random
from collections import deque
from dataclasses import dataclass, field

from .consts import COLORS, GRID_H, GRID_W, ORTH, PLAYER_START
from .enemies import BOSS_FOR_ACT, spawn
from .rules import begin_turn
from .state import Board, GameState

ENEMY_POOL = {
    1: [("pawn", 5), ("lancer", 3), ("bloom", 2), ("warden", 1)],
    2: [("pawn", 3), ("lancer", 3), ("bloom", 3), ("warden", 2), ("splitter", 3)],
    3: [("pawn", 2), ("lancer", 3), ("bloom", 3), ("warden", 3), ("splitter", 4)],
}


def _weighted(rng, table):
    total = sum(w for _, w in table)
    r = rng.uniform(0, total)
    acc = 0
    for item, w in table:
        acc += w
        if r <= acc:
            return item
    return table[-1][0]


def _reachable(walls, start, goals):
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for ox, oy in ORTH:
            n = (x + ox, y + oy)
            if (0 <= n[0] < GRID_W and 0 <= n[1] < GRID_H
                    and n not in walls and n not in seen):
                seen.add(n)
                q.append(n)
    return all(g in seen for g in goals)


def make_walls(rng, count):
    """Scatter walls in the middle rows, keeping the start corner clear and
    every open tile connected."""
    forbidden = {PLAYER_START, (3, 8), (5, 8), (4, 7)}
    for _ in range(50):
        walls = set()
        while len(walls) < count:
            t = (rng.randrange(0, GRID_W), rng.randrange(2, 7))
            if t not in forbidden:
                walls.add(t)
        open_tiles = [(x, y) for x in range(GRID_W) for y in range(GRID_H)
                      if (x, y) not in walls]
        if _reachable(walls, PLAYER_START, open_tiles):
            return walls
    return set()


def enemy_count(rng, act, kind):
    if kind == "boss":
        return 1 + act
    base = {1: (2, 3), 2: (3, 3), 3: (3, 4)}[act]
    n = rng.choice(base)
    return n + 1 if kind == "elite" else n


def _make_combat(rng, act, kind, player, drop=0):
    player.begin_fight()
    walls = make_walls(rng, rng.randrange(3, 8))
    state = GameState(Board(walls=walls), player)
    spots = [(x, y) for y in range(0, 4) for x in range(GRID_W) if (x, y) not in walls]
    rng.shuffle(spots)
    hp_bonus = 2 if kind == "elite" else 0
    if kind == "boss":
        x, y = spots.pop()
        spawn(state, BOSS_FOR_ACT[act], x, y, rng.choice(COLORS))
    adds = enemy_count(rng, act, kind) - (1 if kind == "boss" else 0)
    for _ in range(max(1, adds - drop)):
        k = _weighted(rng, ENEMY_POOL[act])
        x, y = spots.pop()
        spawn(state, k, x, y, rng.choice(COLORS), hp_bonus)
    begin_turn(state)
    return state


REQUIRED_PATHS = 2
VERIFY_ATTEMPTS = 12


def distinct_paths(state, need=REQUIRED_PATHS):
    """How many different styles (tools banned) still win this fight, counted
    up to `need`. Uses the beam solver, so a result below `need` means "not
    found", not "impossible"."""
    from .solver import CONSTRAINTS, solve
    found = []
    for name, allow in CONSTRAINTS.items():
        if name == "any":
            continue
        if solve(state, allow, max_turns=5, beat_beam=14, turn_beam=6).won:
            found.append(name)
            if len(found) >= need:
                break
    return found


def build_combat(rng, act, kind, player, verify=True):
    """Create a fresh GameState for a fight node. `player` carries over.

    With verify=True the room is re-rolled until the solver finds at least
    REQUIRED_PATHS different winning styles for the player's CURRENT kit, so
    no fight is a single forced line. After half the attempts the room gets
    one enemy fewer. The styles found are stored on `state.paths`.
    """
    state = None
    for attempt in range(VERIFY_ATTEMPTS if verify else 1):
        drop = 1 if attempt >= VERIFY_ATTEMPTS // 2 else 0
        state = _make_combat(rng, act, kind, player, drop)
        if not verify:
            state.paths = []
            return state
        state.paths = distinct_paths(state)
        if len(state.paths) >= REQUIRED_PATHS:
            return state
    return state


# ---------------------------------------------------------------- routes

NODE_KINDS = ("fight", "elite", "shop", "rest", "event", "boss")


@dataclass
class Node:
    kind: str
    nexts: list = field(default_factory=list)


@dataclass
class Route:
    layers: list      # list of list[Node]; the last layer is the single boss


def generate_route(rng, act, depth=5):
    layers = []
    sizes = [rng.choice((2, 3)) for _ in range(depth)]
    for li, size in enumerate(sizes):
        layer = []
        for _ in range(size):
            if li == 0:
                kind = "fight" if rng.random() < 0.85 else "event"
            elif li == depth - 1:
                kind = rng.choice(("rest", "shop", "elite"))
            else:
                kind = _weighted(rng, [("fight", 5), ("elite", 2 if li >= 2 else 0),
                                       ("shop", 2), ("rest", 2), ("event", 2)])
            layer.append(Node(kind))
        layers.append(layer)
    layers.append([Node("boss")])
    for li in range(len(layers) - 1):
        cur, nxt = layers[li], layers[li + 1]
        for i, node in enumerate(cur):
            if len(nxt) == 1:
                node.nexts = [0]
                continue
            lo = min(i, len(nxt) - 1)
            options = sorted({lo, max(0, lo - 1), min(len(nxt) - 1, lo + 1)})
            node.nexts = sorted(rng.sample(options, k=min(len(options), rng.choice((1, 2)))))
        covered = {n for node in cur for n in node.nexts}
        for j in range(len(nxt)):          # every node must be reachable
            if j not in covered:
                cur[min(j, len(cur) - 1)].nexts = sorted(
                    set(cur[min(j, len(cur) - 1)].nexts) | {j})
    return Route(layers)
