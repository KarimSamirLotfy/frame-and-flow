# ─────────────────────────────────────────────────────────────────────────────
#  Lyric video render pipeline (see RENDER.md for the why behind each step)
#
#  Quick use:
#     make song2                 # full pipeline for song 2, with audio
#     make SONG_ID=667784 video  # full pipeline for any song id
#     make text                  # just the Manim transparent render
#     make compose               # just the flames composite
#     make sound                 # just mux the audio
#     make draft                 # fast 720p30 preview (no audio)
#     make clean                 # remove generated finals
# ─────────────────────────────────────────────────────────────────────────────

# ── Config (override on the command line, e.g. `make OFFSET=0.8 sound`) ──────
SONG_ID    ?= 667778
SONG       := data/songs/song_$(SONG_ID).json
AUDIO      := data/songs/song_$(SONG_ID).mp3
FLAME      := data/nice flame.mp4

# Quality: high = 1080p60 (final), med = 720p30 (draft)
MOV_HIGH   := media/videos/song_poster_scene/1080p60/SongPoster.mov
MOV_MED    := media/videos/song_poster_scene/720p30/SongPoster.mov

# Audio sync offset in seconds (words late -> increase; early -> decrease)
OFFSET     ?= 0.5

# Output names (per song so they don't clobber each other)
VIDEO_OUT  := final_$(SONG_ID).mp4
FINAL_OUT  := final_$(SONG_ID)_with_sound.mp4

.PHONY: video song2 song1 song3 text compose sound draft clean help

help:
	@echo "Targets:"
	@echo "  make song1 / song2 / song3   full pipeline for that song (+audio)"
	@echo "  make video                   full pipeline for SONG_ID=$(SONG_ID)"
	@echo "  make text | compose | sound  run a single stage"
	@echo "  make draft                   fast 720p30 preview (no audio)"
	@echo "  make clean                   remove generated final_*.mp4"
	@echo ""
	@echo "Override: make SONG_ID=667784 OFFSET=0.8 video"

# ── Convenience song aliases ─────────────────────────────────────────────────
song1: ; @$(MAKE) SONG_ID=666407 video
song2: ; @$(MAKE) SONG_ID=667778 video
song3: ; @$(MAKE) SONG_ID=667784 video

# ── Full pipeline ────────────────────────────────────────────────────────────
video: $(FINAL_OUT)
	@echo "✅ done: $(FINAL_OUT)"
	@open "$(FINAL_OUT)" 2>/dev/null || true

# ── Stage 1: transparent text (1080p60) ──────────────────────────────────────
text:
	@echo "🎬 Stage 1: rendering text for song $(SONG_ID) (1080p60, transparent)…"
	unset HACKATUNE_START HACKATUNE_END HACKATUNE_NLINES; \
	HACKATUNE_SONG="$(SONG)" \
	uv run manim -qh -t --format=mov song_poster_scene.py SongPoster --disable_caching

# ── Stage 2: composite flames (smoothed) -> VIDEO_OUT ────────────────────────
# Depends on `text` so the MOV exists/refreshes for this song.
compose: text
	$(MAKE) _compose

_compose:
	@echo "🔥 Stage 2: compositing flames -> $(VIDEO_OUT)…"
	@TEXT_DUR=$$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$(MOV_HIGH)"); \
	FLAME_DUR=$$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$(FLAME)"); \
	PTS=$$(python3 -c "print(max(1.0, $$TEXT_DUR/$$FLAME_DUR))"); \
	echo "  text=$$TEXT_DUR s  flame=$$FLAME_DUR s  slowdown=$$PTS"; \
	ffmpeg -hide_banner -loglevel error -stats \
	  -i "$(FLAME)" -i "$(MOV_HIGH)" \
	  -filter_complex "[0:v]setpts=$${PTS}*PTS,scale=1920:1080,eq=brightness=-0.25:saturation=0.8,minterpolate=fps=60:mi_mode=blend[bg];[bg][1:v]overlay=format=auto:shortest=1[out]" \
	  -map "[out]" -t "$$TEXT_DUR" \
	  -c:v libx264 -pix_fmt yuv420p -crf 18 -r 60 -movflags +faststart \
	  -y "$(VIDEO_OUT)"
	@echo "  -> $(VIDEO_OUT)"

$(VIDEO_OUT): text
	@$(MAKE) _compose

# ── Stage 3: mux audio -> FINAL_OUT ──────────────────────────────────────────
sound: $(VIDEO_OUT)
	@$(MAKE) _sound

$(FINAL_OUT): $(VIDEO_OUT)
	@$(MAKE) _sound

_sound:
	@echo "🔊 Stage 3: adding audio (offset $(OFFSET)s) -> $(FINAL_OUT)…"
	ffmpeg -hide_banner -loglevel error \
	  -i "$(VIDEO_OUT)" -itsoffset $(OFFSET) -i "$(AUDIO)" \
	  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -movflags +faststart \
	  -y "$(FINAL_OUT)"
	@echo "  -> $(FINAL_OUT)"

# ── Fast draft: 720p30, no audio ─────────────────────────────────────────────
draft:
	@echo "⚡ draft: 720p30 text + flames for song $(SONG_ID) (no audio)…"
	unset HACKATUNE_START HACKATUNE_END HACKATUNE_NLINES; \
	HACKATUNE_SONG="$(SONG)" \
	uv run manim -qm -t --format=mov song_poster_scene.py SongPoster --disable_caching
	@TEXT_DUR=$$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$(MOV_MED)"); \
	FLAME_DUR=$$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$(FLAME)"); \
	PTS=$$(python3 -c "print(max(1.0, $$TEXT_DUR/$$FLAME_DUR))"); \
	ffmpeg -hide_banner -loglevel error -stats \
	  -i "$(FLAME)" -i "$(MOV_MED)" \
	  -filter_complex "[0:v]setpts=$${PTS}*PTS,scale=1280:720,eq=brightness=-0.25:saturation=0.8,minterpolate=fps=30:mi_mode=blend[bg];[bg][1:v]overlay=format=auto:shortest=1[out]" \
	  -map "[out]" -t "$$TEXT_DUR" \
	  -c:v libx264 -pix_fmt yuv420p -crf 20 -r 30 -movflags +faststart \
	  -y "draft_$(SONG_ID).mp4"
	@echo "  -> draft_$(SONG_ID).mp4"; open "draft_$(SONG_ID).mp4" 2>/dev/null || true

clean:
	rm -f final_*.mp4 draft_*.mp4
	@echo "cleaned generated finals/drafts"
