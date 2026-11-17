"""Room generation (combat boards) and the branching route map."""

from collections import deque
from dataclasses import dataclass, field

from .consts import COLORS, GRID_H, GRID_W, ORTH, PLAYER_START, SHAPES
from .enemies import BOSS_FOR_ACT, KINDS, is_boss, shape_weights, spawn
from .rules import begin_turn
from .state import Board, GameState

ENEMY_POOL = {
    1: [("pawn", 4), ("lancer", 3), ("skew", 2), ("bloom", 2), ("warden", 1)],
    2: [("pawn", 3), ("lancer", 3), ("skew", 2), ("hopper", 2), ("bloom", 2), ("warden", 2),
        ("splitter", 3)],
    3: [("pawn", 2), ("lancer", 3), ("skew", 3), ("hopper", 3), ("bloom", 3), ("warden", 2),
        ("splitter", 3)],
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


def _near_start(t, dist=1):
    return max(abs(t[0] - PLAYER_START[0]), abs(t[1] - PLAYER_START[1])) <= dist


def make_walls(rng, count):
    """Scatter walls between the middle and the edges, keeping the tiles
    around the start clear and every open tile connected."""
    for _ in range(50):
        walls = set()
        while len(walls) < count:
            t = (rng.randrange(1, GRID_W - 1), rng.randrange(1, GRID_H - 1))
            if not _near_start(t):
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


FORMATIONS = {
    "row": ((0, 0), (1, 0), (2, 0), (3, 0)),
    "column": ((0, 0), (0, 1), (0, 2), (0, 3)),
    "diagonal": ((0, 0), (1, 1), (2, 2), (3, 3)),
    "antidiagonal": ((0, 0), (1, -1), (2, -2), (3, -3)),
    "clump": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "spread": ((0, 0), (2, 0), (4, 0), (6, 0)),
    "ring": ((0, 0), (2, 0), (0, 2), (2, 2)),
}
SQUAD_HP = 2              # squad members are tough alone and fragile together: sort them in one cast
SQUAD_KINDS = ("pawn", "lancer", "skew", "hopper", "bloom")   # not splitters: a squad of them
                                                             # breaks into twice as many shards


def _place_squad(rng, state, spots, size, act, hp_bonus, shapes):
    """Place `size` enemies of one kind and one shape in a formation, on free
    spots. Same kind means same AI, so they tend to keep their formation as
    they close in: a group one well-aimed cast can fit. Returns how many
    were placed (0 if no formation fits)."""
    if size < 2:
        return 0
    pool = [(k, w) for k, w in ENEMY_POOL[act] if k in SQUAD_KINDS]
    kind = _weighted(rng, pool)
    shape = _weighted(rng, shapes)
    shared = rng.choice(COLORS)
    names = list(FORMATIONS)
    rng.shuffle(names)
    free = set(spots)
    for name in names:
        offs = FORMATIONS[name][:size]
        anchors = list(spots)
        for ax, ay in anchors:
            tiles = [(ax + ox, ay + oy) for ox, oy in offs]
            if all(t in free for t in tiles):
                for t in tiles:
                    spots.remove(t)
                    color = shared if rng.random() < 0.6 else rng.choice(COLORS)
                    spawn(state, kind, t[0], t[1], color, hp_bonus, shape=shape, squad=1)
                return size
    return 0


def make_portals(rng, walls, pairs):
    """`pairs` pairs of holes, on open tiles away from the start and well
    apart from each other (a hole next to its partner would be pointless)."""
    free = [(x, y) for y in range(GRID_H) for x in range(GRID_W)
            if (x, y) not in walls and not _near_start((x, y), 1)]
    rng.shuffle(free)
    out, used = [], set()
    for _ in range(pairs):
        for a in free:
            if a in used or any(abs(a[0] - u[0]) + abs(a[1] - u[1]) < 2 for u in used):
                continue
            far = [b for b in free if b not in used and b != a
                   and abs(a[0] - b[0]) + abs(a[1] - b[1]) >= 5
                   and a[0] != b[0] and a[1] != b[1]             # never in line: a real shortcut
                   and all(abs(b[0] - u[0]) + abs(b[1] - u[1]) >= 2 for u in used)]
            if far:
                b = far[0]
                out.append((a, b))
                used.update((a, b))
                break
    return out


TWIST_COUNTS = {"springs": 4, "bends": 5, "pools": 3}
STRIPS = {"snow": (3, 3), "currents": (2, 3), "gusts": (2, 3)}    # (how many strips, how long)


def make_twist_tiles(rng, walls, twists, taken):
    """Special floor tiles for a tower's twists (see consts.TWISTS): on open
    tiles, away from the start, not on top of each other. Snow lies in
    drifts and currents and gusts run in channels: short straight strips."""
    free = [(x, y) for y in range(GRID_H) for x in range(GRID_W)
            if (x, y) not in walls and (x, y) not in taken and not _near_start((x, y), 1)]
    rng.shuffle(free)
    tiles = {}
    ok = set(free)
    for twist in twists:
        if twist in STRIPS:
            count, length = STRIPS[twist]
            made = 0
            for start in free:
                if made >= count:
                    break
                d = rng.choice(((1, 0), (0, 1), (-1, 0), (0, -1)))
                strip = [(start[0] + d[0] * k, start[1] + d[1] * k) for k in range(length)]
                if not all(t in ok and t not in tiles for t in strip):
                    continue
                for t in strip:
                    if twist == "snow":
                        tiles[t] = "snow"
                    else:
                        tiles[t] = "%s:%d,%d" % (twist[:-1], d[0], d[1])
                made += 1
            continue
        n = TWIST_COUNTS.get(twist, 0)
        for i in range(n):
            spot = next((t for t in free if t not in tiles and
                         all(abs(t[0] - u[0]) + abs(t[1] - u[1]) > 1 for u in tiles)), None)
            if spot is None:
                break
            if twist == "springs":
                tiles[spot] = "spring"
            elif twist == "bends":
                tiles[spot] = rng.choice(("bend/", "bend\\"))
            elif twist == "pools":
                tiles[spot] = "pool:" + ("R", "G", "B")[i % 3]
    return tiles


def _make_combat(rng, act, kind, player, drop=0, shapes=None, boss=None, tier=0, portals=0, twists=()):
    player.begin_fight()
    walls = make_walls(rng, rng.randrange(3, 8))
    holes = make_portals(rng, walls, portals) if portals else []
    taken = {t for pair in holes for t in pair}
    special = make_twist_tiles(rng, walls, [w for w in twists if w != "holes"], taken) if twists else {}
    state = GameState(Board(walls=walls, portals=holes, tiles=special), player)
    taken |= set(special)
    # the Set starts out at the edges, all around you (not on the holes)
    spots = [(x, y) for y in range(GRID_H) for x in range(GRID_W)
             if (x, y) not in walls and not _near_start((x, y), 2) and (x, y) not in taken]
    rng.shuffle(spots)
    hp_bonus = (2 if kind == "elite" else 0) + tier
    if kind == "boss":
        # Keepers start near the middle: fights are about speed, not a long walk
        middle = [t for t in spots if not _near_start(t, 3) and 2 <= t[0] <= 6]
        x, y = (middle or spots)[0]
        spots.remove((x, y))
        spawn(state, boss or BOSS_FOR_ACT[act], x, y, rng.choice(COLORS))
    adds = max(1, enemy_count(rng, act, kind) - (1 if kind == "boss" else 0) - drop + min(tier, 2))
    shapes = list(shapes) if shapes else list(zip(SHAPES, shape_weights(act)))
    # the Set arrives in sets: a squad of one kind and one shape, in formation
    size = rng.choice((3, 3, 4))
    # squads are tougher than loners; in a Hard Set a little more, but not the full
    # Hard Set bonus on top (that made squads of 8-HP shapes)
    squad = _place_squad(rng, state, spots, size, act, SQUAD_HP + (1 if hp_bonus else 0), shapes)
    for _ in range(max(0, adds - squad + 1) if squad else adds):
        k = _weighted(rng, ENEMY_POOL[act])
        x, y = spots.pop()
        spawn(state, k, x, y, rng.choice(COLORS), hp_bonus, shape=_weighted(rng, shapes))
    # what you can learn by winning here: the patterns this Set fights with
    state.seen_patterns = {KINDS[e.kind]["pattern"] for e in state.enemies}
    for e in state.enemies:
        if "summon" in KINDS[e.kind]:
            state.seen_patterns.add(KINDS[KINDS[e.kind]["summon"]]["pattern"])
    begin_turn(state)
    return state


REQUIRED_PATHS = 2
VERIFY_ATTEMPTS = 12


SOLVE_KW = {"max_turns": 5, "beat_beam": 14, "turn_beam": 6}


def _solve_kw(state):
    if any(is_boss(e.kind) for e in state.enemies):
        return dict(SOLVE_KW, max_turns=6)       # Keeper fights run a little longer
    return SOLVE_KW


def distinct_paths(state, need=REQUIRED_PATHS):
    """How many different styles (tools banned) still win this fight, counted
    up to `need`. Uses the beam solver, so a result below `need` means "not
    found", not "impossible"."""
    from .solver import CONSTRAINTS, constraints_for, solve
    found = []
    for name in constraints_for(state.player):
        if solve(state, CONSTRAINTS[name], **_solve_kw(state)).won:
            found.append(name)
            if len(found) >= need:
                break
    return found


def find_par(state, styles=()):
    """Par: the fewest turns the solver can win in, unconstrained or in any
    of the given styles (beam search is not monotonic, so a ban can find a
    win the open search pruned). None if it finds no win at all."""
    from .solver import CONSTRAINTS, solve
    best = None
    for name in ("any",) + tuple(styles):
        res = solve(state, CONSTRAINTS[name], **_solve_kw(state))
        if res.won and (best is None or res.turns < best):
            best = res.turns
    return best


def build_combat(rng, act, kind, player, verify=True, shapes=None, boss=None, tier=0, portals=0,
                 twists=()):
    """Create a fresh GameState for a fight node. `player` carries over.

    With verify=True the room is re-rolled until the solver finds at least
    REQUIRED_PATHS different winning styles for the player's CURRENT kit, so
    no fight is a single forced line. After half the attempts the room gets
    one enemy fewer. The styles found are stored on `state.paths`, and the
    solver's fewest turns to win on `state.par`. `shapes` is an optional
    [(shape, weight)] the Set here may be cut as (see run.shapes_for), and
    `boss` overrides which Keeper a boss room has, and `tier` makes every
    shape a little tougher and the Set one bigger (the towers in the Meadow),
    `portals` is how many pairs of holes the floor has (see state.Board), and
    `twists` which other special tiles it has (consts.TWISTS).
    """
    state = None
    for attempt in range(VERIFY_ATTEMPTS if verify else 1):
        drop = 1 if attempt >= VERIFY_ATTEMPTS // 2 else 0
        state = _make_combat(rng, act, kind, player, drop, shapes, boss, tier, portals, twists)
        if not verify:
            state.paths = []
            state.par = None
            return state
        state.paths = distinct_paths(state)
        if len(state.paths) >= REQUIRED_PATHS:
            break
    state.par = find_par(state, state.paths)
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


COMBAT = ("fight", "elite")
MIN_FIGHTS = 3            # on every path from the start to the Keeper (out of `depth` rooms)
MAX_ELITES = 2


def route_paths(route):
    """Every path through the route as a list of node kinds (the Keeper excluded)."""
    layers = route.layers
    out = []

    def walk(li, i, kinds):
        node = layers[li][i]
        kinds = kinds + [node.kind]
        if li == len(layers) - 2:
            out.append(kinds)
            return
        for j in node.nexts:
            walk(li + 1, j, kinds)

    for i in range(len(layers[0])):
        walk(0, i, [])
    return out


def path_ok(kinds):
    """A path is fair if it has enough fights, its easy rooms are spread out,
    and it isn't all Hard Sets either."""
    fights = sum(k in COMBAT for k in kinds)
    elites = kinds.count("elite")
    calm_run = any(a not in COMBAT and b not in COMBAT for a, b in zip(kinds, kinds[1:]))
    return fights >= MIN_FIGHTS and elites <= MAX_ELITES and not calm_run


def _random_route(rng, depth):
    layers = []
    sizes = [rng.choice((2, 3)) for _ in range(depth)]
    for li, size in enumerate(sizes):
        layer = []
        for _ in range(size):
            if li == 0:
                kind = "fight"                      # every floor opens with a fight
            elif li == depth - 1:
                kind = rng.choice(("rest", "shop", "elite", "fight"))
            else:
                kind = _weighted(rng, [("fight", 5), ("elite", 2 if li >= 2 else 0),
                                       ("shop", 2), ("rest", 2), ("event", 3)])
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


def generate_route(rng, act, depth=5):
    """A floor map where every path is fair (see path_ok): you can choose an
    easier way up, but never one without fights. Tries random maps until one
    is fair, then, failing that, turns the offending calm rooms into fights."""
    route = None
    for _ in range(200):
        route = _random_route(rng, depth)
        if all(path_ok(k) for k in route_paths(route)):
            return route
    for _ in range(depth * 3):           # repair: the first calm room on a bad path fights
        bad = next((k for k in route_paths(route) if not path_ok(k)), None)
        if bad is None:
            break
        for li, layer in enumerate(route.layers[:-1]):
            for node in layer:
                if node.kind not in COMBAT and node.kind == bad[li]:
                    node.kind = "fight"
                    break
            else:
                continue
            break
    return route
