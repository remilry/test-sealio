---
name: frontend-i18n
description: Use when adding or changing any text the user sees in frontend/ (labels, buttons, headings, aria-labels, titles, error messages, counts, plurals), or when adding a language. All interface text goes through next-intl; ESLint forbids text written in JSX.
---

# Frontend i18n (next-intl)

Every string the user can see or hear (screen readers included) comes from
`src/shared/i18n/messages/<locale>.json`. English (`en.json`) is the only language for now and the
source of the types: a key that does not exist fails the typecheck.

## Where things are

| File | Role |
|---|---|
| `src/shared/i18n/config.ts` | `locales`, `defaultLocale`, `timeZone` (Europe/Zurich) |
| `src/shared/i18n/request.ts` | next-intl request config (wired in `next.config.ts`). The locale is fixed: it never reads the request, so pages stay static with Cache Components |
| `src/shared/i18n/messages/en.json` | the messages, one namespace per screen or feature (`tender`, `forms`, `liveFill`, `export`…), plus `common` and `ui` (shadcn components) |
| `src/shared/i18n/next-intl.d.ts` | types the keys from `en.json` |
| `src/app/layout.tsx` | `NextIntlClientProvider`, `<html lang>`, metadata via `getTranslations` |
| `src/shared/test/renderScreen.tsx` | wraps screens in the provider with the English messages |

## Writing text

```tsx
const t = useTranslations("export");
<h3>{t("beforeSubmit")}</h3>
<ul aria-label={t("emptyFields")}>…</ul>
{t("download", { format })}                 // "Download {format}"
{t("emptyWarning", { count: empty })}       // ICU plural
```

- **Plurals and agreement in the message, never in code**: no `count === 1 ? "field" : "fields"`,
  no `plural()` helper. Use ICU: `"{count, plural, one {# field} other {# fields}}"`, and put the
  whole sentence in the message (the verb agrees too: "it will be" / "they will be").
- **Whole sentences with arguments**, not concatenated fragments: `"{formTitle} · {filled} of
  {fillable} fields filled"`, so another language can reorder them.
- **Props too**: `aria-label`, `title`, `placeholder`, `alt`, dialog titles. ESLint only sees JSX
  children (`react/jsx-no-literals`), so check props in review.
- **Text built in a function** (outside a component) becomes a hook returning formatters
  (`useDeadlineFormat` in `features/tender/deadline.ts`).
- **Data is not translated**: form titles, field labels, company and user names come from the
  back (or, for the demo account, from a constant in `AppShell`).
- **Keys** are camelCase and named for the meaning (`backToReview`), not the wording. A key used in
  one place lives in that screen's namespace; `common` holds what several screens share
  (`tryAgain`, `retryLater`, `withdrawnByBuyer`).
- Error messages are for users: plain words, never the API, the server or a status code.
- Dates and times still go through `@/shared/utils/date` (Swiss formatting).

## Tests

Screen tests render with the English messages, so they keep querying the real text
(`getByRole("button", { name: "Back to review" })`). Never mock `useTranslations`.

## Adding a language

1. Add the locale to `locales` in `config.ts` and create `messages/<locale>.json` with the same keys.
2. Pick the locale in `request.ts` from the user's setting (not from the URL: no locale routing).
3. Date formatting in `@/shared/utils/date` follows the locale too.
