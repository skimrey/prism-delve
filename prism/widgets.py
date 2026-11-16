"""Small drawing helpers and a Button widget. CPU-only: plain pygame.draw calls."""

import pygame

BG = (16, 17, 26)
PANEL = (28, 30, 44)
PANEL_LIGHT = (40, 43, 62)
GRID_A = (34, 36, 52)
GRID_B = (30, 32, 46)
WALL = (82, 86, 108)
TEXT = (232, 234, 244)
DIM = (140, 146, 170)
GOOD = (110, 220, 130)
BAD = (240, 96, 96)
WARN = (244, 196, 84)
ACCENT = (120, 160, 255)


def draw_text(surf, font, text, pos, color=TEXT, center=False, right=False):
    img = font.render(str(text), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
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


def draw_wrapped(surf, font, text, pos, width, color=TEXT, spacing=2):
    x, y = pos
    for line in wrap_text(font, text, width):
        draw_text(surf, font, line, (x, y), color)
        y += font.get_height() + spacing
    return y


def draw_shape(surf, shape, cx, cy, r, color, outline=None, width=2):
    """Triangle / square / circle centred on (cx, cy)."""
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


def tint(surf, rect, color, alpha):
    """Translucent rectangle overlay."""
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((*color, alpha))
    surf.blit(s, rect.topleft)


_SMALL = None


def small_font():
    global _SMALL
    if _SMALL is None:
        _SMALL = pygame.font.Font(None, 19)
    return _SMALL


class Button:
    def __init__(self, rect, label, callback, enabled=True, color=(62, 68, 98),
                 key=None, tag="", chip=None, active=False, small=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled = enabled
        self.color = color
        self.key = key
        self.tag = tag
        self.chip = chip          # optional colour swatch
        self.active = active
        self.small = small

    def click(self):
        if self.enabled and self.callback:
            self.callback()
            return True
        return False

    def draw(self, surf, font, hover=False):
        if self.small:
            font = small_font()
        base = self.color if self.enabled else (36, 38, 52)
        if self.enabled and hover:
            base = tuple(min(255, c + 22) for c in base)
        pygame.draw.rect(surf, base, self.rect, border_radius=6)
        if self.active:
            pygame.draw.rect(surf, ACCENT, self.rect, 3, border_radius=6)
        elif self.enabled:
            pygame.draw.rect(surf, (96, 104, 140), self.rect, 1, border_radius=6)
        x = self.rect.x + 10
        if self.chip is not None:
            pygame.draw.circle(surf, self.chip, (self.rect.x + 16, self.rect.centery), 7)
            x += 16
        color = TEXT if self.enabled else (96, 100, 120)
        label = font.render(self.label, True, color)
        r = label.get_rect()
        if self.chip is None:
            r.center = self.rect.center
        else:
            r.midleft = (x, self.rect.centery)
        surf.blit(label, r)
