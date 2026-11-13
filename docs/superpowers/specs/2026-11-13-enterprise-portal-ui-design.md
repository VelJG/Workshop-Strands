# Enterprise IT Support Portal UI — Design

## Goal

Present the existing Vietnamese Strands workshop UI as a credible internal IT
support portal rather than a guided demo, without changing its backend or
agent behavior.

## Approved direction

Use a focused, single-page service portal. Keep the current static HTML/CSS and
JavaScript architecture. Give the page a restrained enterprise visual style,
clear information hierarchy, and a professional Vietnamese identity such as
“Trợ lý CNTT nội bộ”; do not invent an organization name or logo.

Replace workshop/demo language, numbered walkthrough steps, and the demo
disclaimer with concise portal copy. Keep a compact service-status indicator
and three realistic shortcuts for policy lookup, creating a support request,
and web research. Keep the conversation as the primary workspace and retain
the ticket approval controls. Include a brief, unobtrusive note that AI answers
may need verification.

## Scope and files

- `workshop/static/index.html`: layout, Vietnamese portal copy, visual system,
  responsive behavior, and accessible labels.
- `workshop/static/ui.js`: only update shortcut labels or presentation hooks
  if required; preserve API calls, safe citation links, loading/error states,
  and approval behavior.

No API, database, agent, or service-contract changes. No framework migration,
new navigation, unsupported ticket dashboard, or invented company branding.

## Interaction and accessibility

- Preserve current chat submit behavior, Enter/Shift+Enter handling, and busy
  state.
- Keep policy, ticket, and research shortcuts mapped to their existing
  prompts.
- Preserve approval/rejection actions and source/citation rendering.
- Maintain keyboard-visible focus, semantic landmarks, labels, and live chat
  announcements.
- Keep the experience usable on narrow mobile screens without horizontal
  scrolling.

## Risks and mitigations

- **Polish could imply capabilities the app does not have:** do not add ticket
  lists, user profiles, or navigation destinations without backing routes.
- **Removing demo framing could overstate answer reliability:** retain a subtle
  AI verification note and avoid claims of guaranteed correctness.
- **Visual changes could break existing selectors:** preserve IDs and data
  attributes consumed by `ui.js` and validate the existing interaction paths.

## Validation

- Run the existing test suite.
- Verify policy Q&A, ticket draft and approval/rejection, research citations,
  and health status still work through the existing UI/API contract.
- Inspect the page at desktop and mobile widths; check focus visibility,
  labels, and absence of horizontal overflow.

## Self-review

- Scope is limited to the existing portal UI; no unsupported backend features
  are suggested.
- Product copy remains Vietnamese and avoids fabricated organization identity.
- AI transparency and all currently supported interaction paths are retained.
