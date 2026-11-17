"""Rooms that are not fights: reward, Tinter (shop), Still Tile (rest),
Oddity (event), and the end of a climb."""

import math
import random

import pygame

from .art import Particles, draw_player, lighten
from .consts import COLOR_RGB, FLOORS, PRIMARIES, RAINBOW, RELICS
from . import sound
from .run import effects_text
from .vignettes import draw_chip, draw_scene, effect_chips
from .scene import (MEADOW_SKY, Backdrop, draw_facet, draw_pattern_icon, draw_slot, draw_tinter,
                    draw_ware,
                    floor_style, glint_icon, heading, heart_icon, stat_chip)
from .screens import CardButton, Screen
from .widgets import (BAD, DIM, GOOD, INK, PAPER, WHITE, Button, draw_card, draw_colour_mark,
                      draw_text, draw_wrapped, font)


def reward_icon(rid):
    """A picture for a reward/shop id, drawn from shapes."""
    def icon(surf, cx, cy):
        if rid.startswith("pattern:"):
            draw_pattern_icon(surf, rid.split(":", 1)[1], cx, cy, 6, COLOR_RGB["M"])
        elif rid.startswith("relic:"):
            draw_facet(surf, rid.split(":", 1)[1], cx, cy, 18)
        elif rid.startswith("cap:"):
            c = rid.split(":", 1)[1]
            for k in range(3):
                pygame.draw.circle(surf, COLOR_RGB[c], (cx - 12 + k * 12, cy + 4 - (k % 2) * 8), 8)
                pygame.draw.circle(surf, INK, (cx - 12 + k * 12, cy + 4 - (k % 2) * 8), 8, 2)
            draw_colour_mark(surf, c, cx, cy - 4, 8)
        elif rid == "maxhp":
            pygame.draw.line(surf, INK, (cx - 16, cy + 10), (cx + 16, cy - 10), 13)
            pygame.draw.line(surf, (255, 140, 150), (cx - 16, cy + 10), (cx + 16, cy - 10), 7)
        else:   # heal
            for i in range(8):
                a = i * math.tau / 8
                pygame.draw.line(surf, INK, (cx, cy), (cx + math.cos(a) * 18, cy + math.sin(a) * 18), 3)
            pygame.draw.circle(surf, (255, 214, 72), (cx, cy), 11)
            pygame.draw.circle(surf, INK, (cx, cy), 11, 2)
    return icon


class _Room(Screen):
    """Shared look for the non-fight rooms: the floor's sky and a top bar."""

    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.backdrop = Backdrop.for_run(self.run, n=18)

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw_top(self, surf, title, sub="", backdrop=True):
        if backdrop:
            self.backdrop.draw(surf)
        heading(surf, title, (480, 52), 56, center=True)
        if sub:
            draw_text(surf, font(24), sub, (480, 96), WHITE, center=True, shadow=INK)
        p = self.run.player
        x = stat_chip(surf, 20, 596, heart_icon, "%d/%d" % (p.hp, p.max_hp)) + 8
        stat_chip(surf, x, 596, glint_icon, "%d glint" % self.run.gold)

    def draw_msg(self, surf, y):
        if self.msg:
            r = pygame.Rect(0, 0, min(720, font(22).size(self.msg)[0] + 40), 34)
            r.center = (480, y)
            draw_card(surf, r, PAPER, 17, 3)
            draw_text(surf, font(22), self.msg, r.center, self.msg_color, center=True)


