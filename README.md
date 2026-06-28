# hackatune

Generate a kinetic-typography lyric video from a song's lyrics + audio analysis:
words build up across the screen in sync with the vocals, a camera glides/zooms
to follow them, type styling reacts to the music, and it's composited over a
flames background with the song's audio.

---

## 1. Get the data in place

The pipeline reads per-song data from `data/`. You need, for each song:

```
data/
├── songs/
│   ├── song_<id>.json      # lyrics + audio analysis (timestamps, metrics)
│   └── song_<id>.mp3       # the audio track (same <id>)
└── nice flame.mp4          # the flames background clip
```

- `song_<id>.json` and `song_<id>.mp3` **must share the same `<id>`** — the audio
  is matched to the render by that id.
- See [data/songs/README.md](data/songs/README.md) for the JSON format.
- A flames clip (`nice flame.mp4`) must be in `data/`. Any fire/loopable video
  works; longer + higher-fps is better (see RENDER.md notes).

Songs included:

| id | mood / genre |
|------|--------------|
| `666407` | gritty hip-hop / trap |
| `667778` | assertive alt-pop |
| `667784` | dreamy indie pop |

---

## 2. Install (one-time)

```bash
brew install cairo pango pkg-config ffmpeg   # system deps for Manim + ffmpeg
uv sync                                       # Python deps from the lockfile
```

This repo uses **uv** for Python — run things with `uv run …`, not bare `python`.

---

## 3. Render — just use the Makefile

The whole pipeline (render text → composite flames → add audio) is wrapped in a
[Makefile](Makefile). To make a full video for a song:

```bash
make song1     # song 666407
make song2     # song 667778
make song3     # song 667784
```

Each produces `final_<id>_with_sound.mp4` in the project root and opens it.

**Other handy targets:**

```bash
make draft                       # fast 720p30 preview (no audio) — quick checks
make video                       # full pipeline for the default song id
make SONG_ID=667784 video        # full pipeline for any song id
make OFFSET=0.8 song2            # nudge audio sync (words late -> bigger offset)
make text | compose | sound      # run a single stage
make clean                       # remove generated final_*/draft_* files
make help                        # list everything
```

Output files:

| File | What it is |
|------|------------|
| `final_<id>.mp4` | text + flames, **no audio** |
| `final_<id>_with_sound.mp4` | **the deliverable** — text + flames + synced audio |

---

## 4. Understanding / tuning the steps

The Makefile just runs the three stages described in **[RENDER.md](RENDER.md)** —
read that to understand each command, tune the look (flame dimming, word
animation, layout seed), fix audio sync, or run things by hand. It also has a
**Troubleshooting** section for the common gotchas (mid-song starts, choppy
intermediate `.mov`, flame judder, audio offset).

## Project layout

```
song_poster_scene.py   the Manim scene (the lyric video itself)
layout/                edge-tree layout engine (where words go + animations)
style/                 emotion -> typography (per-word metrics & styling)
song_data.py           typed loader for the song JSON
Makefile               one-command render pipeline
RENDER.md              step-by-step render guide + troubleshooting
```
