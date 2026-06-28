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


def _default_make_word(text: str, index: int, color: str) -> Text:
    return Text(text, color=color)


def _word_part(phrase: str, color: str, make_word, counter
               ) -> tuple[VGroup, list[Text]]:
    """Build a part as a row of INDIVIDUAL word mobjects (addressable per word).

    `make_word(text, global_index, color) -> Text` builds each word, so the
    caller can apply per-word styling (font/weight/slant/color). `counter` is a
    1-element list holding the running global word index across the whole line,
    so styles line up with the original word order even after wrapping.
    """
    word_strs = phrase.split()
    word_mobjs: list[Text] = []
    for w in word_strs:
        word_mobjs.append(make_word(w, counter[0], color))
        counter[0] += 1
    # space width ≈ a fraction of a word's height, for natural spacing
    space = word_mobjs[0].height * 0.32
    part = VGroup(*word_mobjs).arrange(RIGHT, buff=space, aligned_edge=DOWN)
    return part, word_mobjs


def fill_side(words: list[str], side: Side, flow: Flow, edge_len: float,
              color: str, aspect_of: AspectFn, make_word=None
              ) -> tuple[VGroup, list[Text]]:
    """Build a block filling `side` (length `edge_len`) per (side, flow).

    Each part is composed of INDIVIDUAL word mobjects so words can be revealed
    one at a time in sync with their timestamps. Returns (block, word_mobjs)
    where word_mobjs is the flat list of every word's mobject in reading order.

    `make_word(text, global_index, color) -> Text` lets the caller apply
    per-word styling; styling is baked in BEFORE measurement so the fit/zoom
    math sees the true styled glyph sizes. Defaults to a plain Text.

    PARALLEL: each part scaled so its along-edge extent == edge_len; tiled
              across the free axis.
    PERPENDICULAR: parts scaled to a shared band; stacked along the edge so the
              stack == edge_len; each extends freely outward.
    """
    if make_word is None:
        make_word = _default_make_word
    rot = _ROT[flow]
    word_mobjs: list[Text] = []
    counter = [0]   # running global word index across the whole line

    if is_parallel(side, flow):
        res = optimize_parallel(words, edge_len, aspect_of)
        parts = []
        for phrase in res.parts:
            part, pwords = _word_part(phrase, color, make_word, counter)
            if rot:
                part.rotate(rot)
            extent = part.height if side.is_vertical_edge else part.width
            if extent > 0:
                part.scale(edge_len / extent)
            parts.append(part)
            word_mobjs.extend(pwords)
        direction = RIGHT if side.is_vertical_edge else DOWN
        block = VGroup(*parts).arrange(direction, buff=res.gap)
        return block, word_mobjs

    # perpendicular
    res = optimize_perpendicular(words, edge_len, aspect_of)
    parts = []
    for phrase in res.parts:
        part, pwords = _word_part(phrase, color, make_word, counter)
        if part.height > 0:
            part.scale(res.band / part.height)   # free-axis == band (pre-rotate)
        if rot:
            part.rotate(rot)
        parts.append(part)
        word_mobjs.extend(pwords)
    direction = DOWN if side.is_vertical_edge else RIGHT
    block = VGroup(*parts).arrange(direction, buff=res.gap)
    return block, word_mobjs
