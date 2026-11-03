# Architecture — AI form filler

> Livrable de l'étape 3 (`docs/PLAN.md`). Statut : **global ✅ et front ✅ validés le 2026-11-03 · back 🟦 en discussion**.
> Parcours : `docs/USER_FLOW.md`. Ce document est en français ; le code et l'UI sont en anglais.

## 1. Architecture globale

```
┌─────────────── frontend/ (Next.js, client uniquement) ───────────────┐
│ Company knowledge · Tender · Setup · Live fill · Export              │
│ types TS générés depuis l'OpenAPI du back                             │
└───────────── REST (JSON, fichiers) ─────── SSE (remplissage) ────────┘
                                │
┌─────────────────────── backend/ (FastAPI) ───────────────────────────┐
│ api/            routes REST + flux SSE                                │
│ form_parser/    DOCX/PDF → FormSchema (champs + localisateurs)        │
│ knowledge/      ingestion : texte par page + positions, passages,     │
│                 index hybride (BM25 + vecteurs), retrieve()           │
│ answer_engine/  retrieve + LLM (1 appel / section) + validateur       │
│ rules/          critères génériques : preuve, conflit, péremption,    │
│                 champ utilisateur, statut/groupe/tri, blocage export  │
│ exporter/       FormSchema + réponses + original → fichier rempli     │
│ llm/            façade + adaptateurs (Claude, Fake)                   │
│ store/          SQLite + fichiers                                     │
└──────────────────────────────────────────────────────────────────────┘
data/ (ignoré par git) : sqlite, uploads, exports. Seed au démarrage : offre, 11 documents, 2 formulaires
```

