"""The rules engine. Pure functions over GameState, no pygame, no randomness.

A turn is BEATS beats long. Each beat the player acts first (move, cast or
wait), then every enemy carries out its order for that beat. At the end of the
turn burn ticks, the palette regenerates and the next turn's orders are
planned. Because nothing is random, the UI can preview a plan exactly by
running it on a clone, and the solver can search plans.

A cast is PATTERN (where) + SHAPE (what it fits) + COLOUR (what it does).
It only touches enemies whose shape matches; the light passes through the
rest. Each pattern can be used once per turn.

Damage for each enemy a cast lands on:
    (colour base + group bonus) x2 if the colour is opposite to the enemy's
    group bonus = GROUP_STEP x (number of shapes the cast landed on - 1), +facet bonus
Casting the SAME colour as the enemy is absorbed (no effect).
"""

from .consts import (BEATS, BEAM_LEN, COLORS, COMPONENTS, DIAG, KNIGHT, LOB_DIST, MAX_SHIELD,
                     OPPOSITE, ORTH, PATTERNS, RING, SHAPES, SLANT_LEN)
from .enemies import (boss_color, boss_shape, halo_tiles, is_boss, leap_tiles, plan_orders,
                      spawn)
from .state import wait

MAX_ENEMIES = 7
ENEMY_SHIELD_CAP = 3


def sign(v):
    return (v > 0) - (v < 0)


def in_bounds(board, x, y):
    return 0 <= x < board.w and 0 <= y < board.h


def tile_open(board, x, y):
    return in_bounds(board, x, y) and (x, y) not in board.walls


def tile_free(state, x, y):
    p = state.player
    return (tile_open(state.board, x, y) and (x, y) != (p.x, p.y)
            and state.enemy_at(x, y) is None)


def line_tiles(board, ox, oy, dx, dy, length, pierce=0):
    """A ray from (ox, oy): stops at the edge, and at walls once `pierce`
    of them have been passed through. A straight ray (a Beam, yours or
    theirs) that meets a crystal facet turns a quarter turn, like a roll."""
    tiles = []
    x, y = ox, oy
    bends = board.tiles if (dx == 0 or dy == 0) else {}
    for _ in range(length):
        x, y = x + dx, y + dy
        if not in_bounds(board, x, y):
            break
        if (x, y) in board.walls:
            if pierce <= 0:
                break
            pierce -= 1
            continue
        tiles.append((x, y))
        kind = bends.get((x, y))
        if kind in ("bend/", "bend\\"):
            dx, dy = (-dy, -dx) if kind == "bend/" else (dy, dx)
    return tiles


def pattern_offsets(pattern, dx=0, dy=0):
    """The pattern's tiles relative to the caster, ignoring the board (rays in
    order, nearest first). None if the aim does not suit the pattern."""
    if pattern == "beam":
        if (dx, dy) not in ORTH:
            return None
        return [(dx * i, dy * i) for i in range(1, BEAM_LEN + 1)]
    if pattern == "slant":
        if (dx, dy) not in DIAG:
            return None
        return [(dx * i, dy * i) for i in range(1, SLANT_LEN + 1)]
    if pattern == "halo":
        return list(RING)
    if pattern == "leap":
        return list(KNIGHT)
    if pattern == "lob":
        if (dx, dy) not in [(ox * LOB_DIST, oy * LOB_DIST) for ox, oy in ORTH]:
            return None
        return [(dx, dy)] + [(dx + ox, dy + oy) for ox, oy in ORTH]
    return None


def pattern_aims(pattern):
    """Every legal aim for a pattern."""
    aim = PATTERNS[pattern]["aim"]
    if aim == "orth":
        return list(ORTH)
    if aim == "diag":
        return list(DIAG)
    if aim == "far":
        return [(ox * LOB_DIST, oy * LOB_DIST) for ox, oy in ORTH]
    return [(0, 0)]


