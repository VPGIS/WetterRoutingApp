"""
Easter egg asset pipeline for scrat.mp4
----------------------------------------
Drop scrat.mp4 into this folder, then run:

    conda run -n secret python process_scrat.py

Steps
-----
1. Extract frames at 30 fps            → out/raw_frames/
2. Extract audio as MP3                → out/scrat_audio.mp3
3. Remove green screen (HSV mask)      → out/frames/  (RGBA PNGs)
4. Pack a sprite sheet                 → out/spritesheet.png
5. Write frame metadata                → out/meta.json

Tune GREEN_LOWER / GREEN_UPPER if the matte is imperfect.
"""

import subprocess, json, shutil
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

# ── paths ─────────────────────────────────────────────────────────────────────
HERE   = Path(__file__).parent
VIDEO  = HERE / "scrat.mp4"
OUT    = HERE / "assets"          # served as _apriori/schpezial/assets/
FRAMES = OUT / "frames"
AUDIO  = OUT / "scrat_audio.mp3"
META   = OUT / "meta.json"
SPRITE = OUT / "spritesheet.png"

# ── green-screen HSV thresholds (OpenCV: H 0-179, S 0-255, V 0-255) ──────────
GREEN_LOWER = np.array([30,  25,  25])
GREEN_UPPER = np.array([95, 255, 255])

# ── fringe erode (px): dilates the green mask to eat chromatic fringing ───────
ERODE_PX = 1
# ── output scale applied after chroma-key ────────────────────────────────────
# 0.30 = 30 % of original frame resolution → smaller sprite sheet, faster load
OUTPUT_SCALE = 0.30
# ── small isolated green blob removal ────────────────────────────────────────
# Interior green blobs smaller than this area (px²) are treated as background
# noise and made transparent. Keep this low — the alpha hole-fill below handles
# larger enclosed patches. Value is intentionally scale-aware: at 30 % output
# only tiny single-pixel specks should be caught here; real features survive.
MIN_BLOB_AREA = int(max(20, 250 * OUTPUT_SCALE ** 2))
# ── sprite sheet layout ───────────────────────────────────────────────────────
SHEET_COLS = 10


# ─────────────────────────────────────────────────────────────────────────────
def check_video():
    if not VIDEO.exists():
        raise FileNotFoundError(
            f"\n  scrat.mp4 not found at:\n  {VIDEO}\n"
            "  Drop the video into this folder and re-run."
        )


