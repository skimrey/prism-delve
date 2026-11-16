# Prism Delve

A turn-based roguelite dungeon delver played with colours and shapes. Pure Python + pygame-ce, CPU-only (no GPU needed).

Plan up to 4 beats per turn, then watch them resolve. Enemy intentions are telegraphed, so dodging, pushing and stunning change the outcome.

## Run

```
python3 -m venv .venv
./.venv/bin/pip install pygame-ce
./.venv/bin/python -m prism            # optional: --seed=123
```

Headless (VM / CI): `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`

## Test

```
./.venv/bin/python -m unittest discover -s tests
```

## Rules in brief

- Colours: R, G, B, and mixes Y (R+G), C (G+B), M (R+B). Opposites (R/C, G/M, B/Y) deal double damage.
- Shapes: triangle (line), square (2x2), circle (plus). Casting a different shape than the last one builds a chain for more damage.
- Every fight is checked at generation to have at least two distinct winning styles.

Licensed under the MIT License.
