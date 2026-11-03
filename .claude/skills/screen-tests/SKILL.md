---
name: screen-tests
description: Use when writing, changing or reviewing frontend tests in frontend/ — screen-level integration tests with Vitest + Testing Library that replay what the user does on a screen (Knowledge, Tender, Live fill, Export). Also use when adding a new screen or a new user interaction to an existing screen.
---

# Screen integration tests (frontend)

## Principle

A test = **one user scenario on one screen**, written as the user lives it:
the user sees something, does something, sees the result. We test the screen
through the DOM like a user would, never through component internals.

The unit of test is a **screen** (`src/screens/<screen>/`), not a component.
Features are covered through the screens that compose them. A feature gets its
own test only for pure logic that has no screen-level expression (e.g. the SSE
event reducer, PDF → CSS coordinate conversion).

## Stack

- `vitest` + `jsdom`
- `@testing-library/react` + `@testing-library/user-event` (always `userEvent.setup()`, never `fireEvent`)
- `@testing-library/jest-dom` matchers
- `msw` (v3) for **all** network: REST handlers and SSE (`sse()` from `msw`). The server
  listens with `onUnhandledFrame: "error"` (v3 name of `onUnhandledRequest`): a request with no handler fails the test
- Helpers in `src/shared/test/`: `renderScreen()`, MSW `server`, `handlers/`, `fixtures/`, `fillStream()`

Scope: these Vitest screen tests cover **every detail of each screen**. The only
other frontend test is **one Playwright e2e for the main scenario** (real back
with `FakeLLM`, in `frontend/e2e/`); do not add more Playwright tests for details.

## What is real, what is mocked

| Real | Mocked |
|---|---|
| Screens, features, shared UI, hooks, TanStack Query, router params | **Network only**, via MSW (back responses = fixtures typed with `schema.gen.ts`) |
| `docx-preview` rendering (works in jsdom) | `react-pdf` canvas rendering: replaced by `src/shared/test/mocks/react-pdf.tsx` (renders a sized `<div>` per page; the field overlay stays real) |

Never `vi.mock` an internal module (`features/*` including their `api.ts`, `shared/*`, hooks). If a test
needs that, the screen is badly designed or the test targets an implementation detail.

## Writing a test

1. **Pick the scenario from `docs/USER_FLOW.md`.** One `it` = one scenario, named
   as a user sentence: `it("lets me pick the most recent value when two sources conflict")`.
2. **Arrange the back**: start from a fixture (`shared/test/fixtures/annex4.ts`, `annex7.ts`)
   and override only what the scenario needs: `server.use(handlers.form(annex4({ ... })))`.
3. **Render the screen** with `renderScreen(<LiveFillScreen formId="annex-4" />)`
   (it provides QueryClient, router and a fresh cache per test).
4. **Act like the user**: `await user.click(...)`, `await user.type(...)`,
   `await user.keyboard("{ArrowDown}{Enter}")`. For live fill, drive the stream with
   `fillStream.emit(event)` / `fillStream.done()`.
5. **Assert what the user sees**, and, when relevant, **what the back received**
   (capture the request body in the MSW handler and assert on it).

### Query priority
`getByRole` (with `name`) > `getByLabelText` > `getByText` > `getByTestId` (last
resort, only for the document-preview zones: `data-field-id`).
Use `findBy*` / `await waitFor` for anything async; never `setTimeout` or arbitrary sleeps.

### Template

```tsx
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderScreen, server, handlers, fillStream } from "@/shared/test";
import { annex4, field } from "@/shared/test/fixtures";
import { LiveFillScreen } from "./LiveFillScreen";

describe("Live fill", () => {
  it("lets me pick the most recent value when two sources conflict", async () => {
    // Given a form whose AHV office field has two conflicting sources
    const patched = handlers.capturePatch();
    server.use(handlers.form(annex4({ fields: [field.conflict("ahv_office")] })), patched.handler);
    const user = userEvent.setup();
    renderScreen(<LiveFillScreen formId="annex-4" />);

    // When I open the doubt and keep the pre-selected most recent option
    await user.click(await screen.findByRole("button", { name: /AHV compensation office/i }));
    const card = screen.getByRole("region", { name: /AHV compensation office/i });
    expect(within(card).getByRole("radio", { name: /most recent/i })).toBeChecked();
    await user.click(within(card).getByRole("button", { name: "Use this one" }));

    // Then the field is resolved by me and the back got the choice
    expect(await within(card).findByText(/Kept by you/i)).toBeInTheDocument();
    expect(patched.lastBody()).toMatchObject({ resolution: "kept", candidateIndex: 0 });
  });
});
```

## Coverage expected per screen

Each screen file covers at least: the happy path, every state from the
USER_FLOW table it renders (loading, empty, error, each field type), and every
user action it offers (click, keyboard, upload). Minimum list:

- **Knowledge**: list of documents with statuses; upload → `Processing` → `Indexed`; unreadable file → `Error` with message.
- **Tender**: form cards per status (`Not started`, `In review x/y`, `Ready`); Setup modal opens, cancels, starts filling.
- **Live fill**: streamed phases and fields appearing; editing a field *during* the stream; each field card type (auto, not found, manual, outdated, conflict, declaration with/without evidence); filters; queue ↔ preview selection sync; keyboard `↑↓`/`j`/`k`/`↵`; export button disabled while filling; reload resumes from persisted state.
- **Export**: ready vs warnings banner; blocked by an unanswered declaration; download in the original format; signature reminder.

## Checklist before finishing

- [ ] Test names are user sentences; body reads Given / When / Then.
- [ ] Only MSW (and the react-pdf canvas mock) is mocked.
- [ ] No `fireEvent`, no sleeps, no `container.querySelector` (except `data-field-id` zones).
- [ ] Fixtures typed from `schema.gen.ts` (a back contract change breaks the tests at compile time).
- [ ] `pnpm test` passes, and the new test fails if the behavior is removed (check once by breaking it).
