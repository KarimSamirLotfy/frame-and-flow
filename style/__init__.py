"""Emotion-driven typography: map per-word audio metrics to type treatments."""

from .aesthetic import BASE_COLOR, BASE_FONT, Stylist, WordStyle
from .metrics import KEPT_METRICS, WordMetrics, word_metrics

__all__ = [
    "word_metrics", "WordMetrics", "KEPT_METRICS",
    "Stylist", "WordStyle", "BASE_FONT", "BASE_COLOR",
]
