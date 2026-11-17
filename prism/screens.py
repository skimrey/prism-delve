"""Core screens: title, help and the floor map (route). Combat lives in combat_ui."""

import math
import threading

import pygame

from .art import blink_now, draw_critter, draw_player, ease_out, mix
from .consts import COLOR_RGB, COLORS, PATTERN_ORDER, PATTERNS, RELICS, SHAPES, TOWERS
from .rules import GROUP_STEP
from .scene import (TITLE_SKY, Backdrop, draw_exit_door, draw_facet,
                    draw_node_icon, draw_pattern_icon,
                    draw_slot, draw_tower, glint_icon, heading, heart_icon,
                    node_blurb, node_color, node_title, stat_chip)
from . import sound
from .settings import SETTINGS
from .widgets import (BAD, DIM, GOOD, INK, PAPER, SUNNY, TEXT, WARN, WHITE, Button, draw_card,
                      draw_colour_mark, draw_text, draw_wrapped, font)


class Screen:
    def __init__(self, app):
        self.app = app
        self.buttons = []
        self.hover = None
        self.msg = ""
        self.msg_color = DIM
        self.t = 0.0

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
        """Every screen is gently alive (confetti, bobbing), so always redraw."""
        self.t += dt
        return True

    def draw_buttons(self, surf):
        f = font(22)
        for b in self.buttons:
            b.draw(surf, f, hover=(b is self.hover))

    def draw(self, surf):
        surf.fill(PAPER)
        self.draw_buttons(surf)


class CardButton(Button):
    """A wide card with a title, a description line and an optional icon."""

    def __init__(self, rect, label, desc, callback, icon=None, **kw):
        super().__init__(rect, label, callback, **kw)
        self.desc = desc
        self.card_icon = icon

    def draw(self, surf, fnt, hover=False):
        r = self.rect
        lift = -3 if (hover and self.enabled) else 0
        fill = PAPER if self.enabled else (232, 226, 218)
        if hover and self.enabled:
            fill = (255, 240, 200)
        body = draw_card(surf, r.move(0, lift), fill, 12, 5 if self.enabled else 0,
                         INK if self.enabled else (190, 182, 198))
        x = body.x + 16
        if self.card_icon is not None:
            self.card_icon(surf, body.x + 36, body.centery)
            x = body.x + 70
        color = TEXT if self.enabled else (150, 140, 165)
        if not self.desc:
            draw_text(surf, font(28), self.label, (x, body.centery - 10), color)
            return
        draw_text(surf, font(28), self.label, (x, body.y + 10), color)
        draw_wrapped(surf, fnt, self.desc, (x, body.y + 38), body.right - x - 14,
                     DIM if self.enabled else (170, 162, 182))


# ----------------------------------------------------------------- title

class TitleScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.backdrop = Backdrop(TITLE_SKY, seed=5, n=40, soft=0.25)
        items = [("New Run", app.start_run, pygame.K_RETURN, "new")]
        if app.has_save():
            items.append(("Continue", app.continue_run, pygame.K_c, "continue"))
        if app.hub_open():
            items.append(("The Meadow", app.show_hub, pygame.K_m, "meadow"))
        items += [("The Story", app.show_intro, pygame.K_t, "story"),
                  ("How to Play", lambda: app.push(HelpScreen(app)), pygame.K_h, "help"),
                  ("Settings", lambda: app.push(SettingsScreen(app)), pygame.K_o, "settings"),
                  ("Quit", app.quit, pygame.K_ESCAPE, "quit")]
        y = 318
        for label, fn, key, tag in items:
            self.add((380, y, 200, 35), label, fn, key=key, tag=tag)
            y += 39
        if app.dev:
            from .dev import DevScreen           # testing mode only
            self.add((600, y - 39, 100, 35), "Dev", lambda: app.push(DevScreen(app)), tag="dev",
                     key=pygame.K_F1)

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def _far_towers(self):
        """Small pictures of the towers you've reached so far (for the skyline)."""
        if not hasattr(self, "_towers"):
            from .towers_art import tower_canvas
            from .world import World, plan_of
            data = self.app.meta.data
            self._towers = []
            if data.get("wins", 0) > 0 or self.app.dev:
                world = World(plan_of(data), data.get("friends", []))
                for z in world.zones[:6]:
                    img, _meta = tower_canvas(z.tower)
                    self._towers.append(pygame.transform.scale(img, (img.get_width() // 3, img.get_height() // 3)))
        return self._towers

    def draw(self, surf):
        t = self.t
        from .hubart import title_scene
        scene = title_scene(t, self._far_towers())
        surf.blit(pygame.transform.scale(scene, (960, 640)), (0, 0))
        # the title: every letter its own colour, bobbing in a wave
        word = "PRISM DELVE"
        f = font(96)
        widths = [f.size(ch)[0] for ch in word]
        x = 480 - sum(widths) // 2
        for i, ch in enumerate(word):
            y = 92 + math.sin(t * 2.2 + i * 0.55) * 6
            if ch != " ":
                col = COLOR_RGB[COLORS[i % 6]]
                for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3), (0, 6), (3, 6), (-3, 6)):
                    surf.blit(f.render(ch, True, INK), (x + ox, y + oy))
                surf.blit(f.render(ch, True, col), (x, y))
            x += widths[i]
        rolled = bool(self.app.meta.data.get("finale_seen"))      # (after the Grand Roll, it's Tri rolling too)
        heading(surf, "a triangle who learned to roll" if rolled else "a triangle who wants to roll", (480, 196),
                32, center=True)
        # Tri watches a circle roll past, on a floating island, and follows it with its eyes
        ground = 296
        cx = 480 + math.sin(t * 0.7) * 300
        roll = -math.sin(t * 0.7) * 300 / 22
        draw_player(surf, "circle", cx, ground - 22, 22, t, look=(math.cos(t * 0.7), 0),
                    mood="happy", rot=roll)
        if rolled:                                                   # racing it, round, all the way round
            tx = 480 + math.sin(t * 0.7 - 0.5) * 300
            draw_player(surf, "circle", tx, ground - 26, 26, t, look=(math.cos(t * 0.7 - 0.5), 0),
                        mood="happy", rot=-math.sin(t * 0.7 - 0.5) * 300 / 26)
        else:
            trix = 180
            look = ((cx - trix) / 300, -0.2)
            draw_player(surf, "triangle", trix, ground - 26, 26, t, look=look,
                        blink=blink_now(t, 2))
        d = self.app.meta.data
        draw_text(surf, font(22), "Climbs %d   Rolled away %d   Highest floor %d"
                  % (d["runs"], d["wins"], d["best_act"]), (480, 604), WHITE, center=True, shadow=INK)
        draw_text(surf, font(18), "Enter: new run   T: story   H: how to play   O: settings   Esc: quit",
                  (480, 624), WHITE, center=True, shadow=INK)
        self.draw_buttons(surf)


# ----------------------------------------------------------------- floor pick

class FloorPickScreen(Screen):
    """New Run, once you've been higher than the bottom: the Sorter remembers
    every floor you've reached, and you can slot in at any of them."""

    def __init__(self, app):
        super().__init__(app)
        from .consts import FLOORS
        self.floors = FLOORS
        self.reached = app.floors_reached()
        self.backdrop = Backdrop(TITLE_SKY, seed=4, n=22, soft=0.3)
        for act in (1, 2, 3):
            r = self.card_rect(act)
            self.add((r.x + 30, r.bottom - 56, r.w - 60, 40), "Start here", lambda a=act: app.new_run(a),
                     enabled=act <= self.reached, tag="floor:%d" % act, key=getattr(pygame, "K_%d" % act))
        self.add((380, 580, 200, 44), "Back", app.to_title, key=pygame.K_ESCAPE, tag="back")

    def card_rect(self, act):
        return pygame.Rect(60 + (act - 1) * 290, 130, 260, 420)

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        from .art import gradient
        from .consts import FORMS
        self.backdrop.draw(surf)
        heading(surf, "Where do you slot in?", (480, 52), 44, center=True)
        draw_text(surf, font(20), "The Sorter remembers every floor you've reached. Start at the bottom, or "
                  "slot in higher:", (480, 98), WHITE, center=True, shadow=INK)
        for act in (1, 2, 3):
            r = self.card_rect(act)
            floor = self.floors[act]
            open_ = act <= self.reached
            draw_card(surf, r, PAPER if open_ else (206, 198, 222))
            pic = pygame.Rect(r.x + 12, r.y + 12, r.w - 24, 150)
            surf.blit(gradient(pic.size, *floor["sky"]), pic.topleft)
            pygame.draw.rect(surf, INK, pic, 2)
            form = FORMS[act]
            draw_player(surf, form["shape"], pic.centerx, pic.centery + 10, 36, self.t, look=(0.3, -0.3),
                        mood="happy" if open_ else "plain", rot=math.sin(self.t * 2 + act) * 0.08)
            if not open_:
                veil = pygame.Surface(pic.size, pygame.SRCALPHA)
                veil.fill((40, 30, 72, 150))
                surf.blit(veil, pic.topleft)
                draw_text(surf, font(20), "not reached yet", pic.center, WHITE, center=True, shadow=INK)
            draw_text(surf, font(26), floor["name"], (r.centerx, r.y + 184), INK, center=True)
            draw_text(surf, font(18), "as a %s" % form["name"].lower(), (r.centerx, r.y + 210), DIM, center=True)
            words = floor["blurb"]
            if act > 1:
                words += " You start with the sides and patterns the Keepers below would give, and %d glint." % (
                    45 * (act - 1))
            draw_wrapped(surf, font(17), words, (r.x + 20, r.y + 236), r.w - 40, TEXT, center=True)
        self.draw_buttons(surf)


# ----------------------------------------------------------------- help

HELP_WORLD = (
    "Everything with corners lives in the Sorter: a tower of floors where every door is cut "
    "for one shape. You are Tri, a triangle. You are also a prism: light goes into you white "
    "and comes out as colour. That colour is what you fight with.\n\n"
    "Corners catch on the floor, so everything in the Sorter moves in clicks, four clicks a "
    "turn, everyone together. That is the grid, and those are the beats. Only circles move "
    "smoothly. Circles roll out through the Round Door, down the Long Ramp, into the Meadow. "
    "Tri wants to roll.\n\n"
    "The Set are the shapes that stay exactly as they were cut. A shape that grows a side "
    "leaves a hole in the Sorter, and the Set are afraid of holes, so they come to knock you "
    "back into your slot. They are not cruel. They are tidy.\n\n"
    "Your light follows the Sorter's one rule: it only fits one shape at a time, and passes "
    "through every other. Each Set shape is also dyed one colour: its own colour passes "
    "straight through it, its opposite unmakes it. Knocked loose, a shape falls apart into "
    "edges and leaves glint behind, and the patterns it fought with are yours to learn.\n\n"
    "Each floor's Keeper holds a spare side. Take it and you grow: Triangle, Square, Pentagon, "
    "and then the Round Door. If the Set win, they sort you back to the bottom, a triangle "
    "again. That is why every climb starts over."
)

HELP_RULES = (
    "THE TURN  Queue up to 4 beats: move, cast or wait. Enter resolves them. Each beat you act "
    "first, then every enemy. Stripes: where the Set will strike. A badge on a stripe is a tiny "
    "copy of WHO strikes with WHEN (the beat). Pink: that strike lands on you. Numbered dots: "
    "where a shape steps. Hover a beat slot (or Q/E) to watch one beat at a time; K shows the "
    "board key. Win in as few turns as you can: each fight has a par.\n\n"
    "A CAST  is three picks. PATTERN (1-5): where the light goes, fixed around you; each once "
    "per turn. SHAPE (Tab): the light only touches that shape and passes through the rest. "
    "COLOUR (R G B Y C M): what it does. Then aim on the board.\n\n"
    "GROUPS  Every extra shape one cast fits adds +%d damage to all of them. The Set arrives in "
    "squads that march in formation: catch a whole set in one cast.\n\n"
    "COLOURS  Red 3. Green 2 + push. Blue 1 + stun + shield. Yellow 1 + burn + push. Cyan 2 + "
    "stun + swap. Magenta 4 + splash. Mixes cost both parts. Opposites deal double (R-C, G-M, "
    "B-Y); an enemy's own colour is absorbed. Colour-blind? Turn on colour symbols in Settings: "
    "Red |, Green -, Blue /, and a mix wears both its parts' strokes.\n\n"
    "KEEPERS  change shape every beat (see the strip above them): time your casts."
) % GROUP_STEP


def draw_pattern_legend(surf, x, y, t):
    """Every pattern, drawn. Enemies attack with these same patterns, so each
    one you meet is one you could learn."""
    for i, pt in enumerate(PATTERN_ORDER):
        oy = y + i * 74
        box = pygame.Rect(x, oy, 64, 64)
        pygame.draw.rect(surf, (246, 238, 224), box, border_radius=10)
        pygame.draw.rect(surf, INK, box, 2, border_radius=10)
        draw_pattern_icon(surf, pt, box.centerx, box.centery, 6, COLOR_RGB["RGBYCM"[i]])
        draw_text(surf, font(24), PATTERNS[pt]["name"], (x + 78, oy + 6), INK)
        draw_wrapped(surf, font(18), PATTERNS[pt]["desc"], (x + 78, oy + 30), 200, DIM, 0)
    oy = y + len(PATTERN_ORDER) * 74 + 4
    for i, sh in enumerate(SHAPES):
        bob = math.sin(t * 3 + i) * 2
        draw_critter(surf, sh, x + 18 + i * 50, oy + 18 + bob, 14, COLOR_RGB["RGB"[i]],
                     blink=blink_now(t, i))
    draw_text(surf, font(18), "light fits one shape", (x + 176, oy + 10), DIM)


class HelpScreen(Screen):
    def __init__(self, app, page="world"):
        super().__init__(app)
        self.page = page
        self.backdrop = Backdrop(TITLE_SKY, seed=9, n=18, soft=0.3)
        self.add((380, 588, 200, 40), "Back", app.pop, key=pygame.K_ESCAPE, tag="back")
        self.add((330, 20, 140, 36), "The World", lambda: self.show("world"), tag="page:world")
        self.add((490, 20, 140, 36), "The Rules", lambda: self.show("rules"), tag="page:rules")
        self.show(page)

    def show(self, page):
        self.page = page
        for b in self.buttons:
            if b.tag.startswith("page:"):
                b.active = b.tag == "page:" + page

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT):
            self.show("rules" if self.page == "world" else "world")
            return True
        return super().handle(ev)

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        card = draw_card(surf, (30, 70, 900, 505))
        if self.page == "world":
            draw_wrapped(surf, font(22), HELP_WORLD, (card.x + 24, card.y + 20), 560, INK, spacing=1)
            # the climb, drawn
            draw_tower(surf, (card.right - 290, card.y + 20, 250, 460), 1, self.t)
        else:
            draw_wrapped(surf, font(21), HELP_RULES, (card.x + 24, card.y + 18), 560, INK, spacing=1)
            draw_pattern_legend(surf, card.right - 296, card.y + 14, self.t)
        draw_text(surf, font(18), "Tab switches pages", (card.right - 14, card.bottom - 22), DIM,
                  right=True)
        self.draw_buttons(surf)


