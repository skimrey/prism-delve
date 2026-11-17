"""The Map (M or Tab in the hub): every tower in your world, in order.

Go anywhere you've been, and climb any tower you've reached, as often as you
like. A tower whose friend is already out is a climb just for fun, and its
floors are generated fresh every time (see App.climb_tower): a new layout,
the same twists, the same difficulty for its place in your world, and every
fight checked by the solver. Towers you haven't reached yet stay veiled.
"""

import pygame

from .consts import COLOR_NAMES, COLOR_RGB, TOWERS, twist_name
from .pixel import sky_up
from .run import tower_difficulty
from .screens import Screen
from .towers_art import draw_tower_art, tower_sprite
from .widgets import DIM, INK, PAPER, WHITE, draw_card, draw_text, font
from .world import ZONES, World, plan_of

CARD_W, CARD_H = 214, 246


class MapScreen(Screen):
    def __init__(self, app, here=None):
        super().__init__(app)
        data = app.meta.data
        pretend = getattr(app, "hub_rescued", None)
        self.rescued = set(data.get("friends", []) if pretend is None else pretend)
        from .settings import SETTINGS
        open_all = SETTINGS.get("open_zones") or bool(getattr(app, "dev_open_zones", False))
        self.plan = plan_of(data)
        self.world = World(self.plan, self.rescued, open_all)
        self.reached = {z.tower: z for z in self.world.zones}
        self.here = self.world.zone_at(here).tower if here is not None else None
        self.hovered = None
        for i, tid in enumerate(self.plan):
            r = self.card_rect(i)
            if tid in self.reached:
                self.add((r.x + 10, r.bottom - 40, 92, 30), "Go", lambda t=tid: self.go(t), small=True,
                         tag="go:" + tid)
                self.add((r.right - 102, r.bottom - 40, 92, 30), "Climb" if tid not in self.rescued else "Again",
                         lambda t=tid: self.climb(t), small=True, tag="climb:" + tid,
                         color=(255, 236, 160))
        self.add((270, 590, 220, 40), "The Meadow's start", self.start, small=True, tag="start")
        self.add((760, 590, 170, 40), "Back", app.pop, key=pygame.K_ESCAPE, tag="back")

    def card_rect(self, i):
        n = len(self.plan)
        cols = min(4, n)
        x0 = 480 - (cols * (CARD_W + 20) - 20) // 2
        return pygame.Rect(x0 + (i % 4) * (CARD_W + 20), 78 + (i // 4) * (CARD_H + 8), CARD_W, CARD_H)

    # -- going places
    def go(self, tid):
        z = self.reached[tid]
        self.app.pop()
        self.app.show_hub(start_x=z.start + (160 if z.index == 0 else 300))

    def climb(self, tid):
        self.app.pop()
        self.app.enter_tower(tid)

    def start(self):
        self.app.pop()
        self.app.show_hub(start_x=160)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_m, pygame.K_TAB):
            self.app.pop()
            return True
        if ev.type == pygame.MOUSEMOTION:
            self.hovered = next((tid for i, tid in enumerate(self.plan) if self.card_rect(i).collidepoint(ev.pos)),
                                None)
        return super().handle(ev)

    # -- drawing
    def draw(self, surf):
        surf.blit(sky_up((104, 78, 236), (255, 124, 150)), (0, 0))
        draw_text(surf, font(40), "The Map", (480, 30), WHITE, center=True, shadow=INK)
        draw_text(surf, font(18), "Go anywhere you've been. Climb any tower you've reached, as often as you like: "
                  "its floors shuffle every time.", (480, 60), WHITE, center=True, shadow=INK)
        for i, tid in enumerate(self.plan):
            self._card(surf, self.card_rect(i), i, tid)
        self.draw_buttons(surf)

    def _card(self, surf, r, i, tid):
        info = TOWERS[tid]
        zone = ZONES[info["zone"]]
        z = self.reached.get(tid)
        hover = self.hovered == tid and z is not None
        draw_card(surf, r, PAPER if z else (206, 198, 222), 14, 5 if hover else 4)
        pic = pygame.Rect(r.x + 8, r.y + 8, r.w - 16, 122)
        surf.blit(sky_up(zone["sky"][0], zone["sky"][1], (pic.w, pic.h), 2), pic.topleft)
        surf.set_clip(pic)
        img, meta = tower_sprite(tid, 1)
        left = pic.centerx - img.get_width() // 2
        friend = info["friend"]
        waiting = z is not None and tid not in self.rescued
        draw_tower_art(surf, tid, left + meta["win"][0] + 0.5, pic.bottom + 2, 1, self.t,
                       friend=(friend["was"], COLOR_RGB[friend["color"]]) if waiting else None)
        pygame.draw.rect(surf, zone["ground"][1], (pic.x, pic.bottom - 4, pic.w, 4))
        surf.set_clip(None)
        pygame.draw.rect(surf, INK, pic, 2)
        if z is None:                                       # not reached yet: veiled
            veil = pygame.Surface(pic.size, pygame.SRCALPHA)
            veil.fill((40, 30, 72, 150))
            surf.blit(veil, pic.topleft)
            draw_text(surf, font(20), "not reached yet", pic.center, WHITE, center=True, shadow=INK)
        # its number in your world, and "you are here"
        pygame.draw.circle(surf, INK, (r.right - 16, r.y + 16), 14)
        pygame.draw.circle(surf, COLOR_RGB["Y"], (r.right - 16, r.y + 16), 12)
        draw_text(surf, font(18), str(i + 1), (r.right - 16, r.y + 16), INK, center=True)
        if tid == self.here:
            tag = pygame.Rect(0, 0, 96, 22)
            tag.topleft = (pic.x + 6, pic.y + 6)
            pygame.draw.rect(surf, INK, tag, border_radius=11)
            draw_text(surf, font(15), "you are here", tag.center, WHITE, center=True)
        draw_text(surf, font(20), info["name"], (r.centerx, r.y + 143), INK, center=True)
        draw_text(surf, font(15), zone["name"], (r.centerx, r.y + 161), DIM, center=True)
        if z is None:
            status, col = "", DIM
        elif tid in self.rescued:
            n = self.app.meta.data.get("tower_climbs", {}).get(tid, 0)
            status = "%s %s is out%s" % (COLOR_NAMES[friend["color"]].lower(), friend["was"],
                                         ", climbed %dx" % n if n else "")
            col = (60, 150, 90)
        else:
            status, col = "a %s at the window!" % friend["was"], COLOR_RGB["M"]
        draw_text(surf, font(15), status, (r.centerx, r.y + 178), col, center=True)
        tier, rooms = tower_difficulty(i)
        twists = ", ".join(twist_name(w, tid) for w in info.get("twists", ())) or "just rolling"
        draw_text(surf, font(14), "%s  |  %d rooms" % (twists, rooms), (r.centerx, r.y + 194), (120, 90, 170),
                  center=True)
