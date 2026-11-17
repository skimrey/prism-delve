"""What every arcade game in the Meadow shares: the frame around it.

Each zone has its own game, hosted by the friend whose rescue opened the
zone (or a local, if every zone is open). They're all about the same things
as the rest of the game: you're round (as round as you've got), shapes want
sides, and nothing is ever at stake. A game subclasses ArcadeScreen and fills
in `reset`, `step`, `draw_field` and its keys; the frame does the backdrop,
the side panel (name, score, how to play), the host cheering, floating
words, the best score, and the "again?" card.
"""

import math
import random

import pygame

from . import sound
from .art import Particles, draw_critter, draw_player
from .consts import COLOR_RGB, TOWERS
from .pixel import Pix, cached, mix
from .screens import Screen
from .widgets import INK, PAPER, WHITE, draw_card, draw_text, draw_wrapped, font
from .world import ZONES, World, friend_sides, plan_of, shape_of, your_sides

FIELD = pygame.Rect(250, 16, 460, 608)          # where a game's play area usually goes


def backdrop(zone_kind, size=(960, 640)):
    """A zone's sky, in pixel bands, with little sparkles."""
    def build():
        top, bottom = ZONES[zone_kind]["sky"]
        w, h = size[0] // 2, size[1] // 2
        p = Pix(w, h, seed=len(zone_kind))
        p.vgrad(0, 0, w, h, mix(top, (255, 255, 255), 0.2), bottom, steps=8)
        for _ in range(70):
            p.px(p.rng.randrange(w), p.rng.randrange(h), mix(bottom, (255, 255, 255), 0.6))
        return p.up(2)
    return cached(("arcade_bg", zone_kind, size), build)


