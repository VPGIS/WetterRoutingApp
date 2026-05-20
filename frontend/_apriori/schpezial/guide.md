# Easter Egg – Scrat Animation Pipeline

Hidden mechanic: typing `67FHNW67` into the **Destination / Ziel** field in
`vp_routing.html` triggers a green-screen-cleaned Scrat animation with audio.

---

## Folder contents

| File | Purpose |
|------|---------|
| `scrat.mp4` | Source video (green-screen footage, 30 fps) |
| `process_scrat.py` | Full processing pipeline (extract → chroma-key → sprite sheet) |
| `environment.yml` | Conda env spec to reproduce the pipeline environment |
| `out/spritesheet.png` | Output: packed RGBA sprite sheet (one HTTP request) |
| `out/scrat_audio.mp3` | Output: extracted audio track |
| `out/meta.json` | Output: frame layout metadata consumed by the JS easter egg |
| `out/frames/` | Output: individual RGBA PNGs (kept for re-packing) |

---

## 1 — Environment setup

```bash
# Create from scratch
conda env create -f environment.yml

# Or recreate if it already exists
conda env create -f environment.yml --force

# Activate
conda activate secret
```

**Packages installed (2026-05-20):**

| Package | Version | Source |
|---------|---------|--------|
| python | 3.11 | conda-forge |
| ffmpeg | 8.1.1 | conda-forge |
| numpy | 2.4.6 | conda-forge |
| pillow | 12.2.0 | conda-forge |
| opencv-python | 4.13.0.92 | pip |

---

## 2 — Place the source video

Drop `scrat.mp4` into this folder:

```
frontend/_apriori/schpezial/scrat.mp4
```

---

## 3 — Run the pipeline

```bash
conda run -n secret python process_scrat.py
```

Or with the env active:

```bash
python process_scrat.py
```

**What the script does, step by step:**

1. **Frame extraction** — calls `ffmpeg -vf fps=30` to dump every frame as a
   raw PNG into `out/raw_frames/`.

2. **Audio extraction** — calls `ffmpeg -vn -q:a 2` to produce `out/scrat_audio.mp3`
   at ~190 kbps VBR.