| Sujet | Décision |
|---|---|
| Dépôt | Monorepo `frontend/` (pnpm) + `backend/` (uv), lancement `make dev`, pas de Docker |
| Source de vérité | Le back : état des champs, fichiers, règles. Next.js = UI seule (pas de routes API) |
| Contrat | Modèles Pydantic → OpenAPI → `openapi-typescript` → types TS |
| Communication | REST + SSE (remplissage). Corrections utilisateur en `PATCH` pendant le flux |
| Remplissage | Job asyncio côté back, événements persistés → SSE rejouable (rechargement), écrans de repli sur le même modèle |
| LLM | Claude via une façade `llm/` (`generate_structured`) ; aucun autre module n'importe le SDK. **Un appel par section** du formulaire, événement SSE par champ |
| Recherche | RAG : embeddings locaux (`fastembed`) + BM25, hybride, dans SQLite (`sqlite-vec`). Passages = document + page + rectangle |
| Fiabilité | Le LLM renvoie toutes les valeurs candidates avec citation exacte, ou `not_found`. Le code vérifie chaque citation, détecte les conflits (valeurs normalisées divergentes) et la péremption (date de validité renvoyée avec sa citation, comparée à aujourd'hui). Citation non vérifiée → `not_found` |
| Ingestion V1 | Pas d'extraction de faits (coût) : *Company knowledge* liste les documents |
| Tests | `FakeLLM` rejouant des réponses enregistrées → pytest et Playwright sans clé ni réseau ; script d'évaluation sur le vrai LLM vs `GROUND_TRUTH.md` (étape 8) |

## 2. Architecture front

### Stack
Next.js (App Router, composants client) · TanStack Query · Tailwind + shadcn/ui · `react-pdf` (PDF.js) · `docx-preview` · Vitest + Testing Library + MSW · Playwright.

### Arborescence

```
frontend/src/
├─ app/                          # routes Next.js minces : une page = un écran
│  ├─ layout.tsx                 # providers (QueryClient) + shell
│  ├─ knowledge/page.tsx
│  ├─ tenders/[tenderId]/page.tsx
│  └─ forms/[formId]/{fill,export}/page.tsx
│
├─ screens/                      # composition des features ; unité des tests d'intégration
│  ├─ knowledge/   KnowledgeScreen.tsx · KnowledgeScreen.test.tsx
│  ├─ tender/      TenderScreen.tsx    · TenderScreen.test.tsx
│  ├─ live-fill/   LiveFillScreen.tsx  · LiveFillProvider.tsx · LiveFillScreen.test.tsx
│  └─ export/      ExportScreen.tsx    · ExportScreen.test.tsx
│
├─ features/                     # modules autonomes ; API publique = index.ts
│  ├─ knowledge-base/    api.ts · DocumentTable · UploadDocuments · useDocuments
│  ├─ tender/            api.ts · TenderHeader · FormCard · SetupDialog · useTender
│  ├─ fill-session/      api.ts (SSE + PATCH) · useFillSession · fillEventsReducer · useUpdateField
│  ├─ review-queue/      ReviewQueue · FilterChips · FieldCard/{Auto,NotFound,Manual,
│  │                     Outdated,Conflict,Declaration} · useReviewKeyboard
│  ├─ document-preview/  DocumentPreview · renderers/{pdf,docx} · FieldOverlay · locator.ts
│  ├─ source-viewer/     api.ts · SourceView
│  └─ form-export/       api.ts · ExportSummary · ExportWarnings · DownloadButton
│
├─ shared/
│  ├─ api/               client.ts (initialisation du client HTTP typé) · schema.gen.ts (généré)
│  ├─ ui/                composants shadcn, StatusBadge, tokens de couleur
│  ├─ lib/               utilitaires sans dépendance métier
│  └─ test/              setup, serveur MSW, handlers, fixtures typées, renderScreen, fillStream
│
frontend/e2e/            # un test Playwright : le scénario principal
```

### Règles de modularité (vérifiées par ESLint, `eslint-plugin-boundaries`)
1. Dépendances à sens unique : `app → screens → features → shared`.
2. Une feature n'importe pas une autre feature ; elles se composent dans les écrans. _Règle par défaut, révisable au cas par cas._
3. Une feature s'importe uniquement par son `index.ts`.
4. Chaque feature possède son `api.ts` (appels, query keys, hooks TanStack Query de son domaine). `shared/api` ne contient que l'initialisation du client et les types générés.
5. `document-preview` est générique : il reçoit `{id, locator, value, tone}` et émet `onSelect(id)`.

### État
- **Données serveur** : cache TanStack Query (seule source côté front). Le flux SSE met à jour ce cache (`setQueryData`) ; les éditions partent en `PATCH` optimiste (« ✓ Saved »).
- **État d'interface** : local à l'écran. Sur *Live fill*, `LiveFillProvider` (Context limité à l'écran) porte `selectedFieldId`, le filtre et l'onglet Form/Source, partagés par la file et l'aperçu. Pas de store global.
- **Logique métier** : aucune côté front. Statut, groupe, tri, compteurs et blocage d'export sont calculés par le back.

### Aperçu des documents
| Fichier | Rendu | Champs |
|---|---|---|
| PDF (Annex 7, documents de la base) | `react-pdf` | calque HTML positionné depuis le rectangle du localisateur |
| DOCX (Annex 4, documents de la base) | `docx-preview` | localisateur (tableau, ligne, cellule) → cellule du DOM ; citations de la base surlignées par recherche de texte |

### Flux Live fill
```
SSE ─► fill-session (reducer) ─► setQueryData(["form", id])
                                     ├─► ReviewQueue ──┐ onSelect / Save
                                     └─► DocumentPreview┤ onSelect
                        LiveFillProvider (selectedFieldId, filtre) ◄┘
                        Save ─► useUpdateField ─► PATCH optimiste
```

### Tests front
- **Vitest + Testing Library, par écran** : chaque détail de chaque écran, sous forme de scénarios utilisateur ; seul le réseau est simulé (MSW, y compris SSE). Règles complètes : skill `.claude/skills/screen-tests/SKILL.md`.
- **Playwright** : un seul test, le scénario principal, avec le vrai back en mode `FakeLLM`.

## 3. Architecture back

_En discussion._
