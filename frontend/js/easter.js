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

  // ── Trigger: lazy-load assets, start audio + animation together ─────────────
  function trigger() {
    if (running) return;
    running = true;

    fetch(ASSET_DIR + 'meta.json')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (meta) {
        var audio = new Audio(ASSET_DIR + meta.audioFile);
        audio.preload = 'auto';

        var img = new Image();
        img.onload = function () {
          var playPromise = audio.play();

          // 'playing' fires when audio is actually outputting — use it as the
          // starting gun so frame 0 is drawn at the same instant as sample 0.
          audio.addEventListener('playing', function onPlaying() {
            audio.removeEventListener('playing', onPlaying);
            animate(img, meta, audio);
          }, { once: true });

          // Autoplay blocked → animate without audio
          if (playPromise !== undefined) {
            playPromise.catch(function () {
              animate(img, meta, null);
            });
          }
        };
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
  function animate(spriteImg, meta, audioEl) {
    var fw    = meta.frameWidth;
    var fh    = meta.frameHeight;
    var cols  = meta.cols;
    var total = meta.totalFrames;
    var fps   = meta.fps;

    // Frames are already at 30 % of original resolution — render at 100 %
    var dw = fw;
    var dh = fh;

    // Anchor canvas bottom to the top edge of #controls-flap (the label tab
    // above the playback bar).  Falls back to #controls if flap is absent.
    var ctrl = document.getElementById('controls-flap') ||
               document.getElementById('controls');
    var rect = ctrl ? ctrl.getBoundingClientRect() : { top: 80, left: 40 };
    var canvasBottom = window.innerHeight - rect.top;
    var canvasLeft   = rect.left - 18;

    var canvas   = document.createElement('canvas');
    canvas.width  = dw;
    canvas.height = dh;
    canvas.style.cssText =
      'position:fixed;' +
      'bottom:'  + canvasBottom + 'px;' +
      'left:'    + canvasLeft   + 'px;' +
      'pointer-events:none;z-index:9999;image-rendering:pixelated;';
    document.body.appendChild(canvas);

    var ctx      = canvas.getContext('2d');
    var rafFrame = 0;   // fallback counter when no audio clock

    function step() {
      // When audio is available use its clock — guarantees A/V sync even if
      // RAF fires late (background tab, jank, etc.).
      var idx = audioEl
        ? Math.min(Math.floor(audioEl.currentTime * fps), total - 1)
        : rafFrame++;

      var col = idx % cols;
      var row = Math.floor(idx / cols);
      ctx.clearRect(0, 0, dw, dh);
      ctx.drawImage(
        spriteImg,
        col * fw, row * fh, fw, fh,
        0, 0, dw, dh
      );

      var done = audioEl ? (audioEl.ended || idx >= total - 1) : rafFrame >= total;
      if (!done) {
        requestAnimationFrame(step);
      } else {
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