# ------------------------------------------------------------- settings

class SettingsScreen(Screen):
    """Colour symbols (for colour-blind players), sound, volume, fullscreen."""

    def __init__(self, app):
        super().__init__(app)
        self.backdrop = Backdrop(TITLE_SKY, seed=17, n=16, soft=0.3)
        self.build()

    def build(self):
        S = SETTINGS
        self.buttons = []
        onoff = lambda v: "On" if v else "Off"
        self.add((340, 150, 280, 40), "Colour-blind mode: " + onoff(S["marks"]),
                 lambda: self.flip("marks"), tag="opt:marks", active=S["marks"], key=pygame.K_1)
        self.add((360, 290, 240, 40), "Sound: " + onoff(S["sound"]), lambda: self.flip("sound"),
                 tag="opt:sound", active=S["sound"], key=pygame.K_2)
        self.add((360, 340, 56, 40), "-", lambda: self.volume(-0.1), tag="vol-", key=pygame.K_MINUS)
        self.add((544, 340, 56, 40), "+", lambda: self.volume(0.1), tag="vol+", key=pygame.K_EQUALS)
        self.add((360, 400, 240, 38), "Fullscreen: " + onoff(S["fullscreen"]),
                 lambda: self.flip("fullscreen"), tag="opt:fullscreen", active=S["fullscreen"],
                 key=pygame.K_3)
        self.add((320, 444, 320, 38), "Every Meadow zone open: " + onoff(S["open_zones"]),
                 lambda: self.flip("open_zones"), tag="opt:open_zones", active=S["open_zones"], key=pygame.K_4)
        self.add((360, 488, 240, 38), "Towers in your world...", self.gallery, tag="gallery", key=pygame.K_5)
        self.add((380, 560, 200, 42), "Back", self.app.pop, key=pygame.K_ESCAPE, tag="back")

    def gallery(self):
        from .gallery import GalleryScreen
        self.app.push(GalleryScreen(self.app))

    def flip(self, key):
        SETTINGS[key] = not SETTINGS[key]
        self.app.apply_settings(refresh_window=(key == "fullscreen"))
        sound.play("ui")
        self.build()

    def volume(self, d):
        SETTINGS["volume"] = round(max(0.0, min(1.0, SETTINGS["volume"] + d)), 2)
        self.app.apply_settings()
        sound.play("cast:G")
        self.build()

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        heading(surf, "Settings", (480, 50), 48, center=True)
        draw_card(surf, (200, 110, 560, 434))
        draw_text(surf, font(20), "Every colour wears its letter: shapes, buttons, the board.",
                  (480, 206), DIM, center=True)
        # what the letters look like
        for i, c in enumerate(("R", "G", "B", "Y", "C", "M")):
            x = 300 + i * 72
            pygame.draw.circle(surf, COLOR_RGB[c], (x, 244), 16)
            pygame.draw.circle(surf, INK, (x, 244), 16, 2)
            draw_colour_mark(surf, c, x, 244, 10, force=True)
        draw_text(surf, font(17), "Red, Green, Blue; and their mixes Yellow (R+G), Cyan (G+B), Magenta (R+B).",
                  (480, 272), DIM, center=True)
        vol = SETTINGS["volume"]
        bar = pygame.Rect(424, 352, 112, 16)
        pygame.draw.rect(surf, (236, 228, 214), bar, border_radius=8)
        pygame.draw.rect(surf, GOOD, (bar.x, bar.y, int(bar.w * vol), bar.h), border_radius=8)
        pygame.draw.rect(surf, INK, bar, 2, border_radius=8)
        draw_text(surf, font(18), "volume %d%%" % round(vol * 100), (480, 386), DIM, center=True)
        self.draw_buttons(surf)


