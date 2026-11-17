"""Enemy definitions and the AI that plans their orders.

Who they are: the Set. Shapes that were cut once and intend to stay exactly
that way. A shape that grows a side leaves a hole in the Sorter, and the Set
are afraid of holes, so they come to knock you back into your slot.

An enemy has three independent parts, mirroring your casts:
    kind    how it behaves, and which PATTERN it attacks with (the same
            patterns you use: Halo, Beam, Slant, Leap, Lob)
    shape   what your light must be cut to fit to touch it
    colour  what it absorbs (its own) and what unmakes it (the opposite)
Keepers (bosses) change shape every beat on a schedule you can see, so
hitting one is a matter of timing.

At the start of every turn each enemy gets one order per beat. Orders are
RELATIVE to where the enemy stands when the beat resolves, so pushing,
stunning or dodging an enemy changes what it hits. That is what makes
planning meaningful: everything is visible and deterministic.

Order forms:
    ("wait",)
    ("move", dx, dy)
    ("hit", dx, dy, dmg)              single tile (kept for scripted tests)
    ("halo", dmg)                     the 8 tiles around it
    ("leap", dmg)                     the 8 tiles an L-step away from it
    ("line", dx, dy, dmg, length)     a ray: Beam (orthogonal) or Slant (diagonal)
    ("splash", cx, cy, dmg)           Lob: a plus centred at an offset
    ("shield", amount)                shield orthogonally adjacent allies
    ("summon", kind)                  spawn a minion next to the summoner
"""

from .consts import BEATS, COLORS, DIAG, KNIGHT, ORTH, RING

ORDER_PATTERN = {"halo": "halo", "leap": "leap", "splash": "lob"}   # "line" depends on dx/dy

