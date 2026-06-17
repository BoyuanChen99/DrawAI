# SVG Layer Animation Promo Workflow

## Purpose

This document records the production method used for the DrawAI promotional
animation that turns a static scientific figure into an exploded editable SVG
layer view.

The goal is not to add a production feature to DrawAI. The goal is to describe a
repeatable visual-making workflow for demos, launch videos, social posts, and
internal product storytelling.

No temporary rendering scripts, generated HTML scenes, frame sequences, videos,
or experiment-only code should be committed to this repository unless explicitly
requested.

## Source Inputs

Use a completed DrawAI case as the source of truth:

- Original bitmap figure: `inputs/figure.png`
- Final semantic SVG: `svg/semantic.svg`
- Optional rendered SVG preview: `svg/rendered.png`
- Optional run reports: `reports/pipeline_summary.json`,
  `reports/element_analysis_codex/element_analysis.json`

The animation should be generated from the final SVG whenever possible. The
original bitmap is used for the opening shot and for visual continuity during the
scan phase.

## Visual Story

The current preferred storyboard is:

1. Show the original bitmap full width on a clean white background.
2. Sweep a red scan line over the figure.
3. As the scan passes, reveal and highlight the actual SVG elements under the
   scan, not rectangular debug boxes.
4. Rotate the figure plane backward in 3D.
5. Lift SVG layers away from the plane.
6. Show that the output is made of independent editable objects: text, boxes,
   arrows, bars, images, and panels separate from one another.

The end state should feel like a clean exploded-view diagram rather than a
random particle burst.

## Layer Extraction Strategy

Use SVG painter order as the basic z-order model:

- Earlier DOM elements are lower visual layers.
- Later DOM elements are higher visual layers.
- Higher visual layers should start earlier and fly higher.
- Lower visual layers should start later and remain closer to the base plane.

Start with the final `semantic.svg`. Preserve document order while extracting
layers.

For a coarse version, top-level groups can be treated as layers, with arrows
split out from connector-heavy groups. This is fast and readable, but some groups
remain too coarse.

For the current preferred version, decompose the SVG into primitive visual
layers:

- `text` elements become text layers.
- `rect` elements with strokes or no fill become frame or box layers.
- filled `rect` elements become shape or bar layers.
- `line`, `polyline`, and arrow-like `path` elements become arrow or connector
  layers.
- `path`, `ellipse`, `circle`, and `polygon` elements become shape layers.
- `image` elements become image layers.

This primitive-level split is important because it shows editability. A label
and the box around it should not move as one object; they should separate at
different heights.

## Text And Box Separation

Text and frame layers should be intentionally decoupled:

- Text layers start slightly earlier than their enclosing frames.
- Text layers rise higher in Z and move farther upward on screen.
- Frame layers stay lower and launch later.
- This contrast should be visible in early float frames and in the final exploded
  view.

This makes it clear that DrawAI produced editable text and editable geometry,
not a single flattened raster or grouped screenshot.

## Special Cases

Some SVG groups contain meaningful repeated sub-elements. If using a coarse
extractor, manually split these cases before rendering:

- vector bars in the left clustering panel
- transformer arrows
- embedding inset arrows
- connector groups
- repeated chart marks, ticks, or legend swatches

For the example animation, the left clustering panel was improved by splitting
its vector bars from the panel base. The final primitive-level approach makes
that split automatic because each bar is a separate `rect`.

## Motion Mapping

Each layer receives deterministic motion parameters:

- `delay`: when the layer starts lifting
- `dx`: horizontal drift
- `dy`: upward screen travel
- `dz`: height above the tilted base plane
- `rx`, `ry`, `rz`: small rotation offsets

Recommended mapping:

- Compute `topness = layer_index / max_layer_index`.
- Larger `topness` means lower delay and larger `dz`.
- Text receives an additional height and earlier-start boost.
- Frames receive a lower-height and later-start adjustment.
- Arrows receive moderate extra height so connectors read clearly.
- Images receive only a small height boost unless they are a key subject.

The motion must remain deterministic for the same SVG. Do not use runtime random
motion unless the random seed is fixed.

## Scan Highlight

The scan phase should highlight the SVG itself:

- Use the layer bounding box or center point to determine when the scan intersects
  a layer.
- Temporarily reveal the matching SVG layer even before the full SVG stack fades
  in.
- Apply red highlight to the actual layer.
- For arrows and connectors, change the actual stroke to red during the hit.
- Avoid showing debug rectangles as the primary highlight.

The scan should communicate that the system is identifying real editable SVG
objects.

## Background And Camera

Use a white background for the current preferred version. The white background is
cleaner for product demos and keeps the scientific figure readable.

Recommended camera behavior:

- Start with a full-width, no-black-border original image.
- Tilt the figure backward around its lower edge.
- Keep the final tilt strong but not so flat that height differences collapse.
- Use enough perspective to show Z separation without distorting text beyond
  recognition.

For the current example, a final tilt around 58 to 64 degrees works better than a
near-flat 72 degree tilt when the highest layers need to remain visible.

## Rendering Quality

Keep the master video at:

- 1920 x 1080
- 30 fps
- 8 to 10 seconds
- H.264 MP4, yuv420p, CRF around 18

Generate a GIF only as a lightweight preview. The GIF can be downscaled to
around 960 px wide and 12 fps.

Avoid always-on heavy SVG filters or large dynamic drop-shadows for every layer.
They slow browser rendering and can blur text. Prefer:

- no default filter, or very light shadows
- scan-hit glow only
- clean white background
- high-resolution PNG frame capture before video encoding

## Output Artifacts

Store generated artifacts outside the repository, under the experiment report
directory for the source run.

Typical outputs:

- `promo_scene.html`
- `scene_manifest.json`
- `frames/frame_0000.png` through the final frame
- `promo_*.mp4`
- `promo_*.gif`
- `storyboard.png`
- `preview_*.png`

The repository should keep only this workflow document unless the user asks to
turn the workflow into production code.

## Version Notes From The Example

The example evolved through these useful checkpoints:

- Coarse layer split: top-level SVG groups and selected arrows.
- Direct SVG scan highlight: highlight the SVG itself instead of overlay boxes.
- White background: keep the final demo clean and shareable.
- SVG painter-order motion: higher DOM layers start earlier and fly higher.
- Left panel bar split: repeated vector bars can be separated from panel bases.
- Primitive split: text, frames, arrows, shapes, and images all become separate
  layers.
- High-clear render: keep 1920 x 1080 quality while reducing always-on blur and
  expensive filters.

The current preferred mode is the primitive split with text and boxes decoupled,
white background, SVG-object scan highlight, and high-clear rendering.

## Repository Boundary

Do not commit experiment-only code by default:

- temporary animation builders
- generated HTML scenes
- frame folders
- generated MP4 or GIF files
- one-off Playwright or ffmpeg wrapper scripts

If this workflow becomes a product feature later, implement it deliberately as a
separate tool with tests, stable inputs, and documented outputs. Until then, keep
the repository limited to the method documentation.
