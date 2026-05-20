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
GREEN_LOWER = np.array([35,  40,  40])
GREEN_UPPER = np.array([90, 255, 255])

# ── fringe erode (px): dilates the green mask to eat chromatic fringing ───────
ERODE_PX = 1

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
    """Return BGRA ndarray with green pixels made fully transparent."""
    hsv  = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, GREEN_LOWER, GREEN_UPPER)   # green pixels = 255

    if ERODE_PX > 0:
        k    = np.ones((ERODE_PX * 2 + 1, ERODE_PX * 2 + 1), np.uint8)
        mask = cv2.dilate(mask, k, iterations=1)        # eat fringe

    alpha = cv2.bitwise_not(mask)                        # non-green = opaque
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)           # soften edge

    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def process_frames(raw_frames):
    """Green-screen removal for every raw frame; saves to out/frames/."""
    FRAMES.mkdir(parents=True, exist_ok=True)
    print(f"▶ Removing green screen ({len(raw_frames)} frames) …")
    for i, path in enumerate(raw_frames):
        bgr  = cv2.imread(str(path))
        bgra = remove_green(bgr)
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
