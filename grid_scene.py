"""Manim scene: random-grid dynamic typography synced to lyrics.

For each lyric line we carve the screen into a random mosaic of rectangles
(one cell per word, via `grid.subdivide`), drop each word into its cell, show
them all dim, then light each word up at its real timestamp. A fresh random
layout is generated per line.

Render (fast preview):
    uv run manim -pql grid_scene.py GridScene

Show rectangle outlines for debugging:
    HACKATUNE_DEBUG=1 uv run manim -pql grid_scene.py GridScene

Config via env vars (all optional):
    HACKATUNE_SONG    path to song JSON   (default: data/songs/song_666407.json)
    HACKATUNE_END     stop after N seconds; 0 = full song   (default: 35)
    HACKATUNE_DEBUG   1 = draw cell outlines                (default: 0)
    HACKATUNE_SEED    base RNG seed                         (default: 7)
"""

from __future__ import annotations

import os
import random

from manim import Rectangle, Scene, Text, VGroup, config

from grid import row_major
from song_data import LyricLine, Song

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
SONG_PATH = os.environ.get("HACKATUNE_SONG", "data/songs/song_666407.json")
END_TIME = float(os.environ.get("HACKATUNE_END", "35"))
SHOW_GRID = os.environ.get("HACKATUNE_DEBUG", "0") == "1"
SEED = int(os.environ.get("HACKATUNE_SEED", "7"))

# Colors
DIM = "#46464f"      # unsung words
ACTIVE = "#ffffff"   # word currently/just sung
GRID_COLOR = "#ff4488"  # debug rectangle outlines

# Layout
AREA_W_FRAC = 0.94   # fraction of frame width used by the grid
AREA_H_FRAC = 0.92   # fraction of frame height used by the grid
GUTTER = 0.08        # spacing baked into each cell
CELL_PAD = 0.82      # text fills this fraction of its cell
DIM_OPACITY = 0.22
BASE_FONT = 72       # starting font size before fit-scaling


class GridScene(Scene):
    def construct(self) -> None:
        song = Song.load(SONG_PATH)
        end = END_TIME if END_TIME > 0 else song.duration

        area_w = config.frame_width * AREA_W_FRAC
        area_h = config.frame_height * AREA_H_FRAC

        clock = 0.0

        def advance_to(t: float) -> None:
            """Wait until scene time reaches `t` seconds (never goes backwards)."""
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                self.wait(dt)
                clock = t

        for i, line in enumerate(song.lyrics):
            if line.start >= end:
                break
            if not line.words:
                continue

            advance_to(line.start)

            layout, word_mobjs = self._build_grid(line, area_w, area_h, seed=SEED + i)
            self.add(layout)

            for word, wm in zip(line.words, word_mobjs):
                if word.start >= end:
                    break
                advance_to(word.start)
                wm.set_color(ACTIVE).set_opacity(1.0)

            advance_to(min(line.end, end))
            self.remove(layout)

        self.wait(0.5)

    # ----------------------------------------------------------------------- #
    def _build_grid(
        self, line: LyricLine, area_w: float, area_h: float, seed: int
    ) -> tuple[VGroup, list[Text]]:
        """Build a random mosaic for one line: one word per cell, all dim."""
        rng = random.Random(seed)
        cells = row_major(area_w, area_h, len(line.words), rng, gutter=GUTTER)

        layout = VGroup()
        word_mobjs: list[Text] = []

        for word, cell in zip(line.words, cells):
            if SHOW_GRID:
                rect = Rectangle(width=cell.w, height=cell.h)
                rect.set_stroke(GRID_COLOR, width=1.5, opacity=0.6)
                rect.set_fill(opacity=0)
                rect.move_to([cell.cx, cell.cy, 0])
                layout.add(rect)

            t = Text(word.text, font_size=BASE_FONT, color=DIM)
            t.set_opacity(DIM_OPACITY)
            self._fit_into_cell(t, cell.w, cell.h)
            t.move_to([cell.cx, cell.cy, 0])
            layout.add(t)
            word_mobjs.append(t)

        return layout, word_mobjs

    @staticmethod
    def _fit_into_cell(mobj: Text, cell_w: float, cell_h: float) -> None:
        """Scale a text mobject to fit inside the cell (with padding)."""
        if mobj.width <= 0 or mobj.height <= 0:
            return
        scale = min(cell_w * CELL_PAD / mobj.width, cell_h * CELL_PAD / mobj.height)
        mobj.scale(scale)