def extract_frames():
    """Use ffmpeg to dump every frame at exactly 30 fps as PNG."""
    raw = OUT / "raw_frames"
    raw.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(VIDEO),
        "-vf", "fps=30",
        str(raw / "frame_%05d.png"),
    ]
    print("▶ Extracting frames …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        raise RuntimeError("ffmpeg frame extraction failed.")
    frames = sorted(raw.glob("frame_*.png"))
    print(f"  → {len(frames)} frames")
    return frames


def extract_audio():
    """Extract audio track to MP3 (VBR ~190 kbps)."""
    cmd = [
        "ffmpeg", "-y", "-i", str(VIDEO),
        "-vn", "-q:a", "2",
        str(AUDIO),
    ]
    print("▶ Extracting audio …")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        raise RuntimeError("ffmpeg audio extraction failed.")
    print(f"  → {AUDIO.name}  ({AUDIO.stat().st_size // 1024} KB)")


def remove_green(bgr: np.ndarray) -> np.ndarray:
    """Return BGRA image. Only background green (pixels reachable from any
    image border) is made transparent. Interior green — eyes, markings, etc. —
    is fully surrounded by non-green pixels and is never reached by the fill,
    so it is preserved as-is."""

    h, w = bgr.shape[:2]
    hsv        = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green_mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)   # 255 = green

    # ── Flood-fill background green from all four edges ───────────────────────
    # Any green pixel connected to the border belongs to the background (→ 128).
    # Interior green (e.g. Scrat's eyes) stays at 255 and is kept opaque.
    temp    = green_mask.copy()
    ff_mask = np.zeros((h + 2, w + 2), np.uint8)   # required by floodFill

    # 8-connectivity catches diagonal border paths that 4-connectivity misses
    FF_FLAGS = 8
    for x in range(w):
        if temp[0,     x] == 255: cv2.floodFill(temp, ff_mask, (x, 0),     128, flags=FF_FLAGS)
        if temp[h - 1, x] == 255: cv2.floodFill(temp, ff_mask, (x, h - 1), 128, flags=FF_FLAGS)
    for y in range(h):
        if temp[y,     0] == 255: cv2.floodFill(temp, ff_mask, (0,     y), 128, flags=FF_FLAGS)
        if temp[y, w - 1] == 255: cv2.floodFill(temp, ff_mask, (w - 1, y), 128, flags=FF_FLAGS)

    # bg_mask: 255 = background green (remove), 0 = keep
    bg_mask = (temp == 128).astype(np.uint8) * 255

    # ── Remove small isolated interior green blobs (background noise) ─────────
    # Any remaining green blob (temp == 255) smaller than MIN_BLOB_AREA px²
    # is a stray speck, not a real feature like an eye — make it transparent.
    interior = (temp == 255).astype(np.uint8)
    if interior.any():
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            interior, connectivity=8
        )
        for lbl in range(1, n_labels):
            if stats[lbl, cv2.CC_STAT_AREA] < MIN_BLOB_AREA:
                bg_mask[labels == lbl] = 255

    # ── Fringe suppression ────────────────────────────────────────────────────
    if ERODE_PX > 0:
        kernel  = np.ones((ERODE_PX * 2 + 1, ERODE_PX * 2 + 1), np.uint8)
        bg_mask = cv2.dilate(bg_mask, kernel, iterations=1)

    alpha = cv2.bitwise_not(bg_mask)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)

    # ── Fill enclosed transparent holes in the alpha channel ─────────────────
    # Any transparent (0) region not reachable from the image border is an
    # interior pocket (e.g. a stubborn green patch inside the silhouette).
    # Flood-fill such pockets back to opaque (255) so they don’t appear as
    # holes in the final sprite.
    inv_alpha = cv2.bitwise_not(alpha)           # transparent=255, opaque=0
    fill_temp = inv_alpha.copy()
    ff2       = np.zeros((h + 2, w + 2), np.uint8)
    FF_FLAGS2 = 8
    for x in range(w):
        if fill_temp[0,     x] == 255: cv2.floodFill(fill_temp, ff2, (x, 0),     128, flags=FF_FLAGS2)
        if fill_temp[h - 1, x] == 255: cv2.floodFill(fill_temp, ff2, (x, h - 1), 128, flags=FF_FLAGS2)
    for y in range(h):
        if fill_temp[y,     0] == 255: cv2.floodFill(fill_temp, ff2, (0,     y), 128, flags=FF_FLAGS2)
        if fill_temp[y, w - 1] == 255: cv2.floodFill(fill_temp, ff2, (w - 1, y), 128, flags=FF_FLAGS2)
    # Pixels still 255 = interior transparent pockets → restore to opaque
    alpha[fill_temp == 255] = 255

    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def process_frames(raw_frames):
    """Green-screen removal + resize for every raw frame; saves to out/frames/."""
    FRAMES.mkdir(parents=True, exist_ok=True)
    print(f"▶ Removing green screen ({len(raw_frames)} frames) …")
    for i, path in enumerate(raw_frames):
        bgr  = cv2.imread(str(path))
        bgra = remove_green(bgr)
        if OUTPUT_SCALE != 1.0:
            nw = max(1, int(bgra.shape[1] * OUTPUT_SCALE))
            nh = max(1, int(bgra.shape[0] * OUTPUT_SCALE))
            bgra = cv2.resize(bgra, (nw, nh), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(FRAMES / f"frame_{i:05d}.png"), bgra)
        if (i + 1) % 30 == 0:
            print(f"   {i + 1}/{len(raw_frames)}")
    print("  → done")
    return sorted(FRAMES.glob("frame_*.png"))


def build_spritesheet(clean_frames):
    """Pack all RGBA frames into a single PNG sprite sheet."""
    print("▶ Building sprite sheet …")
    sample     = Image.open(clean_frames[0]).convert("RGBA")
    fw, fh     = sample.size
    n          = len(clean_frames)
    cols, rows = SHEET_COLS, (n + SHEET_COLS - 1) // SHEET_COLS

    sheet = Image.new("RGBA", (fw * cols, fh * rows), (0, 0, 0, 0))
    for i, path in enumerate(clean_frames):
        sheet.paste(Image.open(path).convert("RGBA"), ((i % cols) * fw, (i // cols) * fh))

    sheet.save(str(SPRITE), optimize=True)
    print(f"  → spritesheet.png  ({cols}×{rows} grid, {fw}×{fh} px/frame, {SPRITE.stat().st_size // 1024} KB)")
    return fw, fh, cols, rows, n


def write_meta(fw, fh, cols, rows, n_frames):
    meta = {
        "frameWidth":      fw,
        "frameHeight":     fh,
        "cols":            cols,
        "rows":            rows,
        "totalFrames":     n_frames,
        "fps":             30,
        "spritesheetFile": "spritesheet.png",
        "audioFile":       "scrat_audio.mp3",
    }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("  → meta.json written")


def cleanup_raw():
    raw = OUT / "raw_frames"
    if raw.exists():
        shutil.rmtree(raw)
        print("  → raw frames cleaned up")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    check_video()
    OUT.mkdir(parents=True, exist_ok=True)

    raw_frames   = extract_frames()
    extract_audio()
    clean_frames = process_frames(raw_frames)
    fw, fh, cols, rows, n = build_spritesheet(clean_frames)
    write_meta(fw, fh, cols, rows, n)
    cleanup_raw()

    print("\n✓ All done!  Assets are in:", OUT)
    print("  spritesheet.png   — sprite sheet (RGBA PNG)")
    print("  scrat_audio.mp3   — audio track")
    print("  meta.json         — frame metadata for the JS easter egg")
    print("  frames/           — individual RGBA PNGs (keep for re-packing)")
    print("\nServed from the HTML as: _apriori/schpezial/assets/")
