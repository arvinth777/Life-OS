# Pixel / voxel refresh

## Existing interface audit

- Structure: nine modules plus settings, with stable hash routes, grouped navigation, forms, and owner sign-in.
- Brand: Life OS wordmark, cobalt accent, Avenir/system sans, white surfaces, 6/10 px corners.
- Useful content: daily totals, real streaks, tasks, agenda, learning entry point, and reminders; no invented progress.
- Preserve: all module labels, routes, content, controls, keyboard focus, authentication, and persistence.
- Retire: uniformly flat panels, undersized metadata, and a learning-card hover state with insufficient contrast.
- Existing visual dials: variance 3, motion 1, density 5; target variance 5, motion 5, density 5.
- Metadata: retain title and description; this is a private workspace with no public SEO migration.

## Design decisions

- Visual language: crisp pixel accents and an isometric voxel staircase paired with readable modern typography.
- Palette: keep cobalt as the primary accent, use midnight navigation, and cool white working surfaces.
- Layout: retain module navigation and the task-first dashboard, with decoration contained inside existing surfaces.
- Typography: retain the wordmark and sans-serif reading text; use monospace for small labels and numeric details.
- Geometry: stepped pixel motifs, squared controls, subtle offset panel shadows, and three-face voxel blocks.
- Motion: short page reveals, staggered block assembly, dialog entry, and tactile hover/press feedback using native CSS.
- Accessibility: honor reduced motion, support system dark mode, preserve focus outlines and touch targets, and keep decorations out of the accessibility tree.
- Implementation: native CSS and a small decorative SVG React component; no paid service or new runtime dependency.

## Validation

- The existing end-to-end workflow test passes across all nine modules and settings at 320, 375, 414, 768, and 1440 px widths.
- Separate browser checks verify both color schemes across all ten routes, voxel animation, reduced-motion disabling, one heading per route, and Escape dismissal of dialogs.
- Desktop, phone, dark-mode DSA/body-map/dialog screenshots inspected; enlarged text revealed a navigation wrapping issue, which was corrected.
- No runtime dependency was added; the production frontend remains approximately 80 KB of gzipped JavaScript.
- These are local checks against the existing local API, not a new test of external integrations or the deployed API.

- Final local Lighthouse mobile audit of the optimized sign-in page: performance 95, accessibility 100, LCP 2.4 seconds, CLS 0, total blocking time 0 ms. These simulated local results are not a production latency guarantee.
