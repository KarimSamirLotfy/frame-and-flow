"""Prototype: two lines that 'build' onto each other.

Line 1 ("Woke up") is the anchor, rendered horizontally at a fixed height H.
Line 2 ("in the car, glass on my shirt.") is split into parts, each ROTATED 90°
(reads bottom-up) and scaled independently so that every part's rotated length
== H. The parts stack left-to-right as columns, flush to the right edge of
line 1 and aligned to its height — so line 2 looks like it grows out of line 1.

Render:
    uv run manim -pql build_scene.py BuildScene

Debug (outline the anchor height H and each column):
    HACKATUNE_DEBUG=1 uv run manim -pql build_scene.py BuildScene
"""

from __future__ import annotations

import os

from manim import (
    DOWN,
    LEFT,
    PI,
    RIGHT,
    UP,
    Rectangle,
    Scene,
    Text,
    VGroup,
)

SHOW_DEBUG = os.environ.get("HACKATUNE_DEBUG", "0") == "1"

# Anchor height for "Woke up" (Manim units). Everything keys off this.
ANCHOR_H = 2.6
COL_BUFF = 0.10      # gap between line-2 columns
PAIR_BUFF = 0.18     # gap between line 1 and line 2's block

DIM = "#46464f"
ACTIVE = "#ffffff"
ACCENT = "#ff4488"

# Line 2 split into parts (each becomes one rotated column).
LINE2_PARTS = ["in the car,", "glass on my", "shirt."]


class BuildScene(Scene):
    def construct(self) -> None:
        # ---- Line 1: anchor, horizontal, fixed height H ------------------- #
        anchor = Text("Woke up", color=ACTIVE)
        anchor.scale(ANCHOR_H / anchor.height)   # set its height to exactly H

        # ---- Line 2: parts, each rotated 90°, each scaled so length == H -- #
        columns: list[Text] = []
        for part in LINE2_PARTS:
            t = Text(part, color=DIM)
            t.rotate(PI / 2)                      # now reads bottom-up
            # After rotation, t.height is the text's *length*. Make it == H.
            t.scale(ANCHOR_H / t.height)
            columns.append(t)

        line2_block = VGroup(*columns).arrange(RIGHT, buff=COL_BUFF)

        # ---- Assemble: line2 block flush-right of anchor, same height ----- #
        whole = VGroup(anchor, line2_block).arrange(RIGHT, buff=PAIR_BUFF)
        # Vertically align the two so their centers (and thus heights) line up.
        line2_block.align_to(anchor, UP)
        whole.move_to([0, 0, 0])

        if SHOW_DEBUG:
            self._add_debug(anchor, columns)

        # ---- "Building" reveal: anchor first, then columns in order ------- #
        anchor.set_opacity(1.0)
        for c in columns:
            c.set_opacity(1.0)

        self.add(whole)
        self.wait(1.0)

    # ----------------------------------------------------------------------- #
    def _add_debug(self, anchor: Text, columns: list[Text]) -> None:
        # Box around the anchor.
        ab = Rectangle(width=anchor.width, height=anchor.height)
        ab.set_stroke(ACCENT, width=1.5, opacity=0.7).set_fill(opacity=0)
        ab.move_to(anchor.get_center())
        self.add(ab)
        # Box around each column.
        for c in columns:
            cb = Rectangle(width=c.width, height=c.height)
            cb.set_stroke("#44aaff", width=1.5, opacity=0.7).set_fill(opacity=0)
            cb.move_to(c.get_center())
            self.add(cb)