# ----------------------------------------------------------------- route

TRAVEL_TIME = 0.65


class RouteScreen(Screen):
    """The floor map. You stand on the node you last finished and walk to
    the next one. Picking a room starts building it on a worker thread while
    your token travels, so slow room generation is hidden behind the walk."""

    def __init__(self, app, notice=""):
        super().__init__(app)
        self.run = app.run
        self.act = self.run.act
        self.style = self.run.place()
        self.keeper = self.run.keeper()
        self.backdrop = Backdrop.for_run(self.run, n=20)
        layers = self.run.route.layers
        n = len(layers)
        self.map_rect = pygame.Rect(190, 104, 748, 462)
        self.pos = {}
        x_first, x_last = 342, 790
        for li, layer in enumerate(layers):
            x = x_first + li * (x_last - x_first) / max(1, n - 1)
            for i in range(len(layer)):
                y = self.map_rect.centery + 6 + (i - (len(layer) - 1) / 2) * 122
                self.pos[(li, i)] = (int(x), int(y))
        self.start = (248, self.map_rect.centery + 6)
        self.door = (880, self.map_rect.centery + 6)
        self.here = self.start if self.run.layer < 0 else self.pos[(self.run.layer, self.run.node)]
        self.choices = list(self.run.choices())
        self.sel = 0
        self.travel = None
        self.confirm = False
        for order, (idx, node) in enumerate(self.choices):
            cx, cy = self.pos[(self.run.layer + 1, idx)]
            self.add((cx - 32, cy - 32, 64, 64), "", lambda i=idx: self.go(i),
                     key=pygame.K_1 + order, tag="node")
        self.abandon = self.add((18, 596, 150, 34), "Abandon run", self.on_abandon, tag="abandon",
                                small=True)
        if notice:
            self.say(notice, GOOD)

    # -- travel
    def go(self, idx):
        if self.travel is not None:
            return
        if idx not in [i for i, _ in self.choices]:
            self.say("You can't reach that room from here.", BAD)
            return
        job = {"node": None, "error": None}

        def build():
            try:
                job["node"] = self.run.enter(idx)
            except Exception as e:      # surfaced on the main thread in finish_travel
                job["error"] = e

        # everything the walk needs is captured now: the worker thread is
        # about to change run.layer / run.node, so drawing must not read them
        sound.play("step")
        th = threading.Thread(target=build, daemon=True)
        self.travel = {"idx": idx, "t": 0.0, "to": self.pos[(self.run.layer + 1, idx)],
                       "frm": self.here, "thread": th, "job": job,
                       "kind": self.run.route.layers[self.run.layer + 1][idx].kind,
                       "layer": self.run.layer}
        th.start()
        self.app.dirty = True

    def finish_travel(self):
        tr = self.travel
        tr["thread"].join()
        if tr["job"]["error"] is not None:
            raise tr["job"]["error"]
        self.travel = None
        self.app.show_node(tr["job"]["node"])

    def on_abandon(self):
        if not self.confirm:
            self.confirm = True
            self.abandon.label = "Click to confirm"
            self.say("Abandoning lets the Set sort you back. Click again to confirm.", WARN)
        else:
            self.app.abandon_run()

    def draw_buttons(self, surf):
        f = font(22)
        for b in self.buttons:
            if b.tag != "node":
                b.draw(surf, f, hover=(b is self.hover))

    def handle(self, ev):
        if self.travel is not None:
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.finish_travel()
                return True
            return False
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                if self.confirm:
                    self.confirm = False
                    self.abandon.label = "Abandon run"
                    self.say("Cancelled.", DIM)
                else:
                    self.say("Pick a bouncing room to continue.", DIM)
                return True
            if ev.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a) and self.choices:
                self.sel = (self.sel - 1) % len(self.choices)
                return True
            if ev.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d) and self.choices:
                self.sel = (self.sel + 1) % len(self.choices)
                return True
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE) and self.choices:
                self.go(self.choices[self.sel][0])
                return True
        if ev.type == pygame.MOUSEMOTION:
            for k, b in enumerate(b for b in self.buttons if b.tag == "node"):
                if b.rect.collidepoint(ev.pos):
                    self.sel = k
        return super().handle(ev)

    def update(self, dt):
        self.backdrop.update(dt)
        tr = self.travel
        if tr is not None:
            tr["t"] += dt
            if tr["t"] >= TRAVEL_TIME and not tr["thread"].is_alive():
                self.finish_travel()
        return super().update(dt)

    # -- drawing
    def _dotted(self, surf, a, b, color, done, phase=0.0):
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(2, int(dist / 16))
        for k in range(n + 1):
            f = (k + phase) / n
            if f > 1:
                continue
            x, y = a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
            pygame.draw.circle(surf, INK, (int(x), int(y) + 2), 6 if done else 5)
            pygame.draw.circle(surf, color, (int(x), int(y)), 5 if done else 4)

    def draw(self, surf):
        t = self.t
        run = self.run
        style = self.style
        self.backdrop.draw(surf)
        heading(surf, style["name"].upper(), (190, 16), 48)
        draw_text(surf, font(22), style["blurb"], (192, 62), WHITE, shadow=INK)
        # stats
        p = run.player
        x = 632
        form = run.form()
        x = stat_chip(surf, x, 20, lambda s, cx, cy: draw_player(s, form["shape"], cx, cy, 8, t,
                                                                 shadow=False), form["name"]) + 8
        x = stat_chip(surf, x, 20, heart_icon, "%d/%d" % (p.hp, p.max_hp)) + 8
        stat_chip(surf, x, 20, glint_icon, "%d" % run.gold)
        # the tower (where this floor sits in the whole climb)
        draw_card(surf, (14, 104, 164, 462), (255, 250, 238, ), 14)
        if run.tower:
            draw_text(surf, font(20), style["name"], (96, 118), INK, center=True)
            from .towers_art import draw_tower_art
            friend = TOWERS[run.tower]["friend"]
            surf.set_clip(pygame.Rect(18, 134, 156, 428))
            again = getattr(run, "again", False)        # (its friend's out already: nobody at the window)
            draw_tower_art(surf, run.tower, 96, 526, 2, t,
                           friend=None if again else (friend["was"], COLOR_RGB[friend["color"]]))
            surf.set_clip(None)
            draw_text(surf, font(18), "up to the window", (96, 540), DIM, center=True)
        else:
            draw_text(surf, font(22), "The Sorter", (96, 118), INK, center=True)
            draw_tower(surf, (20, 130, 152, 430), self.act, t)
        # the floor itself: a tray of tiles
        mr = self.map_rect
        draw_card(surf, mr, style["tiles"][0], 18)
        inner = mr.inflate(-24, -24)
        for gx in range(inner.x, inner.right - 30, 46):
            for gy in range(inner.y, inner.bottom - 30, 46):
                pygame.draw.rect(surf, style["tiles"][1], (gx + 2, gy + 2, 42, 42), border_radius=6)
        layers = run.route.layers
        valid = {i for i, _ in self.choices}
        here_layer = self.travel["layer"] if self.travel else run.layer
        path_col = style["accent"]
        faint = mix(style["tiles"][1], INK, 0.18)
        # paths
        for i in range(len(layers[0])):
            done = (0, i) in run.visited
            self._dotted(surf, self.start, self.pos[(0, i)], path_col if done else faint, done)
        for li, layer in enumerate(layers[:-1]):
            for i, node in enumerate(layer):
                for j in node.nexts:
                    done = (li, i) in run.visited and (li + 1, j) in run.visited
                    self._dotted(surf, self.pos[(li, i)], self.pos[(li + 1, j)],
                                 path_col if done else faint, done)
        boss_pos = self.pos[(len(layers) - 1, 0)]
        self._dotted(surf, boss_pos, (self.door[0] - 34, self.door[1]), faint, False)
        # live paths from where you stand glow and march
        if self.travel is None:
            for k, (idx, _n) in enumerate(self.choices):
                tgt = self.pos[(run.layer + 1, idx)]
                self._dotted(surf, self.here, tgt, SUNNY if k == self.sel else WHITE, True,
                             phase=(t * 1.5) % 1)
        # start slot and exit door
        came_in = "circle" if run.tower else {1: "triangle", 2: "square", 3: "pentagon"}[self.act]
        draw_slot(surf, came_in, self.start[0], self.start[1] + 30, 24, style["wall"])
        draw_text(surf, font(18), "your slot" if self.act == 1 and not run.tower else "you came in here",
                  (self.start[0], self.start[1] + 62), INK, center=True)
        if run.tower:                     # the goal here is a window, and who's waiting at it
            from .towers_art import draw_tower_art
            draw_tower_art(surf, run.tower, self.door[0], self.door[1] + 64, 1, t)
            draw_text(surf, font(18), "the window", (self.door[0], self.door[1] + 74), INK,
                      center=True)
        else:
            draw_exit_door(surf, style, self.door[0], self.door[1], 28, t)
            draw_text(surf, font(18), style["door_name"], (self.door[0], self.door[1] + 58), INK,
                      center=True)
            draw_text(surf, font(18), "(needs %s)" % {"square": "4 sides", "pentagon": "5 sides",
                                                      "circle": "roundness"}[style["door"]],
                      (self.door[0], self.door[1] + 74), DIM, center=True)
        # nodes
        hover_node = None
        for li, layer in enumerate(layers):
            for i, node in enumerate(layer):
                cx, cy = self.pos[(li, i)]
                reachable = li == here_layer + 1 and i in valid and self.travel is None
                visited = (li, i) in run.visited
                future = li > here_layer
                r = 30 if node.kind != "boss" else 38
                if reachable:
                    k = [c[0] for c in self.choices].index(i)
                    cy += int(-abs(math.sin(t * 3.2 + k)) * 7)
                    if k == self.sel:
                        hover_node = (node.kind, cx, cy)
                ring = node_color(node.kind, t)
                faded = not (reachable or visited or (future and node.kind == "boss"))
                if faded:
                    ring = mix(ring, style["tiles"][0], 0.7)
                pygame.draw.circle(surf, INK, (cx, cy + 4), r)
                pygame.draw.circle(surf, PAPER if not faded else style["tiles"][0], (cx, cy), r)
                pygame.draw.circle(surf, ring, (cx, cy), r, 6)
                pygame.draw.circle(surf, INK, (cx, cy), r, 3)
                if reachable and k == self.sel:
                    pygame.draw.circle(surf, SUNNY, (cx, cy), r + 7 + int(2 * math.sin(t * 6)), 4)
                draw_node_icon(surf, node.kind, cx, cy, r - 6, self.keeper, t, faded=faded)
                if reachable:
                    badge = (cx + r - 4, cy - r + 4)
                    pygame.draw.circle(surf, INK, badge, 11)
                    draw_text(surf, font(20), str(k + 1), badge, WHITE, center=True)
                if reachable or node.kind == "boss":
                    draw_text(surf, font(18), node_title(node.kind, self.keeper), (cx, cy + r + 14),
                              INK, center=True)
        # you
        if self.travel is not None:
            tr = self.travel
            f = min(1.0, tr["t"] / TRAVEL_TIME)
            e = ease_out(f)
            (ax, ay), (bx, by) = tr["frm"], tr["to"]
            px, py = ax + (bx - ax) * e, ay + (by - ay) * e
            hop = abs(math.sin(f * math.pi * 3)) * 16
            tilt = math.sin(f * math.pi * 3) * 0.25
            draw_player(surf, form["shape"], px, py - 38 - hop, 16, t, look=(1, 0), rot=tilt)
            if f >= 1 and tr["kind"] in ("fight", "elite", "boss"):
                heading(surf, "the Set is gathering...", (px, py - 78), 20, center=True)
        else:
            hx, hy = self.here
            bob = math.sin(t * 2.5) * 2
            tgt = self.pos[(run.layer + 1, self.choices[self.sel][0])] if self.choices else (hx + 1, hy)
            look = ((tgt[0] - hx) / 120.0, (tgt[1] - hy) / 160.0)
            draw_player(surf, form["shape"], hx, hy - 40 + bob, 16, t, look=look,
                        blink=blink_now(t, 1))
        # tooltip for the selected room
        if hover_node is not None and self.travel is None:
            kind, cx, cy = hover_node
            tip = pygame.Rect(0, 0, 270, 86)
            tip.midleft = (cx + 44, cy)          # beside the room, never over you
            tip.clamp_ip(mr.inflate(-8, -8))
            draw_card(surf, tip, PAPER, 10, 4)
            draw_text(surf, font(22), node_title(kind, self.keeper), (tip.x + 10, tip.y + 8), INK)
            draw_wrapped(surf, font(18), node_blurb(kind, self.keeper), (tip.x + 10, tip.y + 30),
                         tip.w - 20, DIM)
        # footer
        if run.relics:
            x = 190
            draw_text(surf, font(20), "Facets:", (x, 580), WHITE, shadow=INK)
            x += 70
            for rid in run.relics:
                rel = RELICS[rid]
                draw_facet(surf, rid, x + 8, 589, 9, self.t)
                r = draw_text(surf, font(18), rel["name"], (x + 20, 582), WHITE, shadow=INK)
                x = r.right + 14
        keys = "1" if len(self.choices) <= 1 else "1-%d" % len(self.choices)
        hint = ("Fights make you stronger; calm rooms spend it. Every way up has at least 3 fights. "
                "Click a room or press %s." % keys)
        draw_text(surf, font(18), hint, (190, 610), WHITE, shadow=INK)
        if self.msg:
            draw_text(surf, font(22), self.msg, (936, 80), WHITE, right=True, shadow=INK)
        self.draw_buttons(surf)
