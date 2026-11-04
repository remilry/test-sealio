---
name: frontend-data-layer
description: Use when adding or changing how the frontend (frontend/) talks to the API — a new endpoint call, a query, a mutation, query keys, optimistic updates, or a component that needs server data. Defines the `[feature].api.ts` / `[feature].queries.ts` split, enforced by ESLint.
---

# Frontend data layer

Each feature that talks to the back has exactly two data files, named after the feature folder:

| File | Holds | Never holds |
|---|---|---|
| `features/<feature>/<feature>.api.ts` | the response types (`Schema<"...">`) and the HTTP calls, as a plain object (`tenderApi.get(id, signal)`), plus URL builders for downloads | TanStack Query, React |
| `features/<feature>/<feature>.queries.ts` | query keys (`tenderKeys`), `queryOptions`, and the hooks components use: `useTender(id)`, `useSaveAnswer(formId)`… | `api.GET` / `api.PATCH` calls (it goes through `<feature>.api.ts`) |

Components and screens only call the hooks exported by a `.queries.ts` file, through the feature's
`index.ts`. They never import `useQuery`, `useMutation`, `useQueryClient`… nor the HTTP client.

ESLint enforces it (`eslint.config.mjs`, `no-restricted-imports`):
- TanStack Query hooks and `queryOptions` can only be imported in `*.queries.ts` (and tests);
- `api` and `unwrap` from `@/shared/api` can only be imported in `*.api.ts`.

`shared/api` only holds the typed client, `unwrap`, `ApiError` / `isNotFound` and the generated
types (`make gen-api`).

## Example

```ts
// features/tender/tender.api.ts
import { api, unwrap, type Schema } from "@/shared/api";

export type TenderDetail = Schema<"TenderDetail">;

export const tenderApi = {
  get: (tenderId: number, signal?: AbortSignal) =>
    unwrap(api.GET("/tenders/{tender_id}", { params: { path: { tender_id: tenderId } }, signal })),
};
```

```ts
// features/tender/tender.queries.ts
import { queryOptions, useQuery } from "@tanstack/react-query";
import { tenderApi } from "./tender.api";

export const tenderKeys = {
  all: ["tenders"] as const,
  detail: (tenderId: number) => [...tenderKeys.all, tenderId] as const,
};

const tenderQueries = {
  detail: (tenderId: number) =>
    queryOptions({
      queryKey: tenderKeys.detail(tenderId),
      queryFn: ({ signal }) => tenderApi.get(tenderId, signal),
    }),
};

/** A tender with its forms and the current tenant's status on each. */
export function useTender(tenderId: number) {
  return useQuery(tenderQueries.detail(tenderId));
}
```

```tsx
// screens/tender/TenderScreen.tsx
const { data: tender, error, isPending, refetch } = useTender(tenderId);
```

## Rules of thumb

- **One hook per use case**, named for what the component gets (`useFillState`, `useExportSummary`),
  with the options the component may vary (`{ enabled }`), not a raw pass-through of `useQuery` options.
- **Keys** come from the feature's `xxxKeys` object, built hierarchically (`["forms", id]`,
  `["forms", id, "answers"]`) so a prefix invalidates everything below it.
- **Mutations** live in the `.queries.ts` file too, with their optimistic update and rollback
  (`useSaveAnswer` in `fill-session.queries.ts` is the reference).
- **Server data stays in the cache**: no copy in `useState`. UI state (selection, drafts) is local
  to the screen.
- **Tests** don't mock these files: MSW answers the real HTTP calls (skill `screen-tests`).
