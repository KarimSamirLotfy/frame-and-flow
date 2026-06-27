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

from manim import Scene, Text, VGroup

from layout import (
    PosterBuilder,
    WeightedFlowPicker,
    WeightedSidePicker,
    fill_side,
    make_aspect_fn,
)
from song_data import Song

SONG_PATH = os.environ.get("HACKATUNE_SONG", "data/songs/song_666407.json")
SEED = int(os.environ.get("HACKATUNE_SEED", "7"))
END_TIME = float(os.environ.get("HACKATUNE_END", "0"))

ANCHOR_H = 2.2
DIM = "#3a3a44"
ACTIVE = "#ffffff"


class SongPoster(Scene):
    def construct(self) -> None:
        song = Song.load(SONG_PATH)
        end = END_TIME if END_TIME > 0 else song.duration
        rng = random.Random(SEED)

        # ---- anchor = first lyric line, horizontal ----------------------- #
        first = song.lyrics[0]
        anchor = Text(first.text, color=ACTIVE)
        anchor.scale(ANCHOR_H / anchor.height)
        anchor.move_to([0, 0, 0])

        # ---- build the rest around it ------------------------------------ #
        builder = PosterBuilder(
            fill=fill_side,
            aspect_of=make_aspect_fn(),
            side_picker=WeightedSidePicker(),
            flow_picker=WeightedFlowPicker(),
            color=DIM,
        )
        rest = [line.text.split() for line in song.lyrics[1:]]
        placed = builder.build(anchor, rest, rng)

        # ---- centre the whole composition at the origin ------------------ #
        whole = VGroup(anchor, *[p.block for p in placed])
        whole.move_to([0, 0, 0])

        self.add(whole)

        # ---- timed reveal (only when rendering video, not -s) ------------ #
        # anchor lights immediately; each line brightens at its start time.
        clock = 0.0

        def advance_to(t: float) -> None:
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                self.wait(dt)
                clock = t

        for line, p in zip(song.lyrics[1:], placed):
            if line.start >= end:
                break
            advance_to(line.start)
            p.block.set_color(ACTIVE)

        advance_to(min(end, song.duration))
        self.wait(1.0)