def pattern_tiles(state, pattern, dx=0, dy=0):
    """Board tiles a cast would cover, or None if the aim is not legal.
    Rays (Beam, Slant) stop at walls; Leap jumps over them."""
    p, board = state.player, state.board
    if pattern in ("beam", "slant"):
        if pattern_offsets(pattern, dx, dy) is None:
            return None
        length = BEAM_LEN if pattern == "beam" else SLANT_LEN
        return line_tiles(board, p.x, p.y, dx, dy, length, p.mods["pierce"]) or None
    offs = pattern_offsets(pattern, dx, dy)
    if offs is None:
        return None
    if pattern == "lob" and not tile_open(board, p.x + dx, p.y + dy):
        return None
    tiles = [(p.x + ox, p.y + oy) for ox, oy in offs]
    tiles = [t for t in tiles if tile_open(board, *t) and t != (p.x, p.y)]
    tiles.sort(key=lambda t: (abs(t[0] - p.x) + abs(t[1] - p.y), t[1], t[0]))
    return tiles or None


def fitting_targets(state, tiles, shape):
    """Enemies on `tiles` that a cast cut to `shape` would touch."""
    found = []
    for t in tiles:
        e = state.enemy_at(*t)
        if e is not None and e.hp > 0 and e.shape == shape:
            found.append(e)
    return found


def can_afford(player, color):
    return all(player.palette[c] >= 1 for c in set(COMPONENTS[color]))


def validate_action(state, a):
    """(ok, message). The message is always shown to the player when not ok."""
    p = state.player
    if state.outcome != "ongoing":
        return False, "The fight is over."
    if a.kind == "wait":
        return True, ""
    if a.kind == "move":
        nx, ny = p.x + a.dx, p.y + a.dy
        if abs(a.dx) + abs(a.dy) != 1:
            return False, "Move one tile at a time."
        if not in_bounds(state.board, nx, ny):
            return False, "That is the edge of the room."
        if (nx, ny) in state.board.walls:
            return False, "A wall blocks that tile."
        if state.enemy_at(nx, ny) and not p.rolls:       # a circle may roll straight into one
            return False, "An enemy is standing there."
        return True, ""
    if a.kind == "cast":
        if a.pattern not in PATTERNS or a.color not in COLORS or a.shape not in SHAPES:
            return False, "Pick a pattern, a shape and a colour."
        name = PATTERNS[a.pattern]["name"]
        if a.pattern not in p.patterns:
            return False, "You haven't learned %s yet." % name
        if a.pattern in p.used:
            return False, "%s is already used this turn. Each pattern once per turn." % name
        if not can_afford(p, a.color):
            need = "+".join(sorted(set(COMPONENTS[a.color])))
            return False, "Not enough charges (%s needed)." % need
        if pattern_tiles(state, a.pattern, a.dx, a.dy) is None:
            aim = PATTERNS[a.pattern]["aim"]
            if aim == "orth":
                return False, "Beam needs a straight line: up, down, left or right (not into a wall)."
            if aim == "diag":
                return False, "Slant needs a diagonal (not into a wall)."
            if aim == "far":
                return False, "Lob lands 3 tiles away in a straight line, on an open tile."
            return False, "Nowhere for that to go."
        return True, ""
    return False, "Unknown action."


def emit(ev, **kw):
    if ev is not None:
        ev.append(kw)


# ---------------------------------------------------------------- damage

def damage_enemy(state, e, amount, ev, beat):
    if amount <= 0 or e.hp <= 0:
        return 0
    soaked = min(e.shield, amount)
    e.shield -= soaked
    took = amount - soaked
    e.hp -= took
    emit(ev, t="dmg", who=e.id, amount=amount, took=took, pos=(e.x, e.y), beat=beat)
    return took


def damage_player(state, amount, ev, beat):
    p = state.player
    soaked = min(p.shield, amount)
    p.shield -= soaked
    took = amount - soaked
    p.hp -= took
    emit(ev, t="dmg", who="player", amount=amount, took=took, pos=(p.x, p.y), beat=beat)
    return took