KINDS = {
    "pawn": {"label": "Stomper", "hp": 4, "shape": "square", "dmg": 2, "pattern": "halo",
             "mark": "feet", "desc": "Stomps up next to you, then hits all 8 tiles around it."},
    "lancer": {"label": "Lancer", "hp": 3, "shape": "triangle", "dmg": 2, "pattern": "beam",
               "mark": "horn", "desc": "Lines up with you, then fires a Beam 3 tiles long."},
    "skew": {"label": "Skew", "hp": 3, "shape": "triangle", "dmg": 2, "pattern": "slant",
             "mark": "sash", "desc": "Only ever looks at you sideways. Fires a Slant along a diagonal."},
    "hopper": {"label": "Hopper", "hp": 3, "shape": "circle", "dmg": 2, "pattern": "leap",
               "mark": "spring", "desc": "Keeps an L-step away, then Leaps: hits every L-step tile."},
    "bloom": {"label": "Bloom", "hp": 4, "shape": "circle", "dmg": 2, "pattern": "lob",
              "mark": "sprout", "desc": "Took root instead of rolling. Lobs a plus onto you."},
    "warden": {"label": "Warden", "hp": 5, "shape": "square", "dmg": 1, "pattern": "halo",
               "mark": "frame", "desc": "Gives the shapes beside it 1 shield, then hits the 8 tiles around it."},
    "splitter": {"label": "Splitter", "hp": 4, "shape": "square", "dmg": 2, "pattern": "halo",
                 "mark": "seam",
                 "desc": "Has a seam. Knocked loose, it falls into two Shards of the same shape."},
    "shard": {"label": "Shard", "hp": 1, "shape": "triangle", "dmg": 1, "pattern": "beam",
              "size": 0.75, "desc": "Fragile; flicks a Beam 2 tiles long."},
    # Keepers: "shape" is how they look on the map; "shapes" is the beat-by-beat
    # schedule they cycle through in a fight (shifted by one each turn).
    "colossus": {"face": "strict", "label": "Four-Keeper", "hp": 16, "shape": "square", "dmg": 3,
                 "boss": True, "line": 2, "summon": "pawn", "pattern": "halo",
                 "shapes": ("square", "square", "triangle", "triangle"),
                 "script": ("approach", "halo", "line", "summon"),
                 "desc": "Keeper of the Four-Door. Changes shape every beat and colour every turn."},
    "oracle": {"face": "haughty", "label": "Five-Keeper", "hp": 20, "shape": "pentagon", "dmg": 3,
               "boss": True, "line": 3, "splash": 3, "summon": "lancer", "pattern": "lob",
               "shapes": ("circle", "triangle", "circle", "square"),
               "script": ("splash", "approach", "halo", "line"),
               "desc": "Keeper of the Five-Door. Changes shape every beat and colour every turn."},
    "prism": {"face": "melancholy", "label": "Stillwheel", "hp": 24, "shape": "circle", "dmg": 4,
              "boss": True, "line": 3, "splash": 3, "summon": "bloom", "pattern": "lob",
              "shapes": ("circle", "circle", "square", "triangle"),
              "script": ("splash", "line", "halo", "summon"),
              "desc": "The last circle that never rolled. Changes shape every beat."},
    # the Leaning Tower's guardian (see consts.TOWERS)
    "latch": {"face": "worried", "label": "The Latch", "hp": 22, "shape": "square", "dmg": 3,
              "boss": True, "line": 3, "splash": 3, "summon": "skew", "pattern": "halo",
              "shapes": ("square", "triangle", "circle", "square"),
              "script": ("approach", "halo", "line", "summon"),
              "desc": "Keeps the window shut. It means well: it thinks the hexagon might fall."},
    # the Hollow Tree's: a tangle of roots that keeps everything tied where it grew
    "knot": {"face": "stubborn", "label": "The Knot", "hp": 24, "shape": "circle", "dmg": 3,
             "boss": True, "line": 3, "splash": 3, "summon": "bloom", "pattern": "lob",
             "shapes": ("circle", "square", "circle", "triangle"),
             "script": ("splash", "approach", "summon", "halo"),
             "desc": "Holds the tree together. Thinks everything should stay tied where it grew."},
    "cap": {"face": "giddy", "label": "The Cap", "hp": 24, "shape": "circle", "dmg": 3,
            "boss": True, "line": 3, "splash": 3, "summon": "hopper", "pattern": "halo",
            "shapes": ("circle", "triangle", "circle", "square"),
            "script": ("approach", "halo", "summon", "line"),
            "desc": "Keeps everything bouncing. Thinks coming down is dangerous."},
    "rime": {"face": "stern", "label": "The Rime", "hp": 24, "shape": "square", "dmg": 3,
             "boss": True, "line": 3, "splash": 3, "summon": "warden", "pattern": "beam",
             "shapes": ("square", "square", "circle", "triangle"),
             "script": ("line", "approach", "halo", "summon"),
             "desc": "Keeps everything exactly as it froze. Thinks change is just melting."},
    "hour": {"face": "fussy", "label": "The Hourglass", "hp": 24, "shape": "triangle", "dmg": 3,
             "boss": True, "line": 3, "splash": 3, "summon": "skew", "pattern": "lob",
             "shapes": ("triangle", "square", "triangle", "circle"),
             "script": ("splash", "line", "approach", "halo"),
             "desc": "Keeps every grain in its place. Thinks time stops if the pointer leaves."},
    "focus": {"face": "intense", "label": "The Focus", "hp": 24, "shape": "triangle", "dmg": 3,
              "boss": True, "line": 3, "splash": 3, "summon": "lancer", "pattern": "beam",
              "shapes": ("triangle", "circle", "square", "triangle"),
              "script": ("line", "halo", "approach", "splash"),
              "desc": "Bends all the light into one straight beam. Thinks that's the only way."},
    "beacon": {"face": "proud", "label": "The Beacon", "hp": 26, "shape": "circle", "dmg": 3,
               "boss": True, "line": 3, "splash": 3, "summon": "bloom", "pattern": "halo",
               "shapes": ("circle", "square", "triangle", "circle"),
               "script": ("halo", "line", "splash", "summon"),
               "desc": "Thinks the lamp needs its keeper, always."},
    "vane": {"face": "dizzy", "label": "The Vane", "hp": 26, "shape": "square", "dmg": 3,
             "boss": True, "line": 3, "splash": 3, "summon": "hopper", "pattern": "slant",
             "shapes": ("square", "triangle", "circle", "circle"),
             "script": ("approach", "line", "halo", "summon"),
             "desc": "Turns with the wind. Thinks everything should."},
}

SHARD_REACH = 2
GRID = 9                  # longest line a Keeper will walk to line up along
SLANT_REACH = 3

BOSS_FOR_ACT = {1: "colossus", 2: "oracle", 3: "prism"}


def is_boss(kind):
    return bool(KINDS[kind].get("boss"))


def default_shape(kind):
    spec = KINDS[kind]
    return spec["shapes"][0] if spec.get("boss") else spec["shape"]


def spawn(state, kind, x, y, color, hp_bonus=0, shape=None, squad=None):
    e = state.add_enemy(kind, x, y, color, KINDS[kind]["hp"] + hp_bonus,
                        shape or default_shape(kind))
    e.squad = squad
    return e


def boss_shape(state, e, beat):
    """A Keeper's shape during `beat` of the current turn."""
    shapes = KINDS[e.kind]["shapes"]
    return shapes[(beat + state.turn - 1) % len(shapes)]


def order_pattern(order):
    """Which of the shared patterns an attack order uses (None if not an attack)."""
    if order[0] == "line":
        return "beam" if order[1] == 0 or order[2] == 0 else "slant"
    return ORDER_PATTERN.get(order[0])


