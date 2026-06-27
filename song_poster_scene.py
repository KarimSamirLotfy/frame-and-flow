"""Render the whole song as one build-up canvas (test view, no camera yet).

Every lyric line is chained onto the growing shape via the `layout` engine:
sides are pseudo-random (biased right/down), flow is pseudo-random per line.
This is a static test of how the full song lays out; camera framing comes later.

Render:
    uv run manim -ql -s song_poster_scene.py SongPoster        # single frame
    uv run manim -ql   song_poster_scene.py SongPoster         # timed reveal

Env:
    HACKATUNE_SONG   song JSON     (default data/songs/song_666407.json)
    HACKATUNE_SEED   RNG seed      (default 7)
    HACKATUNE_END    stop after N lyric seconds; 0 = full song (default 0)
"""

from __future__ import annotations

import os
import random

from manim import DOWN, RIGHT, Rectangle, Scene, Text, VGroup

from layout import (
    PosterBuilder,
    RangeFractionPicker,
    Side,
    WeightedFlowPicker,
    fill_side,
    make_aspect_fn,
)
from song_data import Song

SONG_PATH = os.environ.get("HACKATUNE_SONG", "data/songs/song_666407.json")
SEED = int(os.environ.get("HACKATUNE_SEED", "7"))
END_TIME = float(os.environ.get("HACKATUNE_END", "0"))
# how many lyric lines to lay out (anchor + this many). 0 = whole song.
N_LINES = int(os.environ.get("HACKATUNE_NLINES", "6"))
SHOW_DEBUG = os.environ.get("HACKATUNE_DEBUG", "0") == "1"

ANCHOR_H = 2.2
DIM = "#3a3a44"
ACTIVE = "#ffffff"
ANCHOR_BOX = "#ff4488"
# per-side outline colors for debug
SIDE_COLOR = {
    Side.RIGHT: "#44aaff",
    Side.DOWN: "#44ff88",
    Side.LEFT: "#ffaa44",
    Side.UP: "#cc66ff",
}


class SongPoster(Scene):
    def construct(self) -> None:
        song = Song.load(SONG_PATH)
        end = END_TIME if END_TIME > 0 else song.duration
        rng = random.Random(SEED)

        # ---- anchor = first lyric line, horizontal (per-word) ------------ #
        first = song.lyrics[0]
        anchor_words = [Text(w.text, color=ACTIVE) for w in first.words]
        space = anchor_words[0].height * 0.32
        anchor = VGroup(*anchor_words).arrange(RIGHT, buff=space, aligned_edge=DOWN)
        anchor.scale(ANCHOR_H / anchor.height)
        anchor.move_to([0, 0, 0])

        # ---- build the rest around it ------------------------------------ #
        builder = PosterBuilder(
            fill=fill_side,
            aspect_of=make_aspect_fn(),
            flow_picker=WeightedFlowPicker(),
            fraction_picker=RangeFractionPicker(0.70, 1.00),
            color=DIM,
        )
        upto = len(song.lyrics) if N_LINES <= 0 else min(N_LINES, len(song.lyrics))
        rest = [line.text.split() for line in song.lyrics[1:upto]]
        placed = builder.build(anchor, rest, rng)

        # ---- centre the whole composition (positions are final now) ------ #
        # We compute the full layout up front so geometry is fixed, but reveal
        # each block over time. Colour everything ACTIVE: it pops in bright.
        whole = VGroup(anchor, *[p.block for p in placed])
        whole.move_to([0, 0, 0])
        for p in placed:
            p.block.set_color(ACTIVE)

        # ---- timed build-up ---------------------------------------------- #
        # The anchor (line 0) is shown at line 0's start; every other line's
        # block pops in bright exactly at its own start time, and stays.
        clock = 0.0

        def advance_to(t: float) -> None:
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                self.wait(dt)
                clock = t

        # Words pop in INDIVIDUALLY at their own timestamps (karaoke build-up).
        # Anchor first:
        self._reveal_words(first, anchor_words, end, advance_to)
        if SHOW_DEBUG:
            self._outline(anchor, ANCHOR_BOX)

        # Then every other line, word by word, in its block:
        for line, p in zip(song.lyrics[1:upto], placed):
            if line.start >= end:
                break
            self._reveal_words(line, p.word_mobjs, end, advance_to)
            if SHOW_DEBUG:
                self._outline(p.block, SIDE_COLOR[p.side])

        advance_to(min(end, song.duration))
        self.wait(1.0)

    # ------------------------------------------------------------------- #
    def _reveal_words(self, line, word_mobjs, end, advance_to) -> None:
        """Add each word's mobject at the word's start time (per-word build-up).

        `line.words` carries per-word start times; `word_mobjs` is the matching
        list in reading order. If counts differ (rare wrap edge case), we fall
        back to spreading words evenly across the line's span.
        """
        words = line.words
        n = min(len(words), len(word_mobjs))
        for i in range(n):
            t = words[i].start
            if t >= end:
                break
            advance_to(t)
            self.add(word_mobjs[i])
        # add any leftover mobjs (count mismatch) at the line end, so nothing
        # is silently dropped
        for j in range(n, len(word_mobjs)):
            self.add(word_mobjs[j])

    # ------------------------------------------------------------------- #
    def _outline(self, mob, color: str) -> None:
        """Outline a mobject's bounding box (call AFTER all transforms)."""
        b = Rectangle(width=max(mob.width, 0.01), height=max(mob.height, 0.01))
        b.set_stroke(color, width=1.5, opacity=0.8).set_fill(opacity=0)
        b.move_to(mob.get_center())
        self.add(b)