def reap(state, ev, beat):
    for e in list(state.enemies):
        if e.hp > 0:
            continue
        state.enemies.remove(e)
        emit(ev, t="kill", who=e.id, kind=e.kind, pos=(e.x, e.y), beat=beat)
        if e.kind == "splitter":
            made = 0
            for ox, oy in ORTH:
                if made == 2 or len(state.enemies) >= MAX_ENEMIES:
                    break
                x, y = e.x + ox, e.y + oy
                if tile_free(state, x, y):
                    s = spawn(state, "shard", x, y, e.color, shape=e.shape)
                    emit(ev, t="spawn", who=s.id, kind="shard", pos=(x, y), beat=beat)
                    made += 1


def check_outcome(state):
    if state.player.hp <= 0:
        state.outcome = "defeat"
    elif not state.enemies:
        state.outcome = "victory"


def push_enemy(state, e, dx, dy, ev, beat):
    nx, ny = e.x + dx, e.y + dy
    blocker = state.enemy_at(nx, ny)
    bonus = state.player.mods["collision_bonus"]
    if tile_free(state, nx, ny):
        emit(ev, t="push", who=e.id, frm=(e.x, e.y), to=(nx, ny), beat=beat)
        e.x, e.y = nx, ny
        return
    emit(ev, t="collision", who=e.id, pos=(e.x, e.y), beat=beat)
    damage_enemy(state, e, 2 + bonus, ev, beat)
    if blocker is not None:
        damage_enemy(state, blocker, 2 + bonus, ev, beat)


def push_direction(state, e):
    p = state.player
    dx, dy = e.x - p.x, e.y - p.y
    if abs(dx) >= abs(dy):
        return sign(dx), 0
    return 0, sign(dy)


# ----------------------------------------------------------------- casts

BASE_DAMAGE = {"R": 3, "G": 2, "B": 1, "Y": 1, "C": 2, "M": 4}
GROUP_STEP = 2            # damage added to every hit, per extra shape one cast fits


def group_bonus(player, fits):
    """Extra damage for landing on several shapes at once."""
    if fits < 2:
        return 0
    return GROUP_STEP * (fits - 1) + player.mods["group_bonus"]


def player_cast(state, a, beat, ev):
    p = state.player
    tiles = pattern_tiles(state, a.pattern, a.dx, a.dy)
    for c in set(COMPONENTS[a.color]):
        p.palette[c] -= 1
    p.used = p.used | {a.pattern}

    targets = fitting_targets(state, tiles, a.shape)
    landed = []
    for e in targets:
        if a.color == e.color:
            emit(ev, t="absorb", who=e.id, pos=(e.x, e.y), beat=beat)
        else:
            landed.append(e)
    bonus = group_bonus(p, len(landed))
    emit(ev, t="cast", pattern=a.pattern, shape=a.shape, color=a.color, tiles=list(tiles),
         fits=len(landed), bonus=bonus, pos=(p.x, p.y), beat=beat)

    hit_positions = []
    first_hit = None
    col = a.color
    for e in landed:
        if e.hp <= 0:
            continue
        weak = OPPOSITE[col] == e.color
        if first_hit is None:
            first_hit = e
        hit_positions.append((e.x, e.y))
        base = BASE_DAMAGE[col] + (p.mods["red_bonus"] if col == "R" else 0)
        damage_enemy(state, e, (base + bonus) * (2 if weak else 1), ev, beat)
        if col == "G":
            if e.hp > 0:
                push_enemy(state, e, *push_direction(state, e), ev, beat)
        elif col == "B":
            e.stun = max(e.stun, 2)
            emit(ev, t="stun", who=e.id, beat=beat)
        elif col == "Y":
            e.burn = max(e.burn, 3 + p.mods["burn_bonus"])
            emit(ev, t="burn", who=e.id, beat=beat)
            if e.hp > 0:
                push_enemy(state, e, *push_direction(state, e), ev, beat)
        elif col == "C":
            e.stun = max(e.stun, 1)
            emit(ev, t="stun", who=e.id, beat=beat)

    if col == "M":
        # the splash is light too: it only fits neighbours of the same shape
        hit_set = set(hit_positions)
        for hx, hy in hit_positions:
            for ox, oy in ORTH:
                n = state.enemy_at(hx + ox, hy + oy)
                if (n is not None and (n.x, n.y) not in hit_set and n.hp > 0
                        and n.shape == a.shape and n.color != col):
                    damage_enemy(state, n, 1, ev, beat)
    if col == "C" and first_hit is not None and first_hit.hp > 0:
        emit(ev, t="swap", who=first_hit.id, a=(p.x, p.y), b=(first_hit.x, first_hit.y),
             beat=beat)
        p.x, first_hit.x = first_hit.x, p.x
        p.y, first_hit.y = first_hit.y, p.y
    if col == "B":
        p.shield = min(MAX_SHIELD, p.shield + p.mods["blue_shield"])
        emit(ev, t="shield", who="player", beat=beat)
    if not landed:
        emit(ev, t="miss", shape=a.shape, beat=beat)