def _sign(v):
    return (v > 0) - (v < 0)


def _passable(state, x, y):
    b = state.board
    return 0 <= x < b.w and 0 <= y < b.h and (x, y) not in b.walls


def _step_toward(state, x, y, tx, ty):
    """One step from (x, y) toward (tx, ty): the straight way if it's open,
    otherwise around walls. None if there is no way at all."""
    dx, dy = tx - x, ty - y
    if abs(dx) >= abs(dy):
        options = [(_sign(dx), 0), (0, _sign(dy))]
    else:
        options = [(0, _sign(dy)), (_sign(dx), 0)]
    for ox, oy in options:
        if (ox, oy) == (0, 0):
            continue
        if _passable(state, x + ox, y + oy) and (x + ox, y + oy) != (tx, ty):
            return ox, oy
    near = [(tx + ox, ty + oy) for ox, oy in ORTH]
    return _step_to(state, x, y, near)


def _line_spots(px, py, length):
    """Tiles from which a straight line of `length` reaches (px, py)."""
    return [(px + ox * k, py + oy * k) for ox, oy in ORTH for k in range(1, length + 1)]


def _step_to(state, x, y, cells):
    """The first step of a shortest walk (around walls, never through the
    player) from (x, y) to any of `cells`. None if none can be reached or
    (x, y) is already one of them."""
    goals = {c for c in cells if _passable(state, *c)}
    if (x, y) in goals or not goals:
        return None
    avoid = (state.player.x, state.player.y)
    dist = {c: 0 for c in goals if c != avoid}
    frontier = list(dist)
    while frontier:                              # distances outward from the goals
        nxt = []
        for cx, cy in frontier:
            for ox, oy in ORTH:
                n = (cx + ox, cy + oy)
                if n not in dist and n != avoid and _passable(state, *n):
                    dist[n] = dist[(cx, cy)] + 1
                    nxt.append(n)
        frontier = nxt
    best, best_d = None, dist.get((x, y))
    for ox, oy in ORTH:
        d = dist.get((x + ox, y + oy))
        if d is not None and (best_d is None or d < best_d):
            best, best_d = (ox, oy), d
    return best


def _follow_step(state, x, y, lead):
    """Copy a squad leader's step, if it can be copied from here."""
    if lead is None:
        return None
    nx, ny = x + lead[0], y + lead[1]
    if not _passable(state, nx, ny) or (nx, ny) == (state.player.x, state.player.y):
        return None
    return lead


def _walk_then(state, e, ready, attack, step, cooldown=1, follow=None):
    """Shared planner: each beat, attack if ready(x, y) (then rest for
    `cooldown` beats), otherwise take step(x, y) (or wait if stuck).
    With `follow` (a leader's per-beat steps), walking copies the leader so
    a squad keeps its formation."""
    x, y = e.x, e.y
    orders = []
    cd = 0
    for beat in range(BEATS):
        if ready(x, y):
            if cd > 0:
                orders.append(("wait",))
                cd -= 1
            else:
                orders.append(attack(x, y))
                cd = cooldown
            continue
        s = _follow_step(state, x, y, follow[beat]) if follow is not None else step(x, y)
        if s is None:
            orders.append(("wait",))
        else:
            orders.append(("move", s[0], s[1]))
            x += s[0]
            y += s[1]
        if cd > 0:
            cd -= 1
    return orders


def _halo_orders(state, e, dmg, follow=None):
    """Walk until you are in one of the 8 tiles around it, then Halo."""
    px, py = state.player.x, state.player.y
    return _walk_then(state, e,
                      lambda x, y: max(abs(px - x), abs(py - y)) == 1,
                      lambda x, y: ("halo", dmg),
                      lambda x, y: _step_toward(state, x, y, px, py), follow=follow)


def _lancer_orders(state, e, dmg, length=3, follow=None):
    px, py = state.player.x, state.player.y

    def ready(x, y):
        return (x == px) != (y == py) and abs(px - x) + abs(py - y) <= length

    spots = _line_spots(px, py, length)

    def step(x, y):
        return _step_to(state, x, y, spots)

    return _walk_then(state, e, ready,
                      lambda x, y: ("line", _sign(px - x), _sign(py - y), dmg, length), step,
                      follow=follow)


def _skew_orders(state, e, dmg, length=SLANT_REACH, follow=None):
    px, py = state.player.x, state.player.y

    def ready(x, y):
        return abs(px - x) == abs(py - y) and 0 < abs(px - x) <= length

    spots = [(px + ox * k, py + oy * k) for ox, oy in DIAG for k in range(1, length + 1)]
    return _walk_then(state, e, ready,
                      lambda x, y: ("line", _sign(px - x), _sign(py - y), dmg, length),
                      lambda x, y: _step_to(state, x, y, spots), follow=follow)


