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


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #
@dataclass
class PlacedBlock:
    block: VGroup
    side: Side
    flow: Flow
    bbox: BBox


class PosterBuilder:
    """Chains lines into a build-up. Pure orchestration; no Manim scene calls."""

    def __init__(
        self,
        fill: FillFn,
        aspect_of,
        side_picker: SidePicker,
        flow_picker: FlowPicker,
        attach_buff: float = 0.16,
        color: str = "#46464f",
    ) -> None:
        self._fill = fill
        self._aspect = aspect_of
        self._pick_side = side_picker
        self._pick_flow = flow_picker
        self._buff = attach_buff
        self._color = color

    def build(self, anchor: VGroup, lines: list[list[str]],
              rng: random.Random) -> list[PlacedBlock]:
        """Place each line around `anchor`. Returns the placed blocks in order.

        The anchor must already be positioned; we read its bbox and grow from it.
        """
        bbox = _mobj_bbox(anchor)
        placed: list[PlacedBlock] = []

        for words in lines:
            side = self._pick_side(rng)
            flow = self._pick_flow(rng)
            edge_len = bbox.edge_length(side)

            block = self._fill(words, side, flow, edge_len, self._color,
                               self._aspect)
            _attach_outside(block, bbox, side, self._buff)

            block_bbox = _mobj_bbox(block)
            bbox = bbox.union(block_bbox)        # grow — next attaches outside
            placed.append(PlacedBlock(block, side, flow, block_bbox))

        return placed


# --------------------------------------------------------------------------- #
# Manim placement helpers (the only Manim-touching code here)
# --------------------------------------------------------------------------- #
def _mobj_bbox(mob) -> BBox:
    c = mob.get_center()
    w, h = mob.width, mob.height
    return BBox(c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2)


def _attach_outside(block: VGroup, bbox: BBox, side: Side, buff: float) -> None:
    """Place `block` flush OUTSIDE `bbox` on `side`, centred on that edge.

    Because the block is placed entirely beyond the bbox edge and spans (or is
    centred on) that full edge, it cannot overlap anything already inside.
    """
    bw, bh = block.width, block.height
    if side is Side.RIGHT:
        block.move_to([bbox.x1 + buff + bw / 2, bbox.cy, 0])
    elif side is Side.LEFT:
        block.move_to([bbox.x0 - buff - bw / 2, bbox.cy, 0])
    elif side is Side.UP:
        block.move_to([bbox.cx, bbox.y1 + buff + bh / 2, 0])
    else:  # DOWN
        block.move_to([bbox.cx, bbox.y0 - buff - bh / 2, 0])