class RewardScreen(_Room):
    def __init__(self, app, gold):
        super().__init__(app)
        self.gold = gold
        self.picked = False
        self.options = self.run.reward_options()
        n = len(self.options)
        for i, opt in enumerate(self.options):
            self.buttons.append(CardButton((200, 176 + i * 76, 560, 68), opt["label"], opt["desc"],
                                           lambda o=opt: self.pick(o), key=pygame.K_1 + i,
                                           tag="reward%d" % i, icon=reward_icon(opt["id"])))
        y = 176 + n * 76 + 6
        self.skip = self.add((380, y, 200, 34), "Skip reward", self.do_skip, tag="skip", small=True)
        self.cont = self.add((380, y + 44, 200, 44), "Continue", app.leave_node, enabled=False,
                             key=pygame.K_RETURN, tag="continue")
        self.say("The Set came apart. Pick one thing from what they left (1-%d), or skip." % n, DIM)
        # a clean sort deserves a moment: light bursts out behind the title
        self.fx = Particles()
        g = self.run.grade
        self.glory = {"Clean": 1.0, "Tidy": 0.5}.get(g["name"], 0.0) if g else 0.0
        if self.glory:
            sound.play("fanfare", self.glory)
            for c in RAINBOW:
                self.fx.burst(480, 60, COLOR_RGB[c], n=int(14 * self.glory), speed=420,
                              shapes=("triangle", "square", "circle", "diamond"), size=(4, 9))

    def update(self, dt):
        self.fx.update(dt)
        return super().update(dt)

    def pick(self, opt):
        if self.picked:
            return
        b = next((b for b in self.buttons if b.tag.startswith("reward") and
                  self.options[int(b.tag[6:])] is opt), None)
        if b is not None:
            big = opt["id"].startswith(("pattern:", "relic:"))
            for c in RAINBOW if big else ("Y",):
                self.fx.burst(b.rect.x + 36, b.rect.centery, COLOR_RGB[c], n=8 if big else 10,
                              speed=300, shapes=("diamond", "triangle"))
        self.run.apply_reward(opt)
        self.picked = True
        for b in self.buttons:
            if b.tag.startswith("reward"):
                b.enabled = False
        self.skip.enabled = False
        self.cont.enabled = True
        self.say("Took %s." % opt["label"], GOOD)

    def do_skip(self):
        if self.picked:
            return
        self.picked = True
        for b in self.buttons:
            if b.tag.startswith("reward"):
                b.enabled = False
        self.skip.enabled = False
        self.cont.enabled = True
        self.say("Skipped.", DIM)

    def draw(self, surf):
        g = self.run.grade
        title = "Knocked loose!"
        sub = "+%d glint   (you have %d)" % (self.gold, self.run.gold)
        if g:
            title = {"Clean": "Clean sort!", "Tidy": "Tidy sort."}.get(g["name"], "Messy, but sorted.")
            sub = "%d turn%s, par %d.   +%d glint%s" % (
                g["turns"], "" if g["turns"] == 1 else "s", g["par"], self.gold,
                ("  (%d for speed)" % g["glint"]) if g["glint"] else "")
        self.backdrop.draw(surf)
        if self.glory:
            rays = pygame.Surface((960, 640), pygame.SRCALPHA)
            for i in range(16):
                a0 = self.t * 0.5 + i * math.tau / 16
                pts = [(480, 52), (480 + math.cos(a0) * 900, 52 + math.sin(a0) * 900),
                       (480 + math.cos(a0 + 0.18) * 900, 52 + math.sin(a0 + 0.18) * 900)]
                pygame.draw.polygon(rays, (*COLOR_RGB[RAINBOW[i % 6]], int(70 * self.glory)), pts)
            surf.blit(rays, (0, 0))
        self.draw_top(surf, title, sub, backdrop=False)
        if g and g["name"] == "Clean":
            draw_text(surf, font(20), "A clean sort leaves more behind: pick from four.",
                      (480, 122), WHITE, center=True, shadow=INK)
        self.draw_msg(surf, 150)
        self.draw_buttons(surf)
        self.fx.draw(surf)


TINTER_HELLO = ("Light! Fresh light! Barely refracted!",
                "Everything's tinted to order. Well. To my order.",
                "Don't mind the lean. It's a feature.",
                "Glint for colour, colour for glint. Simple.")
TINTER_THANKS = ("Pleasure. Mind the drips.", "Wear it well, little prism.", "Sold! Shinier already.")
TINTER_BROKE = ("Come back when you're shinier.", "That's more glint than you've got, friend.")


