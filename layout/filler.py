"""Turn one lyric line into a positioned Manim block filling one edge.

`fill_side` is the single entry point used by the growth engine for every line,
regardless of case (DRY): it picks the optimizer path from (side, flow), builds
the text mobjects with the right orientation and scaling, and arranges them so
the block fills the chosen edge. Positioning against the shape is the caller's
job (growth engine), keeping this focused on building one block.
"""

from __future__ import annotations

from manim import DOWN, PI, RIGHT, Text, VGroup

from .geometry import Flow, Side, is_parallel
from .optimizer import AspectFn, optimize_parallel, optimize_perpendicular

# rotation applied to each part for a given flow
_ROT = {Flow.HORIZONTAL: 0.0, Flow.VERTICAL: PI / 2}


def make_aspect_fn() -> AspectFn:
    """A Manim-backed aspect (w/h) measurer, cached per distinct string."""
    cache: dict[str, float] = {}

    def aspect_of(text: str) -> float:
        if text not in cache:
            t = Text(text)
            cache[text] = t.width / t.height if t.height > 0 else 1.0
        return cache[text]

    return aspect_of


def fill_side(words: list[str], side: Side, flow: Flow, edge_len: float,
              color: str, aspect_of: AspectFn) -> VGroup:
    """Build a VGroup that fills `side` (length `edge_len`) per (side, flow).

    PARALLEL: each part scaled so its along-edge extent == edge_len; tiled
              across the free axis.
    PERPENDICULAR: parts scaled to a shared band; stacked along the edge so the
              stack == edge_len; each extends freely outward.
    """
    rot = _ROT[flow]

    if is_parallel(side, flow):
        res = optimize_parallel(words, edge_len, aspect_of)
        mobjs = []
        for part in res.parts:
            t = Text(part, color=color)
            if rot:
                t.rotate(rot)
            # along-edge axis is height for a vertical edge, width for horizontal
            extent = t.height if side.is_vertical_edge else t.width
            if extent > 0:
                t.scale(edge_len / extent)
            mobjs.append(t)
        # tile across the FREE axis
        direction = RIGHT if side.is_vertical_edge else DOWN
        return VGroup(*mobjs).arrange(direction, buff=res.gap)

    # perpendicular
    res = optimize_perpendicular(words, edge_len, aspect_of)
    mobjs = []
    for part in res.parts:
        t = Text(part, color=color)
        if t.height > 0:
            t.scale(res.band / t.height)   # free-axis size == band (pre-rotation)
        if rot:
            t.rotate(rot)
        mobjs.append(t)
    # tile ALONG the edge
    direction = DOWN if side.is_vertical_edge else RIGHT
    return VGroup(*mobjs).arrange(direction, buff=res.gap)
