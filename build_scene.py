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
COL_BUFF = 0.10      # base gap between line-2 columns
PAIR_BUFF = 0.18     # gap between line 1 and line 2's block

# Wiggle room: the optimizer may pick a split whose *natural* block width is up
# to this fraction of the target SHORTER than the target, then stretch the gaps
# between columns to make up the difference. Bigger slack => the optimizer can
# favour more balanced/readable splits instead of hitting width exactly.
WIDTH_SLACK = 0.22       # allow natural width down to (1 - slack) * target
MAX_STRETCH_BUFF = 0.55  # cap how wide a stretched gap may get (Manim units)

DIM = "#46464f"
ACTIVE = "#ffffff"
ACCENT = "#ff4488"

LINE1 = "Woke up"
LINE2_WORDS = ["in", "the", "car,", "glass", "on", "my", "shirt."]


def _measure_aspect(text: str) -> float:
    """Real rendered aspect (width / height) of a text string at unit scale."""
    t = Text(text)
    return t.width / t.height if t.height > 0 else 1.0


def _split_to_match_width(words: list[str], target_w: float, anchor_h: float,
                          col_buff: float, slack: float,
                          max_stretch: float) -> tuple[list[str], float]:
    """Choose word groups for a rotated block ≈ target wide, with gap slack.

    Each part is rotated and scaled so its rotated *length* == anchor_h. After
    rotation a part's on-screen width = anchor_h / aspect (aspect = measured
    width/height). Long part → narrow column; short part → wide column.

    Instead of forcing the column widths to hit `target_w` exactly, we allow the
    natural block width to be as little as (1 - slack) * target_w, then STRETCH
    the inter-column gaps to fill the remaining width. Within that tolerance we
    prefer the most *balanced* split (columns of similar width) so the block
    reads well rather than being one fat column + one sliver.

    Returns (parts, stretched_buff): the chosen strings and the gap to use
    between columns when laying them out.
    """
    n = len(words)
    aspect_cache: dict[tuple[int, int], float] = {}

    def run_aspect(i: int, j: int) -> float:
        if (i, j) not in aspect_cache:
            aspect_cache[(i, j)] = _measure_aspect(" ".join(words[i:j]))
        return aspect_cache[(i, j)]

    min_natural = (1.0 - slack) * target_w

    best_parts: list[tuple[int, int]] | None = None
    best_buff = col_buff
    best_score = float("inf")

    for mask in range(1 << (n - 1)):
        parts: list[tuple[int, int]] = []
        start = 0
        for i in range(1, n):
            if mask & (1 << (i - 1)):
                parts.append((start, i))
                start = i
        parts.append((start, n))

        widths = [anchor_h / run_aspect(i, j) for (i, j) in parts]
        n_gaps = len(parts) - 1
        sum_w = sum(widths)

        # Need at least one gap, and the columns alone must not exceed target.
        if n_gaps == 0 or sum_w > target_w:
            continue

        # The gaps must close the remaining distance to target without
        # exceeding the stretch cap (or dropping below the base gap).
        needed_buff = (target_w - sum_w) / n_gaps
        if needed_buff > max_stretch:
            continue                      # can't stretch far enough -> too few parts
        buff = max(col_buff, needed_buff)
        achieved_w = sum_w + buff * n_gaps
        if achieved_w < min_natural:
            continue                      # still too narrow even at base gap

        # Score: prefer balanced columns (low width variance), and prefer gaps
        # close to the base (less obvious stretching). No bias toward fewer
        # parts — the target width naturally selects the right count.
        mean_w = sum_w / len(widths)
        variance = sum((w - mean_w) ** 2 for w in widths) / len(widths)
        score = variance + 0.4 * abs(buff - col_buff)

        if score < best_score:
            best_score = score
            best_parts = parts
            best_buff = buff

    if best_parts is None:
        # Fallback: whole line as one column.
        return [" ".join(words)], 0.0

    return [" ".join(words[i:j]) for (i, j) in best_parts], best_buff


class BuildScene(Scene):
    def construct(self) -> None:
        # ---- Line 1: anchor, horizontal, fixed height H ------------------- #
        anchor = Text(LINE1, color=ACTIVE)
        anchor.scale(ANCHOR_H / anchor.height)   # set its height to exactly H

        # ---- Optimize line-2 split so its block width ≈ anchor height ----- #
        parts, stretch_buff = _split_to_match_width(
            LINE2_WORDS, ANCHOR_H, ANCHOR_H, COL_BUFF,
            WIDTH_SLACK, MAX_STRETCH_BUFF,
        )
        print(f"[split] {len(parts)} parts: {parts}  gap={stretch_buff:.3f}")

        # ---- Line 2: parts, each rotated 90°, each scaled so length == H -- #
        columns: list[Text] = []
        for part in parts:
            t = Text(part, color=DIM)
            t.rotate(PI / 2)                      # now reads bottom-up
            # After rotation, t.height is the text's *length*. Make it == H.
            t.scale(ANCHOR_H / t.height)
            columns.append(t)

        line2_block = VGroup(*columns).arrange(RIGHT, buff=stretch_buff)

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
