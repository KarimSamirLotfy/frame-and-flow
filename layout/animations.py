"""Word-entrance animations — an extensible registry of reveal styles.

Each strategy turns a (placed, invisible) word mobject into a Manim Animation
that brings it on screen. Strategies share one interface so the scene can pick
any of them per word, and new ones can be added without touching the scene
(Open/Closed).

    anim = STYLES["slide"].build(word_mobj, side=Side.LEFT,
                                 world_angle=0.0, run_time=0.25)
    self.play(anim)

Direction note: the composition is rotated by `world_angle` to keep the active
line upright, so a "screen-right" offset is `RIGHT` rotated by `world_angle` in
world space. Strategies that move the word must rotate their offset accordingly.
"""

from __future__ import annotations

import math
from typing import Protocol

import numpy as np
from manim import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    Animation,
    FadeIn,
    smooth,
)

from .geometry import Side

# Unit screen-direction a block on each side is aligned toward. The slide-in
# enters from the OPPOSITE side (align left -> come from the right).
_OPPOSITE_DIR = {
    Side.LEFT: RIGHT,
    Side.RIGHT: LEFT,
    Side.UP: DOWN,
    Side.DOWN: UP,
}


def _rotate_vec(v: np.ndarray, angle: float) -> np.ndarray:
    """Rotate a 3D screen-space direction by `angle` into world space."""
    c, s = math.cos(angle), math.sin(angle)
    return np.array([v[0] * c - v[1] * s, v[0] * s + v[1] * c, 0.0])


class WordAnimation(Protocol):
    def build(self, mobj, side: Side, world_angle: float,
              run_time: float) -> Animation: ...


class PopIn:
    """Instant-feeling fade (near-zero duration). The neutral default."""

    def build(self, mobj, side: Side, world_angle: float,
              run_time: float) -> Animation:
        return FadeIn(mobj, run_time=max(run_time * 0.4, 1e-2))


class SlideIn:
    """Word eases in from the side OPPOSITE its aligned edge, fading up.

    The travel distance is a multiple of the word's own size so the motion reads
    at every scale. The offset direction is rotated by `world_angle` so it's
    correct on screen even when the world is spun to keep the line upright.
    """

    def __init__(self, distance_factor: float = 1.4) -> None:
        self._dist = distance_factor

    def build(self, mobj, side: Side, world_angle: float,
              run_time: float) -> Animation:
        screen_dir = _OPPOSITE_DIR.get(side, RIGHT)
        world_dir = _rotate_vec(np.array(screen_dir, dtype=float), world_angle)
        reach = self._dist * max(mobj.width, mobj.height)
        shift = world_dir * reach
        # `mobj` is already at its final layout pose. Displace it to the offset
        # start (transparent), then animate BACK to where it was, fading in.
        mobj.shift(shift).set_opacity(0.0)
        return mobj.animate(run_time=run_time, rate_func=smooth) \
            .shift(-shift).set_opacity(1.0)


# Registry — add new styles here; the scene looks them up by name.
STYLES: dict[str, WordAnimation] = {
    "pop": PopIn(),
    "slide": SlideIn(),
}