class WareButton(Button):
    """A ware on the counter: the object itself, and a price tag."""

    def __init__(self, rect, item, callback, **kw):
        super().__init__(rect, item["name"], callback, **kw)
        self.item = item
        self.t = 0.0

    def draw(self, surf, fnt, hover=False):
        r = self.rect
        sold = self.item.get("sold")
        lift = -6 if (hover and self.enabled) else 0
        if hover and self.enabled:
            glow = pygame.Rect(0, 0, r.w - 6, 24)
            glow.midbottom = (r.centerx, r.y + 96)
            pygame.draw.ellipse(surf, (255, 236, 150), glow)
        if not sold:
            draw_ware(surf, self.item["id"], r.centerx, r.y + 92 + lift, self.t)
        tag = pygame.Rect(0, 0, 86, 28)
        tag.midtop = (r.centerx, r.y + 112)
        pygame.draw.line(surf, INK, (r.centerx, r.y + 100), (r.centerx, tag.y), 2)
        pygame.draw.rect(surf, (236, 228, 214) if sold else PAPER, tag, border_radius=6)
        pygame.draw.rect(surf, INK, tag, 2, border_radius=6)
        if sold:
            draw_text(surf, font(22), "SOLD", tag.center, BAD, center=True)
        else:
            glint_icon(surf, tag.x + 16, tag.centery, 6)
            draw_text(surf, font(22), str(self.item["cost"]), (tag.x + 30, tag.y + 6), INK)
        if self.key:
            draw_text(surf, font(16), str(self.key - pygame.K_0), (r.x + 8, r.y + 4), DIM)


