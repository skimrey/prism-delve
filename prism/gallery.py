"""The tower gallery: every tower there is, painted, with who's in it, its
Keeper, its twist and its zone. Pick which ones are in your world and in
what order (saved as meta["plan"], read by world.py): keep the curated
order, shuffle it, or leave some out."""

import random

import pygame

from .consts import COLOR_RGB, TOWER_ORDER, TOWERS, twist_name
from .enemies import KINDS
from .pixel import sky_up
from .screens import Screen
from .towers_art import draw_tower_art, tower_sprite
from .widgets import DIM, INK, PAPER, WHITE, draw_card, draw_text, draw_wrapped, font
from .world import ZONES, plan_of

CARD_W, CARD_H = 214, 244


class GalleryScreen(Screen):
    def __init__(self, app, back=None):
        super().__init__(app)
        self.back = back or app.pop
        self.plan = plan_of(app.meta.data)
        self.hovered = None
        self.build()

    def build(self):
        self.buttons = []
        for i, tid in enumerate(TOWER_ORDER):
            r = self.card_rect(i)
            self.add(r, "", lambda t=tid: self.toggle(t), tag="tower:" + tid)
        self.add((30, 586, 170, 40), "Curated order", self.curated, tag="curated", small=True)
        self.add((210, 586, 130, 40), "Shuffle", self.shuffle, tag="shuffle", small=True)
        self.add((760, 586, 170, 40), "Done", self.done, key=pygame.K_ESCAPE, tag="done")

    def card_rect(self, i):
        return pygame.Rect(26 + (i % 4) * (CARD_W + 20), 70 + (i // 4) * (CARD_H + 8), CARD_W, CARD_H)

    def toggle(self, tid):
        if tid in self.plan:
            if len(self.plan) > 1:
                self.plan.remove(tid)
        else:
            self.plan.append(tid)
        self.save()

    def curated(self):
        self.plan = list(TOWER_ORDER)
        self.save()

    def shuffle(self):
        random.shuffle(self.plan)
        self.save()

    def save(self):
        self.app.meta.data["plan"] = list(self.plan)
        self.app.meta.save()

    def done(self):
        self.save()
        self.back()

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hovered = None
            for i, tid in enumerate(TOWER_ORDER):
                if self.card_rect(i).collidepoint(ev.pos):
                    self.hovered = tid
        return super().handle(ev)

    def draw(self, surf):
        surf.blit(sky_up((104, 78, 236), (255, 124, 150)), (0, 0))
        draw_text(surf, font(40), "The Towers", (480, 32), WHITE, center=True, shadow=INK)
        draw_text(surf, font(18), "Click a tower to put it in your world or take it out. The numbers are the "
                  "order you'll find them in.", (480, 58), WHITE, center=True, shadow=INK)
        t = self.t
        for i, tid in enumerate(TOWER_ORDER):
            self._card(surf, self.card_rect(i), tid, t)
        info = TOWERS.get(self.hovered) if self.hovered else None
        if info:
            box = draw_card(surf, (356, 584, 394, 50), PAPER, 12)
            draw_wrapped(surf, font(16), '"%s"' % info["plea"], (box.x + 10, box.y + 6), box.w - 20, INK, 2)
        self.draw_buttons(surf)

    def draw_buttons(self, surf):
        f = font(22)
        for b in self.buttons:
            if not b.tag.startswith("tower:"):
                b.draw(surf, f, hover=(b is self.hover))

    def _card(self, surf, r, tid, t):
        info = TOWERS[tid]
        zone = ZONES[info["zone"]]
        chosen = tid in self.plan
        hover = self.hovered == tid
        draw_card(surf, r, PAPER if chosen else (214, 206, 226), 14, 5 if hover else 4)
        pic = pygame.Rect(r.x + 8, r.y + 8, r.w - 16, 144)
        sky = sky_up(zone["sky"][0], zone["sky"][1], (pic.w, pic.h), 2)
        surf.blit(sky, pic.topleft)
        surf.set_clip(pic)
        img, meta = tower_sprite(tid, 1)
        left = pic.centerx - img.get_width() // 2
        draw_tower_art(surf, tid, left + meta["win"][0] + 0.5, pic.bottom + 2, 1, t)
        ground = zone["ground"]
        pygame.draw.rect(surf, ground[1], (pic.x, pic.bottom - 4, pic.w, 4))
        surf.set_clip(None)
        pygame.draw.rect(surf, INK, pic, 2)
        if not chosen:
            veil = pygame.Surface(pic.size, pygame.SRCALPHA)
            veil.fill((255, 255, 255, 130))
            surf.blit(veil, pic.topleft)
        draw_text(surf, font(20), info["name"], (r.centerx, r.y + 164), INK, center=True)
        draw_text(surf, font(16), zone["name"], (r.centerx, r.y + 183), DIM, center=True)
        f = info["friend"]
        twists = ", ".join(twist_name(w, tid) for w in info.get("twists", ())) or "just rolling"
        draw_text(surf, font(15), "%s %s  |  %s" % (
            {"R": "red", "G": "green", "B": "blue", "Y": "yellow", "C": "cyan", "M": "magenta"}[f["color"]],
            f["was"], KINDS[info["boss"]]["label"]), (r.centerx, r.y + 201), INK, center=True)
        draw_text(surf, font(15), twists, (r.centerx, r.y + 218), (120, 90, 170), center=True)
        if chosen:                                  # (difficulty comes from its place in your world)
            from .run import tower_difficulty
            tier, rooms = tower_difficulty(self.plan.index(tid))
            draw_text(surf, font(14), "tier %d, %d rooms" % (tier, rooms), (r.centerx, r.y + 234), DIM,
                      center=True)
        if chosen:
            n = self.plan.index(tid) + 1
            pygame.draw.circle(surf, INK, (r.right - 16, r.y + 16), 14)
            pygame.draw.circle(surf, COLOR_RGB["Y"], (r.right - 16, r.y + 16), 12)
            draw_text(surf, font(18), str(n), (r.right - 16, r.y + 16), INK, center=True)
        else:
            draw_text(surf, font(16), "not in your world", (pic.centerx, pic.centery), INK, center=True)
