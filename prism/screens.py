"""All screens: title, help, route map, combat, reward, shop, rest, event, end."""

import math

import pygame

from . import rules
from .consts import (BEATS, COLOR_EFFECT, COLOR_NAMES, COLOR_RGB, COLORS, COMPONENTS,
                     GRID_H, GRID_W, OPPOSITE, PRIMARIES, RELICS, SHAPE_DESC,
                     SHAPE_NAMES, SHAPES)
from .enemies import KINDS, is_boss
from .state import cast, move, wait
from .widgets import (ACCENT, BAD, BG, DIM, GOOD, GRID_A, GRID_B, PANEL, PANEL_LIGHT,
                      TEXT, WALL, WARN, Button, draw_shape, draw_text, draw_wrapped,
                      tint, wrap_text)

CELL = 56
OX, OY = 24, 64
BEAT_TIME = 0.55


class Screen:
    def __init__(self, app):
        self.app = app
        self.buttons = []
        self.hover = None
        self.msg = ""
        self.msg_color = DIM

    # -- plumbing
    def add(self, rect, label, callback, **kw):
        b = Button(rect, label, callback, **kw)
        self.buttons.append(b)
        return b

    def say(self, msg, color=DIM):
        self.msg, self.msg_color = msg, color
        self.app.dirty = True

    def button_at(self, pos):
        for b in reversed(self.buttons):
            if b.rect.collidepoint(pos):
                return b
        return None

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            hb = self.button_at(ev.pos)
            if hb is not self.hover:
                self.hover = hb
                self.app.dirty = True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            b = self.button_at(ev.pos)
            if b is not None:
                b.click()
                self.app.dirty = True
                return True
        elif ev.type == pygame.KEYDOWN:
            for b in list(self.buttons):
                if b.key == ev.key and b.enabled:
                    b.click()
                    self.app.dirty = True
                    return True
        return False

    def update(self, dt):
        return False

    def draw_buttons(self, surf):
        f = self.app.fonts[22]
        for b in self.buttons:
            b.draw(surf, f, hover=(b is self.hover))

    def draw(self, surf):
        surf.fill(BG)
        self.draw_buttons(surf)


_BIG = None


class CardButton(Button):
    """A wide button with a title and a description line."""

    def __init__(self, rect, label, desc, callback, **kw):
        super().__init__(rect, label, callback, **kw)
        self.desc = desc

    def draw(self, surf, font, hover=False):
        base = self.color if self.enabled else (36, 38, 52)
        if self.enabled and hover:
            base = tuple(min(255, c + 22) for c in base)
        pygame.draw.rect(surf, base, self.rect, border_radius=8)
        pygame.draw.rect(surf, (96, 104, 140) if self.enabled else (50, 52, 70),
                         self.rect, 1, border_radius=8)
        global _BIG
        if _BIG is None:
            _BIG = pygame.font.Font(None, 28)
        big = _BIG
        color = TEXT if self.enabled else (96, 100, 120)
        draw_text(surf, big, self.label, (self.rect.x + 14, self.rect.y + 8), color)
        draw_wrapped(surf, font, self.desc, (self.rect.x + 14, self.rect.y + 34),
                     self.rect.w - 28, DIM if self.enabled else (80, 84, 104))


# ----------------------------------------------------------------- title

class TitleScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.add((380, 300, 200, 48), "New Run", app.new_run, key=pygame.K_RETURN,
                 color=(70, 90, 160))
        self.add((380, 360, 200, 48), "How to Play", lambda: app.push(HelpScreen(app)),
                 key=pygame.K_h)
        self.add((380, 420, 200, 48), "Quit", app.quit, key=pygame.K_ESCAPE)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[72], "PRISM DELVE", (480, 130), TEXT, center=True)
        draw_text(surf, f[26], "Plan four beats. Mix colours. Shape the fight.",
                  (480, 190), DIM, center=True)
        for i, c in enumerate(COLORS):
            draw_shape(surf, SHAPES[i % 3], 330 + i * 60, 245, 14, COLOR_RGB[c])
        d = self.app.meta.data
        draw_text(surf, f[22], "Runs %d   Wins %d   Best act %d" % (d["runs"], d["wins"], d["best_act"]),
                  (480, 500), DIM, center=True)
        draw_text(surf, f[18], "Enter: new run   H: how to play   Esc: quit", (480, 530),
                  DIM, center=True)
        self.draw_buttons(surf)