class ShopScreen(_Room):
    """The Tinter's stall: an awning, a counter, the Tinter, and its wares."""

    def __init__(self, app):
        super().__init__(app)
        self.rng = random.Random(self.run.seed + self.run.layer * 7 + self.run.act)
        self.line = self.rng.choice(TINTER_HELLO)
        self.build()
        self.say("Click a ware to buy it (or press its number). Prices are fixed.", DIM)

    def build(self):
        self.buttons = []
        n = len(self.run.shop)
        x0 = 600 - (n - 1) * 58
        for i, item in enumerate(self.run.shop):
            self.buttons.append(WareButton((x0 + i * 116 - 54, 226, 108, 150), item,
                                           lambda i=i: self.buy(i), enabled=not item.get("sold"),
                                           key=pygame.K_1 + i, tag="item%d" % i))
        self.add((380, 548, 200, 44), "Leave", self.app.leave_node, key=pygame.K_ESCAPE,
                 tag="leave")

    def buy(self, i):
        ok, msg = self.run.buy(i)
        if ok:
            sound.play("buy")
        self.build()
        self.say(msg, GOOD if ok else BAD)
        self.line = self.rng.choice(TINTER_THANKS if ok else TINTER_BROKE)

    def update(self, dt):
        for b in self.buttons:
            if isinstance(b, WareButton):
                b.t = self.t
        return super().update(dt)

    def draw(self, surf):
        t = self.t
        self.backdrop.draw(surf)
        heading(surf, "The Tinter", (480, 30), 44, center=True)
        # the awning
        top = 64
        pygame.draw.rect(surf, INK, (54, top - 4, 852, 40), border_radius=6)
        for x in (70, 890):
            pygame.draw.rect(surf, INK, (x - 5, top + 30, 10, 300))
        # a back shelf of jars, just for show
        shelf = pygame.Rect(300, 200, 590, 10)
        pygame.draw.rect(surf, INK, shelf.move(0, 3))
        pygame.draw.rect(surf, (200, 140, 90), shelf)
        for i in range(11):
            col = COLOR_RGB[RAINBOW[(i * 5) % 6]]
            h = 18 + (i * 7) % 14
            jar = pygame.Rect(318 + i * 52, shelf.y - h, 26, h)
            pygame.draw.rect(surf, lighten(col, 0.35), jar, border_radius=6)
            pygame.draw.rect(surf, INK, jar, 2, border_radius=6)
        for i in range(14):
            col = COLOR_RGB[RAINBOW[i % 6]]
            pygame.draw.rect(surf, col, (58 + i * 60, top, 60, 32))
            pygame.draw.circle(surf, col, (88 + i * 60, top + 32), 30, draw_bottom_left=True,
                               draw_bottom_right=True)
            pygame.draw.circle(surf, INK, (88 + i * 60, top + 32), 30, 3, draw_bottom_left=True,
                               draw_bottom_right=True)
        pygame.draw.line(surf, INK, (56, top), (904, top), 4)
        # the Tinter behind its counter, and what it says
        draw_tinter(surf, 170, 250 + math.sin(t * 2) * 3, 70, t,
                    look=((pygame.mouse.get_pos()[0] - 170) / 400.0, 0.3))
        bub = pygame.Rect(250, 140, 270, 56)
        pygame.draw.polygon(surf, INK, [(262, 194), (290, 194), (236, 214)])
        pygame.draw.rect(surf, INK, bub.move(0, 3), border_radius=12)
        pygame.draw.rect(surf, PAPER, bub, border_radius=12)
        pygame.draw.rect(surf, INK, bub, 2, border_radius=12)
        pygame.draw.polygon(surf, PAPER, [(264, 192), (288, 192), (240, 210)])
        draw_wrapped(surf, font(20), self.line, (bub.x + 10, bub.y + 8), bub.w - 20, INK, 0)
        # the counter
        counter = pygame.Rect(40, 330, 880, 84)
        pygame.draw.rect(surf, INK, counter.move(0, 5), border_radius=10)
        pygame.draw.rect(surf, (255, 214, 170), counter, border_radius=10)
        pygame.draw.rect(surf, (255, 236, 210), (counter.x, counter.y, counter.w, 14), border_radius=10)
        pygame.draw.rect(surf, INK, counter, 3, border_radius=10)
        self.draw_buttons(surf)
        # what's under the mouse
        hov = self.hover.item if isinstance(self.hover, WareButton) else None
        card = draw_card(surf, (140, 430, 680, 64))
        if hov:
            draw_text(surf, font(26), hov["name"], (card.x + 16, card.y + 8), INK)
            draw_text(surf, font(20), hov["desc"], (card.x + 16, card.y + 36), DIM)
        else:
            draw_text(surf, font(22), self.msg, card.center, self.msg_color, center=True)
        p = self.run.player
        x = stat_chip(surf, 20, 596, heart_icon, "%d/%d" % (p.hp, p.max_hp)) + 8
        stat_chip(surf, x, 596, glint_icon, "%d glint" % self.run.gold)


class ChoiceButton(Button):
    """A choice: its label, what it does as pictures, and the same in words."""

    def __init__(self, rect, label, effects, callback, **kw):
        super().__init__(rect, label, callback, **kw)
        self.effects = effects

    def draw(self, surf, fnt, hover=False):
        r = self.rect
        lift = -3 if (hover and self.enabled) else 0
        if self.enabled:
            pygame.draw.rect(surf, INK, r.move(0, 5), border_radius=12)
        body = r.move(0, lift)
        fill = self.fill(hover) if self.enabled else (232, 226, 218)
        if self.active:
            fill = (255, 236, 150)
        pygame.draw.rect(surf, fill, body, border_radius=12)
        pygame.draw.rect(surf, INK if self.enabled or self.active else (190, 182, 198), body, 3,
                         border_radius=12)
        draw_text(surf, font(26), self.label, (body.centerx, body.y + 18), INK, center=True)
        chips = effect_chips(self.effects)
        w = sum(32 + (font(22).size(txt)[0] if txt else 0) for _, txt, _ in chips)
        x = body.centerx - w // 2
        for kind, txt, extra in chips:
            x = draw_chip(surf, x, body.y + 34, kind, txt, extra) + 8
        words = effects_text(self.effects) or "Nothing happens. Walk on."
        draw_wrapped(surf, font(19), words, (body.x + 10, body.y + 60), body.w - 20, INK, 0,
                     center=True)
        if self.key:
            draw_text(surf, font(16), str(self.key - pygame.K_0), (body.x + 8, body.y + 5), DIM)


