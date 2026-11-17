"""Player settings. A plain dict the whole game reads; Meta saves it.

    marks       colour-blind mode: a letter on every colour (R G B Y C M)
    sound       sound effects on/off
    volume      0.0 .. 1.0
    fullscreen  window or full screen
    open_zones  every zone of the Meadow open from the start (normally each
                opens when you get the last tower's friend out)
"""

DEFAULTS = {"marks": False, "sound": True, "volume": 0.7, "fullscreen": False, "open_zones": False}
SETTINGS = dict(DEFAULTS)

# Colour-blind mode: every colour wears its initial, in a little white disc
# (R G B for the three lights, Y C M for their mixes).
LETTERS = {"R": "R", "G": "G", "B": "B", "Y": "Y", "C": "C", "M": "M"}
STROKES = LETTERS          # (the old name)


def load(data):
    """Take settings from a saved dict (unknown keys ignored)."""
    SETTINGS.clear()
    SETTINGS.update(DEFAULTS)
    for k, v in (data or {}).items():
        if k in DEFAULTS:
            SETTINGS[k] = v
    return SETTINGS
