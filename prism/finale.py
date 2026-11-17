"""The Grand Roll: what happens once everyone who asked is out.

You're round now, all the way round. Everyone you got out of a tower (and
the Stillwheel, who rolled after you in the first place) lines up on the
crest above the Meadow, and you all roll down the Long Ramp together: you
smoothly, the newest of them still going ka-thunk. At the bottom they hop
up into a ring around you, a circle made of everyone, and the whole wheel
rolls off across the field while the Keepers, who all meant well, cheer it
past. Then a card, and back to the hub whenever you like.

The world is painted as pixel art (a 240x160 canvas, scaled 4x, like the
hub); everyone in it is drawn smooth on top, like everywhere else.
"""

import math
import random

import pygame

from . import sound
from .art import Particles, draw_body, draw_critter, draw_player, draw_shadow, ease_in_out, lighten
from .consts import COLOR_RGB, RAINBOW, TOWERS
from .enemies import KINDS
from .hubart import K, LH, LW, cloud_sprite, ground_texture, plant_sprite, sky_canvas, sun_sprite
from .pixel import OUTLINE, mix
from .screens import Screen
from .widgets import ACCENT, INK, WHITE, draw_card, draw_text, draw_wrapped, font
from .world import friend_sides, plan_of, rescued_in_plan, shape_of

CREST_END = 420.0           # the flat top, where everyone lines up
RAMP_END = 4600.0           # the bottom of the Long Ramp
DROP = 1500.0               # how far down it goes
GRAVITY, DRAG = 980.0, 0.42
R_YOU, R_FRIEND = 28, 22
RING_GAP = 0                # between the wheel's rim and the ground
SPACING = 78                # how far apart they line up (and stop)
KEEPER_GAP = 330            # the Keepers, cheering, along the field

CHEERS = {
    "latch": "Careful! ...No. Go on!", "knot": "Roll wherever you like!",
    "cap": "Down looks lovely from here!", "rime": "Things change! It's fine!",
    "hour": "Take all the time you want!", "focus": "Look at you all, scattering!",
    "beacon": "I'll keep a light on!", "vane": "Go your own way!",
    "colossus": "Four sides were never the rule!", "oracle": "Fine! Rounder! Go on!",
}
GUARDS = {"latch": (224, 90, 200), "knot": (140, 160, 70), "cap": (240, 120, 110), "rime": (150, 200, 240),
          "hour": (230, 190, 110), "focus": (170, 130, 240), "beacon": (250, 190, 90), "vane": (140, 150, 180)}
SHAPE_SIDES = {"triangle": 3, "square": 4, "diamond": 4, "pentagon": 5, "hexagon": 6}


def ground(x):
    """The crest, the Long Ramp (steepest in the middle, with a few soft
    rolls in it), then the flat, flowery field, forever."""
    if x <= CREST_END:
        return 0.0
    if x >= RAMP_END:
        return DROP
    k = (x - CREST_END) / (RAMP_END - CREST_END)
    rolls = 34 * math.sin(k * math.pi * 5) * math.sin(k * math.pi)
    return DROP * k * k * (3 - 2 * k) + rolls


def slope(x):
    return (ground(x + 2) - ground(x - 2)) / 4.0


class Rider:
    """Someone rolling down: you, a friend, or the Stillwheel."""

    def __init__(self, who, x, r, color, sides, was=None, delay=0.0, stop=0.0):
        self.who = who
        self.x = x
        self.r = r
        self.color = color
        self.sides = sides          # 0: round
        self.was = was              # the shape it started as (a faint memory, inside)
        self.delay = delay
        self.stop = stop            # where it comes to rest in the field
        self.v = 0.0
        self.rot = 0.0
        self.hop = 0.0
        self.thunks = 0

    def y(self):
        return ground(self.x) - self.r

    def lift(self):
        """A polygon rides up on each corner as it rolls."""
        n = self.sides
        if not n:
            return 0.0
        seg = math.tau / n
        return self.r * (1 - math.cos(math.pi / n)) * abs(math.sin((self.rot % seg) / seg * math.pi))

    def step(self, dt, t):
        if t < self.delay:
            self.hop = abs(math.sin((t + self.delay) * 6)) * 6          # bouncing on the spot, can't wait
            return False
        self.hop = 0.0
        if self.x < RAMP_END:
            s = slope(self.x)
            self.v += (GRAVITY * s / math.sqrt(1 + s * s) + 60 - DRAG * self.v) * dt
        else:                                           # the field: coast to a stop, just so
            room = max(0.0, self.stop - self.x)
            self.v = min(self.v, math.sqrt(2 * 420 * room))
        before = int(self.rot / (math.tau / self.sides)) if self.sides else 0
        self.x += self.v * dt
        self.rot += self.v * dt / self.r
        return bool(self.sides) and int(self.rot / (math.tau / self.sides)) > before


