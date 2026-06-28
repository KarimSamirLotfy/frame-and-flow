"""Map per-word metric percentiles -> typographic style (pure; no Manim).

Rules (kept deliberately rare so styling reads as meaningful, not noisy):

  * A word is styled on an axis only if it's in that axis's TOP DECILE
    (percentile >= TOP_DECILE). ~10% of words per axis.
  * Treatments live on different attributes so they COMPOSE, but we cap at
    MAX_TREATMENTS per word (strongest percentiles win) to avoid clutter.

  axis           emotion              treatment
  rms_volume     forceful / loud      bold weight
  brightness     airy / tense         italic slant
  percussiveness sharp / aggressive   warm color tint
  spectral_flux  turbulent / unstable display-font swap

Words below all thresholds get the fixed BASE style.
"""

from __future__ import annotations

from dataclasses import dataclass

from .metrics import WordMetrics

TOP_DECILE = 0.90
MAX_TREATMENTS = 2

# Fixed base look (same for every song).
BASE_FONT = "Georgia"
DISPLAY_FONT = "Impact"          # the turbulent-word swap (high contrast)
BASE_COLOR = "#f2f2f2"
TINT_COLOR = "#ff7a5c"           # warm tint for percussive/aggressive words


@dataclass
class WordStyle:
    font: str = BASE_FONT
    weight: str = "NORMAL"       # Manim weight token: NORMAL | BOLD
    slant: str = "NORMAL"        # Manim slant token: NORMAL | ITALIC
    color: str = BASE_COLOR

    @property
    def is_base(self) -> bool:
        return (self.font == BASE_FONT and self.weight == "NORMAL"
                and self.slant == "NORMAL" and self.color == BASE_COLOR)


# Each axis -> a function that applies its treatment to a WordStyle.
def _apply_rms(s: WordStyle) -> None:
    s.weight = "BOLD"


def _apply_brightness(s: WordStyle) -> None:
    s.slant = "ITALIC"


def _apply_percussiveness(s: WordStyle) -> None:
    s.color = TINT_COLOR


def _apply_flux(s: WordStyle) -> None:
    s.font = DISPLAY_FONT


_TREATMENTS = {
    "rms_volume": _apply_rms,
    "brightness": _apply_brightness,
    "percussiveness": _apply_percussiveness,
    "spectral_flux": _apply_flux,
}


class Stylist:
    """Turns a word's metric percentiles into a WordStyle."""

    def __init__(self, top_decile: float = TOP_DECILE,
                 max_treatments: int = MAX_TREATMENTS) -> None:
        self._thr = top_decile
        self._cap = max_treatments

    def style_for(self, wm: WordMetrics) -> WordStyle:
        # axes where this word is in the top decile, strongest first
        hot = sorted(
            ((m, p) for m, p in wm.pct.items() if p >= self._thr),
            key=lambda kv: kv[1], reverse=True,
        )
        style = WordStyle()
        for metric, _pct in hot[: self._cap]:
            _TREATMENTS[metric](style)
        return style


if __name__ == "__main__":
    import sys
    if __package__ is None:
        sys.path.insert(0, ".")
    from collections import Counter
    from style.metrics import word_metrics
    from song_data import Song

    song = Song.load(sys.argv[1] if len(sys.argv) > 1
                     else "data/songs/song_666407.json")
    st = Stylist()
    styles = [st.style_for(wm) for wm in word_metrics(song)]
    base = sum(1 for s in styles if s.is_base)
    print(f"words: {len(styles)}   base (unstyled): {base}   "
          f"styled: {len(styles) - base}")
    print("treatment counts:")
    print("  bold   :", sum(1 for s in styles if s.weight == "BOLD"))
    print("  italic :", sum(1 for s in styles if s.slant == "ITALIC"))
    print("  tint   :", sum(1 for s in styles if s.color == TINT_COLOR))
    print("  display:", sum(1 for s in styles if s.font == DISPLAY_FONT))
    combos = Counter((s.weight, s.slant, s.color != BASE_COLOR,
                      s.font != BASE_FONT) for s in styles)
    print("distinct style combos:", len(combos))
