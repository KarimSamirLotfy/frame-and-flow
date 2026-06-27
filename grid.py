"""Rectangular grid subdivision — Manim-agnostic geometry.

Two layout strategies, both return cells in guaranteed left-to-right,
top-to-bottom reading order:

  row_major(width, height, n, rng)  ← default for this project
      Slices the area into rows first (random heights), then slices each row
      into cells (random widths). Reading order is correct BY CONSTRUCTION —
      cells are numbered stripe-by-stripe, left to right within each stripe.
      Good for typography that must always be readable.

  subdivide(width, height, n, rng)  ← original free-form BSP (kept for reference)
      Repeatedly splits the largest rectangle along its longer axis. Produces
      more dramatic size contrast but does NOT guarantee reading order.

Coordinates: Manim convention, origin at centre, +x right, +y up.
Each Cell carries its centre (cx, cy) and inner size (w, h) after gutters.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class Cell:
    cx: float  # centre x  (Manim coords)
    cy: float  # centre y
    w: float   # inner width  (after gutter)
    h: float   # inner height (after gutter)

    @property
    def area(self) -> float:
        return self.w * self.h


# --------------------------------------------------------------------------- #
# Row-major layout (guaranteed reading order)
# --------------------------------------------------------------------------- #

def row_major(
    width: float,
    height: float,
    n: int,
    rng: random.Random,
    row_ratio_range: tuple[float, float] = (0.30, 0.70),
    col_ratio_range: tuple[float, float] = (0.25, 0.75),
    gutter: float = 0.0,
) -> list[Cell]:
    """Split area into rows then columns; cells are in L-R, T-B reading order.

    The number of rows is chosen so each row gets at least 1 word and rows stay
    visually balanced (no row gets more than ~60 % of words unless n is tiny).

    Args:
        width, height:     size of the whole area (Manim units).
        n:                 exact number of cells to produce (one per word).
        rng:               seeded Random for reproducibility.
        row_ratio_range:   how unevenly to cut row heights (relative splits).
        col_ratio_range:   how unevenly to cut cell widths within a row.
        gutter:            visual gap — each cell shrinks by this on every side.
    """
    n = max(1, n)

    # ---- decide how many rows and how many cells per row ------------------- #
    n_rows = _choose_n_rows(n, rng)
    counts = _distribute(n, n_rows, rng)   # list of ints, len == n_rows, sum == n

    # ---- cut row heights --------------------------------------------------- #
    row_heights = _random_cuts(height, n_rows, rng, row_ratio_range)

    # ---- build cells top-to-bottom, left-to-right -------------------------- #
    cells: list[Cell] = []
    # Manim: y=0 is screen centre; rows go from top (+height/2) downward.
    y_top = height / 2
    x_left = -width / 2

    for row_idx, (rh, count) in enumerate(zip(row_heights, counts)):
        col_widths = _random_cuts(width, count, rng, col_ratio_range)
        x = x_left
        row_cy = y_top - rh / 2          # centre-y of this row
        for cw in col_widths:
            cells.append(Cell(
                cx=x + cw / 2,
                cy=row_cy,
                w=max(0.0, cw - 2 * gutter),
                h=max(0.0, rh - 2 * gutter),
            ))
            x += cw
        y_top -= rh

    return cells


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _choose_n_rows(n: int, rng: random.Random) -> int:
    """Pick a row count that keeps each row non-empty and visually balanced."""
    if n == 1:
        return 1
    # aim for 2-4 rows; never more words per row than a comfortable max
    max_rows = min(4, n)
    min_rows = max(1, math.ceil(n / 6))    # no row crammed with >6 words
    n_rows = rng.randint(min_rows, max_rows)
    return n_rows


def _distribute(n: int, k: int, rng: random.Random) -> list[int]:
    """Distribute n items into k buckets (each >= 1), randomly."""
    # Start with 1 per bucket, distribute the remainder randomly.
    buckets = [1] * k
    remainder = n - k
    for _ in range(remainder):
        buckets[rng.randrange(k)] += 1
    rng.shuffle(buckets)
    return buckets


def _random_cuts(total: float, n: int, rng: random.Random,
                 ratio_range: tuple[float, float]) -> list[float]:
    """Cut `total` into `n` segments with random but bounded proportions."""
    if n == 1:
        return [total]
    # Generate n random weights, then normalise.
    lo, hi = ratio_range
    # Use a wider weight range to get more size variety.
    weights = [rng.uniform(lo, hi) for _ in range(n)]
    s = sum(weights)
    return [total * w / s for w in weights]


# --------------------------------------------------------------------------- #
# Original free-form BSP (kept for reference / experimentation)
# --------------------------------------------------------------------------- #

def subdivide(
    width: float,
    height: float,
    n: int,
    rng: random.Random,
    ratio_range: tuple[float, float] = (0.35, 0.65),
    gutter: float = 0.0,
) -> list[Cell]:
    """Free-form BSP — dramatic size contrast but NO guaranteed reading order."""
    n = max(1, n)
    rects: list[list[float]] = [[-width / 2, -height / 2, width, height]]
    while len(rects) < n:
        i = max(range(len(rects)), key=lambda k: rects[k][2] * rects[k][3])
        x, y, w, h = rects.pop(i)
        ratio = rng.uniform(*ratio_range)
        if w >= h:
            w1 = w * ratio
            rects.append([x, y, w1, h])
            rects.append([x + w1, y, w - w1, h])
        else:
            h1 = h * ratio
            rects.append([x, y, w, h1])
            rects.append([x, y + h1, w, h - h1])
    return [
        Cell(cx=x + w / 2, cy=y + h / 2,
             w=max(0.0, w - 2 * gutter), h=max(0.0, h - 2 * gutter))
        for x, y, w, h in rects
    ]


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    W, H = 14.0, 8.0
    rng = random.Random(42)
    print("=== row_major ===")
    for n in (1, 2, 5, 7, 12):
        cells = row_major(W, H, n, rng, gutter=0.0)
        total = sum(c.w * c.h for c in cells)
        row_info = f"{len(cells)} cells, area≈{total:.1f}/{W*H:.0f}"
        coords = " | ".join(f"({c.cx:.1f},{c.cy:.1f}) {c.w:.1f}x{c.h:.1f}"
                            for c in cells)
        print(f"  n={n:>2}  {row_info}")
        print(f"        {coords}")
    print()
    print("=== subdivide (BSP, reference) ===")
    rng2 = random.Random(42)
    for n in (1, 2, 5, 7, 12):
        cells = subdivide(W, H, n, rng2)
        total = sum(c.area for c in cells)
        print(f"  n={n:>2}  cells={len(cells)}  area={total:.1f}/{W*H:.0f}")
