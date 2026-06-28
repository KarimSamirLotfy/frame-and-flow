"""Per-word audio metrics + percentile ranks (pure; no Manim).

The JSON's `intensity_sections` give an energy envelope every 0.1s. Styling is
per-WORD, so we aggregate each kept metric over a word's [start, end] window,
then rank every word against the song to get a percentile in [0, 1].

We keep only the NON-REDUNDANT, expressive axes (verified by correlation +
coefficient-of-variation analysis on the dataset):

    rms_volume      loudness / force         (most variable; r≈0.77 w/ energy)
    brightness      airy/sharp vs dark/warm  (distinct timbre axis)
    percussiveness  punchy vs smooth         (≈ -harmonicity; we keep this one)
    spectral_flux   turbulence / change      (independent of the rest)

Dropped as redundant or low-variation: energy_score (≈rms), harmonicity
(≈ -percussiveness, r=-1.0), dynamic_range (low CV, little expressive signal).
"""

from __future__ import annotations

from dataclasses import dataclass

from song_data import Song

# The axes we keep, in priority order (used for the "pick strongest" tie-break).
KEPT_METRICS = ["rms_volume", "brightness", "percussiveness", "spectral_flux"]


@dataclass
class WordMetrics:
    word: str
    start: float
    end: float
    values: dict[str, float]        # raw averaged metric value per kept axis
    pct: dict[str, float]           # percentile rank in [0,1] per kept axis


def _avg_over_window(song: Song, start: float, end: float, metric: str) -> float:
    """Average `metric` of the energy envelope over [start, end]."""
    isec = song.audio.intensity_sections
    interval = isec.interval or 0.1
    n = max(1, int(round((end - start) / interval)))
    total = 0.0
    for k in range(n):
        sample = isec.at(start + k * interval)
        total += getattr(sample, metric) if sample else 0.0
    return total / n


def _percentile_ranks(values: list[float]) -> list[float]:
    """Rank each value in [0,1] = fraction of values it is >= (ties share rank)."""
    if not values:
        return []
    order = sorted(values)
    n = len(order)
    # for each value, percentile = (# strictly less) / (n-1), clamped
    out = []
    for v in values:
        below = sum(1 for x in order if x < v)
        out.append(below / (n - 1) if n > 1 else 1.0)
    return out


def word_metrics(song: Song) -> list[WordMetrics]:
    """Compute per-word metric values + percentile ranks for the kept axes."""
    words = song.all_words
    # raw averaged values per metric
    raw: dict[str, list[float]] = {
        m: [_avg_over_window(song, w.start, w.end, m) for w in words]
        for m in KEPT_METRICS
    }
    ranks: dict[str, list[float]] = {
        m: _percentile_ranks(raw[m]) for m in KEPT_METRICS
    }
    result: list[WordMetrics] = []
    for i, w in enumerate(words):
        result.append(WordMetrics(
            word=w.text,
            start=w.start,
            end=w.end,
            values={m: raw[m][i] for m in KEPT_METRICS},
            pct={m: ranks[m][i] for m in KEPT_METRICS},
        ))
    return result


if __name__ == "__main__":
    import sys
    if __package__ is None:           # allow `python style/metrics.py`
        sys.path.insert(0, ".")
    song = Song.load(sys.argv[1] if len(sys.argv) > 1
                     else "data/songs/song_666407.json")
    wm = word_metrics(song)
    print(f"words: {len(wm)}")
    # how many in the top decile of each axis (the styling candidates)
    for m in KEPT_METRICS:
        hi = [x for x in wm if x.pct[m] >= 0.9]
        print(f"  {m:15} top-decile: {len(hi):2}  "
              f"e.g. {[x.word for x in hi[:6]]}")