HELP_TEXT = (
    "THE TURN\n"
    "Each turn you queue up to 4 beats: move, cast, or wait. Press Enter to resolve. "
    "Each beat you act first, then every enemy acts. Enemy attacks are shown as orange "
    "tiles with the beat number; red-outlined tiles will hit you.\n\n"
    "CASTING\n"
    "Pick a shape (1/2/3) and a colour (R G B Y C M), then click a target tile. "
    "Triangle pierces a line of 3, Square hits a 2x2 block, Circle hits a plus shape. "
    "Primaries cost one charge. Mixed colours cost one of each part: Yellow = R+G, "
    "Cyan = G+B, Magenta = R+B. Charges regenerate each turn.\n\n"
    "COLOURS\n"
    "Red hits hard. Green pushes (walls and allies hurt). Blue stuns and shields you. "
    "Yellow burns. Cyan stuns and swaps places. Magenta explodes onto neighbours. "
    "The OPPOSITE colour to an enemy deals double damage; its OWN colour is absorbed. "
    "Opposites: Red-Cyan, Green-Magenta, Blue-Yellow.\n\n"
    "CHAINS\n"
    "Casting a different shape from your previous cast raises your chain and the "
    "damage multiplier (x1, x1.5, x2, x2.5). Repeating a shape resets it.\n\n"
    "KEYS\n"
    "Arrows/WASD move. Space waits. Backspace/Z undo. X clears. Esc cancels a cast. "
    "Enter resolves. Click a timeline slot to cut the plan back to it."
)


class HelpScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.add((380, 584, 200, 40), "Back", app.pop, key=pygame.K_ESCAPE)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "How to play", (40, 24), TEXT)
        draw_wrapped(surf, f[22], HELP_TEXT, (40, 80), 880, TEXT, spacing=1)
        self.draw_buttons(surf)


# ----------------------------------------------------------------- route

KIND_STYLE = {
    "fight": ("F", (200, 90, 90)), "elite": ("E", (230, 140, 60)),
    "shop": ("$", (230, 200, 80)), "rest": ("R", (100, 200, 130)),
    "event": ("?", (150, 130, 230)), "boss": ("B", (230, 70, 200)),
}
KIND_LABEL = {
    "fight": "Fight", "elite": "Elite fight", "shop": "Shop", "rest": "Rest site",
    "event": "Event", "boss": "Boss",
}