class _Vignette(_Room):
    """A room shown as a little scene: pick a choice, watch what it does."""

    scene = ""
    title = ""
    DURATION = 2.2

    def __init__(self, app, choices):
        super().__init__(app)
        self.done = False
        self.chosen = None
        self.info = {}
        self.effects = []
        self.anim_t = 0.0
        n = len(choices)
        w = 270 if n == 3 else 320
        x0 = 480 - (n * w + (n - 1) * 14) // 2
        for i, (cid, label, effects) in enumerate(choices):
            self.buttons.append(ChoiceButton((x0 + i * (w + 14), 416, w, 106), label, effects,
                                             lambda c=cid: self.pick(c), key=pygame.K_1 + i,
                                             tag=self.choice_tag(cid)))
        self.cont = self.add((380, 546, 200, 42), "Continue", app.leave_node, enabled=False,
                             key=pygame.K_RETURN, tag="continue")

    def choice_tag(self, cid):
        return "choice:" + cid

    def resolve(self, cid):
        """Apply the choice to the run; return a short message (or raise ValueError)."""
        raise NotImplementedError

    def pick(self, cid):
        if self.done:
            return
        try:
            msg = self.resolve(cid)
        except ValueError as e:
            self.say(str(e), BAD)
            return
        self.done = True
        self.chosen = cid
        self.anim_t = 0.0
        for b in self.buttons:
            if isinstance(b, ChoiceButton):
                b.enabled = False
                b.active = b.tag == self.choice_tag(cid)
        self.cont.enabled = True
        self.say(msg, GOOD)

    def update(self, dt):
        if self.chosen is not None:
            self.anim_t += dt
        return super().update(dt)

    def draw(self, surf):
        self.draw_top(surf, self.title)
        stage = draw_card(surf, (70, 80, 820, 318), (255, 250, 240), 18)
        surf.set_clip(stage.inflate(-6, -6))
        hover = None
        if isinstance(self.hover, ChoiceButton) and self.hover.enabled:
            hover = self.hover.tag.split(":", 1)[-1]
        ctx = {"hover": hover, "chosen": self.chosen, "info": self.info, "effects": self.effects,
               "u": min(1.0, self.anim_t / self.DURATION), "form": self.run.form()["shape"]}
        draw_scene(surf, stage, self.scene, self.t, ctx)
        surf.set_clip(None)
        if self.msg_color == BAD:
            self.draw_msg(surf, 404)
        self.draw_buttons(surf)


