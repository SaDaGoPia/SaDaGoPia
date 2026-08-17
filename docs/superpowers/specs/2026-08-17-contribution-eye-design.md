# Contribution-graph eye

## Goal

Add a second animated graphic to the profile: the real GitHub contribution
calendar (53 weeks x 7 days of dots, GitHub's real per-day colors), which
periodically transforms into one of two illustrated creature eyes, then back,
in a looping autoplay animation.

## Hard constraint

GitHub profile READMEs only render SVGs via `<img src="...">` (raw inline
`<svg>`/`<style>`/`<script>` in markdown is sanitized away). An `<img>`-embedded
SVG cannot receive hover or click events — no interactivity is possible.
Time-based SMIL/CSS animation (`<animate>`) *does* autoplay fine through
`<img>` (already proven by the existing `terminal.svg`'s blinking cursor and
boot-log reveal). Consequence: "blinks when you interact with it" is not
achievable on the real profile page. The feature is an always-looping,
autoplaying animation instead — same mechanism as the terminal graphic.

## Layout

All 371 real dots participate in the eye (no cropping, no repositioning).
Top and bottom rows become the eyelid; the middle five rows form one long,
full-width, horizontally elongated eye — closer to a dragon/reptile eye
shape than a round human one, which happens to match the grid's natural
53:7 aspect ratio well. Dots never move or resize; only their fill color
animates. The illusion of the eye (and later, of the eye looking around) is
created purely by which dots read as pupil/iris/sclera at a given moment.

Placement: a new `## Contributions` section in `README.md`, below the
existing terminal dashboard section, with its own `<img>` — not merged into
`terminal.svg`. The terminal keeps its own sci-fi aesthetic; the eye is a
separate, fantasy-themed graphic.

## Variants

**Ender** — the *Eye of Ender* item (the End Portal activator), not the
Enderman's eye. Pearled lavender-grey sclera/shell with grey marbling noise,
a swirling green-to-teal iris (color driven by radial distance *and* angle
from center, to mimic the item's spiral texture), black pupil.

**Smaug** — warm ember/gold dragon eye. Dark red-brown scaled sclera with
per-dot ember-flicker noise, a 5-band iris gradient from near-black red at
the pupil edge out through deep red, orange, amber, to pale gold at the rim,
black pupil.

Both variants share: a tapered, lens/ellipse-shaped pupil (widest at the
center row, pointed at top and bottom — a real slit-eye taper, not a
rectangle), a 5-stop iris gradient instead of a flat two-tone ring, per-dot
brightness noise for texture, and one fixed catchlight glint near the
upper-left of the pupil.

## Animation timeline

One full loop, all durations fixed/no interactivity:

1. Resting — real contribution-calendar colors, held **10s**
2. Blink — eyelid rows and iris/pupil area darken together, **~0.35s**
3. Ender eye open, with gaze movement, **~6.6s** total:
   - center (hold ~1s) -> glance left (~0.4s transition + 0.8s hold) ->
     back to center (~0.4s + 0.6s hold) -> glance right (~0.4s + 0.8s hold)
     -> back to center (~0.4s + 0.4s hold) -> glance up (~0.3s + 0.5s hold)
     -> back to center (~0.3s + 0.3s hold)
   - Gaze shift = recomputing each dot's color as if the pupil/iris center
     had translated a few columns/rows, then holding or interpolating
     between those precomputed color sets. No element moves; only colors do.
4. Blink — **~0.35s**
5. Resting — real colors, held **10s**
6. Blink — **~0.35s**
7. Smaug eye open, same gaze sequence shape as step 3, **~6.6s**
8. Blink — **~0.35s**, loop back to step 1

Total loop ≈ 34.6s. All 371 dots share one `keyTimes` sequence (they're
synchronized); only the per-dot `values` (colors) differ, driven by that
dot's grid position, so the blink reads as one eyelid across the whole
strip rather than per-dot flicker.

## Data source

GitHub only exposes the daily contribution calendar via GraphQL
(`contributionsCollection.contributionCalendar`), which requires a token
with `read:user` scope — the workflow's existing auto-generated
`GITHUB_TOKEN` cannot do this query regardless of its `permissions:` block.
A new `CONTRIB_TOKEN` repo secret (classic PAT, `read:user` scope) is
required. Each day's `color` field from the API is used directly as that
dot's resting-state fill — GitHub has already computed the correct shade,
no re-bucketing needed.

## Caching / anti-spam

The fetched calendar folds into the existing `.stats_cache.json` alongside
REPOS/STARS/COMMITS/FOLLOWERS. Same rule as before: the rendered date only
advances (and a commit only happens) when the cached blob actually changes.
In practice the calendar changes at least once a day as the rolling 53-week
window shifts, which keeps commit frequency at roughly once a day even
though the workflow itself still runs hourly — consistent with the
anti-spam fix already shipped, not a regression of it.

## Error handling

- Missing `CONTRIB_TOKEN` -> hard `RuntimeError` at startup, same pattern as
  the existing missing-`GITHUB_USERNAME` check. No silent degradation.
- GraphQL request failures (bad scope, rate limit, network) -> caught and
  re-raised as a clear `RuntimeError`, same pattern as the existing REST
  error handling.

## Implementation shape

- New module `contribution_eye.py`: color math (seeded per-dot noise, hex
  mix/shade helpers, an `eye_color(col, row, cols, rows, variant,
  gaze_offset)` function) and an SVG-builder that assembles all `<circle>`
  elements with their shared `keyTimes` and per-dot `values`.
- `today.py` gains `get_contribution_calendar()` (GraphQL fetch) and calls
  into `contribution_eye.py` to render `assets/contribution-eye.svg`,
  following the same cache-then-write flow already used for the terminal
  SVG and README.
- `template.md` gains a `## Contributions` section referencing
  `./assets/contribution-eye.svg`.
- `.github/workflows/update.yml` passes `CONTRIB_TOKEN` from secrets as an
  env var, and stages `assets/contribution-eye.svg` in the commit step.

## Testing

No automated test suite exists in this project and one isn't proposed here
— consistent with how the terminal graphic was verified. Verification is a
local `today.py` run inspected visually, plus confirming the cache-diff
logic still suppresses no-op commits with the calendar folded in.

## File size

371 dots x roughly a dozen color keyframes each (resting, blink, 5 gaze
positions x 2 variants, blinks) puts the generated SVG in the tens-of-KB
range — the existing `terminal.svg` is 6KB; this is a proportionate step up
and not a concern for an `<img>`-embedded README asset.
