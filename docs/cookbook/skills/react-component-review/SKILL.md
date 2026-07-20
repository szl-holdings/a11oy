<!-- VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — .agents/skills/react-component-review/SKILL.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
---
name: react-component-review
description: Review React/Vite components for quality, performance, and correctness. Use when auditing a component before shipping, after a design handoff, or when a component feels slow or buggy. Adapted from the Awesome Claude Code React patterns and Claude Agent Blueprints collections.
---

# React Component Review

A focused review checklist for React components in this monorepo's web artifacts (Vite + React + TypeScript). Run `pre-flight-thinking` first if you are about to refactor based on findings.

## Correctness

- **Props are fully typed.** No implicit `any`, no missing required props.
- **Key props on lists.** Every `.map()` rendering JSX has a stable, unique `key` (not array index unless the list is static and never reordered).
- **Effect dependencies are complete.** All values used inside `useEffect` / `useCallback` / `useMemo` appear in the dependency array, or are stable refs.
- **No stale closure bugs.** State read inside a timeout or event listener uses a ref if the timeout outlives the render cycle.
- **Error boundaries.** Any component fetching data or rendering dynamic user content is wrapped (or its parent is) in an error boundary.

## Performance

- **Memoization is justified.** `React.memo`, `useMemo`, and `useCallback` are used only where profiling or clear reasoning shows benefit — not by default.
- **Large lists are virtualized.** Lists rendering > 100 items use a windowing solution (e.g., `@tanstack/react-virtual`).
- **Images have explicit dimensions.** `<img>` tags include `width` and `height` to prevent layout shift.
- **Heavy imports are lazy.** `React.lazy` + `Suspense` for routes and heavy third-party components not needed on initial paint.

## Accessibility

- **Interactive elements are keyboard-reachable.** Buttons, links, and custom controls have `tabIndex` managed correctly.
- **ARIA roles are accurate.** Custom widgets (tabs, dialogs, dropdowns) implement the correct ARIA pattern.
- **Color is not the only signal.** Error states, loading states, and status indicators have a text or icon fallback.
- **Focus is managed on modal open/close.**

## Code Hygiene

- **Component file is ≤ 300 lines.** Larger components should extract sub-components or hooks.
- **No inline object/array literals in JSX props** that create a new reference every render (unless the component is memoized by the parent or the prop is trivially cheap).
- **No direct DOM manipulation** (`document.querySelector`, `innerHTML`) inside React components — use refs.

## Output Format

```markdown
## Component: <ComponentName>

### Issues
- **[severity: critical|high|medium|low]** <description> — <file>:<line>

### Suggestions
- <optional improvement>

### Verdict
[ Pass | Needs Changes | Critical Fix Required ]
```
