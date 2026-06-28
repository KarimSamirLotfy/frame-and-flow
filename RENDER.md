# Rendering a lyric video

How to produce a final lyric video (kinetic typography + flames background +
song audio) for any song. Three stages:

1. **Render the text** with Manim onto a transparent layer (`.mov`).
2. **Composite the flames** behind it with ffmpeg → `final.mp4` (no sound).
3. **Add the song audio** with ffmpeg → `final_with_sound.mp4` (the deliverable).

> Why stages? Manim can't play a video as a background, so we render the text on
> a **transparent** layer (`.mov` with alpha), then overlay it onto the flames
> with ffmpeg, then mux the audio. The `.mov` is only an intermediate —
> **don't judge it by playing it directly** (its `qtrle` codec is heavy and
> stutters in players; the frames are fine). Only the final `.mp4` matters; it's
> smooth h264.

> **TL;DR** — jump to [Quick recap](#quick-recap-do-song-2-end-to-end) for the
> full copy-paste pipeline. Read the stages below to understand/tune each step.

---

## Prerequisites (one-time)

System libs (via Homebrew) and Python deps:

```bash
brew install cairo pango pkg-config ffmpeg
uv sync          # installs manim etc. from the lockfile
```

You also need a flames video in `data/`. We ship:
- `data/nice flame.mp4` — **use this** (131s, ~14.6 fps, smooth)
- `data/slow flame.mp4` — older, near-still (2 fps), needs interpolation; avoid

---

## Choosing the song

The scene reads the song via the `HACKATUNE_SONG` env var. Available songs:

| Song | JSON |
|------|------|
| 1 | `data/songs/song_666407.json` (default) |
| 2 | `data/songs/song_667778.json` |
| 3 | `data/songs/song_667784.json` |

Set it once in your shell so every command below picks it up:

```bash
cd /Users/kiko/Desktop/hackatune

# pick the song you want to render:
export HACKATUNE_SONG="data/songs/song_667778.json"     # <-- song 2
```

Other optional knobs (defaults are fine):
- `HACKATUNE_SEED=7` — layout randomness (change for a different arrangement)
- `HACKATUNE_START` / `HACKATUNE_END` — render only a time window (seconds), for
  quick previews. Leave unset for the whole song.
- `HACKATUNE_WORDANIM=slide` — word entrance style (`slide` or `pop`)

---

## Stage 1 — render the transparent text (Manim)

```bash
# full song, 1080p @ 60fps, transparent:
uv run manim -qh -t --format=mov song_poster_scene.py SongPoster --disable_caching
```

- `-qh` = 1080p, 60fps (smooth eases). Use `-qm` (720p30) for a faster draft.
- `-t` = transparent background.
- `--disable_caching` = always re-render (safe after code/song changes).

**Output (the transparent intermediate):**
```
media/videos/song_poster_scene/1080p60/SongPoster.mov
```
(`-qm` would write to `.../720p30/SongPoster.mov` instead.)

> ⏱ The full song at `-qh` takes a while. For a quick check first, render a
> slice: `HACKATUNE_START=30 HACKATUNE_END=50 uv run manim -qh -t --format=mov
> song_poster_scene.py SongPoster --disable_caching`

---

## Stage 2 — composite the flames behind it (ffmpeg)

### Step 2a — point at the rendered MOV and read durations

```bash
MOV="media/videos/song_poster_scene/1080p60/SongPoster.mov" 
TEXT_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MOV")
FLAME_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "data/nice flame.mp4")
echo "text: $TEXT_DUR s   flames: $FLAME_DUR s"
```

### Step 2b — compute the slowdown so the flames cover the text

```bash
# stretch flames only if they're shorter than the text; else 1.0 (just trim).
PTS=$(python3 -c "print(max(1.0, $TEXT_DUR/$FLAME_DUR))")
echo "slowdown factor: $PTS"
```

### Step 2c — render the final video

```bash
ffmpeg \
  -i "data/nice flame.mp4" \
  -i "$MOV" \
  -filter_complex "[0:v]setpts=${PTS}*PTS,scale=1920:1080,eq=brightness=-0.25:saturation=0.8,minterpolate=fps=60:mi_mode=blend[bg];[bg][1:v]overlay=format=auto:shortest=1[out]" \
  -map "[out]" -t "$TEXT_DUR" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -r 60 \
  -movflags +faststart \
  -y final.mp4
```

What the filter does:
- `setpts=${PTS}*PTS` — slows the flames just enough to fit (no loop, no seam).
- `scale=1920:1080` — match the 1080p text (use `1280:720` if you rendered `-qm`).
- `eq=brightness=-0.25:saturation=0.8` — dims the flames so the text stays
  readable (tweak these two numbers for a brighter/darker background).
- `minterpolate=fps=60:mi_mode=blend` — **smooths the flames.** The flame clip is
  only ~14.6 fps, so forcing it to 60 fps by frame-duplication makes the
  background judder. `blend` cross-fades between flame frames for smooth motion
  (fast; ~2x realtime). Do NOT use `mi_mode=mci` here — it's far slower and
  warps fire. Drop this filter only if your flame source is already ≥60 fps.
- `overlay` — text on top of the dimmed flames.
- `-r 60` — output 60fps, matched to the render (no judder). Use `-r 30` for `-qm`.

---

## Where is the output?

```
final.mp4        <-- in the project root
```

Open it:
```bash
open final.mp4
```

This is the deliverable so far: 1080p60 h264, flames + kinetic typography,
smooth playback — but **no sound yet**. Add the song's audio in Stage 3.

---

## Stage 3 — add the song audio (sync the voice)

The song's audio is the `.mp3` next to its JSON: `data/songs/song_<id>.mp3`.
The video and audio both start at `t=0` (the words reveal at timestamps that are
times *into the mp3*), so we just mux the mp3 on — no clever alignment needed,
except a small **offset** to fine-tune lip-sync.

```bash
# the mp3 must match the song you rendered:
AUDIO="data/songs/song_667778.mp3"      # <-- song 2's mp3

# OFFSET shifts the audio in time to fix sync (seconds):
#   words appear LATE  (voice ahead of text)  -> INCREASE offset (e.g. 0.5, 0.8)
#   words appear EARLY (voice behind text)    -> DECREASE / negative offset
OFFSET=0.5

ffmpeg \
  -i final.mp4 \
  -itsoffset ${OFFSET} -i "$AUDIO" \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -b:a 192k \
  -movflags +faststart \
  -y final_with_sound.mp4
```

- `-c:v copy` — the video is **not re-encoded** (fast, lossless); only audio is
  added. So you can re-run this with different `OFFSET` values cheaply until the
  voice lines up.
- `-itsoffset ${OFFSET}` — delays the audio start by `OFFSET` seconds.

**Tuning the offset:** play `final_with_sound.mp4`, watch a word light up vs.
when it's sung. Adjust `OFFSET` and re-run (it's a few seconds each time). If the
lag is the SAME at the start and end of the song, a single offset fixes it. If
the lag GROWS over the song, that's a render-timeline problem, not an offset —
re-render Stage 1 (the scene caps animations to their beat gaps to prevent this).

