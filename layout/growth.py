"""Growth engine: chain lyric lines into a build-up around a growing shape.

Responsibilities are split so each can change independently (SOLID):

  SidePicker (Strategy)  — decides the next Side. `WeightedSidePicker` is
      pseudo-random biased right/down; swap in another strategy (spiral, longest
      edge) without touching the builder (Open/Closed).

  FlowPicker (Strategy)  — decides the Flow per line (independent of the side).

  PlacedBlock            — a built block + the BBox it occupies once positioned.

  PosterBuilder          — owns the loop: for each line, ask the pickers for a
      side/flow, fill it, position it flush OUTSIDE the current bounding box on
      that side (provably overlap-free), and grow the bbox.

The builder depends on the `fill_side` callable and the pickers via interfaces,
not concretions — so rendering, sizing and strategy are all decoupled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Protocol

from manim import VGroup

from .geometry import BBox, Flow, Side

# fill_side signature: (words, side, flow, edge_len, color, aspect_of) -> VGroup
FillFn = Callable[..., VGroup]


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
class SidePicker(Protocol):
    def __call__(self, rng: random.Random) -> Side: ...


class FlowPicker(Protocol):
    def __call__(self, rng: random.Random) -> Flow: ...


@dataclass
class WeightedSidePicker:
    """Pseudo-random side, biased toward growing right and down."""

    weights: dict[Side, float] = field(default_factory=lambda: {
        Side.RIGHT: 0.40,
        Side.DOWN: 0.35,
        Side.LEFT: 0.15,
        Side.UP: 0.10,
    })

    def __call__(self, rng: random.Random) -> Side:
        sides = list(self.weights.keys())
        return rng.choices(sides, weights=[self.weights[s] for s in sides])[0]


@dataclass
class WeightedFlowPicker:
    """Pseudo-random flow; flow does not affect which edge is filled."""

    p_vertical: float = 0.5

    def __call__(self, rng: random.Random) -> Flow:
        return Flow.VERTICAL if rng.random() < self.p_vertical else Flow.HORIZONTAL


class FractionPicker(Protocol):
    def __call__(self, rng: random.Random) -> float: ...


@dataclass
class RangeFractionPicker:
    """Fraction of the edge a line fills, in [lo, hi].

    Filling < 1.0 makes the block SMALLER than the edge, which is what stops the
    exponential blowup: a small block grows the bbox only a little. The partial
    block packs along the edge (see SideSpans) so same-side blocks never overlap.
    """

    lo: float = 0.70
    hi: float = 1.00

    def __call__(self, rng: random.Random) -> float:
        return rng.uniform(self.lo, self.hi)


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #
@dataclass
class PlacedBlock:
    block: VGroup
    side: Side
    flow: Flow
    bbox: BBox
    fraction: float          # how much of the edge this line filled


class SideSpans:
    """Tracks how much of each side's outer edge is already consumed.

    Partial blocks pack from a side's START corner. `used[side]` is the length
    already taken along that side since it was last reset. When the bounding box
    GROWS on an axis, the perpendicular sides' edges lengthen, so we keep packing
    where we left off; we only reset a side's usage when the bbox edge it packs
    against shifts outward (a block was placed ON that side).
    """

    def __init__(self) -> None:
        self._used: dict[Side, float] = {s: 0.0 for s in Side}

    def used(self, side: Side) -> float:
        return self._used[side]

    def consume(self, side: Side, length: float) -> None:
        self._used[side] += length

    def reset(self, side: Side) -> None:
        self._used[side] = 0.0


class PosterBuilder:
    """Chains lines into a build-up. Pure orchestration; no Manim scene calls."""

    def __init__(
        self,
        fill: FillFn,
        aspect_of,
        side_picker: SidePicker,
        flow_picker: FlowPicker,
        fraction_picker: FractionPicker,
        full_fill_first: int = 1,
        attach_buff: float = 0.16,
        color: str = "#46464f",
    ) -> None:
        self._fill = fill
        self._aspect = aspect_of
        self._pick_side = side_picker
        self._pick_flow = flow_picker
        self._pick_fraction = fraction_picker
        # number of leading lines that always fill their side fully (line 2 = 1)
        self._full_fill_first = full_fill_first
        self._buff = attach_buff
        self._color = color

    def build(self, anchor: VGroup, lines: list[list[str]],
              rng: random.Random) -> list[PlacedBlock]:
        """Place each line around `anchor`. Returns the placed blocks in order."""
        bbox = _mobj_bbox(anchor)
        spans = SideSpans()
        placed: list[PlacedBlock] = []

        for idx, words in enumerate(lines):
            side = self._pick_side(rng)
            flow = self._pick_flow(rng)

            # First few lines fill fully; the rest fill a fraction (70-100%) so
            # the canvas grows roughly linearly instead of exponentially.
            full = idx < self._full_fill_first
            fraction = 1.0 if full else self._pick_fraction(rng)

            edge_len = bbox.edge_length(side)
            # A full-fill block resets the side and uses the whole edge; a
            # partial block fills `fraction` of the *remaining* free edge.
            if full:
                spans.reset(side)
                target = edge_len
                offset = 0.0
            else:
                free = max(0.0, edge_len - spans.used(side))
                if free < 0.15 * edge_len:        # side nearly full -> reset
                    spans.reset(side)
                    free = edge_len
                target = fraction * free
                offset = spans.used(side)

            block = self._fill(words, side, flow, target, self._color,
                               self._aspect)
            _attach_outside(block, bbox, side, self._buff, offset)

            along = block.height if side.is_vertical_edge else block.width
            spans.consume(side, along + self._buff)

            block_bbox = _mobj_bbox(block)
            bbox = bbox.union(block_bbox)
            placed.append(PlacedBlock(block, side, flow, block_bbox, fraction))

        return placed


# --------------------------------------------------------------------------- #
# Manim placement helpers (the only Manim-touching code here)
# --------------------------------------------------------------------------- #
def _mobj_bbox(mob) -> BBox:
    c = mob.get_center()
    w, h = mob.width, mob.height
    return BBox(c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2)


def _attach_outside(block: VGroup, bbox: BBox, side: Side, buff: float,
                    offset: float = 0.0) -> None:
    """Place `block` flush OUTSIDE `bbox` on `side`, packed from the start corner.

    `offset` is how far along the edge (from its start corner) the block begins,
    so partial blocks pack sequentially without overlap. Placing the block fully
    beyond the bbox edge guarantees it can't overlap the interior.

    Start corners per side (packing direction):
        RIGHT / LEFT  -> pack DOWNWARD from the top edge
        UP / DOWN     -> pack RIGHTWARD from the left edge
    """
    bw, bh = block.width, block.height
    if side is Side.RIGHT:
        x = bbox.x1 + buff + bw / 2
        y = bbox.y1 - offset - bh / 2        # from top, downward
        block.move_to([x, y, 0])
    elif side is Side.LEFT:
        x = bbox.x0 - buff - bw / 2
        y = bbox.y1 - offset - bh / 2        # from top, downward
        block.move_to([x, y, 0])
    elif side is Side.UP:
        x = bbox.x0 + offset + bw / 2        # from left, rightward
        y = bbox.y1 + buff + bh / 2
        block.move_to([x, y, 0])
    else:  # DOWN
        x = bbox.x0 + offset + bw / 2        # from left, rightward
        y = bbox.y0 - buff - bh / 2
        block.move_to([x, y, 0])
