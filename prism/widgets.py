"""Palette, text helpers and the Button widget. CPU-only: plain pygame.draw calls.

The look: a toy shape-sorter. Bright backgrounds, cream "paper" cards, and a
thick dark-ink outline on everything, so any of the six colours reads on top
of any other.
"""

import pygame

from .settings import LETTERS, SETTINGS

INK = (40, 30, 72)             # outlines and body text
WHITE = (255, 255, 255)
PAPER = (255, 250, 238)        # cards and panels
PAPER_DIM = (238, 229, 214)
BG = (255, 236, 214)           # fallback background
PANEL = PAPER
PANEL_LIGHT = (255, 232, 186)
TEXT = INK
DIM = (120, 106, 150)
GOOD = (22, 160, 92)
BAD = (232, 44, 86)
WARN = (214, 128, 0)
ACCENT = (98, 70, 238)
SUNNY = (255, 214, 72)         # "selected" fill
DISABLED_FILL = (226, 220, 212)
DISABLED_TEXT = (162, 152, 176)


def draw_text(surf, font, text, pos, color=TEXT, center=False, right=False, shadow=None):
    """shadow: an (r, g, b) to draw a 2px drop shadow in (for text on colour)."""
    img = font.render(str(text), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    if shadow is not None:
        surf.blit(font.render(str(text), True, shadow), r.move(0, 3))
    surf.blit(img, r)
    return r


def wrap_text(font, text, width):
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = (line + " " + word).strip()
            if font.size(trial)[0] <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_wrapped(surf, font, text, pos, width, color=TEXT, spacing=2, center=False, shadow=None):
    x, y = pos
    for line in wrap_text(font, text, width):
        if center:
            draw_text(surf, font, line, (x + width // 2, y + font.get_height() // 2), color,
                      center=True, shadow=shadow)
        else:
            draw_text(surf, font, line, (x, y), color, shadow=shadow)
        y += font.get_height() + spacing
    return y


def draw_card(surf, rect, fill=PAPER, radius=14, lift=6, outline=INK, width=3):
    """A paper card with an ink outline and a hard drop shadow."""
    rect = pygame.Rect(rect)
    if lift:
        pygame.draw.rect(surf, INK, rect.move(0, lift), border_radius=radius)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if width:
        pygame.draw.rect(surf, outline, rect, width, border_radius=radius)
    return rect


def draw_shape(surf, shape, cx, cy, r, color, outline=None, width=2):
    """Small flat triangle / square / circle icon (no face)."""
    if shape == "triangle":
        pts = [(cx, cy - r), (cx + r, cy + r * 0.8), (cx - r, cy + r * 0.8)]
        pygame.draw.polygon(surf, color, pts)
        if outline:
            pygame.draw.polygon(surf, outline, pts, width)
    elif shape == "square":
        rect = pygame.Rect(cx - r, cy - r, r * 2, r * 2)
        pygame.draw.rect(surf, color, rect, border_radius=3)
        if outline:
            pygame.draw.rect(surf, outline, rect, width, border_radius=3)
    else:
        pygame.draw.circle(surf, color, (cx, cy), r)
        if outline:
            pygame.draw.circle(surf, outline, (cx, cy), r, width)


_MARK_CACHE = {}


def draw_colour_mark(surf, key, cx, cy, r, force=False):
    """Colour-blind mode: the colour's letter (R G B Y C M) in a small white
    disc. Drawn only when the setting is on (or force)."""
    if not (force or SETTINGS["marks"]) or key not in LETTERS:
        return
    r = max(6, int(r))
    img = _MARK_CACHE.get((key, r))
    if img is None:
        img = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        c = r + 2
        pygame.draw.circle(img, INK, (c, c + 1), r + 1)
        pygame.draw.circle(img, WHITE, (c, c), r)
        pygame.draw.circle(img, INK, (c, c), r, max(1, r // 6))
        f = font(max(10, int(r * 1.5)))
        txt = f.render(LETTERS[key], True, INK)
        img.blit(txt, txt.get_rect(center=(c, c + 1)))
        _MARK_CACHE[(key, r)] = img
    surf.blit(img, (int(cx - img.get_width() / 2), int(cy - img.get_height() / 2)))


def tint(surf, rect, color, alpha):
    """Translucent rectangle overlay."""
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((*color, max(0, min(255, int(alpha)))))
    surf.blit(s, rect.topleft)


_FONTS = {}


def font(size):
    f = _FONTS.get(size)
    if f is None:
        f = _FONTS[size] = pygame.font.Font(None, size)
    return f


def small_font():
    return font(19)


def _lighter(c, t):
    return tuple(int(v + (255 - v) * t) for v in c)


class Button:
    """A chunky toy button. `chip` makes it a colour button (filled with
    that colour); `active` marks the current selection."""

    def __init__(self, rect, label, callback, enabled=True, color=PAPER,
                 key=None, tag="", chip=None, active=False, small=False, icon=None, chip_key=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled = enabled
        self.color = color
        self.key = key
        self.tag = tag
        self.chip = chip          # optional colour swatch
        self.chip_key = chip_key  # its colour letter, for the colour-blind symbol
        self.active = active
        self.small = small
        self.icon = icon          # optional callable(surf, cx, cy) drawn left of the label

    def click(self):
        if self.enabled and self.callback:
            from . import sound                   # lazy: widgets load before the mixer
            sound.play("ui", 0.5)
            self.callback()
            return True
        return False

    def fill(self, hover):
        if not self.enabled:
            return DISABLED_FILL
        if self.chip is not None:
            base = self.chip if self.active else _lighter(self.chip, 0.55)
        else:
            base = SUNNY if self.active else self.color
        if hover:
            base = _lighter(base, 0.25)
        return base

    def draw(self, surf, fnt, hover=False):
        if self.small:
            fnt = small_font()
        r = self.rect
        lift = 0
        if self.enabled:
            lift = -2 if hover else 0
            pygame.draw.rect(surf, INK, r.move(0, 4), border_radius=10)
        body = r.move(0, lift)
        pygame.draw.rect(surf, self.fill(hover), body, border_radius=10)
        outline = INK if self.enabled else DISABLED_TEXT
        pygame.draw.rect(surf, outline, body, 4 if self.active else 3, border_radius=10)
        x = body.x + 12
        if self.icon is not None:
            self.icon(surf, body.x + 18, body.centery)
            x += 18
        elif self.chip is not None:
            pygame.draw.circle(surf, self.chip if self.enabled else DISABLED_FILL,
                               (body.x + 16, body.centery), 7)
            pygame.draw.circle(surf, outline, (body.x + 16, body.centery), 7, 2)
            draw_colour_mark(surf, self.chip_key, body.x + 16, body.centery, 7)
            x += 16
        color = TEXT if self.enabled else DISABLED_TEXT
        label = fnt.render(self.label, True, color)
        lr = label.get_rect()
        if self.chip is None and self.icon is None:
            lr.center = body.center
        else:
            lr.midleft = (x, body.centery)
        surf.blit(label, lr)