### Final output

```
final_with_sound.mp4     <-- in the project root: video + flames + synced audio
```
```bash
open final_with_sound.mp4
```

---

## Quick recap (do song 2 end to end)

```bash
cd /Users/kiko/Desktop/hackatune
export HACKATUNE_SONG="data/songs/song_667778.json"

# 1) render transparent text
uv run manim -qh -t --format=mov song_poster_scene.py SongPoster --disable_caching

# 2) composite flames (with smoothing)
MOV="media/videos/song_poster_scene/1080p60/SongPoster.mov"
TEXT_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MOV")
FLAME_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "data/nice flame.mp4")
PTS=$(python3 -c "print(max(1.0, $TEXT_DUR/$FLAME_DUR))")

ffmpeg \
  -i "data/nice flame.mp4" -i "$MOV" \
  -filter_complex "[0:v]setpts=${PTS}*PTS,scale=1920:1080,eq=brightness=-0.25:saturation=0.8,minterpolate=fps=60:mi_mode=blend[bg];[bg][1:v]overlay=format=auto:shortest=1[out]" \
  -map "[out]" -t "$TEXT_DUR" \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -r 60 -movflags +faststart \
  -y final_song2.mp4

# 3) add the audio (tune OFFSET until the voice lines up with the words)
OFFSET=0.5
ffmpeg \
  -i final_song2.mp4 -itsoffset ${OFFSET} -i "data/songs/song_667778.mp3" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -movflags +faststart \
  -y final_song2_with_sound.mp4

open final_song2_with_sound.mp4
```

> Tip: give each song its own output name (`final_song2.mp4`, etc.) so Stage 2
> doesn't overwrite a previous final. The Stage 1 `.mov` **does** get
> overwritten each render, so composite before re-rendering another song.

---

## Troubleshooting (things that actually bit us)

**The video starts partway through the song / wrong length.**
You have a leftover render-window env var from a preview. Clear it before a full
render:
```bash
unset HACKATUNE_START HACKATUNE_END HACKATUNE_NLINES
env | grep HACKATUNE          # should show only HACKATUNE_SONG (if set)
```
The scene defaults are `START=0, END=0 (full song), NLINES=0 (all lines)` — so a
mid-song start always means a lingering `export` in your shell.

**The `.mov` plays choppy / laggy.**
Expected — it's a heavy `qtrle/argb` (≈20 Mbit/s) alpha stream that players drop
frames on. It is NOT a sign the animation is bad. Never judge the `.mov`; only
the composited h264 `final*.mp4`. (To preview the text alone smoothly:
`ffmpeg -i <the.mov> -c:v libx264 -pix_fmt yuv420p -crf 20 -y preview.mp4`.)

**The final video's background (flames) judders.**
The flame clip is low-fps (~14.6). Forcing 60 fps by duplication judders. The
`minterpolate=fps=60:mi_mode=blend` filter in Stage 2c fixes it (already
included). If you removed it, add it back. Avoid `mi_mode=mci` — slow + warps
fire.

**The audio is out of sync (words late or early).**
Tune `OFFSET` in Stage 3 (lossless re-mux, cheap to retry):
words late → bigger offset; words early → smaller/negative. A *constant* lag is
an offset fix; a *growing* lag means re-render Stage 1.

**Wrong audio / drifts immediately.**
You muxed the wrong mp3. The mp3 MUST match the `HACKATUNE_SONG` you rendered.
Match by song id (`song_667778.json` → `song_667778.mp3`), not by guessing.

**`ffprobe` returns an empty duration / `zsh: command not found: #`.**
Don't put `# inline comments` after a command in zsh, and make sure the `MOV`
path actually exists (`ls media/videos/song_poster_scene/1080p60/`).

---

## Output files reference

| File | What it is |
|------|------------|
| `media/videos/song_poster_scene/1080p60/SongPoster.mov` | transparent text layer (intermediate; overwritten each render) |
| `final.mp4` | text + flames, no audio (Stage 2) |
| `final_with_sound.mp4` | **final deliverable** — text + flames + synced audio (Stage 3) |

Drafts: render Stage 1 with `-qm` (720p30) instead of `-qh`; then use
`scale=1280:720`, `-r 30`, and `minterpolate=fps=30:mi_mode=blend` in Stage 2,
and `.../720p30/SongPoster.mov` as the MOV path.
