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

import numpy as np
from manim import (
    DOWN,
    ORIGIN,
    PI,
    RIGHT,
    MovingCameraScene,
    Rectangle,
    Text,
    ValueTracker,
    VGroup,
    smooth,
)

from layout import (
    Flow,
    PosterBuilder,
    RangeFractionPicker,
    Side,
    WeightedFlowPicker,
    WORD_ANIM_STYLES,
    fill_side,
    make_aspect_fn,
)
from song_data import Song
from style import Stylist, WordStyle, word_metrics

SONG_PATH = os.environ.get("HACKATUNE_SONG", "data/songs/song_666407.json")
SEED = int(os.environ.get("HACKATUNE_SEED", "7"))
# render window: only emit frames for [START_TIME, END_TIME]. Before START_TIME
# the build-up is fast-forwarded (state applied instantly, no frames) so you can
# preview just a slice (e.g. the last 30s) without waiting for the whole render.
START_TIME = float(os.environ.get("HACKATUNE_START", "0"))
END_TIME = float(os.environ.get("HACKATUNE_END", "0"))
# how many lyric lines to lay out (anchor + this many). 0 = whole song (default).
N_LINES = int(os.environ.get("HACKATUNE_NLINES", "0"))
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
# Readability-first: we zoom so the line's TEXT renders at a target pixel size
# (typography rule: 1080p body kinetic text ~48-64px, never below ~36px), rather
# than sizing the frame to contain the whole block. Wide lines may then extend
# past the frame edges — that's the accepted trade for legibility.
TARGET_GLYPH_PX = 90     # desired on-screen glyph height at 1080p
MIN_GLYPH_PX = 48        # never let text be smaller than this
CAM_PAD = 0.18           # small breathing room when the block is the limiter
RENDER_H_PX = 1080       # reference render height the px targets assume

# Word entrance animation (see layout/animations.py STYLES)
WORD_ANIM = os.environ.get("HACKATUNE_WORDANIM", "slide")  # "slide" | "pop"
WORD_ANIM_RT = float(os.environ.get("HACKATUNE_WORDANIM_RT", "0.28"))
CAM_MAX_GLIDE = 1.1  # longest a single camera glide takes (seconds)
CAM_MIN_GLIDE = 0.35 # shortest glide, so motion always reads as eased


