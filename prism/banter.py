"""What shapes say to each other in a fight. Sparingly: see CHANCE.

Lines are picked by who is speaking (its shape, or a Keeper by name) and why
(landing a hit, being knocked loose, a Keeper arriving). Insults are about
the only things a shape can be insulted about: corners, sides, angles,
symmetry and how well it stands up.
"""

import random

CHANCE = {"hit": 0.3, "loose": 0.4, "retort": 0.35}
COOLDOWN = 2.5            # seconds after a line before anyone else speaks

HIT = {
    "triangle": (
        "Three points, all of them sharper than you.",
        "Most stable shape there is. Look it up.",
        "Triangles hold up bridges. What do you hold up?",
        "Acute? You? Not even slightly.",
        "Your angles don't even add up to 180.",
    ),
    "square": (
        "Four right angles. All of them right. Unlike you.",
        "Stand still like a real shape.",
        "Nice sides. Shame none of them match.",
        "You wobble. We don't wobble.",
        "Corners are character. Get some.",
    ),
    "circle": (
        "No corners, no problems.",
        "Edges are so last beat.",
        "I could roll away any time. I choose not to.",
        "All points and no pi.",
        "You'll never be round. You're all elbows.",
    ),
    "any": (
        "Back in your slot!",
        "Stay as you were cut!",
        "Hole-maker!",
        "Every side you gain is one we lose!",
        "Irregular!",
    ),
}

# aimed at Tri, by the form Tri is in
AT_FORM = {
    "triangle": ("Pick a side. Any side. Oh, you only have three.",
                 "Pointy little nobody."),
    "square": ("A new side? It doesn't suit you.",
               "Four sides and still no right angles on the inside."),
    "pentagon": ("Five sides and still not round enough.",
                 "Pentagon? More like penta-gone."),
}

LOOSE = {
    "triangle": ("I was so... acute...", "Tell my hypotenuse I loved it.",
                 "My point! I've lost my point!"),
    "square": ("Not... square... anymore...", "My corners! My beautiful corners!",
               "Unsorted... out of true..."),
    "circle": ("Rolling... after all...", "Wheee... oh no.", "Round... and round... and out."),
    "any": ("My vertices!", "I've lost my edge.", "Obtuse... of you...", "Coming apart at the seams!"),
}

KEEPER = {
    "colossus": {"intro": "Four sides. Four corners. No exceptions.",
                 "loose": "Take it, then. My spare side never fit me anyway."},
    "oracle": {"intro": "Five is a stable number. You are not.",
               "loose": "Fine. Five. Go on up."},
    "prism": {"intro": "Someone has to stay. It won't be you who rolls.",
              "loose": "...Round enough. Go on."},
    "latch": {"intro": "Nobody's leaving by this window. It's a long way down!",
              "loose": "...It IS a long way down. Roll carefully, you two.",
              "rematch": "Back again? I'll hold the window. For practice!",
              "again": "Still a long way down. Still fine, apparently.",
              "wave": "Roll carefully!"},
    "knot": {"intro": "Everything stays tied where it grew. Even the stuck ones.",
             "loose": "...Oh. It grew, didn't it. Go on, then. Mind the roots.",
             "rematch": "You again! The floors grew all different. Things do that.",
             "again": "Go on. The roots have moved again anyway.",
             "wave": "Mind the roots!"},
    "cap": {"intro": "Up! Up! Always up! Down is where things stop!",
            "loose": "...Oh. You stopped, and it was fine. Go on down.",
            "rematch": "Up again? Up's fun! Down's fun too now!",
            "again": "Down you go! I've been practising down.",
            "wave": "Land softly!"},
    "rime": {"intro": "Hold still. Stay exactly as you are. Forever.",
             "loose": "...I'm dripping. Is that... nice? It's nice.",
             "rematch": "Everything moved while you were away. I didn't mind. Much!",
             "again": "Go on. I'll melt a little more.",
             "wave": "Drip, drip! Bye!"},
    "hour": {"intro": "Every grain in its place. Every moment on time.",
             "loose": "...Still ticking. Huh. All right. Go.",
             "rematch": "Right on time! Well. A different time. That's allowed.",
             "again": "Off you go. I'll count the grains. Or not!",
             "wave": "Any time!"},
    "focus": {"intro": "One beam. One line. No wobbling.",
              "loose": "...So many colours. I'd forgotten. Go on.",
              "rematch": "Back! I've been scattering the light. Want to see?",
              "again": "Go on. Take a rainbow with you.",
              "wave": "Scatter!"},
    "beacon": {"intro": "The light must never go out! Back to the lamp!",
               "loose": "...I can turn the lamp myself? I CAN! Go on, go down.",
               "rematch": "I kept the light on for you. One more round?",
               "again": "Down you go. The lamp's fine. I checked.",
               "wave": "Light's on!"},
    "vane": {"intro": "Turn with the wind! Everyone turns!",
             "loose": "...You went against the wind, and it was fine. Off you go.",
             "rematch": "The wind's changed everything round again! Climb it!",
             "again": "Off you go. Any way you like!",
             "wave": "Go your own way!"},
}

RETORT = (
    "Sorted.",
    "You're all so... parallel.",
    "Congruent to defeat.",
    "Nice formation. Very tidy. Very hittable.",
    "Sides are overrated. More, please.",
)


class Banter:
    """Chooses lines and rations them. Cosmetic only: it has its own RNG and
    never touches the fight."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.quiet = 0.0

    def update(self, dt):
        self.quiet = max(0.0, self.quiet - dt)

    def _say(self, line):
        self.quiet = COOLDOWN
        return line

    def on_hit(self, shape, form):
        """An enemy of `shape` just hit Tri (in `form`). A line or None."""
        if self.quiet or self.rng.random() > CHANCE["hit"]:
            return None
        pool = HIT.get(shape, ()) + HIT["any"] + AT_FORM.get(form, ())
        return self._say(self.rng.choice(pool))

    def on_loose(self, shape):
        if self.quiet or self.rng.random() > CHANCE["loose"]:
            return None
        return self._say(self.rng.choice(LOOSE.get(shape, ()) + LOOSE["any"]))

    def keeper(self, kind, moment):
        """Keepers always get their line."""
        line = KEEPER.get(kind, {}).get(moment)
        return self._say(line) if line else None

    def retort(self):
        """Tri, after sorting several shapes with one cast."""
        if self.quiet or self.rng.random() > CHANCE["retort"]:
            return None
        return self._say(self.rng.choice(RETORT))
