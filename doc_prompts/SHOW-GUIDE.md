# SHOW Authoring Guide (480x270 Retro Widescreen Cinema)

Turn the subsection's current `tell_html` into an effortless, high-craft visual explanation.

## Motion Craft & Determinism
- Target `window.CinemaEngine` (`480x270` dark stage, integer-snapped sprites, 4x4 Bayer dithering).
- Keep `render(ctx, state)` a **tight**, pure function of `t`: use `springMove`, `stagger`, `breathe`, `createRNG(seed)`, and `boilStep`—zero `Math.random()` or `Date.now()`.
- Combine 2–3 properties on entrances (`opacity + y + scale`), stagger sibling elements by `0.08–0.15s`, make exits ~2x faster than entrances, and add subtle `breathe()` micro-motion on elements resting > 2s.
- Use concrete real-world metaphors or simplified product mini-UI; avoid abstract glowing orbs.
- Keep one `THEME` object at the top of `show.js` and supply `beats: [{label, start, end}]` for the clickable Chapter Progress Bar.
- Keep on-canvas callouts concise (`<= 48` chars) in high-contrast dark pockets; max two text levels per beat.

## Title, Subtitle & Companion Description
- `show_subtitle`: one punchy feeling/message headline shown only in SHOW mode.
- `show_companion_html`: 1–2 short paragraphs rendered underneath the canvas explaining the concept from a different angle or highlighting trade-offs/edge cases—never repeating the canvas callouts.
- Export `export function mountShow(container, engine, meta) { ... return stage; }` in `show_js`.
