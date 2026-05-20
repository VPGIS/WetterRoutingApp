// easter.js — Scrat animation easter egg
// Triggered by typing 67FHNW67 into the destination input (#route_end).
// Desktop-only: silently bails on touch/mobile devices.
(function () {
  'use strict';

  // ── Desktop guard ─────────────────────────────────────────────────────────
  // (pointer:fine) = mouse or trackpad = desktop browser.
  // Touch devices match (pointer:coarse) and are excluded entirely.
  if (!window.matchMedia('(pointer: fine)').matches) return;

  const TRIGGER   = '67FHNW67';
  const ASSET_DIR = '_apriori/schpezial/assets/';

  let running = false;

  // ── Attach listener after DOM is ready ────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    var input = document.getElementById('route_end');
    if (!input) return;

    input.addEventListener('input', function () {
      var val = input.value.toUpperCase();
      if (val.endsWith(TRIGGER)) {
        // Strip the code from the field so it doesn't confuse geocoding
        input.value = val.slice(0, -TRIGGER.length);
        trigger();
      }
    });
  });

  // ── Trigger: lazy-load assets, then animate ───────────────────────────────
  function trigger() {
    if (running) return;
    running = true;

    fetch(ASSET_DIR + 'meta.json')
      .then(function (r) { return r.json(); })
      .then(function (meta) {
        // Preload audio; autoplay may be blocked — ignore silently
        var audio = new Audio(ASSET_DIR + meta.audioFile);
        audio.play().catch(function () {});

        var img   = new Image();
        img.onload = function () { animate(img, meta, audio); };
        img.onerror = function () {
          console.warn('[easter egg] sprite sheet not found');
          running = false;
        };
        img.src = ASSET_DIR + meta.spritesheetFile;
      })
      .catch(function (err) {
        console.warn('[easter egg] meta.json not found:', err);
        running = false;
      });
  }

  // ── Canvas sprite-sheet animation ─────────────────────────────────────────
  function animate(spriteImg, meta, audio) {
    var fw    = meta.frameWidth;
    var fh    = meta.frameHeight;
    var cols  = meta.cols;
    var total = meta.totalFrames;
    var mspf  = 1000 / meta.fps;   // ms per frame

    // Canvas overlay — centred, above the playback bar, no pointer events
    var canvas       = document.createElement('canvas');
    canvas.width     = fw;
    canvas.height    = fh;
    canvas.style.cssText =
      'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);' +
      'pointer-events:none;z-index:9999;image-rendering:pixelated;';
    document.body.appendChild(canvas);

    var ctx      = canvas.getContext('2d');
    var frameIdx = 0;
    var lastTime = null;

    function step(ts) {
      if (lastTime === null) lastTime = ts;

      if (ts - lastTime >= mspf) {
        lastTime = ts;
        var col = frameIdx % cols;
        var row = Math.floor(frameIdx / cols);
        ctx.clearRect(0, 0, fw, fh);
        ctx.drawImage(
          spriteImg,
          col * fw, row * fh, fw, fh,   // source rect in sprite sheet
          0, 0, fw, fh                   // destination on canvas
        );
        frameIdx++;
      }

      if (frameIdx < total) {
        requestAnimationFrame(step);
      } else {
        // Fade out, then remove
        canvas.style.transition = 'opacity 0.5s';
        canvas.style.opacity    = '0';
        setTimeout(function () {
          canvas.remove();
          running = false;
        }, 550);
      }
    }

    requestAnimationFrame(step);
  }
})();
