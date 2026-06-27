"""Render the whole song as a build-up canvas with a moving camera.

Every lyric line is chained onto a growing shape via the `layout` engine (edge
tree). Words pop in at their per-word timestamps, and the CAMERA glides+zooms to
frame the whole current lyric line as it is sung, with eased (non-linear) motion.

Render:
    uv run manim -ql   song_poster_scene.py SongPoster         # the video
    uv run manim -ql -s song_poster_scene.py SongPoster        # final frame

Env:
    HACKATUNE_SONG   song JSON     (default data/songs/song_666407.json)
    HACKATUNE_SEED   RNG seed      (default 7)
    HACKATUNE_END    stop after N lyric seconds; 0 = full song (default 0)
    HACKATUNE_NLINES lines to lay out; 0 = whole song          (default 0)
    HACKATUNE_DEBUG  1 = draw block outlines                   (default 0)
"""

from __future__ import annotations

import os
import random

from manim import (
    DOWN,
    RIGHT,
    MovingCameraScene,
    Rectangle,
    Text,
    VGroup,
    smooth,
)

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

# Camera framing
CAM_MARGIN = 1.6      # extra world-units of padding around the framed line
CAM_MIN_W = 6.0      # don't zoom in tighter than this frame width (tiny lines)
CAM_MAX_GLIDE = 1.1  # longest a single camera glide takes (seconds)
CAM_MIN_GLIDE = 0.35 # shortest glide, so motion always reads as eased


class SongPoster(MovingCameraScene):
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

        # ---- timed build-up with moving camera --------------------------- #
        # Per line: glide the camera to frame the whole line (eased), then pop in
        # its words at their timestamps. The camera glide consumes real timeline
        # time, tracked by the clock so word reveals stay in sync.
        clock = 0.0

        def advance_to(t: float) -> None:
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                self.wait(dt)
                clock = t

        def glide_to(target, line_start: float) -> None:
            """Ease the camera to frame `target`; consumes up to the line's lead."""
            nonlocal clock
            cx, cy, w, h = self._frame_for(target)
            lead = max(0.0, line_start - clock)         # time available before words
            run = min(CAM_MAX_GLIDE, max(CAM_MIN_GLIDE, lead))
            # don't overshoot the line start; if no lead, do a quick eased move
            run = min(run, lead) if lead > 1e-3 else CAM_MIN_GLIDE
            self.play(
                self.camera.frame.animate.move_to([cx, cy, 0]).set(width=w),
                run_time=max(run, 1e-2), rate_func=smooth,
            )
            clock += run

        # Start framed on the anchor, then reveal it.
        cx, cy, w, h = self._frame_for(anchor)
        self.camera.frame.move_to([cx, cy, 0]).set(width=w)
        advance_to(first.start)
        self._reveal_words(first, anchor_words, end, advance_to)
        if SHOW_DEBUG:
            self._outline(anchor, ANCHOR_BOX)

        # Then every other line: glide to it, then reveal its words.
        for line, p in zip(song.lyrics[1:upto], placed):
            if line.start >= end:
                break
            glide_to(p.block, line.start)
            advance_to(line.start)
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
    def _frame_for(self, mob) -> tuple[float, float, float, float]:
        """Camera (cx, cy, width, height) that frames `mob` with margin.

        Respects the frame's aspect ratio (so the line fits on BOTH axes) and a
        minimum width so tiny lines don't zoom in absurdly far.
        """
        aspect = self.camera.frame.width / self.camera.frame.height
        need_w = mob.width + 2 * CAM_MARGIN
        need_h = mob.height + 2 * CAM_MARGIN
        # width must cover both the horizontal need and the height*aspect need
        w = max(need_w, need_h * aspect, CAM_MIN_W)
        h = w / aspect
        c = mob.get_center()
        return c[0], c[1], w, h

    # ------------------------------------------------------------------- #
    def _outline(self, mob, color: str) -> None:
        """Outline a mobject's bounding box (call AFTER all transforms)."""
        b = Rectangle(width=max(mob.width, 0.01), height=max(mob.height, 0.01))
        b.set_stroke(color, width=1.5, opacity=0.8).set_fill(opacity=0)
        b.move_to(mob.get_center())
        self.add(b)
