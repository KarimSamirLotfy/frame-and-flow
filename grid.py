"""Random rectangular grid subdivision (Manim-agnostic geometry).

Splits a rectangle into `n` sub-rectangles of varied sizes using binary space
partitioning: repeatedly take the largest rectangle and split it along its
longer side at a random ratio. This guarantees:

  * exactly `n` cells (for any n >= 1),
  * a perfect tiling (no gaps, no overlaps),
  * varied sizes without thin slivers (we always split the longer side).

Coordinates are returned in Manim's convention: origin at the center, +x right,
+y up. Each `Cell` carries its center (cx, cy) and size (w, h).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Cell:
    cx: float  # center x
    cy: float  # center y
    w: float   # width
    h: float   # height

    @property
    def area(self) -> float:
        return self.w * self.h


def subdivide(
    width: float,
    height: float,
    n: int,
    rng: random.Random,
    ratio_range: tuple[float, float] = (0.35, 0.65),
    gutter: float = 0.0,
) -> list[Cell]:
    """Split a `width` x `height` rectangle (centered on origin) into `n` cells.

    Args:
        width, height: size of the whole area.
        n: number of cells to produce (>= 1).
        rng: seeded random source (for reproducibility).
        ratio_range: where along the longer side a split may fall.
        gutter: shrink every cell by this much on each side (visual spacing).
    """
    n = max(1, n)

    # Rectangles stored as [x, y, w, h] with (x, y) = bottom-left corner.
    rects: list[list[float]] = [[-width / 2, -height / 2, width, height]]

    while len(rects) < n:
        # Always split the current largest rectangle -> keeps sizes balanced.
        i = max(range(len(rects)), key=lambda k: rects[k][2] * rects[k][3])
        x, y, w, h = rects.pop(i)
        ratio = rng.uniform(*ratio_range)

        if w >= h:  # split along x (vertical cut)
            w1 = w * ratio
            rects.append([x, y, w1, h])
            rects.append([x + w1, y, w - w1, h])
        else:       # split along y (horizontal cut)
            h1 = h * ratio
            rects.append([x, y, w, h1])
            rects.append([x, y + h1, w, h - h1])

    cells = []
    for x, y, w, h in rects:
        cells.append(
            Cell(
                cx=x + w / 2,
                cy=y + h / 2,
                w=max(0.0, w - 2 * gutter),
                h=max(0.0, h - 2 * gutter),
            )
        )
    return cells


if __name__ == "__main__":
    # Sanity check: exact count + perfect tiling (areas sum to the whole).
    W, H = 14.0, 8.0
    rng = random.Random(42)
    for n in (1, 2, 5, 7, 12):
        cells = subdivide(W, H, n, rng)
        total = sum(c.area for c in cells)
        sizes = ", ".join(f"{c.w:.1f}x{c.h:.1f}" for c in cells)
        print(f"n={n:>2}  cells={len(cells):>2}  area={total:5.1f}/{W*H:.0f}  [{sizes}]")