class SongPoster(MovingCameraScene):
    def construct(self) -> None:
        song = Song.load(SONG_PATH)
        end = END_TIME if END_TIME > 0 else song.duration
        rng = random.Random(SEED)

        # ---- emotion -> per-word typographic styles ---------------------- #
        # Computed across the whole song (word order), then split per line so
        # each line gets a make_word factory. Styling is baked in BEFORE the
        # layout measures glyphs, so fit/zoom math sees the true styled sizes.
        stylist = Stylist()
        all_metrics = word_metrics(song)
        styles_flat = [stylist.style_for(wm) for wm in all_metrics]
        per_line_styles: list[list[WordStyle]] = []
        idx = 0
        for line in song.lyrics:
            k = len(line.words)
            per_line_styles.append(styles_flat[idx:idx + k])
            idx += k

        def make_word_factory(styles: list[WordStyle]):
            def make_word(text: str, i: int, _color: str) -> Text:
                s = styles[i] if i < len(styles) else WordStyle()
                return Text(text, font=s.font, weight=s.weight,
                            slant=s.slant, color=s.color)
            return make_word

        # ---- anchor = first lyric line, horizontal (per-word, styled) ---- #
        first = song.lyrics[0]
        anchor_make = make_word_factory(per_line_styles[0])
        anchor_words = [anchor_make(w.text, i, ACTIVE)
                        for i, w in enumerate(first.words)]
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
        rest_makers = [make_word_factory(per_line_styles[i])
                       for i in range(1, upto)]
        placed = builder.build(anchor, rest, rng, make_words=rest_makers)

        # ---- centre the whole composition (positions are final now) ------ #
        # We compute the full layout up front so geometry is fixed, but reveal
        # each WORD over time. `whole` is added to the scene ONCE so its rotation
        # updater works; every word starts INVISIBLE (opacity 0) and is revealed
        # by setting opacity to 1 at its timestamp — so words don't all show at
        # once, and rotating `whole` doesn't force-add unrevealed words.
        whole = VGroup(anchor, *[p.block for p in placed])
        whole.move_to([0, 0, 0])
        all_words = list(anchor_words)
        for p in placed:
            p.block.set_color(ACTIVE)
            all_words.extend(p.word_mobjs)
        for wmob in all_words:
            wmob.set_opacity(0.0)
        self.add(whole)

        # ---- timed build-up with moving camera --------------------------- #
        # Per line: glide the camera to frame the whole line (eased), then pop in
        # its words at their timestamps. The camera glide consumes real timeline
        # time, tracked by the clock so word reveals stay in sync.
        clock = 0.0

        def rendering() -> bool:
            return clock >= START_TIME

        def advance_to(t: float) -> None:
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                if rendering():
                    self.wait(dt)        # real time, emits frames
                # else: fast-forward, just advance the clock (no frames)
                clock = t

        def bump(dt: float) -> None:
            """Advance the clock by `dt` already consumed by a self.play()."""
            nonlocal clock
            clock += dt

        # Camera can't rotate in v0.20.1, so we ROTATE THE WORLD instead: spin
        # `whole` so the target line becomes horizontal, then pan/zoom to it.
        # `world_angle` is the current accumulated rotation of the composition.
        world_angle = 0.0

        def glide_to(target, word_mobjs, target_text_angle: float,
                     line_start: float) -> None:
            """Rotate world so the line is upright + pan/zoom to it (eased).

            IMPORTANT: we must NOT do `whole.animate.rotate(...)` — animating the
            big group forces Manim to add ALL its members (every unrevealed word)
            to the scene at once. Instead we rotate `whole` via a ValueTracker +
            updater: the group's geometry (and thus its already-added word
            children) rotates, while unrevealed words stay off-screen.
            """
            nonlocal clock, world_angle
            delta = -(target_text_angle + world_angle)
            new_world_angle = world_angle + delta

            lead = max(0.0, line_start - clock)
            run = min(run_glide(lead), lead) if lead > 1e-3 else CAM_MIN_GLIDE
            run = max(run, 1e-2)

            cx, cy, w, _ = self._frame_for_rotated(target, word_mobjs, delta)

            if not rendering():
                # fast-forward: apply the END state of the glide instantly.
                if abs(delta) > 1e-4:
                    whole.rotate(delta, about_point=ORIGIN)
                self.camera.frame.move_to([cx, cy, 0]).set(width=w)
                clock += run
                world_angle = new_world_angle
                return

            if abs(delta) > 1e-4:
                # incremental rotation driven by a tracker (no group add)
                tracker = ValueTracker(0.0)
                applied = {"a": 0.0}

                def _rot(_m):
                    step = tracker.get_value() - applied["a"]
                    if abs(step) > 1e-9:
                        whole.rotate(step, about_point=ORIGIN)
                        applied["a"] = tracker.get_value()

                whole.add_updater(_rot)
                self.play(
                    tracker.animate.set_value(delta),
                    self.camera.frame.animate.move_to([cx, cy, 0]).set(width=w),
                    run_time=run, rate_func=smooth,
                )
                whole.remove_updater(_rot)
            else:
                self.play(
                    self.camera.frame.animate.move_to([cx, cy, 0]).set(width=w),
                    run_time=run, rate_func=smooth,
                )
            clock += run
            world_angle = new_world_angle

        def run_glide(lead: float) -> float:
            return min(CAM_MAX_GLIDE, max(CAM_MIN_GLIDE, lead))

        # Start framed on the anchor (always horizontal), then reveal it.
        cx, cy, w, _ = self._frame_for(anchor, anchor_words)
        self.camera.frame.move_to([cx, cy, 0]).set(width=w)
        advance_to(first.start)
        # anchor has no aligned edge; slide it up from below (Side.DOWN), no spin
        self._reveal_words(first, anchor_words, Side.DOWN, 0.0, end,
                           advance_to, rendering, bump)
        if SHOW_DEBUG:
            self._outline(anchor, ANCHOR_BOX)

        # Then every other line: rotate-world + glide to it, then reveal words.
        for line, p in zip(song.lyrics[1:upto], placed):
            if line.start >= end:
                break
            text_angle = (PI / 2) if p.flow is Flow.VERTICAL else 0.0
            glide_to(p.block, p.word_mobjs, text_angle, line.start)
            advance_to(line.start)
            # use the LIVE accumulated world rotation so slide offsets are
            # correct on screen (the world is spun to keep this line upright).
            self._reveal_words(line, p.word_mobjs, p.side, world_angle, end,
                               advance_to, rendering, bump)
            if SHOW_DEBUG:
                self._outline(p.block, SIDE_COLOR[p.side])

        advance_to(min(end, song.duration))
        self.wait(1.0)

    # ------------------------------------------------------------------- #
    def _reveal_words(self, line, word_mobjs, side, world_angle, end,
                      advance_to, rendering, bump) -> None:
        """Animate each word in at its start time (per-word build-up).

        Each word's entrance STARTS on its timestamp (slide begins at word.start
        and settles ~WORD_ANIM_RT later). The play consumes run_time, which the
        caller's clock accounts for via `advance_to`. While fast-forwarding
        (before the render window), entrances are applied instantly.
        """
        style = WORD_ANIM_STYLES.get(WORD_ANIM, WORD_ANIM_STYLES["pop"])
        words = line.words
        n = min(len(words), len(word_mobjs))

        for i in range(n):
            t = words[i].start
            if t >= end:
                break
            advance_to(t)                       # reach this word's beat
            wmob = word_mobjs[i]
            if not rendering():
                wmob.set_opacity(1.0)           # fast-forward: instant
                continue
            anim = style.build(wmob, side, world_angle, WORD_ANIM_RT)
            self.play(anim)                     # starts on the beat, eases in
            bump(WORD_ANIM_RT)                  # clock += time the play consumed

        for j in range(n, len(word_mobjs)):     # leftovers (count mismatch)
            word_mobjs[j].set_opacity(1.0)

    # ------------------------------------------------------------------- #
    @staticmethod
    def _glyph_h(word_mobjs) -> float:
        """A representative glyph height (world units): the tallest word.

        Tallest, not first, so the readability target is met by every word in
        the line (the biggest word is the limiter once we hit a px target).
        """
        if not word_mobjs:
            return 0.5
        # word mobjs may be rotated; their on-screen text height is min(w, h)
        return max(min(w.width, w.height) for w in word_mobjs) or 0.5

    def _frame_for(self, mob, word_mobjs) -> tuple[float, float, float, float]:
        """Frame `mob` so its glyphs hit the target px size (readability-first)."""
        return self._frame_dims(mob.width, mob.height,
                                self._glyph_h(word_mobjs), mob.get_center())

    def _frame_for_rotated(self, mob, word_mobjs, delta: float
                           ) -> tuple[float, float, float, float]:
        """Frame `mob` after the world rotates by `delta`, readability-first."""
        c = mob.get_center()
        cos, sin = np.cos(delta), np.sin(delta)
        rx = c[0] * cos - c[1] * sin
        ry = c[0] * sin + c[1] * cos
        w_axis = max(mob.width, mob.height)   # long (reading) axis after upright
        h_axis = min(mob.width, mob.height)
        return self._frame_dims(w_axis, h_axis,
                                self._glyph_h(word_mobjs), [rx, ry, 0])

    def _frame_dims(self, content_w: float, content_h: float,
                    glyph_h: float, center
                    ) -> tuple[float, float, float, float]:
        aspect = self.camera.frame.width / self.camera.frame.height

        # --- readability target: pick frame width so glyphs hit TARGET_GLYPH_PX
        # px = glyph_world_h * (RENDER_H_PX / frame_height_world)
        #    = glyph_world_h * RENDER_H_PX * aspect / frame_width
        # => frame_width = glyph_world_h * RENDER_H_PX * aspect / target_px
        def width_for_px(px: float) -> float:
            if glyph_h <= 0 or px <= 0:
                return 1.0
            return glyph_h * RENDER_H_PX * aspect / px

        w_target = width_for_px(TARGET_GLYPH_PX)   # the size we'd LIKE
        w_floor = width_for_px(MIN_GLYPH_PX)        # the largest frame still legible

        # --- containment: the frame the whole block would need (with padding)
        need_w = content_w * (1 + CAM_PAD)
        need_h = content_h * (1 + CAM_PAD)
        w_contain = max(need_w, need_h * aspect)

        # Prefer to contain the block, but NEVER zoom out past the legibility
        # floor: if containing the block would shrink text below MIN_GLYPH_PX,
        # cap at w_floor (long lines then run off-frame, but stay readable).
        # Also don't zoom in tighter than the nice target.
        w = min(max(w_contain, w_target), w_floor) if w_floor >= w_target \
            else w_target
        h = w / aspect
        return center[0], center[1], w, h

    # ------------------------------------------------------------------- #
    def _outline(self, mob, color: str) -> None:
        """Outline a mobject's bounding box (call AFTER all transforms)."""
        b = Rectangle(width=max(mob.width, 0.01), height=max(mob.height, 0.01))
        b.set_stroke(color, width=1.5, opacity=0.8).set_fill(opacity=0)
        b.move_to(mob.get_center())
        self.add(b)