3. **Green-screen removal** — for each raw frame:
   - Converts BGR → HSV
   - Creates a binary mask for the green range
     (`H 35-90 / S 40-255 / V 40-255` in OpenCV's 0-179 hue scale)
   - Dilates the mask by 1 px to eat chroma fringing
   - Applies a 3×3 Gaussian blur to the alpha edge for soft falloff
   - Writes the result as a 4-channel (RGBA) PNG

4. **Sprite sheet** — packs all RGBA frames into a single `spritesheet.png`
   (10 columns × N rows). One file = one HTTP request = no per-frame overhead.

5. **Metadata** — writes `meta.json`:
   ```json
   {
     "frameWidth": <px>,
     "frameHeight": <px>,
     "cols": 10,
     "rows": <n>,
     "totalFrames": <n>,
     "fps": 30,
     "spritesheetFile": "spritesheet.png",
     "audioFile": "scrat_audio.mp3"
   }
   ```

6. **Cleanup** — deletes `out/raw_frames/` (raw PNGs no longer needed).

---

## 4 — Green-screen removal algorithm

The `remove_green()` function runs four passes per frame:

1. **HSV mask** — flags every pixel in the green range as potentially background.

2. **Border flood-fill (8-connectivity)** — starts from all four image edges and
   marks only background-connected green pixels. Interior green (e.g. Scrat's eyes)
   is *not* reached and therefore stays opaque.

3. **Small blob removal** — any remaining interior green patch smaller than
   `MIN_BLOB_AREA` px² is also removed.  This value is scale-aware:
   `int(max(20, 250 * OUTPUT_SCALE²))` — at 30 % output that's ≈ 22 px², catching
   only single-pixel noise while preserving the eyes.  **Do not raise this above
   ~100 at 30 % scale** — the eyes will be classified as background.

4. **Alpha hole-fill** — inverts the alpha channel, flood-fills from borders to
   find *exterior* transparent regions; any transparent pixel unreachable from the
   border is an enclosed interior pocket and is forced back to fully opaque.
   This is the main defence against leftover green patches inside the silhouette.

**Tuning knobs in `process_scrat.py`:**

```python
GREEN_LOWER  = np.array([30,  25,  25])   # widen if edges are still greenish
GREEN_UPPER  = np.array([95, 255, 255])   # narrow H upper bound if eyes are clipped
ERODE_PX     = 1                          # px dilation of bg mask (fringe removal)
OUTPUT_SCALE = 0.30                       # final frame scale (0.1 – 1.0)
MIN_BLOB_AREA = int(max(20, 250 * OUTPUT_SCALE**2))  # keep low!
```

OpenCV uses H ∈ [0, 179], S/V ∈ [0, 255]. A studio green sits around H = 60–70.

Re-run `process_scrat.py` after any change — raw frames are re-extracted automatically.

---

## 5 — Web integration

The pipeline writes assets **directly** to the serving location — no copying needed:

```
frontend/_apriori/schpezial/assets/spritesheet.png
frontend/_apriori/schpezial/assets/scrat_audio.mp3
frontend/_apriori/schpezial/assets/meta.json
frontend/_apriori/schpezial/assets/frames/   ← individual PNGs, keep for re-packing
```

`easter.js` fetches them as `_apriori/schpezial/assets/` relative to `vp_routing.html`.

> **Status: complete.** `frontend/js/easter.js` is written and loaded in
> `vp_routing.html`.

### How the JS easter egg works

**Desktop-only guard**

The very first thing `easter.js` does is check
```js
window.matchMedia('(pointer: fine)').matches
```
`(pointer: fine)` is true only for a mouse or trackpad — i.e. a real desktop
browser. On any touch device the script returns immediately and nothing is
registered. This check is instant and runs zero code on mobile.

**Trigger sequence**

A single `input` event listener is attached to `#route_end` (the Ziel field).
Every keystroke compares the **uppercased** current value against the suffix
`67FHNW67`. On match the code is silently stripped from the field (so it
doesn't confuse the geocoder) and the animation fires.

**Lazy asset loading**

No assets are fetched until the trigger fires for the first time:

1. `fetch('assets/easter/meta.json')` — tiny JSON, describes the sprite layout
2. `new Image()` loads `spritesheet.png`
3. `new Audio()` loads and immediately plays `scrat_audio.mp3`
   (silently ignored if autoplay is blocked)

**Sprite-sheet animation**

A `<canvas>` is appended to `<body>`:
- `position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%)`
  — centred above the playback bar
- `pointer-events: none` — doesn't interfere with map interaction
- `z-index: 9999` — on top of everything

`requestAnimationFrame` steps through the sprite sheet at 30 fps by computing
`(col, row)` from the frame index and calling `ctx.drawImage()` with the
corresponding source rect. After the last frame the canvas fades out (CSS
transition) and is removed from the DOM. `running` is reset so the egg can
fire again.

---

## Changelog

| Date | Action |
|------|--------|
| 2026-05-20 | Created conda env `secret` (python 3.11, ffmpeg 8.1.1, opencv-python 4.13, pillow 12.2, numpy 2.4) |
| 2026-05-20 | Wrote `process_scrat.py` — full frame extract + chroma-key + sprite sheet pipeline |
| 2026-05-20 | Wrote `environment.yml` for env reproducibility |
| 2026-05-20 | Wrote this guide |
| 2026-05-20 | Wrote `frontend/js/easter.js` — desktop-only guard + lazy asset load + sprite-sheet animation |
| 2026-05-20 | Added `easter.js` to `vp_routing.html` script load order (last, after `ui.js`) |
| 2026-05-20 | Requirement: easter egg is **desktop-only** (`(pointer: fine)` media-query guard) |
| 2026-05-20 | Green-screen fix: replaced simple HSV mask with border flood-fill (8-conn) — preserves Scrat's green eyes |
| 2026-05-20 | Green-screen fix: added connected-component blob removal for interior noise + alpha hole-fill pass |
| 2026-05-20 | Widened HSV range to `[30,25,25]–[95,255,255]`, raised `MIN_BLOB_AREA` to 500 — too aggressive (eyes removed) |
| 2026-05-20 | Reverted `MIN_BLOB_AREA` to scale-aware formula `int(max(20, 250 × OUTPUT_SCALE²))` — ~22 px² at 30 % scale |
| 2026-05-20 | Fixed `NameError`: moved `OUTPUT_SCALE` definition before `MIN_BLOB_AREA` in constants block |