ROLL_BUMP = 2             # damage a rolling circle does to whatever stops it


BEND = {"bend/": lambda dx, dy: (-dy, -dx), "bend\\": lambda dx, dy: (dy, dx)}
SNOW_BUMP = 1             # every snow tile you roll through packs on this much bump
FLOWS = {"current": 1, "gust": 2}   # how far a current / a gust carries whoever ends a beat on it


def roll_info(state, dx, dy):
    """Everything about a circle rolling (dx, dy), as a dict:

        tiles    tiles passed through, in order (where you end is the last)
        bumped   the shape that stops you (None: a wall, the edge, or nothing)
        jumps    holes dropped through, as [(in, out)]
        hops     springy caps that flung you, as [(cap, landing)]
        snow     snow tiles rolled through (each packs +1 onto your bump)
        dye      the colour of the last pool you rolled through (or None)
        dir      the way you're rolling at the end (after any turns)

    It rolls until a wall, the edge, or a shape gets in the way. Special
    tiles (Board.tiles; only round things notice them) change the roll:

        hole     drop through, roll out of its twin, same way (a hole whose
                 twin has a shape on it is plugged: you roll over it)
        spring   a springy cap flings you over the next tile (a shape, a
                 wall, anything) and you land two tiles on, still rolling
                 (if you'd land on something, you just stop on the cap)
        bend     a crystal facet turns you a quarter turn, the way it slants
        snow     you pack on snow: +1 to your bump for every tile of it
        pool     you're dyed its colour: your bump lands as that colour

    A roll never goes round the same loop twice: it stops instead."""
    p = state.player
    x, y = p.x, p.y
    info = {"tiles": [], "bumped": None, "jumps": [], "hops": [], "snow": 0, "dye": None, "dir": (dx, dy)}
    seen = {(x, y, dx, dy)}
    board = state.board
    portals, specials = board.portals, board.tiles
    while True:
        nx, ny = x + dx, y + dy
        info["dir"] = (dx, dy)
        if not tile_open(board, nx, ny):
            return info
        e = state.enemy_at(nx, ny)
        if e is not None:
            info["bumped"] = e
            return info
        x, y = nx, ny
        info["tiles"].append((x, y))
        kind = specials.get((x, y), "")
        if kind == "spring":
            lx, ly = x + 2 * dx, y + 2 * dy
            if tile_open(board, lx, ly) and state.enemy_at(lx, ly) is None:
                info["hops"].append(((x, y), (lx, ly)))
                x, y = lx, ly
                info["tiles"].append((x, y))
                kind = specials.get((x, y), "")
            else:
                return info                                  # nowhere to land: stop on the cap
        if kind == "snow":
            info["snow"] += 1
        elif kind.startswith("pool:"):
            info["dye"] = kind[5:]
        elif kind in BEND:
            dx, dy = BEND[kind](dx, dy)
        out = portals.get((x, y))
        if out is not None and state.enemy_at(*out) is None:
            info["jumps"].append(((x, y), out))
            x, y = out
            info["tiles"].append(out)
        if (x, y, dx, dy) in seen:                        # round and round: stop here
            return info
        seen.add((x, y, dx, dy))


