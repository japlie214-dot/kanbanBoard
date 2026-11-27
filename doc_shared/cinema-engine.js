/* doc_shared/cinema-engine.js — KanbanBoard v4.0.1 Retro Widescreen Motion Kit
 * Strict-CSP compliant (zero inline styles).
 * Closed-form springs, seeded Mulberry32 RNG, on-2s boil, 4x4 Bayer dithering,
 * high-contrast text pockets, beat capsule HUD, and clickable Chapter Progress Bar.
 */
(function (global) {
  "use strict";

  const BAYER_4X4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
  ];

  const SPRING = {
    snappy:  { omega: 14.0, zeta: 0.72 },
    smooth:  { omega: 9.0,  zeta: 0.88 },
    heavy:   { omega: 7.5,  zeta: 0.78 },
    playful: { omega: 12.0, zeta: 0.52 },
  };

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function snap(v) { return Math.round(v) | 0; }

  function springProgress(t, t0, preset) {
    const dt = t - t0;
    if (dt <= 0) return 0;
    const p = SPRING[preset] || SPRING.snappy;
    const wd = p.omega * Math.sqrt(Math.max(0.001, 1 - p.zeta * p.zeta));
    const decay = Math.exp(-p.zeta * p.omega * dt);
    const val = 1 - decay * (Math.cos(wd * dt) + (p.zeta / Math.sqrt(1 - p.zeta * p.zeta)) * Math.sin(wd * dt));
    return dt > 2.2 ? 1 : val;
  }

  function springMove(t, t0, from, to, preset) {
    return from + (to - from) * springProgress(t, t0, preset);
  }

  function springTrack(t, keyframes, preset) {
    if (!keyframes || !keyframes.length) return 0;
    let val = keyframes[0][1];
    for (let i = 1; i < keyframes.length; i++) {
      const [kt, kv] = keyframes[i];
      if (t >= kt) val = springMove(t, kt, val, kv, preset);
    }
    return val;
  }

  function easeOutCubic(u) { const c = clamp(u, 0, 1); return 1 - Math.pow(1 - c, 3); }
  function easeInQuad(u) { const c = clamp(u, 0, 1); return c * c; }
  function stagger(t, idx, stepSec) { return t - idx * (stepSec || 0.1); }
  function breathe(t, amp, freq) { return Math.sin(t * (freq || 2.4)) * (amp || 1.4); }
  function boilStep(t, fps) { return Math.floor(t * (fps || 8)); }

  function createRNG(seed) {
    let a = (seed >>> 0) || 1;
    return function () {
      a = (a + 0x6D2B79F5) | 0;
      let r = Math.imul(a ^ (a >>> 15), 1 | a);
      r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  function ditherRect(ctx, x, y, w, h, colorA, colorB, ratio) {
    const rx = snap(x), ry = snap(y), rw = snap(w), rh = snap(h);
    const thr = clamp(ratio, 0, 1) * 16;
    ctx.fillStyle = colorA;
    ctx.fillRect(rx, ry, rw, rh);
    if (thr <= 0) return;
    ctx.fillStyle = colorB;
    for (let py = 0; py < rh; py += 2) {
      for (let px = 0; px < rw; px += 2) {
        if (BAYER_4X4[(py >> 1) & 3][(px >> 1) & 3] < thr) {
          ctx.fillRect(rx + px, ry + py, 2, 2);
        }
      }
    }
  }

  function drawCallout(ctx, x, y, text, opts) {
    const o = typeof opts === "string" ? { border: opts } : (opts || {});
    ctx.save();
    ctx.globalAlpha = clamp(o.alpha == null ? 1 : o.alpha, 0, 1);
    ctx.font = "bold 9px monospace";
    const tw = Math.ceil(ctx.measureText(text).width);
    const bx = snap(x), by = snap(y), bw = tw + 12, bh = 17;
    ctx.fillStyle = o.bg || "#0B0D12";
    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeStyle = o.border || "#5EEAD4";
    ctx.lineWidth = 1;
    ctx.strokeRect(bx + 0.5, by + 0.5, bw - 1, bh - 1);
    ctx.fillStyle = o.fg || "#F8FAFC";
    ctx.fillText(text, bx + 6, by + 11);
    ctx.restore();
  }

  function drawHudCapsule(ctx, beatIdx, totalBeats, label) {
    const txt = `BEAT ${beatIdx + 1}/${totalBeats} · ${label}`;
    ctx.font = "bold 9px monospace";
    const tw = Math.ceil(ctx.measureText(txt).width);
    ctx.fillStyle = "#0B0D12";
    ctx.fillRect(10, 8, tw + 12, 16);
    ctx.strokeStyle = "#4D8BFF";
    ctx.strokeRect(10.5, 8.5, tw + 11, 15);
    ctx.fillStyle = "#F2F0E8";
    ctx.fillText(txt, 16, 19);
  }

  function drawScanlinesAndVignette(ctx, width, height) {
    ctx.fillStyle = "rgba(0,0,0,0.13)";
    for (let y = 0; y < height; y += 3) ctx.fillRect(0, y, width, 1);
  }

  function createCinemaStage(container, opts) {
    const o = opts || {};
    const width = 480;
    const height = 270;
    const duration = Number(o.duration) > 0 ? Number(o.duration) : 9.0;
    const beats = Array.isArray(o.beats) ? o.beats : [];

    container.innerHTML = "";
    const frame = document.createElement("div");
    frame.className = "cinema-frame";

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.className = "cinema-canvas";
    frame.appendChild(canvas);

    const chapBtns = [];
    if (beats.length) {
      const strip = document.createElement("div");
      strip.className = "chapter-strip";
      beats.forEach((b, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chap-btn";
        const span = document.createElement("span");
        span.textContent = b.label || `BEAT ${idx + 1}`;
        btn.appendChild(span);
        btn.addEventListener("click", () => {
          elapsed = Number(b.start || 0) + 0.02;
          lastNow = performance.now();
        });
        strip.appendChild(btn);
        chapBtns.push(btn);
      });
      frame.appendChild(strip);
    }

    const bar = document.createElement("div");
    bar.className = "cinema-bar";

    const playBtn = document.createElement("button");
    playBtn.type = "button";
    playBtn.className = "hw-btn";
    playBtn.textContent = "Pause";
    bar.appendChild(playBtn);

    const restartBtn = document.createElement("button");
    restartBtn.type = "button";
    restartBtn.className = "hw-btn";
    restartBtn.textContent = "Restart";
    bar.appendChild(restartBtn);

    const scrubBox = document.createElement("label");
    scrubBox.className = "scrub-box";
    const scrubLbl = document.createElement("span");
    scrubLbl.textContent = o.scrubberLabel || "Timeline";
    const scrubber = document.createElement("input");
    scrubber.type = "range";
    scrubber.min = "0";
    scrubber.max = "1000";
    scrubber.value = "0";
    const timeOut = document.createElement("span");
    timeOut.textContent = "0.0s";
    scrubBox.appendChild(scrubLbl);
    scrubBox.appendChild(scrubber);
    scrubBox.appendChild(timeOut);
    bar.appendChild(scrubBox);

    frame.appendChild(bar);
    container.appendChild(frame);

    const ctx = canvas.getContext("2d");
    let playing = true;
    let elapsed = 0;
    let lastNow = performance.now();
    let rafId = 0;

    playBtn.addEventListener("click", () => {
      playing = !playing;
      playBtn.textContent = playing ? "Pause" : "Play";
      lastNow = performance.now();
    });
    restartBtn.addEventListener("click", () => {
      elapsed = 0;
      lastNow = performance.now();
    });
    scrubber.addEventListener("input", () => {
      elapsed = (Number(scrubber.value) / 1000) * duration;
      lastNow = performance.now();
    });

    function onKey(e) {
      if (e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
      if (e.code === "Space") { e.preventDefault(); playBtn.click(); }
      else if (e.key === "r" || e.key === "R") { elapsed = 0; lastNow = performance.now(); }
    }
    window.addEventListener("keydown", onKey);

    function loop(now) {
      const dt = Math.min(0.05, (now - lastNow) / 1000);
      lastNow = now;
      if (playing) elapsed = (elapsed + dt) % duration;
      if (typeof o.render === "function") {
        ctx.save();
        ctx.imageSmoothingEnabled = false;
        o.render(ctx, {
          t: elapsed,
          duration,
          width,
          height,
          snap,
          clamp,
          springMove,
          springTrack,
          springProgress,
          easeOutCubic,
          easeInQuad,
          stagger,
          breathe,
          boilStep,
          createRNG,
          ditherRect,
          drawCallout,
          drawHudCapsule,
          drawScanlinesAndVignette,
        });
        ctx.restore();
      }
      scrubber.value = String(Math.round((elapsed / duration) * 1000));
      timeOut.textContent = elapsed.toFixed(1) + "s";
      beats.forEach((b, i) => {
        if (chapBtns[i]) {
          chapBtns[i].classList.toggle("active", elapsed >= Number(b.start) && elapsed < Number(b.end));
        }
      });
      rafId = requestAnimationFrame(loop);
    }
    rafId = requestAnimationFrame(loop);

    return {
      canvas,
      ctx,
      destroy: function () {
        if (rafId) cancelAnimationFrame(rafId);
        window.removeEventListener("keydown", onKey);
      },
    };
  }

  global.CinemaEngine = {
    WIDTH: 480,
    HEIGHT: 270,
    BAYER_4X4,
    SPRING,
    clamp,
    snap,
    springProgress,
    springMove,
    springTrack,
    easeOutCubic,
    easeInQuad,
    stagger,
    breathe,
    boilStep,
    createRNG,
    ditherRect,
    drawCallout,
    drawHudCapsule,
    drawScanlinesAndVignette,
    createCinemaStage,
  };
})(window);