class RouteScreen(Screen):
    def __init__(self, app, notice=""):
        super().__init__(app)
        self.run = app.run
        self.pos = {}
        layers = self.run.route.layers
        n = len(layers)
        for li, layer in enumerate(layers):
            x = 110 + li * (740 / (n - 1))
            for i in range(len(layer)):
                y = 300 + (i - (len(layer) - 1) / 2) * 110
                self.pos[(li, i)] = (int(x), int(y))
        self.confirm = False
        for order, (idx, node) in enumerate(self.run.choices()):
            li = self.run.layer + 1
            cx, cy = self.pos[(li, idx)]
            self.add((cx - 30, cy - 30, 60, 60), "", lambda i=idx: app.enter_node(i),
                     key=pygame.K_1 + order, tag="node")
        self.abandon = self.add((24, 592, 170, 36), "Abandon run", self.on_abandon)
        if notice:
            self.say(notice, GOOD)

    def on_abandon(self):
        if not self.confirm:
            self.confirm = True
            self.abandon.label = "Click again to abandon"
            self.say("Abandoning ends this run. Click again to confirm.", WARN)
        else:
            self.app.abandon_run()

    def draw_buttons(self, surf):
        f = self.app.fonts[22]
        for b in self.buttons:
            if b.tag != "node":
                b.draw(surf, f, hover=(b is self.hover))

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            if self.confirm:
                self.confirm = False
                self.abandon.label = "Abandon run"
                self.say("Cancelled.", DIM)
            else:
                self.say("Pick a glowing node to continue.", DIM)
            return True
        return super().handle(ev)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        run = self.run
        p = run.player
        draw_text(surf, f[32], "Act %d" % run.act, (24, 16), TEXT)
        draw_text(surf, f[22], "HP %d/%d   Gold %d   Seed %d" % (p.hp, p.max_hp, run.gold, run.seed),
                  (140, 22), DIM)
        layers = run.route.layers
        valid = {run.layer + 1: [i for i, _ in run.choices()]}
        for li, layer in enumerate(layers[:-1]):
            for i, node in enumerate(layer):
                for j in node.nexts:
                    a, b = self.pos[(li, i)], self.pos[(li + 1, j)]
                    on_path = (li, i) in run.visited and (li + 1, j) in run.visited
                    pygame.draw.line(surf, ACCENT if on_path else (60, 64, 90), a, b, 3 if on_path else 2)
        tick = pygame.time.get_ticks() / 400.0
        for li, layer in enumerate(layers):
            for i, node in enumerate(layer):
                glyph, col = KIND_STYLE[node.kind]
                cx, cy = self.pos[(li, i)]
                reachable = li in valid and i in valid[li]
                visited = (li, i) in run.visited
                r = 24 if node.kind != "boss" else 30
                pygame.draw.circle(surf, col if (reachable or visited) else tuple(c // 3 for c in col), (cx, cy), r)
                if reachable:
                    pulse = int(4 + 3 * math.sin(tick))
                    pygame.draw.circle(surf, TEXT, (cx, cy), r + pulse, 2)
                if visited and (li, i) == (run.layer, run.node):
                    pygame.draw.circle(surf, GOOD, (cx, cy), r + 6, 3)
                draw_text(surf, f[32], glyph, (cx, cy), BG, center=True)
        draw_text(surf, f[18], "F fight  E elite  $ shop  R rest  ? event  B boss.  Click a glowing node or press 1-%d."
                  % max(1, len(run.choices())), (24, 540), DIM)
        if run.relics:
            draw_text(surf, f[18], "Relics: " + ", ".join(RELICS[r]["name"] for r in run.relics),
                      (24, 562), WARN)
        draw_text(surf, f[22], self.msg, (24, 70), self.msg_color)
        self.draw_buttons(surf)


# ---------------------------------------------------------------- combat

KEY_MOVES = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
}
KEY_SHAPES = {pygame.K_1: "triangle", pygame.K_2: "square", pygame.K_3: "circle"}
KEY_COLORS = {pygame.K_r: "R", pygame.K_g: "G", pygame.K_b: "B",
              pygame.K_y: "Y", pygame.K_c: "C", pygame.K_m: "M"}


def _lerp(a, b, t):
    return a + (b - a) * t


class CombatScreen(Screen):
    def __init__(self, app, run):
        super().__init__(app)
        self.run = run
        self.state = run.state
        self.queue = []
        self.shape = "triangle"
        self.color = None
        self.tool = "move"
        self.tile_hover = None
        self.mode = "plan"          # "plan" | "anim"
        self.anim = None
        self.last_summary = ""
        self.refresh()
        self.say("Plan up to %d beats, then press Resolve (Enter)." % BEATS, DIM)

    # -- state helpers
    def draw_buttons(self, surf):
        f = self.app.fonts[22]
        for b in self.buttons:
            if not b.tag.startswith("slot"):
                b.draw(surf, f, hover=(b is self.hover))

    def refresh(self):
        self.cur, _ = rules.simulate_prefix(self.state, self.queue)
        self.pre, self.pre_events = rules.preview_full(self.state, self.queue)
        self.build_buttons()
        self.app.dirty = True

    def tile_rect(self, gx, gy):
        return pygame.Rect(OX + gx * CELL, OY + gy * CELL, CELL, CELL)

    def tile_at(self, pos):
        gx, gy = (pos[0] - OX) // CELL, (pos[1] - OY) // CELL
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H and pos[0] >= OX and pos[1] >= OY:
            return int(gx), int(gy)
        return None

    # -- buttons
    def build_buttons(self):
        self.buttons = []
        plan = self.mode == "plan"
        px = 552
        for i, s in enumerate(SHAPES):
            self.add((px + i * 126, 208, 120, 32), "%d %s" % (i + 1, SHAPE_NAMES[s]),
                     lambda s=s: self.pick_shape(s), enabled=plan, key=None,
                     active=(self.shape == s and self.tool == "cast"), tag="shape:" + s)
        pl = self.cur.player
        for i, c in enumerate(COLORS):
            x, y = px + (i % 3) * 126, 264 + (i // 3) * 38
            cost = "+".join(COMPONENTS[c])
            name = COLOR_NAMES[c] if c in PRIMARIES else "%s %s" % (COLOR_NAMES[c], cost)
            ok = plan and rules.can_afford(pl, c)
            self.add((x, y, 120, 32), name, lambda c=c: self.pick_color(c),
                     enabled=ok, chip=COLOR_RGB[c], active=(self.color == c and self.tool == "cast"),
                     tag="color:" + c, small=True)
        self.add((px, 346, 90, 34), "Move", self.pick_move, enabled=plan,
                 active=(self.tool == "move"), tag="tool_move")
        self.add((px + 96, 346, 90, 34), "Wait", lambda: self.queue_action(wait()), enabled=plan,
                 key=None, tag="wait")
        self.add((px + 192, 346, 90, 34), "Undo", self.undo, enabled=plan and bool(self.queue),
                 tag="undo")
        self.add((px + 288, 346, 88, 34), "Clear", self.clear, enabled=plan and bool(self.queue),
                 tag="clear")
        n = len(self.queue)
        label = "Resolve turn (Enter)" if n == BEATS else (
            "Pass turn (Enter)" if n == 0 else "Resolve %d beat%s, rest wait" % (n, "s" if n != 1 else ""))
        self.add((px, 390, 376, 44), label, self.resolve, enabled=plan, tag="resolve",
                 color=(70, 110, 80))
        self.add((px + 300, 16, 76, 28), "Help", lambda: self.app.push(HelpScreen(self.app)),
                 tag="help", key=pygame.K_h)
        for i in range(BEATS):
            self.add(self.slot_rect(i), "", lambda i=i: self.cut_to(i), enabled=plan and i < len(self.queue),
                     tag="slot%d" % i, color=PANEL)

    def slot_rect(self, i):
        return pygame.Rect(OX + i * 126, 580, 120, 50)

    # -- actions
    def pick_shape(self, s):
        self.shape = s
        self.tool = "cast"
        if self.color is None:
            self.say("%s selected: %s. Now pick a colour." % (SHAPE_NAMES[s], SHAPE_DESC[s]), ACCENT)
        else:
            self.say("%s %s: click a target tile." % (COLOR_NAMES[self.color], SHAPE_NAMES[s]), ACCENT)
        self.build_buttons()

    def pick_color(self, c):
        self.color = c
        self.tool = "cast"
        self.say("%s (%s): %s. Click a target tile." % (COLOR_NAMES[c], "+".join(COMPONENTS[c]),
                                                       COLOR_EFFECT[c]), ACCENT)
        self.build_buttons()

    def pick_move(self):
        self.tool = "move"
        self.say("Move tool: click a tile next to you, or use the arrow keys.", DIM)
        self.build_buttons()

    def cancel_selection(self):
        if self.tool == "cast" or self.color is not None:
            self.color = None
            self.tool = "move"
            self.say("Cast cancelled.", DIM)
        else:
            self.say("Nothing to cancel.", DIM)
        self.build_buttons()

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
        self.last_summary = "Turn done: you took %d, enemies lost %d." % (
            max(0, hp_before - self.state.player.hp), max(0, foes_before - foes_after))
        self.anim = {"snaps": [before] + res.snapshots, "events": res.events,
                     "i": 0, "t": 0.0, "outcome": res.outcome}
        self.mode = "anim"
        self.queue = []
        self.build_buttons()
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
            self.say("%s Turn %d: plan your beats." % (self.last_summary, self.state.turn), DIM)

    def skip_anim(self):
        if self.mode == "anim":
            self.finish_anim()

    # -- input
    def board_click(self, tile):
        gx, gy = tile
        if self.tool == "cast" and self.color is not None:
            self.queue_action(cast(self.shape, self.color, gx, gy))
            return
        p = self.cur.player
        dx, dy = gx - p.x, gy - p.y
        if abs(dx) + abs(dy) == 1:
            self.queue_action(move(dx, dy))
        elif (dx, dy) == (0, 0):
            self.say("That is you. Pick a colour to cast, or click an adjacent tile to move.", DIM)
        else:
            self.say("Move one tile at a time, or pick a colour to cast.", DIM)

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
        elif k in KEY_SHAPES:
            self.pick_shape(KEY_SHAPES[k])
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
        elif k == pygame.K_ESCAPE:
            self.cancel_selection()
        else:
            return False
        return True

    def update(self, dt):
        if self.mode != "anim":
            return False
        a = self.anim
        a["t"] += dt
        while a["t"] >= BEAT_TIME:
            a["t"] -= BEAT_TIME
            a["i"] += 1
            if a["i"] >= len(a["snaps"]) - 1:
                self.finish_anim()
                return True
        return True

    # -- drawing
    def view(self):
        """(positions/hp for drawing, t, beat index, events) for plan or anim."""
        if self.mode == "anim":
            a = self.anim
            i = min(a["i"], len(a["snaps"]) - 2)
            return a["snaps"][i], a["snaps"][i + 1], a["t"] / BEAT_TIME, i
        snap = rules.snapshot(self.state)
        return snap, snap, 0.0, -1

    def cell_center(self, x, y):
        return OX + int((x + 0.5) * CELL), OY + int((y + 0.5) * CELL)

    def draw_enemy(self, surf, kind, x, y, hp, max_hp, color, shield, stun, burn, ghost=False,
                   alpha_scale=1.0):
        spec = KINDS[kind]
        cx, cy = self.cell_center(x, y)
        r = 22 if is_boss(kind) else 17
        rgb = COLOR_RGB[color]
        if ghost:
            draw_shape(surf, spec["shape"], int(cx), int(cy), r, BG, outline=rgb, width=2)
            return
        draw_shape(surf, spec["shape"], int(cx), int(cy), r, tuple(int(c * alpha_scale) for c in rgb),
                   outline=TEXT if is_boss(kind) else BG, width=2)
        f = self.app.fonts
        draw_text(surf, f[18], spec["label"][0], (int(cx), int(cy)), BG, center=True)
        draw_text(surf, f[18], "%d" % hp, (int(cx), int(cy) + r + 6), TEXT, center=True)
        if shield:
            pygame.draw.circle(surf, (120, 170, 255), (int(cx), int(cy)), r + 4, 2)
        if stun:
            draw_text(surf, f[18], "Z", (int(cx) + r, int(cy) - r - 4), WARN, center=True)
        if burn:
            draw_text(surf, f[18], "~", (int(cx) - r, int(cy) - r - 4), (255, 140, 60), center=True)

    def draw_player(self, surf, x, y, shield, ghost=False):
        cx, cy = self.cell_center(x, y)
        cx, cy = int(cx), int(cy)
        pts = [(cx, cy - 20), (cx + 18, cy), (cx, cy + 20), (cx - 18, cy)]
        if ghost:
            pygame.draw.polygon(surf, TEXT, pts, 1)
            return
        pygame.draw.polygon(surf, (236, 238, 250), pts)
        pygame.draw.circle(surf, (60, 70, 120), (cx, cy), 6)
        if shield:
            pygame.draw.circle(surf, (120, 170, 255), (cx, cy), 24, 2)

    def draw_board(self, surf):
        for gy in range(GRID_H):
            for gx in range(GRID_W):
                r = self.tile_rect(gx, gy)
                if (gx, gy) in self.state.board.walls:
                    pygame.draw.rect(surf, WALL, r)
                    pygame.draw.rect(surf, (110, 116, 142), r.inflate(-10, -10), 2)
                else:
                    pygame.draw.rect(surf, GRID_A if (gx + gy) % 2 == 0 else GRID_B, r)
        a, b, t, seg = self.view()
        if self.mode == "plan":
            self.draw_plan_overlay(surf)
        else:
            self.draw_anim_overlay(surf, seg, t)
        # enemies
        prev = {e[0]: e for e in a["enemies"]}
        nxt = {e[0]: e for e in b["enemies"]}
        for eid, e in prev.items():
            n = nxt.get(eid)
            if n is None:
                if t < 0.6:
                    self.draw_enemy(surf, e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9],
                                    alpha_scale=1.0 - t)
                continue
            x, y = _lerp(e[2], n[2], min(1, t * 1.6)), _lerp(e[3], n[3], min(1, t * 1.6))
            src = n if t >= 0.5 else e
            self.draw_enemy(surf, e[1], x, y, src[4], e[5], n[6] if t >= 0.5 else e[6],
                            src[7], src[8], src[9])
        for eid, n in nxt.items():
            if eid not in prev and t >= 0.4:
                self.draw_enemy(surf, n[1], n[2], n[3], n[4], n[5], n[6], n[7], n[8], n[9])
        pa, pb = a["player"], b["player"]
        self.draw_player(surf, _lerp(pa[0], pb[0], min(1, t * 1.6)), _lerp(pa[1], pb[1], min(1, t * 1.6)),
                         (pb if t >= 0.5 else pa)[3])

    def draw_plan_overlay(self, surf):
        f = self.app.fonts
        # telegraphed enemy attacks from the exact preview of the queued plan
        for ev in self.pre_events:
            if ev["t"] != "enemy_attack":
                continue
            for (x, y) in ev["tiles"]:
                r = self.tile_rect(x, y)
                tint(surf, r, (255, 150, 40), 80)
                if ev["hit"]:
                    pygame.draw.rect(surf, BAD, r, 3)
                draw_text(surf, f[18], str(ev["beat"] + 1), (r.x + 4, r.y + 2), (255, 220, 160))
        # where the plan takes you / the enemies
        p0 = self.state.player
        path = [self.cell_center(p0.x, p0.y)]
        for ev in self.pre_events:
            if ev["t"] == "move" and ev["who"] == "player":
                path.append(self.cell_center(*ev["to"]))
            elif ev["t"] == "swap":
                path.append(self.cell_center(*ev["b"]))
        if len(path) > 1:
            pygame.draw.lines(surf, (200, 210, 255), False, path, 2)
        pp = self.pre.player
        if (pp.x, pp.y) != (p0.x, p0.y):
            self.draw_player(surf, pp.x, pp.y, 0, ghost=True)
        live = {e.id: e for e in self.state.enemies}
        for e in self.pre.enemies:
            o = live.get(e.id)
            if o is not None and (o.x, o.y) != (e.x, e.y):
                self.draw_enemy(surf, e.kind, e.x, e.y, e.hp, e.max_hp, e.color, 0, 0, 0, ghost=True)
        # hover
        t = self.tile_hover
        if t is None:
            return
        if self.tool == "cast" and self.color is not None:
            tiles = rules.shape_tiles(self.cur, self.shape, *t)
            if tiles is None:
                r = self.tile_rect(*t)
                pygame.draw.line(surf, BAD, r.topleft, r.bottomright, 3)
                pygame.draw.line(surf, BAD, r.topright, r.bottomleft, 3)
            else:
                rgb = COLOR_RGB[self.color]
                for tx, ty in tiles:
                    r = self.tile_rect(tx, ty)
                    tint(surf, r, rgb, 110)
                    pygame.draw.rect(surf, rgb, r, 2)
        elif self.tool == "move":
            p = self.cur.player
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                if rules.validate_action(self.cur, move(dx, dy))[0]:
                    tint(surf, self.tile_rect(p.x + dx, p.y + dy), (255, 255, 255), 28)

    def draw_anim_overlay(self, surf, seg, t):
        events = self.anim["events"]
        fade = max(0.0, 1.0 - t)
        for ev in events:
            if ev.get("beat") != seg:
                continue
            if ev["t"] == "cast":
                rgb = COLOR_RGB[ev["color"]]
                for (x, y) in ev["tiles"]:
                    tint(surf, self.tile_rect(x, y), rgb, int(150 * fade))
            elif ev["t"] == "enemy_attack":
                for (x, y) in ev["tiles"]:
                    tint(surf, self.tile_rect(x, y), (255, 120, 40), int(140 * fade))
                    if ev["hit"]:
                        pygame.draw.rect(surf, BAD, self.tile_rect(x, y), 3)
            elif ev["t"] == "dmg" and t > 0.15:
                x, y = ev["pos"]
                r = self.tile_rect(x, y)
                col = BAD if ev["who"] == "player" else TEXT
                draw_text(surf, self.app.fonts[26], "-%d" % ev["took"], (r.centerx, r.y - int(8 * t)),
                          col, center=True)

    def draw_panel(self, surf):
        f = self.app.fonts
        px = 552
        a, b, t, seg = self.view()
        if self.mode == "anim":
            php, shield = (b if t >= 0.5 else a)["player"][2:4]
            pal = (b if t >= 0.5 else a)["palette"]
        else:
            php, shield = self.state.player.hp, self.state.player.shield
            pal = self.cur.player.palette
        p = self.state.player
        pygame.draw.rect(surf, PANEL, (px - 12, 56, 396, 576), border_radius=8)
        draw_text(surf, f[26], "HP %d/%d" % (php, p.max_hp), (px, 66), TEXT)
        pygame.draw.rect(surf, (60, 40, 46), (px + 100, 70, 200, 14), border_radius=4)
        pygame.draw.rect(surf, BAD, (px + 100, 70, int(200 * max(0, php) / p.max_hp), 14), border_radius=4)
        draw_text(surf, f[22], "Shield %d" % shield, (px + 310, 68), (140, 180, 255))
        draw_text(surf, f[22], "Gold %d" % self.run.gold, (px, 98), WARN)
        draw_text(surf, f[22], "Turn %d" % self.state.turn, (px + 100, 98), DIM)
        chain = self.cur.player.chain
        draw_text(surf, f[22], "Chain x%s" % ("%.1f" % ((chain + 1) / 2) if chain else "1"),
                  (px + 200, 98), ACCENT)
        draw_text(surf, f[18], "Charges (regen +%d per colour each turn)" % p.mods["regen"], (px, 122), DIM)
        for i, c in enumerate(PRIMARIES):
            x = px + i * 126
            cap = p.cap[c]
            for k in range(cap):
                rect = pygame.Rect(x + k * 20, 142, 16, 22)
                pygame.draw.rect(surf, COLOR_RGB[c] if k < pal[c] else (50, 52, 70), rect, border_radius=3)
            draw_text(surf, f[18], "%s %d/%d" % (c, pal[c], cap), (x, 167), DIM)
        draw_text(surf, f[18], "Shape", (px, 190), DIM)
        draw_text(surf, f[18], "Colour (mixes cost one of each part)", (px, 246), DIM)
        self.draw_buttons(surf)
        # message
        draw_wrapped(surf, f[22], self.msg, (px, 440), 360, self.msg_color)
        # enemies
        y = 490
        draw_text(surf, f[18], "Enemies (own colour is absorbed, opposite colour = double)", (px, y), DIM)
        y += 20
        shown = self.state.enemies if self.mode == "plan" else self.state.enemies
        for e in shown[:6]:
            spec = KINDS[e.kind]
            draw_shape(surf, spec["shape"], px + 10, y + 9, 8, COLOR_RGB[e.color])
            tags = ("  Z" if e.stun else "") + ("  ~burn" if e.burn else "") + ("  +%d sh" % e.shield if e.shield else "")
            draw_text(surf, f[18], "%s %d/%d  weak: %s%s" % (spec["label"], e.hp, e.max_hp,
                                                          COLOR_NAMES[OPPOSITE[e.color]], tags),
                      (px + 26, y), TEXT)
            y += 20
        if len(self.state.enemies) > 6:
            draw_text(surf, f[18], "+%d more" % (len(self.state.enemies) - 6), (px + 26, y), DIM)

    def draw_timeline(self, surf):
        f = self.app.fonts
        dmg_by_beat = {}
        for ev in self.pre_events:
            if ev["t"] == "dmg" and ev["who"] == "player" and ev["beat"] < BEATS:
                dmg_by_beat[ev["beat"]] = dmg_by_beat.get(ev["beat"], 0) + ev["took"]
        for i in range(BEATS):
            r = self.slot_rect(i)
            pygame.draw.rect(surf, PANEL_LIGHT if i < len(self.queue) else PANEL, r, border_radius=6)
            border = ACCENT if (i == len(self.queue) and self.mode == "plan") else (70, 74, 100)
            pygame.draw.rect(surf, border, r, 2, border_radius=6)
            draw_text(surf, f[18], "Beat %d" % (i + 1), (r.x + 8, r.y + 4), DIM)
            if i < len(self.queue):
                a = self.queue[i]
                if a.kind == "cast":
                    pygame.draw.circle(surf, COLOR_RGB[a.color], (r.x + 14, r.y + 34), 7)
                    draw_text(surf, f[18], "%s" % SHAPE_NAMES[a.shape], (r.x + 26, r.y + 27), TEXT)
                else:
                    draw_text(surf, f[18], a.describe(), (r.x + 8, r.y + 27), TEXT)
            else:
                draw_text(surf, f[18], "(wait)" if self.mode == "plan" else "", (r.x + 8, r.y + 27), (90, 94, 120))
            if dmg_by_beat.get(i) and self.mode == "plan":
                draw_text(surf, f[22], "-%d" % dmg_by_beat[i], (r.right - 8, r.y + 4), BAD, right=True)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        node = self.run.current_kind()
        draw_text(surf, f[32], "%s  -  Act %d" % (KIND_LABEL.get(node, "Fight"), self.run.act), (OX, 20), TEXT)
        if self.mode == "plan":
            draw_text(surf, f[18], "Orange tiles = enemy attacks (number = beat). Red outline = it hits you.",
                      (OX + 260, 28), DIM)
        else:
            draw_text(surf, f[18], "Resolving... click or press a key to skip.", (OX + 260, 28), WARN)
        self.draw_board(surf)
        self.draw_timeline(surf)
        self.draw_panel(surf)
