/* doc_shared/cinema-engine.js
 * Universal 480x270 2D Retro Widescreen Cinema helper for KanbanBoard v4.0 SHOW mode.
 * Integer-snapped sprites, 4x4 Bayer dithering, passive annotated loops + optional scrubbers.
 */
(function (global) {
  "use strict";

  const BAYER_4X4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
  ];

  function snap(v) {
    return Math.round(v) | 0;
  }

  function hexToRgb(hex) {
    const h = String(hex || "#000000").replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function ditherRect(ctx, x, y, w, h, colorA, colorB, ratio) {
    const rx = snap(x), ry = snap(y), rw = snap(w), rh = snap(h);
    const t = Math.max(0, Math.min(1, ratio));
    ctx.fillStyle = colorA;
    ctx.fillRect(rx, ry, rw, rh);
    ctx.fillStyle = colorB;
    const threshold = t * 16;
    for (let py = 0; py < rh; py += 2) {
      for (let px = 0; px < rw; px += 2) {
        if (BAYER_4X4[(py >> 1) & 3][(px >> 1) & 3] < threshold) {
          ctx.fillRect(rx + px, ry + py, 2, 2);
        }
      }
    }
  }

  function drawCallout(ctx, x, y, text, opts) {
    const o = opts || {};
    const bg = o.bg || "#111622";
    const border = o.border || "#5eead4";
    const fg = o.fg || "#f8fafc";
    ctx.font = "bold 9px monospace";
    const padX = 5, padY = 4;
    const tw = Math.ceil(ctx.measureText(text).width);
    const bx = snap(x), by = snap(y), bw = tw + padX * 2, bh = 16;
    ctx.fillStyle = bg;
    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = border;
    ctx.lineWidth = 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, bw - 1, bh - 1);
    ctx.fillStyle = fg;
    ctx.fillText(text, bx + padX, by + 11);
  }

  function createCinemaStage(container, opts) {
    const o = opts || {};
    const width = 480;
    const height = 270;

    container.innerHTML = "";
    const wrap = document.createElement("div");
    wrap.className = "cinema-stage";

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.className = "cinema-canvas";
    wrap.appendChild(canvas);

    const bar = document.createElement("div");
    bar.className = "cinema-controls";
    const playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "cinema-btn";
    playBtn.textContent = "Pause";
    bar.appendChild(playBtn);

    let scrubber = null;
    let scrubVal = o.initialScrub != null ? o.initialScrub : 0;
    if (o.scrubberLabel) {
      const lbl = document.createElement("label");
      lbl.className = "cinema-scrubber";
      lbl.textContent = o.scrubberLabel + " ";
      scrubber = document.createElement("input");
      scrubber.type = "range";
      scrubber.min = String(o.scrubberMin != null ? o.scrubberMin : 0);
      scrubber.max = String(o.scrubberMax != null ? o.scrubberMax : 100);
      scrubber.value = String(scrubVal);
      scrubber.addEventListener("input", function () {
        scrubVal = Number(scrubber.value);
      });
      lbl.appendChild(scrubber);
      bar.appendChild(lbl);
    }

    const caption = document.createElement("span");
    caption.className = "cinema-caption";
    caption.textContent = o.caption || "";
    bar.appendChild(caption);

    wrap.appendChild(bar);
    container.appendChild(wrap);

    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;

    let playing = true;
    let rafId = 0;
    let startTs = performance.now();
    let elapsed = 0;

    playBtn.addEventListener("click", function () {
      playing = !playing;
      playBtn.textContent = playing ? "Pause" : "Play";
      if (playing) startTs = performance.now() - elapsed * 1000;
    });

    function loop(now) {
      if (playing) elapsed = (now - startTs) / 1000;
      if (typeof o.render === "function") {
        ctx.save();
        ctx.imageSmoothingEnabled = false;
        o.render(ctx, { t: elapsed, scrub: scrubVal, width, height, snap, ditherRect, drawCallout, hexToRgb });
        ctx.restore();
      }
      rafId = requestAnimationFrame(loop);
    }
    rafId = requestAnimationFrame(loop);

    return {
      canvas,
      ctx,
      destroy: function () {
        if (rafId) cancelAnimationFrame(rafId);
      },
      setCaption: function (txt) {
        caption.textContent = txt || "";
      },
    };
  }

  global.CinemaEngine = {
    WIDTH: 480,
    HEIGHT: 270,
    BAYER_4X4,
    snap,
    hexToRgb,
    ditherRect,
    drawCallout,
    createCinemaStage,
  };
})(window);
