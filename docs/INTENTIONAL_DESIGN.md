# Purpose-led layout and interaction

This revision supersedes the original requirement to show water and steps on Home, following the owner's explicit request on September 14.

## Audit

The dashboard gave water and steps first position despite their belonging to physical tracking. A breadcrumb repeated the page title. Decorative dots, diagonal fills, square heading ornaments, and offset shadows added visual weight without explaining state. The learning illustration occupied more space than the action it supported. Water had no visual relationship to the owner's saved target.

## Placement decisions

- Home: tasks and agenda form the primary column; learning, three query-derived streaks, and actionable non-health reminders form the secondary column.
- Journal: search and writing remain primary; entry history stays beside the reading surface, and AI remains a per-entry action.
- Personal growth: prompts precede trait history because reflection is the action and the chart is evidence over time.
- Academics: term/course summaries remain the overview; configuration and record types stay in tabs rather than competing on the opening screen.
- Work: projects are the entry point; project tasks, notes, and career records remain scoped within this module.
- DSA: the curriculum stays beside the current lesson, while walkthrough movement explains algorithm state rather than decorating navigation.
- Physical goals: hydration and daily readings come first, with training logs/body map and nutrition targets below; water reminders are shown here.
- Calendar: agenda and event creation remain primary; the disconnected Google notice becomes a compact connection status.
- To-do list: open tasks remain the default; completion and recurrence stay within the task list.
- Settings: preferences, integrations, reminders, and backups retain their existing groups and persist through their existing APIs.

## Visual and motion decisions

- Remove the duplicate top breadcrumb, background grid, panel heading dots, striped empty states, and repeated decorative heading blocks across every module.
- Use borders to group related content and spacing to separate sections, with stronger color reserved for primary actions and selected navigation.
- Keep the pixel vocabulary in squared controls and the sign-in voxel motif; remove the decorative learning sculpture from the working dashboard.
- Hydration fill encodes today's persisted millilitres divided by the user's saved daily goal, capped visually at 100% while the full recorded total stays visible.
- A water click saves a 250 ml manual record through the normalized ingestion endpoint, then reads back the total before showing success and animating the fill.
- Reuse a failed attempt's external ID when retrying an uncertain save; prevent duplicate clicks while a request is pending.
- If saving succeeds but reading the total fails, offer a read-only refresh and do not log another drink.
- Wave and splash motion run briefly after a successful drink; reduced motion shows the same final water level immediately.
- Existing routes, owner authentication, data tables, and export/import remain unchanged; no new service or paid dependency is added.

## Verification

- Both Playwright tests pass: all nine module workflows, responsive pages at 320–1440 px, and the hydration interaction.
- Hydration tests verify saved totals after reload, rapid-click protection, deduplication after a lost save response, read-only recovery after a failed total refresh, full-tank clamping, dark mode, reduced motion, and enlarged text.
- Checked the custom-amount dialog and direct journal-reminder action with keyboard dismissal.
- Inspected the revised Home and Physical goals screens on desktop and mobile, and the filled water tank in dark mode.
- Local accessibility checks found low contrast in secondary light-mode labels; the muted text token was darkened across the app. Rechecks of Home and Physical goals reported no automated WCAG A/AA violations in either theme.
- These checks use the local API; no wearable or Google integration was newly enabled or claimed as tested.
