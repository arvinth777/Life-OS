# Context workspaces

Design: preserve Life OS's midnight identity while making each mode a distinct working surface.
Navigation: keep a persistent three-way mode switch, one Quick add, and a shared All agenda; filter module navigation by mode.
Work: blue and slate, compact task-first layout with a project rail.
Academics: violet and amber, learning-first layout with deadlines and a study activity grid.
Personal: teal, softer surfaces, workout and reflection actions with a workout activity grid.
Motion: animate the mode selector and stagger incoming sections; honour reduced motion and keep keyboard focus stable.
Data: reuse task and note tags for context and energy; leave existing deadlines and integration contracts intact.
Legacy records: project-linked tasks default to Work, academic-tagged tasks to Academics, and unclassified tasks to Personal; allow explicit reassignment.
Capture: accept a single sentence, recognise supported date phrases locally, preview editable context/type/time before saving, retain original text.
Rollover: show unfinished tasks in Next up with their original dates; never silently reschedule real deadlines.
Review: link to the existing opt-in ChatGPT weekly review; do not send logs automatically or introduce an LLM bill.
Validation: verify context isolation, saved capture/readback, date interpretation, task completion, mobile layout, keyboard access, reduced motion, and existing module reachability.

## Using the modes

- Pick Work, Academics, or Personal at the top. The choice is remembered on this browser.
- Quick add accepts a sentence, then previews type, context, and any recognised date. It never saves just because you type. Its draft survives closing the dialog and switching modes, but not refreshing or closing the tab.
- Supported date phrases are today, tomorrow, or an ISO date (YYYY-MM-DD), paired with a 12-hour time or `at HH:MM`. The preview uses the timezone in Settings. Unrecognised or ambiguous dates require explicit input; this is a small local parser, not general-purpose AI.
- Context and energy use ordinary tags (`context:work`, `context:academics`, `context:personal`; `energy:focus`, `energy:light`, `energy:quick`). Other tags/custom fields are retained. The task list has a Show every context checkbox for organising older records.
- Quick-add events retain `Context: Work`, `Context: Academics`, or `Context: Personal` at the start of their description. Unclassified calendar events remain in All agenda. Linked exams and assignments appear in Academics; task deadlines use task context. Nothing silently moves a deadline.
- Notes and journal entries are filtered by mode. Work quick-notes use the existing Work notes table; journal entries in any mode use the journal with a context tag. Existing unclassified journal entries remain Personal.
- Personal → Reflect on my week offers a copyable prompt and opens the existing Life OS ChatGPT project. It does not submit a message or transmit logs automatically.

## Verification, 2026-10-04

Real local Postgres saves/readback verified for task capture, context reassignment, energy tags, note capture, event creation, and task completion. Existing deadlines and unrelated tags remain unchanged. The selected mode survives reload; the capture draft survives mode changes. Date tests cover an owner timezone different from the test browser and rejection of nonexistent/repeated DST times.

All 46 existing module/tab sections remain reachable. Existing login continuity, owner entry workflows, body-map feedback, and module accessibility checks pass. New mode homes pass automated accessibility checks at 320px; mobile/desktop screenshots were inspected. Keyboard mode switching and reduced-motion behaviour pass. Production build passes.

No database migration, backend deployment, new paid dependency, or LLM key is required. Tests used the disposable local database, not personal production records. Google Calendar and watch round trips were not repeated for this presentation/capture update. No automatic AI classification, automatic task rescheduling, or automatic weekly inference is claimed.