def _hopper_orders(state, e, dmg, follow=None):
    px, py = state.player.x, state.player.y
    spots = [(px + ox, py + oy) for ox, oy in KNIGHT]
    return _walk_then(state, e,
                      lambda x, y: (x - px, y - py) in KNIGHT,
                      lambda x, y: ("leap", dmg),
                      lambda x, y: _step_to(state, x, y, spots), follow=follow)


def _bloom_orders(state, e, dmg, reach=3, follow=None):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    cd = 1                     # wind-up beat: lets you step two tiles clear of the burst
    for beat in range(BEATS):
        dist = abs(px - x) + abs(py - y)
        if dist <= reach:
            if cd > 0:
                orders.append(("wait",))
                cd -= 1
            else:
                orders.append(("splash", px - x, py - y, dmg))
                cd = 1
            continue
        if follow is not None:
            step = _follow_step(state, x, y, follow[beat])
        else:
            step = _step_toward(state, x, y, px, py)
        if step is None:
            orders.append(("wait",))
        else:
            orders.append(("move", step[0], step[1]))
            x += step[0]
            y += step[1]
        if cd > 0:
            cd -= 1
    return orders


def _warden_orders(state, e, dmg):
    orders = [("shield", 1)]
    rest = _halo_orders(state, e, dmg)
    # the first beat is spent shielding, so the walk starts one beat late
    return orders + rest[:BEATS - 1]


def _boss_orders(state, e, spec):
    px, py = state.player.x, state.player.y
    x, y = e.x, e.y
    orders = []
    for beat in range(BEATS):
        action = spec["script"][beat % len(spec["script"])]
        dist = abs(px - x) + abs(py - y)
        aligned = (x == px) != (y == py)
        order = None
        step = None
        if action == "approach":
            if dist > 1:
                step = _step_toward(state, x, y, px, py)
        elif action == "halo":
            if max(abs(px - x), abs(py - y)) == 1:
                order = ("halo", spec["dmg"])
            else:
                step = _step_toward(state, x, y, px, py)
        elif action == "line":
            if aligned:
                order = ("line", _sign(px - x), _sign(py - y), spec["line"], 3)
            else:
                step = _step_to(state, x, y, _line_spots(px, py, GRID))
        elif action == "splash":
            if dist <= 4:
                order = ("splash", px - x, py - y, spec.get("splash", spec["dmg"]))
            else:
                step = _step_toward(state, x, y, px, py)
        elif action == "summon":
            if state.turn % 2 == 0:
                order = ("summon", spec["summon"])
        if order is None and step:
            order = ("move", step[0], step[1])
            x += step[0]
            y += step[1]
        orders.append(order or ("wait",))
    return orders


def _orders_for(state, e, follow=None):
    spec = KINDS[e.kind]
    dmg = spec["dmg"]
    if spec.get("boss"):
        return _boss_orders(state, e, spec)
    if e.kind in ("pawn", "splitter"):
        return _halo_orders(state, e, dmg, follow=follow)
    if e.kind == "shard":
        return _lancer_orders(state, e, dmg, length=SHARD_REACH, follow=follow)
    if e.kind == "lancer":
        return _lancer_orders(state, e, dmg, follow=follow)
    if e.kind == "skew":
        return _skew_orders(state, e, dmg, follow=follow)
    if e.kind == "hopper":
        return _hopper_orders(state, e, dmg, follow=follow)
    if e.kind == "bloom":
        return _bloom_orders(state, e, dmg, follow=follow)
    if e.kind == "warden":
        return _warden_orders(state, e, dmg)
    return [("wait",)] * BEATS     # pragma: no cover - a new kind with no AI


def plan_orders(state):
    """Give every enemy its orders for the coming turn. A squad's leader (its
    lowest id) walks its own way; the others copy its steps, so the set keeps
    its formation, and each still attacks on its own when you are in reach."""
    leaders = {}
    for e in sorted(state.enemies, key=lambda en: en.id):
        follow = None
        if e.squad is not None:
            lead = leaders.get(e.squad)
            if lead is None:
                leaders[e.squad] = e
            else:
                follow = [(o[1], o[2]) if o[0] == "move" else None for o in lead.orders]
        e.orders = _orders_for(state, e, follow)


def halo_tiles(x, y):
    return [(x + ox, y + oy) for ox, oy in RING]


def leap_tiles(x, y):
    return [(x + ox, y + oy) for ox, oy in KNIGHT]


def boss_color(state, e):
    return COLORS[(state.turn + e.id) % len(COLORS)]


def shape_weights(act):
    """Which shapes the Set on each floor tends to be. Rounder as you climb."""
    return {1: (3, 2, 1), 2: (2, 3, 2), 3: (1, 2, 3)}.get(act, (1, 1, 1))

