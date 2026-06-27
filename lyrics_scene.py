"""Manim scene: render a song's lyrics in sync with their timestamps.

This is a thin *view* on top of `song_data.Song` — all the parsing lives in
`song_data.py`, so this file only worries about putting things on screen at the
right time. No audio yet; timing comes straight from the JSON.

Render (fast preview, low quality):
    uv run manim -pql lyrics_scene.py LyricsScene

Render the whole song in higher quality (HACKATUNE_END=0 means full song):
    HACKATUNE_END=0 uv run manim -qh lyrics_scene.py LyricsScene

Config via env vars (all optional):
    HACKATUNE_SONG   path to the song JSON   (default: data/songs/song_666407.json)
    HACKATUNE_END    stop after N seconds; 0 = full song   (default: 35)
"""

from __future__ import annotations

import os

from manim import (
    DOWN,
    UP,
    Scene,
    Text,
    VGroup,
    config,
)

from song_data import LyricLine, Song

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
SONG_PATH = os.environ.get("HACKATUNE_SONG", "data/songs/song_666407.json")
# Render only the first N seconds so prototype renders are quick. 0 = full song.
END_TIME = float(os.environ.get("HACKATUNE_END", "35"))

# Colors
DIM = "#5a5a66"     # unsung words
ACTIVE = "#ffffff"  # word currently/just sung
ACCENT = "#ffcc33"  # section label / accents

LINE_FONT_SIZE = 48
MAX_LINE_WIDTH_FRAC = 0.85  # scale a line down if it's wider than this * frame


class LyricsScene(Scene):
    def construct(self) -> None:
        song = Song.load(SONG_PATH)

        # ---- persistent chrome -------------------------------------------- #
        a = song.audio
        footer = Text(
            f"{a.key} {a.scale}   ·   {a.bpm:.0f} BPM   ·   {', '.join(a.moods[:3])}",
            font_size=22,
            color=DIM,
        ).to_edge(DOWN, buff=0.35)
        self.add(footer)

        section_label = Text("", font_size=28, color=ACCENT).to_edge(UP, buff=0.4)
        self.add(section_label)
        current_section = ""

        # ---- synced playback --------------------------------------------- #
        clock = 0.0

        def advance_to(t: float) -> None:
            """Wait until scene time reaches `t` seconds (never goes backwards)."""
            nonlocal clock
            dt = t - clock
            if dt > 1e-3:
                self.wait(dt)
                clock = t

        end = END_TIME if END_TIME > 0 else song.duration

        for line in song.lyrics:
            if line.start >= end:
                break

            advance_to(line.start)

            # Update the section label if we've entered a new section.
            seg = song.segment_at(line.start)
            seg_name = seg.label.upper() if seg else ""
            if seg_name != current_section:
                current_section = seg_name
                new_label = Text(seg_name, font_size=28, color=ACCENT).to_edge(
                    UP, buff=0.4
                )
                self.remove(section_label)
                section_label = new_label
                self.add(section_label)

            # Build the line as individual word mobjects so we can reveal them.
            line_group, word_mobjs = self._build_line(line)
            self.add(line_group)

            # Reveal each word at its own start time.
            for word, wm in zip(line.words, word_mobjs):
                if word.start >= end:
                    break
                advance_to(word.start)
                wm.set_color(ACTIVE).set_opacity(1.0)

            advance_to(min(line.end, end))
            self.remove(line_group)

        self.wait(0.5)

    # ----------------------------------------------------------------------- #
    def _build_line(self, line: LyricLine) -> tuple[VGroup, list[Text]]:
        """Lay out a lyric line as dim word mobjects, centered on screen."""
        word_mobjs = [
            Text(word.text, font_size=LINE_FONT_SIZE, color=DIM).set_opacity(0.35)
            for word in line.words
        ]
        if not word_mobjs:  # safety: empty line
            word_mobjs = [Text(line.text, font_size=LINE_FONT_SIZE, color=DIM)]

        group = VGroup(*word_mobjs).arrange(buff=0.22)

        max_w = config.frame_width * MAX_LINE_WIDTH_FRAC
        if group.width > max_w:
            group.scale(max_w / group.width)

        group.move_to([0, 0, 0])
        return group, word_mobjs
