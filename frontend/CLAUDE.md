@AGENTS.md

# Frontend

Next.js 16 (App Router, Turbopack, Cache Components) · React 19 · TanStack Query · Tailwind 4 + shadcn/ui (Base UI, style `base-nova`) · Vitest + Testing Library + MSW 3 · Playwright.
Architecture and module rules: `../docs/ARCHITECTURE.md` §2. Tests: skill `screen-tests`.

Node 26 (see `../.nvmrc`, run `fnm use`), pnpm 12 via corepack.

| Command                                        | What it does                                                                                 |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `pnpm dev`                                     | dev server on :3000 (also exposes `/_next/mcp`)                                              |
| `pnpm test` / `pnpm test:watch`                | Vitest screen tests                                                                          |
| `pnpm e2e`                                     | Playwright (builds and starts the app)                                                       |
| `pnpm lint` · `pnpm typecheck` · `pnpm format` | ESLint (incl. module boundaries) · tsc · Prettier                                            |
| `pnpm gen:api`                                 | regenerate `src/shared/api/schema.gen.ts` from the back's OpenAPI (`API_URL`, default :8000) |
| `pnpm dlx shadcn@latest add <component>`       | add a shadcn component into `src/shared/ui`                                                  |

Skills for this app: `next-dev-loop` (verify at runtime after edits), `shadcn`, `vercel-react-best-practices`, `vercel-composition-patterns`, `screen-tests`.