def roll_route(state, dx, dy):
    """(tiles passed through, enemy bumped or None, holes dropped through):
    the short answer (see roll_info for everything)."""
    info = roll_info(state, dx, dy)
    return info["tiles"], info["bumped"], info["jumps"]


def roll_path(state, dx, dy):
    """(tiles passed through, enemy bumped or None): see roll_route."""
    tiles, bumped, _jumps = roll_route(state, dx, dy)
    return tiles, bumped


def bump_damage(info, target):
    """What a roll's bump does to `target`: (damage, colour or None). Snow
    packs on +1 a tile; a dye makes it land as that colour (the opposite
    colour doubles it, the same colour is absorbed)."""
    dmg = ROLL_BUMP + SNOW_BUMP * info["snow"]
    c = info["dye"]
    if c is None:
        return dmg, None
    if c == target.color:
        return 0, c
    dmg += BASE_DAMAGE[c]
    if OPPOSITE[c] == target.color:
        dmg *= 2
    return dmg, c


def roll(state, dx, dy, beat, ev):
    """A circle's move: roll until stopped; bump (and push) a shape that stops you."""
    p = state.player
    info = roll_info(state, dx, dy)
    tiles, bumped = info["tiles"], info["bumped"]
    if tiles:
        emit(ev, t="move", who="player", frm=(p.x, p.y), to=tiles[-1], beat=beat, rolled=len(tiles),
             via=info["jumps"], hops=info["hops"], path=[(p.x, p.y)] + tiles)
        for a, b in info["jumps"]:
            emit(ev, t="portal", who="player", a=a, b=b, beat=beat)
        specials = state.board.tiles
        for t in tiles:
            kind = specials.get(t, "")
            if kind.startswith("pool:"):
                emit(ev, t="paint", who="player", color=kind[5:], pos=t, beat=beat)
            elif kind == "snow":
                emit(ev, t="snow", who="player", pos=t, beat=beat)
            elif kind in BEND or kind == "spring":
                emit(ev, t="turn", who="player", kind=kind, pos=t, beat=beat)
        p.x, p.y = tiles[-1]
    if bumped is not None:
        dmg, c = bump_damage(info, bumped)
        emit(ev, t="bump", who=bumped.id, pos=(bumped.x, bumped.y), beat=beat, snow=info["snow"], color=c)
        if c is not None and c == bumped.color:
            emit(ev, t="absorb", who=bumped.id, pos=(bumped.x, bumped.y), beat=beat)
        else:
            damage_enemy(state, bumped, dmg, ev, beat)
            if c == "B" and bumped.hp > 0:                # a blue bump stuns
                bumped.stun = max(bumped.stun, 2)
                emit(ev, t="stun", who=bumped.id, beat=beat)
        if bumped.hp > 0:
            push_enemy(state, bumped, *info["dir"], ev, beat)
            if c == "G" and bumped.hp > 0:                # a green bump shoves twice
                push_enemy(state, bumped, *info["dir"], ev, beat)


