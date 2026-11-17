"""The combat screen.

A cast is built from three picks, then aimed on the board:
    PATTERN  where the light goes (buttons 1-5; each once per turn)
    SHAPE    which shapes it fits (Tab cycles; it passes through the rest)
    COLOUR   what it does (R G B Y C M)
Hovering the board previews exactly what the cast would do, including the
damage on each shape it fits, by running the real rules on a copy.
"""

import math

import pygame

from . import board_art, rules, sound
from .art import (Particles, blink_now, darken, draw_body, draw_critter, draw_player, ease_out,
                  hatch, lighten, tint)
from .consts import (BEATS, COLOR_EFFECT, COLOR_NAMES, COLOR_RGB, COLORS, COMPONENTS,
                     GRID_H, GRID_W, LOB_DIST, OPPOSITE, PATTERN_ORDER, PATTERNS, PRIMARIES,
                     RAINBOW, SHAPE_PLURAL, SHAPES, TWISTS, twist_name)
from .enemies import KINDS, boss_shape, is_boss
from .banter import Banter
from .scene import Backdrop, draw_pattern_icon, glint_icon, heading, node_title
from .screens import HelpScreen, Screen
from .state import DIR_NAMES, cast, move, wait
from .widgets import (ACCENT, BAD, DIM, DISABLED_TEXT, GOOD, INK, PAPER, PAPER_DIM, SUNNY, TEXT,
                      WHITE, Button, draw_card, draw_colour_mark, draw_text, draw_wrapped, font,
                      wrap_text)

CELL = 56
OX, OY = 24, 64
BEAT_TIME = 0.55
PX = 552                                   # left edge of the side panel's contents

KEY_MOVES = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
}
KEY_PATTERNS = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3, pygame.K_5: 4}
KEY_COLORS = {pygame.K_r: "R", pygame.K_g: "G", pygame.K_b: "B",
              pygame.K_y: "Y", pygame.K_c: "C", pygame.K_m: "M"}
BANNER_TIME = 4.0
BUBBLE_TIME = 2.8
FLASH_TIME = 0.35


def _along(path, via, t):
    """Where you are (x, y in tiles) and how big (1 = whole), a fraction t of
    the way along a roll: tile by tile, round the turns and bounces, and
    down any knotholes (shrink into one, grow out of its twin)."""
    drops = {tuple(a): tuple(b) for a, b in via}
    steps = []                                   # (from, to, kind): "roll" or "drop"
    for a, b in zip(path, path[1:]):
        a, b = tuple(a), tuple(b)
        steps.append((a, b, "drop" if drops.get(a) == b else "roll"))
    drop = 0.6                                   # a drop takes as long as rolling this many tiles
    cost = [drop * 2 if k == "drop" else 1.0 for _a, _b, k in steps]
    pos = t * sum(cost)
    for (a, b, kind), c in zip(steps, cost):
        if pos <= c:
            if kind == "drop":
                half = c / 2
                if pos < half:
                    return a[0], a[1], 1.0 - pos / half
                return b[0], b[1], (pos - half) / half
            return a[0] + (b[0] - a[0]) * pos, a[1] + (b[1] - a[1]) * pos, 1.0
        pos -= c
    end = tuple(path[-1])
    return end[0], end[1], 1.0


def _through_holes(frm, via, to, t):
    """(kept for a straight roll through holes) see _along."""
    path = [tuple(frm)]
    for a, b in via:
        x, y = path[-1]
        while (x, y) != tuple(a):
            x += (a[0] > x) - (a[0] < x)
            y += (a[1] > y) - (a[1] < y)
            path.append((x, y))
        path.append(tuple(b))
    x, y = path[-1]
    while (x, y) != tuple(to):
        x += (to[0] > x) - (to[0] < x)
        y += (to[1] > y) - (to[1] < y)
        path.append((x, y))
    return _along(path, via, t)


def _lerp(a, b, t):
    return a + (b - a) * t


def _sign(v):
    return (v > 0) - (v < 0)


def _shape_icon(shape):
    def icon(surf, cx, cy):
        draw_body(surf, shape, cx, cy, 8, WHITE, INK, 2)
    return icon


class PatternButton(Button):
    """A square-ish button showing the pattern's diagram and name."""

    def __init__(self, rect, pattern, callback, known, used, **kw):
        super().__init__(rect, PATTERNS[pattern]["name"] if known else "?", callback, **kw)
        self.pattern = pattern
        self.known = known
        self.used = used

    def draw(self, surf, fnt, hover=False):
        r = self.rect
        lift = -2 if (hover and self.enabled) else 0
        if self.enabled:
            pygame.draw.rect(surf, INK, r.move(0, 4), border_radius=10)
        body = r.move(0, lift)
        pygame.draw.rect(surf, self.fill(hover), body, border_radius=10)
        pygame.draw.rect(surf, INK if self.enabled else DISABLED_TEXT, body,
                         4 if self.active else 3, border_radius=10)
        if self.known:
            draw_pattern_icon(surf, self.pattern, body.centerx, body.y + 17, 4,
                              INK if self.enabled else DISABLED_TEXT)
        draw_text(surf, font(18), self.label, (body.centerx, body.bottom - 10),
                  TEXT if self.enabled else DISABLED_TEXT, center=True)
        if self.used:
            draw_text(surf, font(16), "used", (body.right - 4, body.y + 3), BAD, right=True)


