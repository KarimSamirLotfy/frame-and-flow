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


@dataclass
class Shelf:
    """An open packing shelf along one side.

    `outer`    fixed coordinate of the side's outer edge (x for L/R, y for U/D),
               captured when the shelf opened — every block on the shelf shares
               this edge line instead of marching outward as the bbox grows.
    `start`    fixed start-corner coordinate ALONG the edge (top for L/R, left
               for U/D), so packing offsets stay anchored even as the bbox grows.
    `edge_len` the edge length when the shelf opened (target fractions use this,
               so all blocks on the shelf size against the same edge).
    `offset`   distance already packed along the edge from `start`.
    """

    outer: float
    start: float
    edge_len: float
    offset: float = 0.0


class ShelfBook:
    """Per-side open shelves. A shelf opens on first use and reopens when full."""

    def __init__(self) -> None:
        self._shelves: dict[Side, Shelf | None] = {s: None for s in Side}

    def get(self, side: Side) -> Shelf | None:
        return self._shelves[side]

    def open(self, side: Side, outer: float, start: float,
             edge_len: float) -> Shelf:
        shelf = Shelf(outer=outer, start=start, edge_len=edge_len)
        self._shelves[side] = shelf
        return shelf


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
        book = ShelfBook()
        placed: list[PlacedBlock] = []

        for idx, words in enumerate(lines):
            side = self._pick_side(rng)
            flow = self._pick_flow(rng)

            full = idx < self._full_fill_first
            fraction = 1.0 if full else self._pick_fraction(rng)

            # Find or open the shelf for this side. A shelf shares ONE fixed
            # outer edge + start corner + edge_len so same-side blocks pack ALONG
            # it (perpendicular to the growth axis), each sized against the same
            # edge. We reopen only on a full-fill or when the shelf is full.
            shelf = book.get(side)
            need_target = fraction * bbox.edge_length(side)
            if full or shelf is None or shelf.offset + need_target > \
                    shelf.edge_len + 1e-6:
                shelf = book.open(
                    side,
                    outer=_outer_coord(bbox, side),
                    start=_start_coord(bbox, side),
                    edge_len=bbox.edge_length(side),
                )

            # Fraction is OF THE SHELF'S EDGE, packed from its start corner.
            target = shelf.edge_len if full else fraction * shelf.edge_len

            block = self._fill(words, side, flow, target, self._color,
                               self._aspect)
            _place_on_shelf(block, side, shelf, self._buff)

            along = block.height if side.is_vertical_edge else block.width
            shelf.offset += along + self._buff

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


def _outer_coord(bbox: BBox, side: Side) -> float:
    """The coordinate of `side`'s outer edge (x for L/R, y for U/D)."""
    return {
        Side.RIGHT: bbox.x1, Side.LEFT: bbox.x0,
        Side.UP: bbox.y1, Side.DOWN: bbox.y0,
    }[side]


def _start_coord(bbox: BBox, side: Side) -> float:
    """Start-corner coordinate ALONG the edge: top for L/R, left for U/D."""
    return bbox.y1 if side.is_vertical_edge else bbox.x0


def _place_on_shelf(block: VGroup, side: Side, shelf, buff: float) -> None:
    """Place `block` on `side`'s shelf: fixed outer edge, packed along from start.

    All coordinates come from the SHELF (captured when it opened), so same-side
    blocks share one outer edge line and one start corner — they pack ALONG the
    edge (perpendicular to the growth axis) without marching outward. Packing:
        RIGHT / LEFT  -> downward from the top corner
        UP   / DOWN   -> rightward from the left corner
    """
    bw, bh = block.width, block.height
    off = shelf.offset
    if side is Side.RIGHT:
        block.move_to([shelf.outer + buff + bw / 2, shelf.start - off - bh / 2, 0])
    elif side is Side.LEFT:
        block.move_to([shelf.outer - buff - bw / 2, shelf.start - off - bh / 2, 0])
    elif side is Side.UP:
        block.move_to([shelf.start + off + bw / 2, shelf.outer + buff + bh / 2, 0])
    else:  # DOWN
        block.move_to([shelf.start + off + bw / 2, shelf.outer - buff - bh / 2, 0])