def flow(state, beat, ev):
    """Currents and gusts: whoever ends a beat on one (you or a shape) is
    carried along its arrow, a tile for a current, two for a gust, as far
    as the way is clear."""
    specials = state.board.tiles
    if not specials:
        return
    movers = [state.player] + sorted([e for e in state.enemies if e.hp > 0], key=lambda e: e.id)
    for m in movers:
        kind = specials.get((m.x, m.y), "")
        name = kind.split(":")[0]
        if name not in FLOWS:
            continue
        fdx, fdy = (int(v) for v in kind.split(":")[1].split(","))
        start = (m.x, m.y)
        for _ in range(FLOWS[name]):
            nx, ny = m.x + fdx, m.y + fdy
            if not tile_free(state, nx, ny):
                break
            m.x, m.y = nx, ny
        if (m.x, m.y) != start:
            who = "player" if m is state.player else m.id
            emit(ev, t="carried", who=who, frm=start, to=(m.x, m.y), flow=name, beat=beat)


def player_action(state, a, beat, ev):
    ok, msg = validate_action(state, a)
    if not ok:
        emit(ev, t="fizzle", who="player", msg=msg, beat=beat)
        return
    p = state.player
    if a.kind == "move" and p.rolls:
        roll(state, a.dx, a.dy, beat, ev)
    elif a.kind == "move":
        emit(ev, t="move", who="player", frm=(p.x, p.y), to=(p.x + a.dx, p.y + a.dy),
             beat=beat)
        p.x += a.dx
        p.y += a.dy
    elif a.kind == "cast":
        player_cast(state, a, beat, ev)
    else:
        emit(ev, t="wait", who="player", beat=beat)


# --------------------------------------------------------------- enemies

def _enemy_attack(state, e, order, tiles, dmg, ev, beat):
    p = state.player
    hit = (p.x, p.y) in tiles
    emit(ev, t="enemy_attack", who=e.id, kind=e.kind, order=order, tiles=list(tiles),
         dmg=dmg, hit=hit, beat=beat)
    if hit:
        damage_player(state, dmg, ev, beat)


def enemy_order(state, e, order, ev, beat):
    kind = order[0]
    board = state.board
    if kind == "wait":
        return
    if kind == "move":
        nx, ny = e.x + order[1], e.y + order[2]
        if tile_free(state, nx, ny):
            emit(ev, t="move", who=e.id, frm=(e.x, e.y), to=(nx, ny), beat=beat)
            e.x, e.y = nx, ny
        else:
            emit(ev, t="blocked", who=e.id, beat=beat)
    elif kind == "hit":
        tile = (e.x + order[1], e.y + order[2])
        _enemy_attack(state, e, kind, [tile], order[3], ev, beat)
    elif kind in ("halo", "leap"):
        raw = halo_tiles(e.x, e.y) if kind == "halo" else leap_tiles(e.x, e.y)
        tiles = [t for t in raw if tile_open(board, *t)]
        _enemy_attack(state, e, kind, tiles, order[1], ev, beat)
    elif kind == "line":
        tiles = line_tiles(board, e.x, e.y, order[1], order[2], order[4])
        _enemy_attack(state, e, kind, tiles, order[3], ev, beat)
    elif kind == "splash":
        cx, cy = e.x + order[1], e.y + order[2]
        tiles = [(cx, cy)] + [(cx + ox, cy + oy) for ox, oy in ORTH]
        tiles = [t for t in tiles if tile_open(board, *t)]
        _enemy_attack(state, e, kind, tiles, order[3], ev, beat)
    elif kind == "shield":
        for ox, oy in ORTH:
            ally = state.enemy_at(e.x + ox, e.y + oy)
            if ally is not None:
                ally.shield = min(ENEMY_SHIELD_CAP, ally.shield + order[1])
                emit(ev, t="shield", who=ally.id, beat=beat)
    elif kind == "summon":
        if len(state.enemies) >= MAX_ENEMIES:
            return
        for ox, oy in ORTH:
            x, y = e.x + ox, e.y + oy
            if tile_free(state, x, y):
                s = spawn(state, order[1], x, y, e.color, shape=e.shape)   # a copy of its shape
                emit(ev, t="spawn", who=s.id, kind=order[1], pos=(x, y), beat=beat)
                break