class CombatScreen(Screen):
    def __init__(self, app, run):
        super().__init__(app)
        self.run = run
        self.state = run.state
        self.queue = []
        self.pattern = None         # selected pattern
        self.shape = "triangle"     # what the light is cut to fit (sticky)
        self.color = None
        self.tool = "move"
        self.tile_hover = None
        self.mode = "plan"          # "plan" | "anim"
        self.anim = None
        self.last_summary = ""
        self.style = run.place()
        self.material = board_art.material_for(run.tower) if getattr(run, "tower", None) else "tile"
        self.backdrop = Backdrop.for_run(run, n=14)
        self.fx = Particles()
        self.fx_seg = -1
        self.shake = 0.0
        self.jolt = (0, 0)
        self.flash = None           # [colour, seconds left]: a big moment lights the board
        self.focus_key = None       # beat picked with Q/E (None = the whole turn)
        self.slot_hover = None      # beat slot under the mouse
        self.banner = self._new_shapes_banner()
        if run.player.rolls and not app.meta.data.get("seen_roll_tip"):
            app.meta.data["seen_roll_tip"] = True
            self.banner = {"shapes": ["circle"], "t": 0.0, "text": (
                "YOU'RE A CIRCLE NOW", "YOU ROLL",
                "A move rolls you until something stops you. Roll into a shape to bump it.")}
        else:
            for twist in (run.twists() if hasattr(run, "twists") else ()):
                key = "seen_twist_" + twist                  # each tower's special tiles, explained once
                if not app.meta.data.get(key):
                    app.meta.data[key] = True
                    info = TWISTS[twist]
                    tip = info["tip"].replace("Knotholes", twist_name(twist, run.tower))
                    self.banner = {"shapes": ["circle"], "t": 0.0, "text": (
                        "IN THESE FLOORS", twist_name(twist, run.tower).upper(), tip)}
                    break
        self.banter = Banter(getattr(run, "seed", 0) + run.act * 31 + len(self.state.enemies))
        self.bubbles = []           # speech: {"text", "pos", "t"}
        for e in self.state.enemies:
            if is_boss(e.kind):
                moment = "rematch" if getattr(run, "again", False) else "intro"     # (back for another climb)
                self.speak(self.banter.keeper(e.kind, moment), self.cell_center(e.x, e.y))
        self.refresh()
        self.say("Pick a pattern, a shape and a colour, then aim on the board.", DIM)

    def speak(self, line, pos):
        if line:
            sound.play("talk", 0.6)
            self.bubbles = [b for b in self.bubbles if b["t"] < BUBBLE_TIME - 0.3][-1:]
            self.bubbles.append({"text": line, "pos": pos, "t": 0.0})

    def _new_shapes_banner(self):
        """Shapes are introduced one at a time; the first fight with a new one
        says so, loudly."""
        present = set()
        for e in self.state.enemies:
            present.add(e.shape)
            if is_boss(e.kind):
                present |= set(KINDS[e.kind]["shapes"])
        seen = getattr(self.run, "seen_shapes", None)
        if seen is None:
            return None
        new = [sh for sh in SHAPES if sh in present and sh not in seen]
        first = not seen
        seen |= present
        if not new:
            return None
        return {"shapes": new, "t": 0.0, "first": first}

    @property
    def focus(self):
        """The beat being previewed on its own, or None for the whole turn."""
        if self.mode != "plan":
            return None
        return self.slot_hover if self.slot_hover is not None else self.focus_key

    def step_focus(self, d):
        order = [None, 0, 1, 2, 3]
        self.focus_key = order[(order.index(self.focus_key) + d) % len(order)]
        if self.focus_key is None:
            self.say("Showing the whole turn.", DIM)
        else:
            self.say("Showing beat %d only. Q/E to step, Esc for the whole turn."
                     % (self.focus_key + 1), ACCENT)

    # -- state helpers
    @property
    def par(self):
        return getattr(self.state, "par", None)

    def draw_buttons(self, surf):
        f = font(22)
        for b in self.buttons:
            if not b.tag.startswith("slot"):
                b.draw(surf, f, hover=(b is self.hover))

    def refresh(self):
        self.cur, _ = rules.simulate_prefix(self.state, self.queue)
        self.pre, res = rules.preview_turn(self.state, self.queue)
        self.pre_events = res.events
        self.pre_snaps = res.snapshots        # where everyone is after each beat
        self.build_buttons()
        self.app.dirty = True

    def tile_rect(self, gx, gy):
        """Where a tile is for input (never shaken)."""
        return pygame.Rect(OX + gx * CELL, OY + gy * CELL, CELL, CELL)

    def draw_rect(self, gx, gy):
        """Where a tile is drawn this frame (shaken when you get hit)."""
        return pygame.Rect(OX + self.jolt[0] + gx * CELL, OY + self.jolt[1] + gy * CELL, CELL, CELL)

    def tile_at(self, pos):
        gx, gy = (pos[0] - OX) // CELL, (pos[1] - OY) // CELL
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H and pos[0] >= OX and pos[1] >= OY:
            return int(gx), int(gy)
        return None

    def armed(self):
        return self.tool == "cast" and self.pattern is not None and self.color is not None

    # -- buttons
    def build_buttons(self):
        self.buttons = []
        plan = self.mode == "plan"
        pl = self.cur.player
        for i, pt in enumerate(PATTERN_ORDER):
            known = pt in pl.patterns
            used = pt in pl.used
            self.buttons.append(PatternButton(
                (PX + i * 76, 192, 70, 48), pt, lambda pt=pt: self.pick_pattern(pt),
                known, used, enabled=plan and known and not used,
                active=(self.pattern == pt and self.tool == "cast"), tag="pattern:" + pt))
        for i, s in enumerate(SHAPES):
            self.add((PX + i * 126, 264, 120, 30), SHAPE_PLURAL[s].capitalize(),
                     lambda s=s: self.pick_shape(s), enabled=plan,
                     active=(self.shape == s), tag="shape:" + s, icon=_shape_icon(s), small=True)
        for i, c in enumerate(COLORS):
            x, y = PX + (i % 3) * 126, 318 + (i // 3) * 36
            cost = "+".join(COMPONENTS[c])
            name = COLOR_NAMES[c] if c in PRIMARIES else "%s %s" % (COLOR_NAMES[c], cost)
            ok = plan and rules.can_afford(pl, c)
            self.add((x, y, 120, 30), name, lambda c=c: self.pick_color(c),
                     enabled=ok, chip=COLOR_RGB[c], chip_key=c,
                     active=(self.color == c and self.tool == "cast"), tag="color:" + c, small=True)
        self.add((PX, 394, 90, 32), "Move", self.pick_move, enabled=plan,
                 active=(self.tool == "move"), tag="tool_move", small=True)
        self.add((PX + 96, 394, 90, 32), "Wait", lambda: self.queue_action(wait()), enabled=plan,
                 tag="wait", small=True)
        self.add((PX + 192, 394, 90, 32), "Undo", self.undo, enabled=plan and bool(self.queue),
                 tag="undo", small=True)
        self.add((PX + 288, 394, 88, 32), "Clear", self.clear, enabled=plan and bool(self.queue),
                 tag="clear", small=True)
        n = len(self.queue)
        label = "Resolve turn (Enter)" if n == BEATS else (
            "Pass turn (Enter)" if n == 0 else "Resolve %d beat%s, rest wait" % (n, "s" if n != 1 else ""))
        self.add((PX, 434, 376, 40), label, self.resolve, enabled=plan, tag="resolve",
                 color=(150, 236, 160))
        self.add((860, 12, 76, 32), "Help", lambda: self.app.push(HelpScreen(self.app, "rules")),
                 tag="help", key=pygame.K_h, small=True)
        self.add((778, 12, 76, 32), "Key", lambda: self.app.push(BoardKeyScreen(self.app)),
                 tag="key", small=True)
        for i in range(BEATS):
            self.add(self.slot_rect(i), "", lambda i=i: self.cut_to(i),
                     enabled=plan and i < len(self.queue), tag="slot%d" % i)

    def slot_rect(self, i):
        return pygame.Rect(OX + i * 126, 582, 120, 48)

    # -- picking
    def _armed_msg(self):
        if self.pattern is None:
            self.say("Now pick a pattern (1-5): where the light goes.", ACCENT)
        elif self.color is None:
            self.say("%s, cut to fit %s. Now pick a colour." % (
                PATTERNS[self.pattern]["name"], SHAPE_PLURAL[self.shape]), ACCENT)
        else:
            aim = {"orth": "point up, down, left or right", "diag": "point along a diagonal",
                   "none": "click anywhere", "far": "point up, down, left or right"}[
                PATTERNS[self.pattern]["aim"]]
            self.say("%s %s at %s: %s. (%s)" % (
                COLOR_NAMES[self.color], PATTERNS[self.pattern]["name"], SHAPE_PLURAL[self.shape],
                aim, COLOR_EFFECT[self.color]), ACCENT)

    def pick_pattern(self, pt):
        pl = self.cur.player
        if pt not in pl.patterns:
            self.say("You haven't learned %s yet. Beat a shape that uses it." % PATTERNS[pt]["name"], BAD)
            return
        if pt in pl.used:
            self.say("%s is already used this turn. Each pattern once per turn." % PATTERNS[pt]["name"],
                     BAD)
            return
        self.pattern = pt
        self.tool = "cast"
        self._armed_msg()
        self.build_buttons()

    def pick_shape(self, s):
        self.shape = s
        if self.pattern is not None or self.color is not None:
            self.tool = "cast"
            self._armed_msg()
        else:
            self.say("Your light now fits %s only. It passes through every other shape."
                     % SHAPE_PLURAL[s], ACCENT)
        self.build_buttons()

    def cycle_shape(self):
        self.pick_shape(SHAPES[(SHAPES.index(self.shape) + 1) % len(SHAPES)])

    def pick_color(self, c):
        self.color = c
        self.tool = "cast"
        self._armed_msg()
        self.build_buttons()

    def pick_move(self):
        self.tool = "move"
        self.say("Move tool: click a tile next to you, or use the arrow keys.", DIM)
        self.build_buttons()

    def cancel_selection(self):
        if self.tool == "cast" or self.color is not None or self.pattern is not None:
            self.color = None
            self.pattern = None
            self.tool = "move"
            self.say("Cast cancelled.", DIM)
        else:
            self.say("Nothing to cancel.", DIM)
        self.build_buttons()

    # -- queue
    def queue_action(self, a):
        if self.mode != "plan":
            return False
        if len(self.queue) >= BEATS:
            self.say("Timeline is full. Resolve (Enter) or Undo a beat.", BAD)
            return False
        ok, msg = rules.validate_action(self.cur, a)
        if not ok:
            self.say(msg, BAD)
            return False
        self.queue.append(a)
        if self.banner is not None:
            self.banner["t"] = max(self.banner["t"], BANNER_TIME - 0.4)
        if a.kind == "cast":
            self.pattern = None            # it's spent for this turn; keep shape and colour
        self.refresh()
        self.say("Beat %d: %s." % (len(self.queue), a.describe()), GOOD)
        return True

    def undo(self):
        if self.mode != "plan":
            return
        if not self.queue:
            self.say("Nothing to undo.", DIM)
            return
        a = self.queue.pop()
        self.refresh()
        self.say("Removed beat %d (%s)." % (len(self.queue) + 1, a.describe()), DIM)

    def clear(self):
        if self.mode != "plan":
            return
        if not self.queue:
            self.say("The timeline is already empty.", DIM)
            return
        self.queue = []
        self.refresh()
        self.say("Timeline cleared.", DIM)

    def cut_to(self, i):
        if self.mode != "plan" or i >= len(self.queue):
            return
        self.queue = self.queue[:i]
        self.refresh()
        self.say("Plan cut back to %d beat%s." % (i, "" if i == 1 else "s"), DIM)

    def resolve(self):
        if self.mode != "plan":
            return
        before = rules.snapshot(self.state)
        hp_before = self.state.player.hp
        foes_before = sum(e.hp + e.shield for e in self.state.enemies)
        res = rules.resolve_turn(self.state, self.queue, advance=True, record=True)
        foes_after = sum(e.hp + e.shield for e in self.state.enemies)
        self.last_summary = "Turn done: you took %d, the Set lost %d." % (
            max(0, hp_before - self.state.player.hp), max(0, foes_before - foes_after))
        self.anim = {"snaps": [before] + res.snapshots, "events": res.events,
                     "i": 0, "t": 0.0, "outcome": res.outcome}
        self.mode = "anim"
        self.fx_seg = -1
        self.queue = []
        self.pattern = None
        self.build_buttons()
        self.spawn_fx(0)
        self.app.dirty = True

    def finish_anim(self):
        outcome = self.anim["outcome"]
        self.anim = None
        self.mode = "plan"
        self.refresh()
        if outcome == "victory":
            self.app.combat_won()
        elif outcome == "defeat":
            self.app.combat_lost()
        else:
            over = ""
            if self.par is not None and self.state.turn > self.par:
                over = " (past par %d)" % self.par
            self.say("%s Turn %d%s: plan your beats." % (self.last_summary, self.state.turn, over),
                     DIM)

    def skip_anim(self):
        if self.mode == "anim":
            self.finish_anim()

    # -- aiming
    def aim_for(self, tile):
        """The aim a click on `tile` means for the selected pattern (None if none)."""
        p = self.cur.player
        dx, dy = tile[0] - p.x, tile[1] - p.y
        kind = PATTERNS[self.pattern]["aim"]
        if kind == "none":
            return (0, 0)
        if (dx, dy) == (0, 0):
            return None
        if kind == "orth":
            return (_sign(dx), 0) if abs(dx) >= abs(dy) else (0, _sign(dy))
        if kind == "diag":
            if dx == 0 or dy == 0:
                return None
            return (_sign(dx), _sign(dy))
        # Lob: aim with any tile in that direction; it always lands LOB_DIST away
        if dx == 0 or dy == 0:
            return (_sign(dx) * LOB_DIST, _sign(dy) * LOB_DIST)
        return None

    def cast_at(self, tile):
        return cast(self.pattern, self.shape, self.color, *(self.aim_for(tile) or (99, 99)))

    def preview_cast(self, a):
        """Run one cast on a copy of the planned board: (tiles, events)."""
        sim = self.cur.clone()
        rules.set_boss_shapes(sim, len(self.queue))
        ev = []
        if not rules.validate_action(sim, a)[0]:
            return None, []
        tiles = rules.pattern_tiles(sim, a.pattern, a.dx, a.dy)
        rules.player_action(sim, a, len(self.queue), ev)
        return tiles, ev

    # -- input
    def board_click(self, tile):
        if self.tool == "cast":
            if not self.armed():
                self._armed_msg()
                return
            if self.aim_for(tile) is None:
                aim = PATTERNS[self.pattern]["aim"]
                self.say({"orth": "Beam goes straight: click a tile up, down, left or right of you.",
                          "diag": "Slant goes diagonally: click a tile on a diagonal from you.",
                          "far": "Lob goes straight: click a tile up, down, left or right of you."}.get(
                    aim, "Click somewhere else."), BAD)
                return
            self.queue_action(self.cast_at(tile))
            return
        p = self.cur.player
        dx, dy = tile[0] - p.x, tile[1] - p.y
        if abs(dx) + abs(dy) == 1:
            self.queue_action(move(dx, dy))
        elif p.rolls and (dx == 0) != (dy == 0):        # a circle: any tile in a straight line
            self.queue_action(move(_sign(dx), _sign(dy)))
        elif (dx, dy) == (0, 0):
            self.say("That is you. Pick a pattern to cast, or click an adjacent tile to move.", DIM)
        else:
            self.say("Move one tile at a time, or pick a pattern to cast.", DIM)

    def handle(self, ev):
        if self.mode == "anim":
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.skip_anim()
                return True
            return False
        if ev.type == pygame.MOUSEMOTION:
            t = self.tile_at(ev.pos)
            if t != self.tile_hover:
                self.tile_hover = t
                self.app.dirty = True
            self.slot_hover = next((i for i in range(BEATS) if self.slot_rect(i).collidepoint(ev.pos)),
                                   None)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3:
                self.cancel_selection()
                return True
            if ev.button == 1:
                b = self.button_at(ev.pos)
                if b is not None:
                    b.click()
                    self.app.dirty = True
                    return True
                tile = self.tile_at(ev.pos)
                if tile is not None:
                    self.board_click(tile)
                    return True
        elif ev.type == pygame.KEYDOWN:
            if self.key(ev.key):
                return True
        return super().handle(ev)

    def key(self, k):
        if k in KEY_MOVES:
            self.queue_action(move(*KEY_MOVES[k]))
        elif k in KEY_PATTERNS:
            self.pick_pattern(PATTERN_ORDER[KEY_PATTERNS[k]])
        elif k == pygame.K_TAB:
            self.cycle_shape()
        elif k in KEY_COLORS:
            c = KEY_COLORS[k]
            if rules.can_afford(self.cur.player, c):
                self.pick_color(c)
            else:
                self.say("Not enough charges for %s." % COLOR_NAMES[c], BAD)
        elif k == pygame.K_SPACE:
            self.queue_action(wait())
        elif k in (pygame.K_BACKSPACE, pygame.K_z):
            self.undo()
        elif k == pygame.K_x:
            self.clear()
        elif k == pygame.K_RETURN:
            self.resolve()
        elif k == pygame.K_q:
            self.step_focus(-1)
        elif k == pygame.K_e:
            self.step_focus(1)
        elif k == pygame.K_k:
            self.app.push(BoardKeyScreen(self.app))
        elif k == pygame.K_ESCAPE:
            if self.focus_key is not None and self.tool == "move" and self.pattern is None \
                    and self.color is None:
                self.focus_key = None
                self.say("Showing the whole turn.", DIM)
            else:
                self.cancel_selection()
        else:
            return False
        return True

    def update(self, dt):
        super().update(dt)
        self.backdrop.update(dt)
        if self.banner is not None:
            self.banner["t"] += dt
            if self.banner["t"] > BANNER_TIME:
                self.banner = None
        if self.flash is not None:
            self.flash[1] -= dt
            if self.flash[1] <= 0:
                self.flash = None
        self.banter.update(dt)
        for b in self.bubbles:
            b["t"] += dt
        self.bubbles = [b for b in self.bubbles if b["t"] < BUBBLE_TIME]
        self.fx.update(dt)
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)
            k = self.shake * 22
            self.jolt = (int(math.sin(self.t * 71) * k), int(math.cos(self.t * 53) * k))
        else:
            self.jolt = (0, 0)
        if self.mode != "anim":
            return True
        a = self.anim
        a["t"] += dt
        while a["t"] >= BEAT_TIME:
            a["t"] -= BEAT_TIME
            a["i"] += 1
            if a["i"] >= len(a["snaps"]) - 1:
                self.finish_anim()
                return True
            self.spawn_fx(a["i"])
        return True

    # -- effects
    def spawn_fx(self, seg):
        """Particles for everything that happens in one beat of the animation."""
        if seg == self.fx_seg or self.anim is None:
            return
        self.fx_seg = seg
        sound.play("tock" if seg == 0 else "tick", 0.7)          # every beat clicks
        prev = {e[0]: e for e in self.anim["snaps"][seg]["enemies"]}
        for ev in self.anim["events"]:
            if ev.get("beat") != seg:
                continue
            t = ev["t"]
            if t == "enemy_attack" and ev["hit"] and ev["who"] in prev:
                e = prev[ev["who"]]
                self.speak(self.banter.on_hit(e[10], self.run.form()["shape"]),
                           self.cell_center(e[2], e[3]))
            if t == "cast":
                sound.play("cast:" + ev["color"])
                if ev["fits"] >= 2:
                    sound.play("group")
                    self.speak(self.banter.retort(), self.cell_center(*ev["pos"]))
                    px, py = self.cell_center(*ev["pos"])
                    for i, c in enumerate(RAINBOW[:2 + ev["fits"]]):
                        self.fx.ring(px, py, COLOR_RGB[c], 10 + i * 6, CELL * (2 + ev["fits"]), 0.6)
                    if ev["fits"] >= 3:
                        self.flash = [COLOR_RGB[ev["color"]], FLASH_TIME]
                # the light comes out cut into the shape it fits
                col = COLOR_RGB[ev["color"]]
                for (x, y) in ev["tiles"]:
                    cx, cy = self.cell_center(x, y)
                    self.fx.burst(cx, cy, col, n=3, speed=110, shapes=(ev["shape"],))
            elif t == "enemy_attack" and ev.get("order") == "splash":
                cx, cy = self.cell_center(*ev["tiles"][0]) if ev["tiles"] else (0, 0)
                self.fx.ring(cx, cy, WHITE, 8, CELL * 1.4)
            elif t == "enemy_attack" and ev.get("order") in ("halo", "leap"):
                e = prev.get(ev["who"])
                if e is not None:
                    cx, cy = self.cell_center(e[2], e[3])
                    self.fx.ring(cx, cy, WHITE, 10, CELL * (1.5 if ev["order"] == "halo" else 2.3))
            elif t == "dmg":
                cx, cy = self.cell_center(*ev["pos"])
                if ev["who"] == "player":
                    if ev["took"] > 0:
                        sound.play("hurt")
                        self.shake = 0.35
                        self.fx.burst(cx, cy, BAD, n=10, speed=200)
                else:
                    sound.play("hit", 0.8)
                    e = prev.get(ev["who"])
                    col = COLOR_RGB[e[6]] if e else WHITE
                    self.fx.burst(cx, cy, lighten(col, 0.3), n=6, speed=150)
            elif t == "kill":
                sound.play("loose")
                cx, cy = self.cell_center(*ev["pos"])
                e = prev.get(ev["who"])
                if is_boss(ev["kind"]):
                    self.speak(self.banter.keeper(ev["kind"], "loose"), (cx, cy))
                    self.flash = [WHITE, FLASH_TIME * 2]
                    for i, c in enumerate(RAINBOW):
                        self.fx.ring(cx, cy, COLOR_RGB[c], 12 + i * 8, CELL * 6, 1.0)
                        self.fx.burst(cx, cy, COLOR_RGB[c], n=10, speed=380,
                                      shapes=("triangle", "square", "circle", "diamond"))
                elif e is not None:
                    self.speak(self.banter.on_loose(e[10]), (cx, cy))
                col = COLOR_RGB[e[6]] if e else WHITE
                self.fx.edges(cx, cy, col, e[10] if e else "square", 18)
                self.fx.burst(cx, cy, (255, 226, 92), n=6, speed=140, shapes=("diamond",))
            elif t == "shield" and ev["who"] == "player":
                cx, cy = self.cell_center(self.state.player.x, self.state.player.y)
                self.fx.ring(cx, cy, COLOR_RGB["B"], 10, 34)

    # -- drawing
    def view(self):
        """(before, after, t, beat index) for plan or anim."""
        if self.mode == "anim":
            a = self.anim
            i = min(a["i"], len(a["snaps"]) - 2)
            return a["snaps"][i], a["snaps"][i + 1], a["t"] / BEAT_TIME, i
        f = self.focus
        if f is not None and self.pre_snaps:
            snap = self.pre_snaps[min(f, len(self.pre_snaps) - 1)]
            return snap, snap, 0.0, -1
        snap = rules.snapshot(self.state)
        return snap, snap, 0.0, -1

    def cell_center(self, x, y):
        return (OX + self.jolt[0] + int((x + 0.5) * CELL),
                OY + self.jolt[1] + int((y + 0.5) * CELL))

    def _seg_events(self, seg):
        if self.mode != "anim":
            return []
        return [ev for ev in self.anim["events"] if ev.get("beat") == seg]

    def planned_boss_shape(self, e):
        """A Keeper's shape on the beat you are planning next."""
        return boss_shape(self.state, e, min(len(self.queue), BEATS - 1))

    def draw_enemy(self, surf, kind, x, y, hp, color, shape, shield=0, stun=0, burn=0,
                   ghost=False, eid=0, mood=None, hop=0.0, tilt=0.0, swell=0.0, predicted=None):
        spec = KINDS[kind]
        cx, cy = self.cell_center(x, y)
        boss = is_boss(kind)
        r = (24 if boss else 17) * spec.get("size", 1.0)
        rgb = COLOR_RGB[color]
        if ghost:
            draw_body(surf, shape, cx, cy, r, None, rgb, 3)
            return
        p = self.state.player
        look = ((p.x - x) * 0.4, (p.y - y) * 0.4)
        bob = math.sin(self.t * 3 + eid * 1.7) * 1.5
        mood = mood or ("sleep" if stun else "cross")
        if boss:
            # Keepers hold every colour: a ring of all six, turning
            for i, c in enumerate(RAINBOW):
                a = self.t * 1.2 + i * math.tau / 6
                dot = (int(cx + math.cos(a) * (r + 9)), int(cy + math.sin(a) * (r + 9) * 0.45 + 8))
                pygame.draw.circle(surf, COLOR_RGB[c], dot, 5)
                pygame.draw.circle(surf, INK, dot, 5, 2)
        s = 1.0 + swell
        draw_critter(surf, shape, cx, cy - hop + bob, r, rgb, look=look, mood=mood, rot=tilt,
                     sx=s * (1 + 0.04 * math.sin(self.t * 3 + eid)), sy=s,
                     blink=blink_now(self.t, eid), mark=spec.get("mark"), face=spec.get("face"))
        draw_colour_mark(surf, color, cx + r * 0.85, cy - hop + bob - r * 0.85, max(6, r * 0.42))
        f = font(18)
        pill = pygame.Rect(0, 0, 26 if hp < 10 else 32, 16)
        pill.midtop = (int(cx), int(cy) + r + 4)
        pygame.draw.rect(surf, INK, pill, border_radius=8)
        draw_text(surf, f, "%d" % hp, pill.center, WHITE, center=True)
        if shield:
            sh = pygame.Rect(pill.right + 2, pill.y, 24, 16)
            pygame.draw.rect(surf, COLOR_RGB["B"], sh, border_radius=8)
            pygame.draw.rect(surf, INK, sh, 2, border_radius=8)
            draw_text(surf, f, "+%d" % shield, sh.center, WHITE, center=True)
        if stun:
            for k in range(2):
                a = self.t * 4 + k * math.pi
                draw_text(surf, f, "z", (int(cx + math.cos(a) * r), int(cy - r - 6 + math.sin(a) * 4)),
                          INK, center=True)
        if burn:
            fl = 5 + 2 * math.sin(self.t * 12 + eid)
            draw_body(surf, "triangle", cx - r, cy - r, fl, COLOR_RGB["Y"], INK, 2)
        if predicted:
            draw_text(surf, font(26), predicted, (int(cx), int(cy - r - 14)), WHITE, center=True,
                      shadow=INK)

    def draw_keeper_strip(self, surf, e):
        """The shapes a Keeper will be on each beat this turn (yours to time)."""
        cx, cy = self.cell_center(e.x, e.y)
        y = cy - 48
        now = len(self.queue)
        for b in range(BEATS):
            x = cx - 33 + b * 22
            box = pygame.Rect(0, 0, 20, 20)
            box.center = (x, y)
            pygame.draw.rect(surf, SUNNY if b == now else PAPER, box, border_radius=5)
            pygame.draw.rect(surf, INK, box, 2, border_radius=5)
            draw_body(surf, boss_shape(self.state, e, b), x, y, 5, COLOR_RGB[e.color], INK, 1)

    def draw_you(self, surf, x, y, shield, ghost=False, mood="plain", hop=0.0, tilt=0.0, size=1.0):
        if size < 0.08:
            return                                         # all the way down a hole
        cx, cy = self.cell_center(x, y)
        form = self.run.form()["shape"]
        if ghost:
            draw_body(surf, form, cx, cy, 17, None, INK, 2)
            return
        look = (0, -1)
        foes = self.state.enemies
        if foes:
            e = min(foes, key=lambda e: abs(e.x - x) + abs(e.y - y))
            d = max(1.0, abs(e.x - x) + abs(e.y - y))
            look = ((e.x - x) / d, (e.y - y) / d)
        if shield:
            pygame.draw.circle(surf, lighten(COLOR_RGB["B"], 0.3), (int(cx), int(cy)),
                               25 + int(2 * math.sin(self.t * 5)), 4)
        draw_player(surf, form, cx, cy - hop + math.sin(self.t * 2.6) * 1.5, 19 * size, self.t, look=look,
                    mood=mood, rot=tilt, blink=blink_now(self.t, 4))

    def hover_preview(self):
        """(cast, tiles, events) for the cast under the mouse, or None."""
        if self.mode != "plan" or not self.armed() or self.tile_hover is None:
            return None
        if self.aim_for(self.tile_hover) is None:
            return None
        a = self.cast_at(self.tile_hover)
        tiles, ev = self.preview_cast(a)
        if tiles is None:
            return None
        return a, tiles, ev

    def draw_board(self, surf):
        style = self.style
        board = pygame.Rect(OX - 10, OY - 10, GRID_W * CELL + 20, GRID_H * CELL + 20)
        draw_card(surf, board.move(*self.jolt), darken(style["tiles"][1], 0.08), 16)
        walls = self.state.board.walls
        for gy in range(GRID_H):                              # the floor: pixel-art tiles
            for gx in range(GRID_W):
                if (gx, gy) not in walls:
                    tile = board_art.floor_tile(CELL, style["tiles"][(gx + gy) % 2], self.material,
                                                (gx * 7 + gy * 3) % 3)
                    surf.blit(tile, self.draw_rect(gx, gy).topleft)
        pb = self.state.board
        frame = int(self.t * 6)
        for i, pair in enumerate(pb.pairs):                    # knotholes, glowing by pair
            for tile in pair:
                surf.blit(board_art.hole_tile(CELL, i, frame, sea=getattr(self.run, "tower", None) == "lighthouse"), self.draw_rect(*tile).topleft)
        for tile, kind in pb.tiles.items():                    # the tower's other special tiles
            r = self.draw_rect(*tile)
            surf.blit(board_art.special_tile(CELL, kind, frame), r.topleft)
            col = board_art.pool_colour(kind)
            if col:
                draw_colour_mark(surf, col, r.right - 10, r.y + 10, 6)
        for gy in range(GRID_H):
            for gx in range(GRID_W):
                if (gx, gy) in walls:
                    r = self.draw_rect(gx, gy)
                    surf.blit(board_art.wall_block(CELL, style["wall"], self.material), (r.x, r.y - 10))
        a, b, t, seg = self.view()
        preview = None
        if self.mode == "plan":
            preview = self.hover_preview()
            self.draw_plan_overlay(surf, preview)
        else:
            self.draw_anim_overlay(surf, seg, t)
        predicted = {}
        if preview is not None:
            for ev in preview[2]:
                if ev["t"] == "dmg" and ev["who"] != "player":
                    predicted[ev["who"]] = predicted.get(ev["who"], 0) + ev["took"]
                elif ev["t"] == "absorb":
                    predicted.setdefault(ev["who"], "absorbed")
        seg_ev = self._seg_events(seg)
        hurt = {ev["who"] for ev in seg_ev if ev["t"] == "dmg" and ev["took"] > 0}
        attacks = {ev["who"]: ev for ev in seg_ev if ev["t"] == "enemy_attack"}
        prev = {e[0]: e for e in a["enemies"]}
        nxt = {e[0]: e for e in b["enemies"]}
        live = {e.id: e for e in self.state.enemies}
        for eid, e in prev.items():
            n = nxt.get(eid)
            if n is None:
                continue                     # knocked loose: its edges are flying (see spawn_fx)
            mt = min(1, t * 1.6)
            x, y = _lerp(e[2], n[2], mt), _lerp(e[3], n[3], mt)
            moved = (e[2], e[3]) != (n[2], n[3])
            hop = math.sin(math.pi * mt) * 10 if moved else 0.0
            tilt = (n[2] - e[2]) * -0.3 * math.sin(math.pi * mt) if moved else 0.0
            src = n if t >= 0.5 else e
            shape = n[10]                     # Keepers change shape at the start of a beat
            if self.mode == "plan" and self.focus is None and is_boss(e[1]) and eid in live:
                shape = self.planned_boss_shape(live[eid])
            swell = 0.3 * math.sin(math.pi * min(1, t * 1.4)) if eid in attacks else 0.0
            mood = "hurt" if eid in hurt and t < 0.7 else None
            pv = predicted.get(eid)
            label = None
            if pv == "absorbed":
                label = "absorbed"
            elif pv:
                label = "-%d" % pv
            self.draw_enemy(surf, e[1], x, y, src[4], n[6] if t >= 0.5 else e[6], shape,
                            src[7], src[8], src[9], eid=eid, mood=mood, hop=hop, tilt=tilt,
                            swell=swell, predicted=label)
        for eid, n in nxt.items():
            if eid not in prev and t >= 0.4:
                self.draw_enemy(surf, n[1], n[2], n[3], n[4], n[6], n[10], n[7], n[8], n[9], eid=eid)
        if self.mode == "plan":
            for e in self.state.enemies:
                if is_boss(e.kind):
                    self.draw_keeper_strip(surf, e)
        pa, pb = a["player"], b["player"]
        mt = min(1, t * 1.6)
        moved = (pa[0], pa[1]) != (pb[0], pb[1])
        mv = next((ev for ev in seg_ev if ev["t"] == "move" and ev["who"] == "player"), None)
        carried = next((ev for ev in seg_ev if ev["t"] == "carried" and ev["who"] == "player"), None)
        rolled = mv is not None and mv.get("path") and len(mv["path"]) > 2
        hop_lift = 0.0
        if rolled or carried:                               # along the roll: turns, hops, holes, the tide
            path = list(mv["path"]) if mv is not None and mv.get("path") else [(pa[0], pa[1])]
            if carried:
                path = path + [carried["to"]]
            px, py, size = _along(path, mv.get("via") or [] if mv else [], mt)
            for a_, b_ in (mv.get("hops") or []) if mv else []:      # flung over by a cap: up in an arc
                ax, ay = a_
                bx_, by_ = b_
                span = abs(bx_ - ax) + abs(by_ - ay)
                d = abs(px - ax) + abs(py - ay)
                if min(ax, bx_) <= px <= max(ax, bx_) and min(ay, by_) <= py <= max(ay, by_) and span:
                    hop_lift = math.sin(math.pi * min(1.0, d / span)) * 40
        else:
            px, py, size = _lerp(pa[0], pb[0], mt), _lerp(pa[1], pb[1], mt), 1.0
        self.draw_you(surf, px, py, (pb if t >= 0.5 else pa)[3],
                      mood="hurt" if "player" in hurt and t < 0.8 else "plain",
                      hop=(math.sin(math.pi * mt) * 12 if moved and not (rolled or carried) else 0.0) + hop_lift,
                      tilt=(pb[0] - pa[0]) * -0.3 * math.sin(math.pi * mt) if moved else 0.0,
                      size=size)
        if self.flash is not None:
            tint(surf, pygame.Rect(OX, OY, GRID_W * CELL, GRID_H * CELL), self.flash[0],
                 160 * min(1.0, self.flash[1] / FLASH_TIME))
        self.fx.draw(surf)
        if self.mode == "anim":
            self.draw_anim_text(surf, seg, t)
        elif preview is not None:
            self.draw_preview_text(surf, preview)

    # -- reading the plan
    def isolated(self):
        """The enemy whose plan alone is shown (you are hovering it), or None."""
        if self.mode != "plan" or self.tile_hover is None or self.armed() or self.focus is not None:
            return None
        e = self.state.enemy_at(*self.tile_hover)
        return e.id if e is not None else None

    def who(self, eid, beat):
        """(kind, colour, shape, x, y) of an enemy during a beat of the preview."""
        snaps = self.pre_snaps
        for snap in ([snaps[min(beat, len(snaps) - 1)]] if snaps else []) + [rules.snapshot(self.state)]:
            for e in snap["enemies"]:
                if e[0] == eid:
                    return e[1], e[6], e[10], e[2], e[3]
        return None

    def draw_badge(self, surf, x, y, beat, eid):
        """A little tag on a danger tile: WHO strikes (a tiny copy of it) and
        WHEN (the beat). (x, y) is the tag's top-left corner."""
        info = self.who(eid, beat)
        color, shape = (info[1], info[2]) if info else ("R", "circle")
        _tag(surf, x, y, shape, COLOR_RGB[color], beat + 1)

    def enemy_paths(self, only=None):
        """{enemy id: [(beat, (x, y)), ...]} steps each enemy takes this turn."""
        paths = {}
        for ev in self.pre_events:
            if ev["t"] == "move" and ev["who"] != "player" and ev["beat"] < BEATS:
                if only is None or ev["who"] == only:
                    paths.setdefault(ev["who"], []).append((ev["beat"], ev["to"]))
        return paths

    def draw_plan_overlay(self, surf, preview):
        """The telegraph: stripes where the Set will strike, a badge saying
        who strikes and on which beat, numbered steps for where each shape
        walks, and pink where a strike will land on you."""
        f = self.focus
        iso = self.isolated()
        aiming = preview is not None             # fade the threats so your cast reads clearly
        attacks = [ev for ev in self.pre_events
                   if ev["t"] == "enemy_attack" and ev["beat"] < BEATS
                   and (f is None or ev["beat"] == f) and (iso is None or ev["who"] == iso)]
        tiles = {}
        for ev in attacks:
            for tile in ev["tiles"]:
                tiles.setdefault(tile, []).append(ev)
        pulse = 0.5 + 0.5 * math.sin(self.t * 6)
        # pink goes only on the tile where a strike actually lands on you
        you_hit = set()
        for ev in attacks:
            if ev["hit"] and self.pre_snaps:
                you_hit.add(tuple(self.pre_snaps[min(ev["beat"], len(self.pre_snaps) - 1)]["player"][:2]))
        for (x, y), evs in tiles.items():
            r = self.draw_rect(x, y)
            hits = (x, y) in you_hit
            # danger tiles take the colour of whoever strikes them
            info = self.who(evs[0]["who"], evs[0]["beat"])
            col = darken(COLOR_RGB[info[1]], 0.15) if info else INK
            solo = f is not None or iso is not None
            hatch(surf, r.inflate(-3, -3), col, (150 if solo else 110) // (3 if aiming else 1), 10, 4)
            if hits and not aiming:
                pygame.draw.rect(surf, BAD, r.inflate(-2, -2), 3 + int(2 * pulse), border_radius=8)
        for (x, y), evs in tiles.items():
            r = self.draw_rect(x, y)
            marks = sorted({(ev["beat"], ev["who"]) for ev in evs})
            for i, (beat, eid) in enumerate(marks[:2]):
                self.draw_badge(surf, r.x + 3, r.y + 3 + i * 20, beat, eid)
            if len(marks) > 2:
                draw_text(surf, font(17), "+%d" % (len(marks) - 2), (r.right - 5, r.bottom - 18), INK,
                          right=True)
        if f is None:
            # where each shape walks: a dotted trail with a numbered stop per beat
            for eid, steps in self.enemy_paths(iso).items():
                info = self.who(eid, 0)
                if info is None:
                    continue
                col = COLOR_RGB[info[1]]
                pts = [self.cell_center(info[3], info[4])]
                start = self.state.get(eid)
                if start is not None:
                    pts[0] = self.cell_center(start.x, start.y)
                pts += [self.cell_center(*to) for _, to in steps]
                for i in range(len(pts) - 1):
                    self._dots(surf, pts[i], pts[i + 1], col)
                for beat, to in steps:
                    cx, cy = self.cell_center(*to)
                    pygame.draw.circle(surf, col, (cx, cy + 14), 8)
                    pygame.draw.circle(surf, INK, (cx, cy + 14), 8, 2)
                    draw_text(surf, font(16), str(beat + 1), (cx, cy + 15), WHITE, center=True,
                              shadow=INK)
            self.draw_your_path(surf)
            live = {e.id: e for e in self.state.enemies}
            for e in self.pre.enemies:
                o = live.get(e.id)
                if o is not None and (o.x, o.y) != (e.x, e.y) and iso in (None, e.id):
                    self.draw_enemy(surf, e.kind, e.x, e.y, e.hp, e.color, e.shape, ghost=True)
        else:
            # this beat only: arrows for whoever moves, and your own cast if you made one
            before = self.pre_snaps[f - 1] if f > 0 and len(self.pre_snaps) >= f else \
                rules.snapshot(self.state)
            old = {e[0]: (e[2], e[3]) for e in before["enemies"]}
            for eid, to in [(ev["who"], ev["to"]) for ev in self.pre_events
                            if ev["t"] == "move" and ev["who"] != "player" and ev["beat"] == f]:
                if eid in old:
                    info = self.who(eid, f)
                    self._dots(surf, self.cell_center(*old[eid]), self.cell_center(*to),
                               COLOR_RGB[info[1]] if info else INK)
            for ev in self.pre_events:
                if ev["t"] == "cast" and ev["beat"] == f:
                    rgb = COLOR_RGB[ev["color"]]
                    for (x, y) in ev["tiles"]:
                        r = self.draw_rect(x, y).inflate(-3, -3)
                        tint(surf, r, rgb, 90)
                        pygame.draw.rect(surf, rgb, r, 3, border_radius=8)
        self.draw_hover_cast(surf, preview)

    def draw_your_path(self, surf):
        """Where your plan takes you: a white trail with your beat numbers."""
        p0 = self.state.player
        path = [self.cell_center(p0.x, p0.y)]
        legs = [path]                                      # a knothole breaks the trail in two
        stops = []
        for ev in self.pre_events:
            if ev["t"] == "move" and ev["who"] == "player":
                drops = {tuple(a): tuple(b) for a, b in ev.get("via") or ()}
                route = ev.get("path") or [ev["frm"], ev["to"]]
                for a, b in zip(route, route[1:]):
                    if drops.get(tuple(a)) == tuple(b):        # down a hole: the trail breaks
                        path = [self.cell_center(*b)]
                        legs.append(path)
                    else:
                        path.append(self.cell_center(*b))
                stops.append((ev["beat"], path[-1]))
            elif ev["t"] == "swap":
                path.append(self.cell_center(*ev["b"]))
                stops.append((ev["beat"], path[-1]))
        for leg in legs:
            if len(leg) > 1:
                pygame.draw.lines(surf, INK, False, [(x, y + 2) for x, y in leg], 7)
                pygame.draw.lines(surf, WHITE, False, leg, 4)
        if len(legs) > 1 or len(path) > 1:
            for beat, (x, y) in stops:
                pygame.draw.circle(surf, WHITE, (x, y - 14), 8)
                pygame.draw.circle(surf, INK, (x, y - 14), 8, 2)
                draw_text(surf, font(16), str(beat + 1), (x, y - 13), INK, center=True)
        cp = self.cur.player
        if (cp.x, cp.y) != (p0.x, p0.y):
            self.draw_you(surf, cp.x, cp.y, 0, ghost=True)

    def draw_hover_cast(self, surf, preview):
        # the cast under the mouse
        t = self.tile_hover
        if t is None:
            return
        if self.tool == "cast" and self.armed():
            if preview is None:
                r = self.draw_rect(*t).inflate(-14, -14)
                pygame.draw.line(surf, BAD, r.topleft, r.bottomright, 5)
                pygame.draw.line(surf, BAD, r.topright, r.bottomleft, 5)
                return
            rgb = COLOR_RGB[self.color]
            for tx, ty in preview[1]:
                r = self.draw_rect(tx, ty).inflate(-3, -3)
                tint(surf, r, rgb, 165)
                pygame.draw.rect(surf, INK, r, 3, border_radius=8)
                pygame.draw.rect(surf, WHITE, r.inflate(-8, -8), 2, border_radius=6)
            # shapes the light fits get a ring; the rest it passes straight through
            for tx, ty in preview[1]:
                e = self.cur.enemy_at(tx, ty)
                if e is None:
                    continue
                cx, cy = self.cell_center(tx, ty)
                fits = self._cur_shape(e) == self.shape
                pygame.draw.circle(surf, INK if fits else WHITE, (cx, cy), 26, 4 if fits else 2)
        elif self.tool == "move":
            p = self.cur.player
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                if not rules.validate_action(self.cur, move(dx, dy))[0]:
                    continue
                if p.rolls:
                    self._draw_roll_preview(surf, dx, dy)
                    continue
                r = self.draw_rect(p.x + dx, p.y + dy).inflate(-3, -3)
                tint(surf, r, WHITE, 110)
                pygame.draw.rect(surf, INK, r, 2, border_radius=8)

    def _draw_roll_preview(self, surf, dx, dy):
        """A circle rolls until stopped: show where to, and who it would bump."""
        info = rules.roll_info(self.cur, dx, dy)
        tiles, bumped, jumps = info["tiles"], info["bumped"], info["jumps"]
        for a, b in jumps:                                 # down one hole, out of its twin
            self._dots(surf, self.cell_center(*a), self.cell_center(*b), WHITE)
        for a, b in info["hops"]:                          # flung over by a cap: an arc
            pa, pb = self.cell_center(*a), self.cell_center(*b)
            pts = [(pa[0] + (pb[0] - pa[0]) * k / 8, pa[1] + (pb[1] - pa[1]) * k / 8 - math.sin(math.pi * k / 8) * 34)
                   for k in range(9)]
            pygame.draw.lines(surf, WHITE, False, pts, 3)
        for x, y in tiles[:-1]:
            pygame.draw.circle(surf, WHITE, self.cell_center(x, y), 5)
            pygame.draw.circle(surf, INK, self.cell_center(x, y), 5, 2)
        if tiles:
            r = self.draw_rect(*tiles[-1]).inflate(-3, -3)
            tint(surf, r, WHITE, 110)
            pygame.draw.rect(surf, INK, r, 2, border_radius=8)
        if bumped is not None:
            cx, cy = self.cell_center(bumped.x, bumped.y)
            dmg, c = rules.bump_damage(info, bumped)
            words = "absorbed" if (c and c == bumped.color) else "bump -%d" % dmg
            col = COLOR_RGB[c] if c else WHITE
            draw_text(surf, font(22), words, (cx, cy - 30), col, center=True, shadow=INK)
            if info["snow"]:
                draw_text(surf, font(16), "+%d snow" % info["snow"], (cx, cy - 48), WHITE, center=True, shadow=INK)

    def _dots(self, surf, a, b, col):
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(dist / 9))
        for k in range(1, n):
            x = a[0] + (b[0] - a[0]) * k / n
            y = a[1] + (b[1] - a[1]) * k / n
            pygame.draw.circle(surf, INK, (int(x), int(y) + 1), 4)
            pygame.draw.circle(surf, lighten(col, 0.2), (int(x), int(y)), 3)

    def _cur_shape(self, e):
        return self.planned_boss_shape(e) if is_boss(e.kind) else e.shape

    def draw_preview_text(self, surf, preview):
        a, _tiles, ev = preview
        cast_ev = next((x for x in ev if x["t"] == "cast"), None)
        if cast_ev is None:
            return
        cx, cy = self.cell_center(self.cur.player.x, self.cur.player.y)
        absorbed = sum(1 for x in ev if x["t"] == "absorb")
        if cast_ev["fits"] >= 2:
            text = "fits %d %s: +%d each" % (cast_ev["fits"], SHAPE_PLURAL[a.shape], cast_ev["bonus"])
        elif cast_ev["fits"] == 1:
            text = "fits 1 %s" % a.shape
        elif absorbed:
            text = "same colour: absorbed"
        else:
            text = "no %s there: it passes through" % SHAPE_PLURAL[a.shape]
        draw_text(surf, font(22), text, (cx, cy - 46), WHITE, center=True, shadow=INK)

    def draw_anim_overlay(self, surf, seg, t):
        fade = max(0.0, 1.0 - t)
        snaps = self.anim["snaps"]
        for ev in self._seg_events(seg):
            if ev["t"] == "cast":
                rgb = COLOR_RGB[ev["color"]]
                for (x, y) in ev["tiles"]:
                    r = self.draw_rect(x, y).inflate(-3, -3)
                    tint(surf, r, rgb, int(190 * fade))
                    pygame.draw.rect(surf, rgb, r, 3, border_radius=8)
            elif ev["t"] == "enemy_attack":
                for (x, y) in ev["tiles"]:
                    r = self.draw_rect(x, y).inflate(-3, -3)
                    hatch(surf, r, BAD if ev["hit"] else INK, 120, 10, 4)
                if ev.get("order") == "line" and ev["tiles"]:
                    # a point flies down the ray
                    e = next((s for s in snaps[seg]["enemies"] if s[0] == ev["who"]), None)
                    if e is not None:
                        ax, ay = self.cell_center(e[2], e[3])
                        bx, by = self.cell_center(*ev["tiles"][-1])
                        f = ease_out(min(1, t * 1.8))
                        ang = math.atan2(by - ay, bx - ax) + math.pi / 2
                        draw_body(surf, "triangle", _lerp(ax, bx, f), _lerp(ay, by, f), 9,
                                  COLOR_RGB[e[6]], INK, 2, rot=ang)

    def draw_anim_text(self, surf, seg, t):
        for ev in self._seg_events(seg):
            if ev["t"] == "dmg" and t > 0.15:
                x, y = ev["pos"]
                r = self.draw_rect(x, y)
                col = BAD if ev["who"] == "player" else WHITE
                draw_text(surf, font(30), "-%d" % ev["took"], (r.centerx, r.y - int(14 * t)),
                          col, center=True, shadow=INK)
            elif ev["t"] == "absorb" and t > 0.1:
                r = self.draw_rect(*ev["pos"])
                draw_text(surf, font(20), "absorbed", (r.centerx, r.y - int(10 * t)), WHITE,
                          center=True, shadow=INK)
            elif ev["t"] == "cast" and ev["fits"] >= 2:
                cx, cy = self.cell_center(*ev["pos"])
                draw_text(surf, font(30), "%d %s! +%d" % (ev["fits"], SHAPE_PLURAL[ev["shape"]],
                                                        ev["bonus"]),
                          (cx, cy - 40 - int(20 * t)), SUNNY, center=True, shadow=INK)
            elif ev["t"] == "miss" and t > 0.1:
                cx, cy = self.cell_center(*self.anim["snaps"][seg]["player"][:2])
                draw_text(surf, font(20), "no %s there" % SHAPE_PLURAL.get(ev.get("shape"), "shapes"),
                          (cx, cy - 36), WHITE, center=True, shadow=INK)

    def draw_panel(self, surf):
        a, b, t, seg = self.view()
        if self.mode == "anim":
            php, shield = (b if t >= 0.5 else a)["player"][2:4]
            pal = (b if t >= 0.5 else a)["palette"]
        else:
            php, shield = self.state.player.hp, self.state.player.shield
            pal = self.cur.player.palette
        p = self.state.player
        draw_card(surf, (PX - 14, 54, 400, 578), PAPER, 16)
        # you
        draw_player(surf, self.run.form()["shape"], PX + 12, 78, 12, self.t, shadow=False)
        draw_text(surf, font(26), "%d/%d" % (php, p.max_hp), (PX + 32, 68), INK)
        bar = pygame.Rect(PX + 110, 68, 190, 20)
        pygame.draw.rect(surf, PAPER_DIM, bar, border_radius=10)
        fill = bar.copy()
        fill.w = int(bar.w * max(0, php) / p.max_hp)
        if fill.w:
            pygame.draw.rect(surf, BAD, fill, border_radius=10)
            pygame.draw.rect(surf, lighten(BAD, 0.4), (fill.x + 6, fill.y + 4, max(0, fill.w - 12), 4),
                             border_radius=2)
        pygame.draw.rect(surf, INK, bar, 3, border_radius=10)
        sh = pygame.Rect(PX + 310, 66, 66, 24)
        pygame.draw.rect(surf, lighten(COLOR_RGB["B"], 0.55) if shield else PAPER_DIM, sh,
                         border_radius=12)
        pygame.draw.rect(surf, INK, sh, 2, border_radius=12)
        draw_text(surf, font(20), "shield %d" % shield, sh.center, INK, center=True)
        # glint, turn, par
        glint_icon(surf, PX + 8, 106)
        draw_text(surf, font(22), "%d glint" % self.run.gold, (PX + 20, 98), INK)
        turn = self.state.turn
        draw_text(surf, font(22), "Turn %d" % turn, (PX + 130, 98), INK)
        if self.par is not None:
            col = GOOD if turn <= self.par else (ACCENT if turn == self.par + 1 else BAD)
            draw_text(surf, font(22), "Par %d" % self.par, (PX + 210, 98), col)
        draw_text(surf, font(18), "Light (+%d of each colour every turn)" % p.mods["regen"],
                  (PX, 122), DIM)
        for i, c in enumerate(PRIMARIES):
            x = PX + i * 126
            cap = p.cap[c]
            step = min(18, 96 // max(1, cap))
            for k in range(cap):
                cx = x + 8 + k * step
                full = k < pal[c]
                pygame.draw.circle(surf, COLOR_RGB[c] if full else PAPER_DIM, (cx, 148), 7)
                pygame.draw.circle(surf, INK, (cx, 148), 7, 2)
            draw_colour_mark(surf, c, x + 8, 148, 7)
            draw_text(surf, font(18), "%d/%d" % (pal[c], cap), (x + 8 + cap * step, 141), DIM)
        draw_text(surf, font(18), "Pattern: where it goes (each once per turn)", (PX, 172), DIM)
        draw_text(surf, font(18), "Shape: the only shapes it touches (Tab)", (PX, 246), DIM)
        draw_text(surf, font(18), "Colour: what it does (mixes cost both parts)", (PX, 300), DIM)
        self.draw_buttons(surf)
        draw_wrapped(surf, font(20), self.msg, (PX, 480), 372, self.msg_color, 0)
        # the Set
        y = 532
        draw_text(surf, font(18), "The Set here (own colour absorbs, opposite = x2)", (PX, y), DIM)
        y += 18
        foes = self.state.enemies
        shown = foes[:4] if len(foes) <= 4 else foes[:3]
        for e in shown:
            spec = KINDS[e.kind]
            shape = self._cur_shape(e)
            draw_critter(surf, shape, PX + 10, y + 9, 8, COLOR_RGB[e.color], shadow=False,
                         width=2)
            draw_colour_mark(surf, e.color, PX + 18, y + 3, 5)
            draw_text(surf, font(18), "%s %d/%d" % (spec["label"], e.hp, e.max_hp), (PX + 26, y + 1), INK)
            draw_pattern_icon(surf, spec["pattern"], PX + 160, y + 9, 3, INK, you=False)
            wk = OPPOSITE[e.color]
            tx = PX + 190
            draw_text(surf, font(18), "weak:", (tx, y + 1), DIM)
            pygame.draw.circle(surf, COLOR_RGB[wk], (tx + 50, y + 8), 6)
            pygame.draw.circle(surf, INK, (tx + 50, y + 8), 6, 2)
            draw_colour_mark(surf, wk, tx + 50, y + 8, 6)
            tags = ("  stunned" if e.stun else "") + ("  +%d sh" % e.shield if e.shield else "")
            draw_text(surf, font(18), COLOR_NAMES[wk] + tags, (tx + 60, y + 1), INK)
            y += 20
        if len(foes) > len(shown):
            draw_text(surf, font(18), "+%d more (hover them on the board)" % (len(foes) - len(shown)),
                      (PX + 26, y), DIM)

    def draw_timeline(self, surf):
        dmg_by_beat = {}
        for ev in self.pre_events:
            if ev["t"] == "dmg" and ev["who"] == "player" and ev["beat"] < BEATS:
                dmg_by_beat[ev["beat"]] = dmg_by_beat.get(ev["beat"], 0) + ev["took"]
        playing = self.anim["i"] if self.mode == "anim" else -1
        for i in range(BEATS):
            r = self.slot_rect(i)
            filled = i < len(self.queue)
            nextslot = i == len(self.queue) and self.mode == "plan"
            fill = PAPER if filled else lighten(self.style["tiles"][1], 0.2)
            if i == playing or i == self.focus:
                fill = SUNNY
            draw_card(surf, r, fill, 10, 4, ACCENT if nextslot else INK, 4 if nextslot else 3)
            draw_text(surf, font(18), "Beat %d" % (i + 1), (r.x + 8, r.y + 5), DIM)
            if filled:
                a = self.queue[i]
                if a.kind == "cast":
                    draw_pattern_icon(surf, a.pattern, r.x + 20, r.y + 32, 3, COLOR_RGB[a.color],
                                      aim=(a.dx, a.dy) if PATTERNS[a.pattern]["aim"] != "none" else None)
                    draw_body(surf, a.shape, r.x + 46, r.y + 33, 7, COLOR_RGB[a.color], INK, 2)
                    draw_text(surf, font(18), PATTERNS[a.pattern]["name"], (r.x + 58, r.y + 26), INK)
                elif a.kind == "move":
                    cx, cy = r.x + 18, r.y + 32
                    pts = [(cx + a.dx * 8, cy + a.dy * 8), (cx - a.dy * 6 - a.dx * 4, cy + a.dx * 6 - a.dy * 4),
                           (cx + a.dy * 6 - a.dx * 4, cy - a.dx * 6 - a.dy * 4)]
                    pygame.draw.polygon(surf, INK, pts)
                    draw_text(surf, font(18), a.describe(), (r.x + 32, r.y + 26), INK)
                else:
                    draw_text(surf, font(18), a.describe(), (r.x + 8, r.y + 26), INK)
            elif self.mode == "plan":
                draw_text(surf, font(18), "(wait)", (r.x + 8, r.y + 26), DIM)
            if dmg_by_beat.get(i) and self.mode == "plan":
                draw_text(surf, font(22), "-%d" % dmg_by_beat[i], (r.right - 8, r.y + 5), BAD, right=True)

    def danger_at(self, tile):
        """[(beat, enemy id, hits you?)] for every strike planned on `tile`."""
        out = []
        for ev in self.pre_events:
            if ev["t"] == "enemy_attack" and ev["beat"] < BEATS and tuple(tile) in \
                    [tuple(t) for t in ev["tiles"]]:
                where = self.pre_snaps[min(ev["beat"], len(self.pre_snaps) - 1)]["player"][:2]
                out.append((ev["beat"], ev["who"], ev["hit"] and tuple(where) == tuple(tile),
                            ev["dmg"]))
        return sorted(set(out))

    def draw_danger_popup(self, surf, tile, note=None):
        """DANGER: who strikes this tile, on which beat, and whether you'll be on it."""
        danger = self.danger_at(tile)
        if not danger:
            return False
        r = self.tile_rect(*tile)
        lines = danger[:4]
        tip = pygame.Rect(0, 0, 300, 40 + 24 * len(lines) + (22 if note else 0))
        tip.midbottom = (r.centerx, r.y - 8)
        if tip.y < 50:
            tip.midtop = (r.centerx, r.bottom + 8)
        tip.clamp_ip(pygame.Rect(6, 50, 940, 580))
        draw_card(surf, tip, PAPER, 10, 4)
        draw_text(surf, font(22), "DANGER", (tip.x + 12, tip.y + 8), BAD)
        draw_text(surf, font(17), "a shape will strike this tile", (tip.x + 86, tip.y + 11), DIM)
        y = tip.y + 34
        names = {e.id: e for e in self.state.enemies + self.pre.enemies}
        for beat, eid, you, dmg in lines:
            info = self.who(eid, beat)
            e = names.get(eid)
            if info:
                draw_body(surf, info[2], tip.x + 20, y + 9, 7, COLOR_RGB[info[1]], INK, 2)
            label = "%s %s" % (COLOR_NAMES[info[1]].lower(), KINDS[e.kind]["label"]) if (info and e) \
                else "a shape"
            draw_text(surf, font(19), "%s, beat %d" % (label, beat + 1), (tip.x + 34, y + 1), INK)
            draw_text(surf, font(19), ("hits you -%d" % dmg) if you else "you're not here",
                      (tip.right - 10, y + 1), BAD if you else GOOD, right=True)
            y += 24
        if note:
            draw_text(surf, font(17), note, (tip.x + 12, y + 2), ACCENT)
        return True

    def draw_tooltip(self, surf):
        """Hovering an enemy explains what it is and does; hovering a danger
        tile says who will strike it and when."""
        if self.mode != "plan" or self.tile_hover is None or self.armed():
            self.draw_first_danger_tip(surf)
            return
        e = self.state.enemy_at(*self.tile_hover)
        twin = self.state.board.portals.get(self.tile_hover)
        special = self.state.board.tiles.get(self.tile_hover)
        if e is None and (twin is not None or special) and not self.danger_at(self.tile_hover):
            # a special tile: what it does (a knothole also shows where it comes out)
            if twin is not None:
                self._dots(surf, self.cell_center(*self.tile_hover), self.cell_center(*twin), WHITE)
                name = twist_name("holes", getattr(self.run, "tower", None))[:-1]
                line = "Roll in: out of its twin, still rolling."
            else:
                twist = {"spring": "springs", "snow": "snow"}.get(special) or (
                    "bends" if special.startswith("bend") else "currents" if special.startswith("current")
                    else "gusts" if special.startswith("gust") else "pools")
                name = twist_name(twist, getattr(self.run, "tower", None))
                name = name[:-1] if name.endswith("s") else name
                line = TWISTS[twist]["short"].capitalize() + "."
                if twist == "pools":
                    name = "%s pool" % COLOR_NAMES[special[5:]]
            r = self.tile_rect(*self.tile_hover)
            f = font(18)
            tip = pygame.Rect(0, 0, max(200, f.size(line)[0] + 26), 62)
            tip.midbottom = (r.centerx, r.y - 6)
            if tip.y < 60:
                tip.midtop = (r.centerx, r.bottom + 6)
            tip.clamp_ip(pygame.Rect(OX - 10, 50, GRID_W * CELL + 20, 560))
            draw_card(surf, tip, PAPER, 10, 4)
            draw_text(surf, font(22), name, (tip.x + 12, tip.y + 8), INK)
            draw_text(surf, f, line, (tip.x + 12, tip.y + 34), DIM)
            return
        if e is None:
            if self.draw_danger_popup(surf, self.tile_hover):
                self.danger_tip_done()
            else:
                self.draw_first_danger_tip(surf)
            return
        spec = KINDS[e.kind]
        shape = self._cur_shape(e)
        r = self.tile_rect(*self.tile_hover)
        tip = pygame.Rect(0, 0, 300, 104)
        tip.midbottom = (r.centerx, r.y - 6)
        if tip.y < 60:
            tip.midtop = (r.centerx, r.bottom + 6)
        tip.clamp_ip(pygame.Rect(OX - 10, 50, GRID_W * CELL + 20, 560))
        draw_card(surf, tip, PAPER, 10, 4)
        draw_critter(surf, shape, tip.x + 22, tip.y + 24, 11, COLOR_RGB[e.color],
                     shadow=False, width=2, mark=spec.get("mark"))
        draw_colour_mark(surf, e.color, tip.x + 32, tip.y + 14, 6)
        draw_text(surf, font(22), spec["label"], (tip.x + 42, tip.y + 8), INK)
        draw_text(surf, font(18), "%s %s. Weak to %s." % (COLOR_NAMES[e.color], shape,
                                                         COLOR_NAMES[OPPOSITE[e.color]]),
                  (tip.x + 42, tip.y + 28), DIM)
        draw_pattern_icon(surf, spec["pattern"], tip.right - 28, tip.y + 26, 4, BAD)
        draw_wrapped(surf, font(18), spec["desc"], (tip.x + 10, tip.y + 50), tip.w - 20, INK)

    def beat_story(self, f):
        """What happens on beat f, in order, in words: you first, then the Set."""
        a = self.queue[f] if f < len(self.queue) else wait()
        parts = ["You: %s" % a.describe().lower()]
        names = {}
        for e in self.state.enemies + self.pre.enemies:
            names.setdefault(e.id, "%s %s" % (COLOR_NAMES[e.color].lower(), KINDS[e.kind]["label"]))
        verbs = {"halo": "hits the 8 tiles around it", "leap": "Leaps", "splash": "lobs a plus",
                 "line": "fires along its line", "hit": "strikes"}
        for ev in self.pre_events:
            if ev.get("beat") != f or ev.get("who") == "player":
                continue
            n = names.get(ev.get("who"), "a shape")
            if ev["t"] == "move":
                parts.append("%s steps %s" % (n, DIR_NAMES.get((ev["to"][0] - ev["frm"][0],
                                                               ev["to"][1] - ev["frm"][1]), "")))
            elif ev["t"] == "enemy_attack":
                parts.append("%s %s%s" % (n, verbs.get(ev["order"], "attacks"),
                                          " and HITS YOU for %d" % ev["dmg"] if ev["hit"] else " (misses)"))
            elif ev["t"] == "stunned":
                parts.append("%s is stunned" % n)
            elif ev["t"] == "blocked":
                parts.append("%s is blocked" % n)
            elif ev["t"] == "kill":
                parts.append("%s is knocked loose" % n)
            elif ev["t"] == "spawn":
                parts.append("a %s appears" % KINDS[ev["kind"]]["label"])
        return "; ".join(parts) + "."

    # -- the first danger tile you ever see gets pointed out
    def danger_tip_done(self):
        if not self.app.meta.data.get("seen_danger_tip"):
            self.app.meta.data["seen_danger_tip"] = True
            self.app.meta.save()

    def draw_first_danger_tip(self, surf):
        if self.mode != "plan" or self.app.meta.data.get("seen_danger_tip") or self.banner \
                or self.focus is not None:
            return
        tiles = [t for ev in self.pre_events if ev["t"] == "enemy_attack" and ev["beat"] < BEATS
                 for t in ev["tiles"]]
        if not tiles:
            return
        p = self.state.player
        tile = min(tiles, key=lambda t: abs(t[0] - p.x) + abs(t[1] - p.y))
        r = self.draw_rect(*tile)
        grow = 4 + int(abs(math.sin(self.t * 4)) * 6)
        pygame.draw.rect(surf, SUNNY, r.inflate(grow, grow), 4, border_radius=10)
        self.draw_danger_popup(surf, tile, note="Hover any striped tile to ask who and when.")

    def draw_legend(self, surf, x, y):
        """What the marks on the board mean, drawn with the marks themselves."""
        f = font(17)
        _tag(surf, x - 6, y, "triangle", COLOR_RGB["B"], 2)
        r = draw_text(surf, f, "who strikes, on which beat", (x + 30, y + 2), WHITE, shadow=INK)
        box = pygame.Rect(r.right + 14, y, 20, 20)
        hatch(surf, box, COLOR_RGB["B"], 170, 6, 3)
        pygame.draw.rect(surf, INK, box, 2, border_radius=4)
        r = draw_text(surf, f, "danger (hover it)", (box.right + 6, y + 2), WHITE, shadow=INK)
        box = pygame.Rect(r.right + 14, y, 20, 20)
        pygame.draw.rect(surf, PAPER, box, border_radius=4)
        pygame.draw.rect(surf, BAD, box, 4, border_radius=4)
        draw_text(surf, f, "hits you", (box.right + 6, y + 2), WHITE, shadow=INK)
        y += 24
        pygame.draw.circle(surf, COLOR_RGB["Y"], (x + 9, y + 9), 8)
        pygame.draw.circle(surf, INK, (x + 9, y + 9), 8, 2)
        draw_text(surf, f, "1", (x + 9, y + 10), WHITE, center=True, shadow=INK)
        draw_text(surf, f, "where it steps.  Hover a beat below (or Q/E) to play the turn one beat "
                  "at a time.", (x + 24, y + 2), WHITE, shadow=INK)

    def draw(self, surf):
        self.backdrop.draw(surf)
        kind = self.run.current_kind()
        f = self.focus
        if f is not None:
            heading(surf, "BEAT %d / %d" % (f + 1, BEATS), (OX, 10), 34)
            draw_wrapped(surf, font(18), self.beat_story(f), (210, 6), 560, WHITE, 0, shadow=INK)
        else:
            title = node_title(kind, self.run.keeper())
            heading(surf, title, (OX, 4), 32)
            draw_text(surf, font(18), self.run.place()["name"],
                      (OX + 2, 34), WHITE, shadow=INK)
            if self.mode == "plan":
                self.draw_legend(surf, 206, 6)
            else:
                draw_text(surf, font(20), "Resolving... click or press a key to skip.", (206, 18),
                          WHITE, shadow=INK)
        self.draw_board(surf)
        self.draw_timeline(surf)
        self.draw_panel(surf)
        self.draw_tooltip(surf)
        self.draw_banner(surf)
        self.draw_bubbles(surf)

    def draw_bubbles(self, surf):
        """Speech bubbles: white, inked, with a tail pointing at the speaker."""
        f = font(19)
        for b in self.bubbles:
            lines = wrap_text(f, b["text"], 200)
            w = max(f.size(line)[0] for line in lines) + 20
            h = len(lines) * (f.get_height() + 1) + 12
            x, y = b["pos"]
            pop = min(1.0, b["t"] / 0.15)
            box = pygame.Rect(0, 0, int(w * pop), int(h * pop))
            box.midbottom = (int(x), int(y) - 26)
            box.clamp_ip(pygame.Rect(4, 4, 952, 600))
            tail = [(box.centerx - 8, box.bottom - 2), (box.centerx + 8, box.bottom - 2),
                    (int(x), int(y) - 14)]
            pygame.draw.polygon(surf, INK, [(px, py + 3) for px, py in tail])
            pygame.draw.rect(surf, INK, box.move(0, 3), border_radius=10)
            pygame.draw.polygon(surf, WHITE, tail)
            pygame.draw.rect(surf, WHITE, box, border_radius=10)
            pygame.draw.rect(surf, INK, box, 2, border_radius=10)
            if pop >= 1:
                yy = box.y + 6
                for line in lines:
                    draw_text(surf, f, line, (box.centerx, yy + f.get_height() // 2), INK, center=True)
                    yy += f.get_height() + 1

    def draw_banner(self, surf):
        """NEW SHAPE: a burst of light behind a card, shapes spinning in it."""
        b = self.banner
        if b is None:
            return
        t = b["t"]
        k = min(1.0, t / 0.35, (BANNER_TIME - t) / 0.5)
        if k <= 0:
            return
        cx, cy = OX + GRID_W * CELL // 2, OY + GRID_H * CELL // 2 - 30
        rays = pygame.Surface((GRID_W * CELL, GRID_H * CELL), pygame.SRCALPHA)
        rc = (rays.get_width() // 2, rays.get_height() // 2 - 30)
        for i in range(12):
            a0 = t * 0.8 + i * math.tau / 12
            pts = [rc, (rc[0] + math.cos(a0) * 400, rc[1] + math.sin(a0) * 400),
                   (rc[0] + math.cos(a0 + 0.22) * 400, rc[1] + math.sin(a0 + 0.22) * 400)]
            pygame.draw.polygon(rays, (*COLOR_RGB[RAINBOW[i % 6]], int(110 * k)), pts)
        surf.blit(rays, (OX, OY))
        card = pygame.Rect(0, 0, 460, 190)
        card.center = (cx, cy)
        card.y += int((1 - k) * 30)
        draw_card(surf, card, PAPER, 18)
        plural = [SHAPE_PLURAL[sh] for sh in b["shapes"]]
        names = (", ".join(plural[:-1]) + " & " + plural[-1] if len(plural) > 1 else plural[0]).upper()
        label = "THE SET HERE ARE" if b.get("first") else (
            "NEW SHAPE" if len(b["shapes"]) == 1 else "NEW SHAPES")
        if b.get("text"):
            label, names = b["text"][0], b["text"][1]
        draw_text(surf, font(22), label, (card.centerx, card.y + 22), ACCENT, center=True)
        size = 44
        while font(size).size(names)[0] > card.w - 30 and size > 24:
            size -= 4
        draw_text(surf, font(size), names, (card.centerx, card.y + 56), INK, center=True)
        for i, sh in enumerate(b["shapes"]):
            x = card.centerx + (i - (len(b["shapes"]) - 1) / 2) * 70
            draw_critter(surf, sh, x, card.y + 104, 18, COLOR_RGB[RAINBOW[(i * 2 + int(t * 2)) % 6]],
                         look=(math.cos(t * 2), 0), rot=math.sin(t * 3) * 0.3)
        note = b["text"][2] if b.get("text") else (
                "Learn your patterns and colours on them first. Other shapes are coming."
                if b.get("first") and len(b["shapes"]) == 1 else
                "Your light fits one shape at a time (Tab to switch). It passes through the rest.")
        draw_wrapped(surf, font(20), note, (card.x + 20, card.bottom - 50), card.w - 40, DIM, 1,
                     center=True)



def _tag(surf, x, y, shape, rgb, beat):
    """The danger tag drawn on the board: a tiny attacker and its beat."""
    tag = pygame.Rect(x, y, 30, 18)
    pygame.draw.rect(surf, WHITE, tag, border_radius=9)
    pygame.draw.rect(surf, INK, tag, 2, border_radius=9)
    draw_body(surf, shape, tag.x + 9, tag.centery, 6, rgb, INK, 1)
    draw_text(surf, font(17), str(beat), (tag.x + 22, tag.centery + 1), INK, center=True)


class BoardKeyScreen(Screen):
    """How to read the combat board, drawn with the same marks the board uses.
    Opens on your first fight, and from the Key button (K) any time."""

    LINES = (
        ("badge", "A tag on a tile: WHO will strike it (a tiny copy, in its colour) and WHEN "
                  "(the beat, 1 to 4)."),
        ("stripes", "Stripes in a shape's colour: danger. That shape will strike this tile. "
                    "Hover any of them to ask."),
        ("pink", "Pink: that strike lands on you, where your plan puts you on that beat. "
                 "Step out, stun it, push it, or knock it loose first."),
        ("steps", "A dotted trail with numbers: where a shape will step, and on which beat."),
        ("hp", "The dark pill under a shape is its HP. Your own plan is the white trail."),
        ("order", "Each beat you act first, then the Set. Hover a beat slot under the board "
                  "(or press Q / E) to play the turn one beat at a time. Hover a shape to see "
                  "only its plan."),
    )

    def __init__(self, app):
        super().__init__(app)
        self.backdrop = Backdrop.for_act(getattr(app.run, "act", 1) if app.run else 1, n=12)
        self.add((380, 584, 200, 42), "Got it", self.close, key=pygame.K_RETURN, tag="back")

    def close(self):
        self.app.meta.data["seen_board_key"] = True
        self.app.meta.save()
        self.app.pop()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_k, pygame.K_SPACE):
            self.close()
            return True
        return super().handle(ev)

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        heading(surf, "Reading the board", (480, 30), 40, center=True)
        card = draw_card(surf, (24, 64, 912, 506))
        c = 62
        ox, oy = card.x + 20, card.y + 60
        tiles = (255, 241, 222), (255, 230, 204)
        for gx in range(6):
            for gy in range(5):
                pygame.draw.rect(surf, tiles[(gx + gy) % 2], (ox + gx * c + 2, oy + gy * c + 2, c - 4, c - 4),
                                 border_radius=7)

        def centre(gx, gy):
            return ox + gx * c + c // 2, oy + gy * c + c // 2

        pulse = 0.5 + 0.5 * math.sin(self.t * 6)
        # a blue Lancer fires down its column on beat 2, into where you stand
        for gy in (1, 2, 3):
            r = pygame.Rect(ox + 1 * c + 2, oy + gy * c + 2, c - 4, c - 4)
            hatch(surf, r, darken(COLOR_RGB["B"], 0.15), 110, 10, 4)
        r = pygame.Rect(ox + 1 * c + 1, oy + 3 * c + 1, c - 2, c - 2)
        pygame.draw.rect(surf, BAD, r, 3 + int(2 * pulse), border_radius=8)
        # a red Stomper steps twice, then hits around itself on beat 3
        halo = ((3, 1), (4, 1), (5, 1), (3, 2), (5, 2), (3, 3), (4, 3), (5, 3))
        for gx, gy in halo:
            hatch(surf, pygame.Rect(ox + gx * c + 2, oy + gy * c + 2, c - 4, c - 4),
                  darken(COLOR_RGB["R"], 0.15), 110, 10, 4)
        badge = [((1, 1), "triangle", "B", 2), ((1, 2), "triangle", "B", 2), ((1, 3), "triangle", "B", 2)]
        badge += [(t, "square", "R", 3) for t in halo]
        for (gx, gy), shape, col, beat in badge:
            _tag(surf, ox + gx * c + 5, oy + gy * c + 5, shape, COLOR_RGB[col], beat)
        for (a, b), (gx, gy), beat in ((((4, 0), (4, 1)), (4, 1), 1), (((4, 1), (4, 2)), (4, 2), 2)):
            pa, pb = centre(*a), centre(*b)
            n = 6
            for k in range(1, n):
                x = pa[0] + (pb[0] - pa[0]) * k / n
                y = pa[1] + (pb[1] - pa[1]) * k / n
                pygame.draw.circle(surf, INK, (int(x), int(y) + 1), 4)
                pygame.draw.circle(surf, lighten(COLOR_RGB["R"], 0.2), (int(x), int(y)), 3)
            cx, cy = centre(gx, gy)
            pygame.draw.circle(surf, COLOR_RGB["R"], (cx, cy + 14), 8)
            pygame.draw.circle(surf, INK, (cx, cy + 14), 8, 2)
            draw_text(surf, font(16), str(beat), (cx, cy + 15), WHITE, center=True, shadow=INK)
        draw_critter(surf, "triangle", *centre(1, 0), 16, COLOR_RGB["B"], look=(0, 1), mark="horn")
        draw_critter(surf, "square", *centre(4, 0), 16, COLOR_RGB["R"], look=(-1, 1), mark="feet")
        for (gx, gy), hp in (((1, 0), 3), ((4, 0), 4)):
            cx, cy = centre(gx, gy)
            pill = pygame.Rect(0, 0, 26, 16)
            pill.midtop = (cx, cy + 20)
            pygame.draw.rect(surf, INK, pill, border_radius=8)
            draw_text(surf, font(18), str(hp), pill.center, WHITE, center=True)
        draw_player(surf, "triangle", *centre(1, 3), 17, self.t, look=(0, -1))
        draw_text(surf, font(18), "you", (centre(1, 3)[0], centre(1, 3)[1] + 34), INK, center=True)
        draw_wrapped(surf, font(24), "Nothing on this board is hidden or random. If the preview says "
                     "a plan is safe, it is.", (card.x + 24, card.bottom - 80), card.w - 48, ACCENT, 2,
                     center=True)
        # the words
        y = card.y + 22
        x = card.x + 410
        for key, text in self.LINES:
            self._icon(surf, key, x + 14, y + 12)
            y = draw_wrapped(surf, font(22), text, (x + 40, y), card.right - x - 60, INK, 2) + 16
        self.draw_buttons(surf)

    def _icon(self, surf, key, cx, cy):
        if key == "badge":
            _tag(surf, cx - 15, cy - 9, "triangle", COLOR_RGB["B"], 2)
        elif key == "stripes":
            r = pygame.Rect(cx - 12, cy - 12, 24, 24)
            hatch(surf, r, COLOR_RGB["B"], 170, 7, 3)
            pygame.draw.rect(surf, INK, r, 2, border_radius=4)
        elif key == "pink":
            r = pygame.Rect(cx - 12, cy - 12, 24, 24)
            pygame.draw.rect(surf, PAPER, r, border_radius=4)
            pygame.draw.rect(surf, BAD, r, 4, border_radius=4)
        elif key == "hp":
            pill = pygame.Rect(cx - 13, cy - 8, 26, 16)
            pygame.draw.rect(surf, INK, pill, border_radius=8)
            draw_text(surf, font(18), "4", pill.center, WHITE, center=True)
        elif key == "steps":
            pygame.draw.circle(surf, COLOR_RGB["R"], (cx, cy), 9)
            pygame.draw.circle(surf, INK, (cx, cy), 9, 2)
            draw_text(surf, font(16), "1", (cx, cy + 1), WHITE, center=True, shadow=INK)
        else:
            box = pygame.Rect(cx - 14, cy - 10, 28, 22)
            pygame.draw.rect(surf, SUNNY, box, border_radius=5)
            pygame.draw.rect(surf, INK, box, 2, border_radius=5)
            draw_text(surf, font(16), "2", box.center, INK, center=True)