class ArcadeScreen(Screen):
    NAME = "A game"
    ZONE = "meadow"
    BEST = "game_best"
    HELP = ("",)
    KEYS = ("Esc: back",)

    def __init__(self, app, back=None, theme=None, seed=None):
        super().__init__(app)
        self.back = back or app.show_hub
        self.theme = theme or self.ZONE
        self.rng = random.Random(seed if seed is not None else 7)
        self.fx = Particles()
        self.held = set()                     # keys being held down
        self.words = []                       # floating words: [text, x, y, age, colour]
        self.score = 0
        self.over = None                      # seconds since the game ended
        self.best = app.meta.data.get(self.BEST, 0)
        pretend = getattr(app, "hub_rescued", None)
        self.you_sides = your_sides(app.meta.data, pretend)
        self.you = shape_of(self.you_sides)
        self._host(pretend)
        self.add((24, 592, 200, 34), "Back", self.leave, tag="back", small=True)
        self.reset()

    def _host(self, pretend):
        """Whoever runs this game: the friend whose rescue opened the zone."""
        data = self.app.meta.data
        rescued = data.get("friends", []) if pretend is None else pretend
        plan = plan_of(data)
        zone = next((z for z in World(plan, rescued, True).zones if z.kind == self.theme and z.index), None)
        tid = plan[zone.index - 1] if zone else plan[0]
        f = TOWERS[tid]["friend"]
        self.host = (f["was"], COLOR_RGB[f["color"]], friend_sides(tid, data, rescued))

    # -- to fill in
    def reset(self):
        pass

    def step(self, dt):
        pass

    def draw_field(self, surf):
        pass

    def status(self):
        """A couple of lines for the panel under the score."""
        return ()

    # -- shared
    def leave(self):
        self.save_best()
        sound.roll(0)
        self.back()

    def save_best(self):
        if self.score > self.app.meta.data.get(self.BEST, 0):
            self.app.meta.data[self.BEST] = self.score
            self.app.meta.save()
            self.best = self.score

    def end(self):
        """The game's over: the card, and the best score kept."""
        if self.over is None:
            self.over = 0.0
            self.save_best()
            sound.play("fanfare", 0.6)

    def restart(self):
        self.save_best()
        self.score = 0
        self.over = None
        self.words = []
        self.reset()

    def pop(self, text, x, y, col=None):
        self.words.append([text, x, y, 0.0, col or COLOR_RGB["Y"]])

    def axis(self, neg=(pygame.K_LEFT, pygame.K_a), pos=(pygame.K_RIGHT, pygame.K_d)):
        """-1, 0 or 1 from the keys being held."""
        return (1 if self.held & set(pos) else 0) - (1 if self.held & set(neg) else 0)

    def handle(self, ev):
        if ev.type == pygame.KEYUP:
            self.held.discard(ev.key)
        if ev.type == pygame.KEYDOWN:
            self.held.add(ev.key)
            if ev.key == pygame.K_ESCAPE:
                self.leave()
                return True
            if self.over is not None and self.over > 1.0 and ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                self.restart()
                return True
        return super().handle(ev)

    def update(self, dt):
        super().update(dt)
        self.fx.update(dt)
        for w in self.words:
            w[3] += dt
        self.words = [w for w in self.words if w[3] < 1.3]
        dt = min(dt, 1 / 30)
        if self.over is not None:
            self.over += dt
        else:
            self.step(dt)
        return True

    def draw(self, surf):
        surf.blit(backdrop(self.theme), (0, 0))
        self.draw_field(surf)
        self.fx.draw(surf)
        for text, x, y, age, col in self.words:
            draw_text(surf, font(22 if len(text) < 10 else 26), text, (x, y - age * 30), col, center=True,
                      shadow=INK)
        self._panel(surf)
        if self.over is not None:
            k = min(1.0, self.over / 0.4)
            card = draw_card(surf, (FIELD.x + 20, int(220 - 30 * (1 - k)), FIELD.w - 40, 170))
            draw_text(surf, font(38), "%d points!" % self.score, (card.centerx, card.y + 40), INK, center=True)
            draw_text(surf, font(20), self.summary(), (card.centerx, card.y + 84), INK, center=True)
            draw_text(surf, font(18), "Best: %d" % max(self.best, self.score), (card.centerx, card.y + 110),
                      (120, 106, 150), center=True)
            if self.over > 1.0:
                draw_text(surf, font(22), "Space: again!   Esc: back", (card.centerx, card.bottom - 28), INK,
                          center=True)
        self.draw_buttons(surf)

    def summary(self):
        return "Nothing at stake. Well played."

    def _panel(self, surf):
        card = draw_card(surf, (14, 16, 222, 566), PAPER, 16)
        draw_text(surf, font(28), self.NAME, (card.centerx, card.y + 26), INK, center=True)
        draw_text(surf, font(34), "%d" % self.score, (card.centerx, card.y + 68), INK, center=True)
        draw_text(surf, font(16), "best %d" % max(self.best, self.score), (card.centerx, card.y + 96),
                  (120, 106, 150), center=True)
        y = card.y + 124
        for line in self.status():
            draw_text(surf, font(19), line, (card.centerx, y), INK, center=True)
            y += 24
        draw_wrapped(surf, font(17), " ".join(self.HELP), (card.x + 12, max(y + 10, card.y + 230)),
                     card.w - 24, INK, 1, center=True)
        for i, line in enumerate(self.KEYS):
            draw_text(surf, font(16), line, (card.centerx, card.bottom - 24 - (len(self.KEYS) - 1 - i) * 20),
                      (120, 106, 150), center=True)
        # the host, cheering from the right
        shape, col, sides = self.host
        hx, hy = 835, 520
        bob = abs(math.sin(self.t * 3)) * 10
        draw_critter(surf, shape_of(sides), hx, hy - bob, 40, col, mood="happy", look=(-0.8, -1),
                     rot=self.t * 0.5)
        line = self.cheer()
        fnt = font(22)
        box = pygame.Rect(0, 0, fnt.size(line)[0] + 24, 34)
        box.midbottom = (hx, int(hy - 60 - bob))
        box.clamp_ip(pygame.Rect(720, 0, 236, 640))
        pygame.draw.rect(surf, WHITE, box, border_radius=12)
        pygame.draw.rect(surf, INK, box, 2, border_radius=12)
        draw_text(surf, fnt, line, box.center, INK, center=True)

    def cheer(self):
        return "Go go go!" if self.over is None else "Again? Again!"

    def draw_you(self, surf, x, y, r, rot=0.0, color=None, mood="happy"):
        """You, as round as you've got: prism light, or dyed a colour."""
        if color:
            draw_critter(surf, self.you, x, y, r, color, mood=mood, rot=rot, shadow=False)
        else:
            draw_player(surf, self.you, x, y, r, self.t, mood=mood, rot=rot, shadow=False)
