# Playful, purposeful interactions

## Audit and direction

Water already connects an action with a persistent visual result. Other successful saves simply close their dialog; task completion removes a row before acknowledging it; DSA steps change without showing which cells moved into focus; concept reviews disappear immediately; muscle volume and charts change abruptly.

The design stays a serious working surface, with short, game-like feedback tied to actual input or confirmed saves. Existing module placement, typography, palette, and data contracts remain in place. Motion intensity is moderate during interaction and quiet at rest.

## Decisions

- Tasks: pop a check into place and show a small pixel burst after the server confirms completion, then refresh the task list.
- Journal, work, academics, calendar, and settings: give successful saves a brief, dismissible receipt with the actual kind of record saved.
- DSA walkthroughs: lift and mark the active cells, animate the explanation between steps, and show position through the example with a segmented rail.
- Concept reviews: reveal the answer with a short card turn, lock grading during submission, then show the next review date returned by SM-2.
- Physical goals: illuminate only muscle groups whose logged volume changes, keeping their intensity tied to actual sets.
- Progress: animate existing trait points and add restrained bars to existing course-weight coverage, pattern accuracy, and relative muscle volume.
- Shared sections: use a small moving selection accent and tactile buttons to make navigation state legible.
- Water: preserve the existing fill, deduplication, and error-recovery behavior.
- Restraint: no invented XP, ranks, badges, scores, sound, random rewards, floating decorations, or continuous animation.
- Accessibility: all motion stops under reduced motion; status text remains available, controls keep keyboard behavior, and success never appears before a confirmed save.
- Implementation: existing React, Lucide, and native CSS; no paid service or additional runtime dependency.

## Validation

- Three local browser tests pass: all nine module workflows, hydration persistence/retry behavior, and the new task/journal/review interactions.
- Verified that blocked task completion produces no success feedback and that pending task/review submissions cannot be double-clicked.
- Verified journal confirmation only after a persisted save, actual next-review dates, step progression, muscle activation after a logged set, and relative volume bars for three muscle groups.
- Responsive checks cover 320–1440 px; confirmations fit on a phone and dismiss with the keyboard.
- Automated WCAG A/AA checks report no violations on Home, DSA, Physical goals, Academics, Personal growth, and To-do in light and dark modes, or on the confirmation component.
- Reduced-motion checks confirm that water, review receipts, and pixel bursts become static while preserving all status information.
- No backend schema, sync behavior, or external integration changed. These are local checks against the local API.

- Optimized local sign-in Lighthouse check: performance 94, accessibility 100, LCP 2.6 s, CLS 0, blocking time 0 ms. This simulated local result does not measure hosted API cold starts.