def enemy_phase(state, beat, ev):
    for e in sorted(state.enemies, key=lambda en: en.id):
        if e.hp <= 0 or e not in state.enemies:
            continue
        if e.stun > 0:
            e.stun -= 1
            emit(ev, t="stunned", who=e.id, beat=beat)
            continue
        order = e.orders[beat] if beat < len(e.orders) else ("wait",)
        enemy_order(state, e, order, ev, beat)
        if state.player.hp <= 0:
            break


# ------------------------------------------------------------ turn flow

def set_boss_shapes(state, beat):
    for e in state.enemies:
        if is_boss(e.kind):
            e.shape = boss_shape(state, e, beat)


def resolve_beat(state, action, beat, ev=None):
    if state.outcome != "ongoing":
        return
    set_boss_shapes(state, beat)          # Keepers change shape before you act
    player_action(state, action, beat, ev)
    reap(state, ev, beat)
    check_outcome(state)
    if state.outcome != "ongoing":
        return
    enemy_phase(state, beat, ev)
    reap(state, ev, beat)
    check_outcome(state)
    if state.outcome == "ongoing":
        flow(state, beat, ev)


def end_turn(state, ev=None):
    for e in list(state.enemies):
        if e.burn > 0:
            damage_enemy(state, e, 1, ev, BEATS)
            e.burn -= 1
    reap(state, ev, BEATS)
    check_outcome(state)
    p = state.player
    if state.outcome == "ongoing":
        for c in p.palette:
            p.palette[c] = min(p.cap[c], p.palette[c] + p.mods["regen"])


def begin_turn(state):
    state.turn += 1
    state.player.used = frozenset()
    for e in state.enemies:
        if is_boss(e.kind):
            e.color = boss_color(state, e)
    set_boss_shapes(state, 0)
    plan_orders(state)


def snapshot(state):
    p = state.player
    return {
        "player": (p.x, p.y, p.hp, p.shield),
        "palette": dict(p.palette),
        "used": p.used,
        "enemies": [(e.id, e.kind, e.x, e.y, e.hp, e.max_hp, e.color, e.shield,
                     e.stun, e.burn, e.shape) for e in state.enemies],
        "outcome": state.outcome,
    }


class TurnResult:
    def __init__(self, events, snapshots, outcome):
        self.events = events
        self.snapshots = snapshots
        self.outcome = outcome


def padded(actions):
    acts = list(actions)[:BEATS]
    return acts + [wait()] * (BEATS - len(acts))


def resolve_turn(state, actions, advance=True, record=True):
    """Run a full turn in place. Returns a TurnResult (events + per-beat
    snapshots for animation)."""
    ev = [] if record else None
    snaps = []
    for beat, a in enumerate(padded(actions)):
        if state.outcome != "ongoing":
            break
        resolve_beat(state, a, beat, ev)
        if record:
            snaps.append(snapshot(state))
    if state.outcome == "ongoing":
        end_turn(state, ev)
        if record:
            snaps.append(snapshot(state))
        if advance and state.outcome == "ongoing":
            begin_turn(state)
    return TurnResult(ev, snaps, state.outcome)


def simulate_prefix(state, actions):
    """Clone of the state after the first len(actions) beats (player then
    enemies each beat), without end-of-turn effects. Used to validate the
    next queued action against what the board will really look like."""
    s = state.clone()
    ev = []
    for beat, a in enumerate(actions):
        resolve_beat(s, a, beat, ev)
    return s, ev


def preview_full(state, actions):
    """Exact preview of the whole turn for a (possibly short) queue."""
    s, res = preview_turn(state, actions)
    return s, res.events


def preview_turn(state, actions):
    """Like preview_full, but also returns the per-beat snapshots, so the UI
    can show where everyone will be on each beat."""
    s = state.clone()
    res = resolve_turn(s, actions, advance=False, record=True)
    return s, res