class RestScreen(_Vignette):
    scene = "rest"
    title = "Still Tile"

    def __init__(self, app):
        p = app.run.player
        heal = max(1, (p.max_hp * 4) // 10)
        low = min(PRIMARIES, key=lambda c: p.cap[c])
        self.options = {"heal": [("heal", heal)], "focus": [("cap", low, 1)]}
        super().__init__(app, [("heal", "Rest", self.options["heal"]),
                               ("focus", "Deepen", self.options["focus"])])
        self.info = {"color": low}
        self.say("Nothing clicks here. Nothing moves.", DIM)

    def choice_tag(self, cid):
        return cid                      # "heal" / "focus"

    def resolve(self, cid):
        msg = self.run.rest(cid)
        self.effects = self.options[cid]
        return msg


class EventScreen(_Vignette):
    DURATION = 2.4

    def __init__(self, app):
        self.event = app.run.event
        super().__init__(app, self.event["choices"])
        self.scene = self.event["id"]
        self.title = self.event["title"]
        for _cid, _label, effects in self.event["choices"]:
            for eff in effects:
                if eff[0] == "cap":
                    self.info.setdefault("color", eff[1])
        self.say("Choose.", DIM)

    def resolve(self, cid):
        msg = self.run.resolve_event(cid)
        out = self.run.event_outcome or {"ok": True, "effects": []}
        chosen = next(c for c in self.event["choices"] if c[0] == cid)
        self.effects = out["effects"] if chosen[2] else []
        self.info["ok"] = out["ok"]
        self.info["relic"] = next((e[1] for e in self.effects if e[0] == "facet"), None)
        self.info["hurts"] = any(e[0] == "hp" for e in self.effects)
        colours = [e[1] for e in self.effects if e[0] == "cap"]
        if colours:
            self.info["color"] = colours[0]
        return msg


class EndScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.won = self.run.finished == "victory"
        self.tower = self.run.tower
        if self.tower:                    # out of a Meadow tower: nothing lost, back you roll
            self.backdrop = Backdrop(MEADOW_SKY, seed=4, n=26)
            self.add((380, 450, 200, 48), "To the Meadow", app.show_hub, key=pygame.K_RETURN,
                     tag="meadow")
        else:
            self.backdrop = Backdrop(MEADOW_SKY, seed=4, n=26) if self.won else Backdrop.for_act(1, n=18)
            self.add((380, 450, 200, 48), "New Run", app.new_run, key=pygame.K_RETURN, tag="new")
        self.add((380, 510, 200, 40), "Title", app.to_title, key=pygame.K_ESCAPE, tag="title")

    def update(self, dt):
        self.backdrop.update(dt)
        return super().update(dt)

    def draw(self, surf):
        self.backdrop.draw(surf)
        run = self.run
        t = self.t
        if self.tower:
            heading(surf, "OUT YOU ROLL", (480, 90), 80, center=True)
            draw_text(surf, font(26), "The Set bundled you back out of the window. Someone's still waving.",
                      (480, 148), WHITE, center=True, shadow=INK)
            draw_player(surf, "circle", 480 + math.sin(t) * 120, 220, 30, t, mood="plain",
                        rot=-math.sin(t) * 120 / 30)
            self.draw_buttons(surf)
            return
        if self.won:
            heading(surf, "YOU ROLLED", (480, 90), 80, center=True)
            draw_text(surf, font(26), "Tri is round now, and somewhere in a meadow, still rolling.",
                      (480, 148), WHITE, center=True, shadow=INK)
            draw_player(surf, "circle", 480 + math.sin(t) * 120, 220, 30, t, mood="happy",
                        rot=-math.sin(t) * 120 / 30)
        else:
            heading(surf, "SORTED", (480, 90), 80, center=True)
            draw_text(surf, font(26), "The Set knocked you back into your slot. A triangle again.",
                      (480, 148), WHITE, center=True, shadow=INK)
            draw_slot(surf, "triangle", 480, 248, 30, FLOORS[1]["wall"])
            draw_player(surf, "triangle", 480, 222 + math.sin(t * 2) * 2, 24, t, mood="sleep",
                        look=(0, 1))
        card = draw_card(surf, (230, 290, 500, 140))
        floor = floor_style(min(run.act, 3))["name"]
        draw_text(surf, font(24), "Highest floor: %s" % floor, (card.x + 20, card.y + 16), INK)
        draw_text(surf, font(24), "%d glint    seed %d" % (run.gold, run.seed), (card.x + 20, card.y + 46), INK)
        rel = ", ".join(RELICS[r]["name"] for r in run.relics) or "none"
        draw_wrapped(surf, font(20), "Facets: " + rel, (card.x + 20, card.y + 76), card.w - 40, DIM)
        d = self.app.meta.data
        draw_text(surf, font(20), "Climbs %d   Rolled away %d   Highest floor %d"
                  % (d["runs"], d["wins"], d["best_act"]), (card.centerx, card.bottom - 16), DIM,
                  center=True)
        self.draw_buttons(surf)