class FinaleScreen(Screen):
    """The Grand Roll (see the module's words). `then` runs when you leave."""

    TOP, GATHER, WHEEL_CARD = 2.6, 1.8, 5.5

    def __init__(self, app, then=None):
        super().__init__(app)
        self.then = then or (lambda: app.show_hub())
        data = app.meta.data
        pretend = getattr(app, "hub_rescued", None)
        plan, done = rescued_in_plan(data, pretend)
        if not done:                                    # (dev: nobody out yet? pretend everyone is)
            plan = plan_of(data)
            done = list(plan)
        self.done = done
        self.t = 0.0
        self.phase = "top"
        self.phase_t = 0.0
        self.fx = Particles()
        # who rolls: you at the front, then everyone you got out (most recent nearest), then the Stillwheel
        self.you = Rider("you", CREST_END - 40, R_YOU, WHITE, 0, delay=self.TOP, stop=RAMP_END + 1500)
        self.riders = [self.you]
        for i, tid in enumerate(reversed(done)):
            f = TOWERS[tid]["friend"]
            self.riders.append(Rider(tid, CREST_END - 40 - SPACING * (i + 1), R_FRIEND, COLOR_RGB[f["color"]],
                                     friend_sides(tid, data, pretend), was=f["was"], delay=self.TOP + 0.16 * (i + 1),
                                     stop=RAMP_END + 1500 - SPACING * (i + 1)))
        n = len(self.riders)
        self.riders.append(Rider("stillwheel", CREST_END - 40 - SPACING * n, 30, (150, 140, 170), 0,
                                 delay=self.TOP + 0.16 * n, stop=RAMP_END + 1500 - SPACING * n))
        # and, tagging along at the back, a few who have only just started rolling (ka-THUNK)
        from .meadow import NEWCOMERS
        from .world import ZONES
        tagalongs = [(c, was, sides) for c, was, _home, _lines, sides in NEWCOMERS]
        tagalongs += [(c, was, sides) for c, was, _f, _lines, sides in ZONES["wilds"].get("newcomers", ())]
        for c, was, sides in tagalongs:
            n = len(self.riders)
            self.riders.append(Rider("newcomer", CREST_END - 40 - SPACING * n, 20, COLOR_RGB[c], sides, was=was,
                                     delay=self.TOP + 0.16 * n, stop=RAMP_END + 1500 - SPACING * n))
        # the Keepers of your towers, along the field, cheering
        self.keepers = [(TOWERS[tid]["boss"], RAMP_END + 2000 + KEEPER_GAP * i) for i, tid in enumerate(done)]
        self.cheered = set()
        self.rested = 0.0                               # how long you've been stopped in the field
        self.bubbles = []                               # [text, world x, world y, age]
        self.wheel = None                               # once it forms: {"x", "x0", "phi"}
        self.cam = [self.you.x - 380, -380.0]
        rng = random.Random(11)
        self.clouds = [(rng.uniform(0, LW * 3), rng.uniform(6, 60), rng.randrange(6)) for _ in range(10)]
        self.card = None
        self.add((380, 580, 200, 44), "Skip", self.advance, tag="continue")
        sound.play("fanfare", 0.7)

    # -- moving on
    def advance(self):
        if self.card is None:
            self._skip_to_wheel()
            self._show_card()
            return
        self.leave()

    def leave(self):
        self.app.meta.data["finale_seen"] = True
        self.app.meta.save()
        sound.roll(0)
        self.then()

    def again(self):
        self.app.replace(FinaleScreen(self.app, self.then))

    def _show_card(self):
        self.card = 0.0
        self.buttons.clear()
        self.add((300, 560, 170, 44), "Watch again", self.again, tag="again")
        self.add((490, 560, 170, 44), "Roll on", self.leave, tag="continue")
        sound.play("fanfare", 0.8)

    def _skip_to_wheel(self):
        if self.wheel is None:
            for r in self.riders:
                r.x, r.v, r.delay = r.stop, 0.0, 0.0
            self._form_wheel(done=True)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE,
                                                    pygame.K_KP_ENTER):
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None \
                and self.card is None:
            self.advance()
            return True
        return super().handle(ev)

    # -- the wheel: a ring of everyone, you at its hub
    def _ring(self):
        members = self.riders[1:]
        radius = max(96, (len(members) * (R_FRIEND * 2 + 14)) / math.tau)
        return members, radius

    def _form_wheel(self, done=False):
        members, radius = self._ring()
        x0 = self.you.x
        self.wheel = {"x": x0, "x0": x0, "phi": 0.0, "form": 1.0 if done else 0.0, "radius": radius,
                      "from": [(m.x, m.y()) for m in members]}
        self.phase, self.phase_t = "gather", 0.0
        if done:
            self.phase = "wheel"
        sound.play("ascend", 0.8)

    def wheel_spot(self, i):
        """Where member i rides on the wheel (screen-free world coords)."""
        members, radius = self._ring()
        w = self.wheel
        cy = ground(w["x"]) - radius - R_FRIEND - RING_GAP
        a = -math.pi / 2 + i * math.tau / max(1, len(members)) + w["phi"]
        return w["x"] + math.cos(a) * radius, cy + math.sin(a) * radius, cy

    # -- time passing
    def update(self, dt):
        self.t += dt
        self.phase_t += dt
        self.fx.update(dt)
        for b in self.bubbles:
            b[3] += dt
        self.bubbles = [b for b in self.bubbles if b[3] < 2.0]
        if self.phase == "top" and not self.bubbles and 0.6 < self.t < 0.7 and len(self.riders) > 2:
            r = self.riders[1]
            self.bubbles.append(["Last one down's a square!", r.x, r.y() - 40, 0.0])
            sound.play("talk", 0.5)
        if self.phase == "top" and self.t >= self.TOP:
            self.phase, self.phase_t = "roll", 0.0
            sound.play("door", 0.6)
        if self.phase in ("top", "roll"):
            for ahead, r in zip([None] + self.riders, self.riders):
                if ahead is not None and self.t > r.delay and r.x < RAMP_END:   # keep up with the one ahead
                    gap = ahead.x - r.x
                    if gap > SPACING:
                        r.v += min(600.0, (gap - SPACING) * 4.0) * dt
                    elif gap < SPACING * 0.7:
                        r.v = min(r.v, ahead.v)
                thunk = r.step(dt, self.t)
                if ahead is not None and r.x > ahead.x - (ahead.r + r.r + 6):    # no rolling through each other
                    r.x = ahead.x - (ahead.r + r.r + 6)
                    r.v = min(r.v, ahead.v)
                if thunk and r.x > CREST_END:                       # ka-thunk
                    sound.play("step", 0.25)
                    r.thunks += 1
                    if r.thunks % 3 == 0 and r.v > 200:
                        self.fx.burst(r.x, ground(r.x), WHITE, n=2, speed=70, shapes=("circle",))
            if self.phase == "roll":
                sound.roll(min(1.0, self.you.v / 900.0))
                if self.you.v > 300 and int(self.t * 8) != int((self.t - dt) * 8):   # a rainbow trail
                    c = RAINBOW[int(self.t * 8) % 6]
                    self.fx.burst(self.you.x - 20, self.you.y(), COLOR_RGB[c], n=1, speed=40,
                                  shapes=("circle",))
                if self.you.v < 1 and self.you.x > RAMP_END:
                    self.rested += dt
                if all(r.x >= r.stop - 2 for r in self.riders) or self.rested > 1.2 or self.phase_t > 16:
                    sound.roll(0)
                    self._form_wheel()
        elif self.phase == "gather":
            self.wheel["form"] = min(1.0, self.phase_t / self.GATHER)
            if self.phase_t >= self.GATHER:
                self.phase, self.phase_t = "wheel", 0.0
                for c in RAINBOW:
                    self.fx.burst(self.wheel["x"], ground(self.wheel["x"]) - 140, COLOR_RGB[c], n=6, speed=260)
        elif self.phase == "wheel":
            w = self.wheel
            speed = min(190.0, 60 + self.phase_t * 80)
            w["x"] += speed * dt
            w["phi"] = (w["x"] - w["x0"]) / (w["radius"] + R_FRIEND + RING_GAP)
            sound.roll(0.35)
            for boss, kx in self.keepers:                         # each Keeper cheers as it goes by
                if boss not in self.cheered and w["x"] > kx - 560:
                    self.cheered.add(boss)
                    self.bubbles.append([CHEERS.get(boss, "Go on!"), kx, ground(kx) - 90, 0.0])
                    sound.play("talk", 0.5)
                    self.fx.burst(kx, ground(kx) - 40, COLOR_RGB[RAINBOW[len(self.cheered) % 6]], n=8, speed=200)
            if self.card is None and self.phase_t > self.WHEEL_CARD:
                self._show_card()
        if self.card is not None:
            self.card += dt
        # the camera follows you (or the wheel), a little ahead
        lead = self.wheel["x"] if self.wheel else self.you.x
        tx = lead - 360
        ty = ground(lead) - (430 if self.wheel else 400)
        k = 1 - math.exp(-dt * 5)
        self.cam[0] += (tx - self.cam[0]) * k
        self.cam[1] += (ty - self.cam[1]) * k
        return super().update(dt)

    # -- drawing
    def draw(self, surf):
        cx, cy = self.cam
        low = self._paint(cx, cy)
        surf.blit(pygame.transform.scale(low, (LW * K, LH * K)), (0, 0))
        for boss, kx in self.keepers:
            self._keeper(surf, boss, kx - cx, ground(kx) - cy)
        self._everyone(surf, cx, cy)
        self.fx.draw(surf, -cx, -cy)
        for text, bx, by, age in self.bubbles:
            self._bubble(surf, text, bx - cx, by - cy - age * 8)
        self._caption(surf)
        if self.card is not None:
            self._card(surf)
        self.draw_buttons(surf)

    def _paint(self, cx, cy):
        """The world at 240x160: a sunset sky, a rainbow coming out, clouds,
        two layers of hills, the ground with the Long Ramp painted as a
        rainbow road down it, and flowers."""
        L = pygame.Surface((LW, LH))
        L.blit(sky_canvas((118, 120, 250), (255, 196, 170)), (0, 0))
        rain = 0.0
        if self.wheel is not None:
            rain = min(1.0, (self.phase_t if self.phase == "wheel" else 0.0) / 2.0 + (self.phase == "wheel") * 0.2)
        sun = sun_sprite((255, 226, 150))
        L.blit(sun, (LW - 60, 30 + int(cy * 0.004)))
        for x, y, v in self.clouds:
            img = cloud_sprite(v)
            X = (x - cx * 0.05 / K) % (LW * 3) - LW
            L.blit(img, (int(X), int(y)))
        for col, base, amp, par, freq, vpar in (((196, 160, 236), 92, 12, 0.10, 0.030, 0.02),
                                               ((160, 214, 150), 110, 9, 0.22, 0.045, 0.05),
                                               ((130, 200, 120), 124, 6, 0.38, 0.07, 0.08)):
            off = cx * par / K
            lift = cy * vpar / K
            pts = [(0, LH)]
            for X in range(0, LW + 4, 3):
                u = X + off
                pts.append((X, int(base - lift - amp * (1 + math.sin(u * freq) * 0.6 + math.sin(u * freq * 2.3) * 0.4))))
            pts.append((LW, LH))
            pygame.draw.polygon(L, col, pts)
            if rain > 0 and base == 92:                         # the rainbow, coming out behind the near hills
                arc = pygame.Surface((LW, LH), pygame.SRCALPHA)
                for j, c in enumerate(RAINBOW):
                    pygame.draw.circle(arc, (*COLOR_RGB[c], int(200 * rain)), (LW // 2 + 10, LH - 14), 94 - j * 3, 3)
                L.blit(arc, (0, 0))
        tex = ground_texture("meadow")
        for X in range(LW):
            wx = cx + X * K + 2
            top = int((ground(wx) - cy) / K)
            if top >= LH:
                continue
            t0 = max(0, top)
            L.blit(tex, (X, t0), (int(wx / K) % 64, 0, 1, LH - t0))
            if CREST_END < wx < RAMP_END + 40:                  # the Long Ramp: a rainbow road
                for j, c in enumerate(RAINBOW):
                    if 0 <= top + j < LH:
                        L.set_at((X, top + j), COLOR_RGB[c])
                if 0 <= top + 6 < LH:
                    L.set_at((X, top + 6), OUTLINE)
            elif 0 <= top < LH:
                L.set_at((X, top), (170, 240, 140))
                if top + 1 < LH:
                    L.set_at((X, top + 1), (130, 220, 104))
            if CREST_END < wx < RAMP_END + 40 and 0 <= top - 1 < LH:
                L.set_at((X, top - 1), OUTLINE)
            col = int(wx // K)
            h = (col * 2654435761) & 0xffff
            if (wx < CREST_END or wx > RAMP_END + 60) and h % 5 == 0 and 0 < top < LH:
                img = plant_sprite("flower" if h % 3 else "bloom", h % 12)
                L.blit(img, (X - 2, top - img.get_height() + 1))
        return L

    def _everyone(self, surf, cx, cy):
        if self.wheel is None:
            for r in reversed(self.riders):
                self._rider(surf, r, r.x - cx, r.y() - cy - r.lift() - r.hop, r.rot)
            return
        members, radius = self._ring()
        w = self.wheel
        f = ease_in_out(w["form"])
        hubx, hub_ground = w["x"] - cx, ground(w["x"]) - cy
        _x, _y, ring_cy = self.wheel_spot(0)
        # the spokes: light from you to each of them
        you_y = (self.you.y() - cy) * (1 - f) + (ring_cy - cy) * f
        if f > 0.3:
            for i, c in enumerate(members):
                x, y, _c = self.wheel_spot(i)
                col = COLOR_RGB[RAINBOW[i % 6]]
                pygame.draw.line(surf, lighten(col, 0.3), (hubx, you_y), (x - cx, y - cy), 3)
            pygame.draw.circle(surf, INK, (int(hubx), int(ring_cy - cy)), int(radius + 2), 3)
        draw_shadow(surf, hubx, hub_ground, (radius + R_FRIEND) * 2 * f + 40, 18, 50)
        for i, m in enumerate(members):
            x, y, _c = self.wheel_spot(i)
            fx0, fy0 = w["from"][i]
            hop = math.sin(f * math.pi) * 120
            px = fx0 + (x - fx0) * f
            py = fy0 + (y - fy0) * f - hop
            self._rider(surf, m, px - cx, py - cy, m.rot + w["phi"], shadow=f < 0.1)
        draw_player(surf, "circle", hubx, you_y, R_YOU, self.t, look=(1, -0.2), mood="happy",
                    rot=w["phi"] * 1.5, shadow=f < 0.1)

    def _rider(self, surf, r, x, y, rot, shadow=True):
        if not -80 < x < 1040 or not -80 < y < 720:
            return
        if r.who == "you":
            draw_player(surf, "circle", x, y, r.r, self.t, look=(1, 0.1), mood="happy", rot=rot, shadow=shadow)
            return
        look = (1, 0) if self.wheel is None else (0, -0.3)
        draw_critter(surf, shape_of(r.sides), x, y, r.r, r.color, look=look, mood="happy", rot=rot, shadow=shadow)
        if r.was:
            draw_body(surf, r.was, x, y, r.r * 0.55, None, lighten(r.color, 0.45), 2, rot * 0.2)
        if r.who == "stillwheel":                                  # its little orbit of colours
            for i, c in enumerate(RAINBOW):
                a = self.t * 1.2 + i * math.tau / 6
                pygame.draw.circle(surf, COLOR_RGB[c], (int(x + math.cos(a) * (r.r + 10)),
                                                        int(y + math.sin(a) * 8 + r.r * 0.4)), 4)

    def _keeper(self, surf, boss, x, gy):
        if not -80 < x < 1040:
            return
        from .meadow import TOWERS_SHAPE, _keeper_prop
        cheer = boss in self.cheered
        bounce = abs(math.sin(self.t * 7 + x * 0.01)) * (14 if cheer else 3)
        y = gy - 30 - bounce
        draw_critter(surf, TOWERS_SHAPE.get(boss, KINDS[boss]["shape"]), x, y, 30, GUARDS.get(boss, (224, 90, 200)),
                     look=(-0.6, -0.3), mood="happy", face=KINDS[boss].get("face"))
        _keeper_prop(surf, boss, x, y, 30, self.t)

    def _bubble(self, surf, text, x, y):
        f = font(18)
        w = f.size(text)[0] + 24
        box = pygame.Rect(0, 0, w, 30)
        box.midbottom = (int(x), int(y))
        box.clamp_ip(pygame.Rect(8, 8, 944, 624))
        pygame.draw.rect(surf, WHITE, box, border_radius=12)
        pygame.draw.rect(surf, INK, box, 2, border_radius=12)
        draw_text(surf, f, text, box.center, INK, center=True)

    CAPTIONS = (("top", "Everyone who asked is out."),
                ("roll", "Down the Long Ramp, all of you together."),
                ("gather", "Nobody was sanded down. Everyone grew."),
                ("wheel", "A circle, made of everyone."))

    def _caption(self, surf):
        if self.card is not None:
            return
        words = dict(self.CAPTIONS)[self.phase]
        a = min(1.0, self.phase_t / 0.5)
        f = font(30)
        w = f.size(words)[0] + 40
        plate = pygame.Surface((w, 48), pygame.SRCALPHA)
        pygame.draw.rect(plate, (*INK, int(140 * a)), plate.get_rect(), border_radius=24)
        surf.blit(plate, (480 - w // 2, 26))
        img = f.render(words, True, WHITE)
        img.set_alpha(int(255 * a))
        surf.blit(img, img.get_rect(center=(480, 50)))

    def _card(self, surf):
        k = ease_in_out(min(1.0, self.card / 0.6))
        shade = pygame.Surface((960, 640), pygame.SRCALPHA)
        shade.fill((*INK, int(70 * k)))
        surf.blit(shade, (0, 0))
        card = draw_card(surf, (170, int(160 + (1 - k) * 60), 620, 370))
        draw_text(surf, font(40), "Round, all the way round.", (480, card.y + 42), INK, center=True)
        words = ("Tri wanted to roll. It took every side it grew on the way up, and every friend it helped "
                 "out on the way down. Nobody was sanded down to fit: everyone grew until they were "
                 "round enough, in their own time, with a faint memory inside of the shape they started as.")
        y = draw_wrapped(surf, font(21), words, (card.x + 34, card.y + 80), card.w - 68, INK, center=True)
        data = self.app.meta.data
        stats = "Friends out: %d      Climbs: %d      Rolled away: %d" % (
            len(self.done), data.get("runs", 0), data.get("wins", 0))
        draw_text(surf, font(22), stats, (480, y + 22), ACCENT, center=True)
        for i, r in enumerate(self.riders[1:]):                     # everyone, in a row, happy
            n = len(self.riders) - 1
            x = 480 - (n - 1) * 26 + i * 52
            draw_critter(surf, shape_of(r.sides), x, y + 78, 18, r.color, look=(0, -0.2), mood="happy",
                         rot=self.t * 0.8 + i, shadow=False)
        draw_text(surf, font(26), "Thanks for playing.", (480, card.bottom - 56), INK, center=True)
        draw_text(surf, font(18), "The Meadow's still there, and everyone's in it.", (480, card.bottom - 26),
                  mix(INK, WHITE, 0.4), center=True)
