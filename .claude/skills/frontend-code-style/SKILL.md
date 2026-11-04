---
name: frontend-code-style
description: Use when writing or reviewing React components, hooks or functions in frontend/ — how to structure conditions (early returns, no nested ternaries, sub-components) and how a screen handles the loading / not found / error / data states of its queries.
---

# Frontend code style

## Early return, always

Functions and components handle the special cases first and return, so the main path reads at the
end without nesting. A component with several states returns one per `if`, never a ternary tree in
the JSX.

The query states of a screen follow this order: pending → not found → error → data.

```tsx
export function TenderScreen({ tenderId }: { tenderId: number }) {
  const { data: tender, error, isPending, refetch } = useTender(tenderId);

  if (isPending) {
    return <TenderFrame><TenderSkeleton /></TenderFrame>;
  }
  if (isNotFound(error)) {
    return <TenderFrame><EmptyState title="Tender not found">…</EmptyState></TenderFrame>;
  }
  if (error) {
    return <TenderFrame><LoadError title="We couldn't load this tender." onRetry={() => void refetch()} /></TenderFrame>;
  }
  return (
    <TenderFrame title={tender.title}>
      <TenderHeader tender={tender} />
      <FormList forms={tender.forms} />
    </TenderFrame>
  );
}
```

What every state shares (top bar, page column) goes in a small layout component (`TenderFrame`)
rather than being repeated or kept around a ternary.

Avoid:

```tsx
{isPending ? <Skeleton /> : error ? (isNotFound(error) ? <NotFound /> : <Alert />) : <Content />}
```

## No nested ternaries (ESLint `no-nested-ternary`)

A single `a ? b : c` is fine. As soon as a second condition appears:
- in JSX: extract a **sub-component** that returns early for each case
  (`FormLoadFailed` in `LiveFillScreen.tsx`, `ExportPending` in `ExportDialog.tsx`);
- in a value: extract a **named function** with early returns (`zoneTone` in `LiveFillScreen.tsx`,
  `shiftRequirement` in `useHandleKeyDown.ts`).

TypeScript narrowing: test the query flags directly (`if (form.isError || fill.isError)`), not a
copied variable, or `data` stays possibly undefined after the checks.

## Shared states

`@/shared/components/LoadStates` provides `EmptyState` (nothing to show: not found, none yet) and
`LoadError` (loading failed, plain words + "Try again"). Error messages are for users: never mention
the API, the server or a status code. All text comes from the translations (skill `frontend-i18n`).
