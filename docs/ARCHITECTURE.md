# Architecture — AI form filler

> Livrable de l'étape 3 (`docs/PLAN.md`). Statut : **global, front et back validés le 2026-11-03**.
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
│ core/db         PostgreSQL + pgvector ; fichiers sur disque           │
└──────────────────────────────────────────────────────────────────────┘
data/ (ignoré par git) : uploads, exports. Seed au démarrage : offre, 11 documents, 2 formulaires
```

| Sujet | Décision |
|---|---|
| Dépôt | Monorepo `frontend/` (pnpm) + `backend/` (uv), lancement `make dev`. Docker Compose uniquement pour PostgreSQL (image `pgvector/pgvector`) ; front et back tournent en local |
| Base de données | PostgreSQL + pgvector. Toutes les tables ont `created_at` et `updated_at` |
| Source de vérité | Le back : état des champs, fichiers, règles. Next.js = UI seule (pas de routes API) |
| Contrat | Modèles Pydantic → OpenAPI → `openapi-typescript` → types TS |
| Communication | REST + SSE (remplissage). Corrections utilisateur en `PATCH` pendant le flux |
| Remplissage | Job asyncio côté back, événements persistés → SSE rejouable (rechargement), écrans de repli sur le même modèle |
| LLM | Claude via une façade `llm/` (`generate_structured`) ; aucun autre module n'importe le SDK. **Un appel par section** du formulaire, événement SSE par champ |
| Recherche | RAG hybride dans PostgreSQL : vecteurs (`fastembed` local + pgvector) + plein texte (`tsvector`), fusion des rangs (RRF). Passages = document + page + rectangle |
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
│  └─ forms/[formId]/fill/page.tsx
│
├─ screens/                      # composition des features ; unité des tests d'intégration
│  ├─ knowledge/   KnowledgeScreen.tsx · KnowledgeScreen.test.tsx
│  ├─ tender/      TenderScreen.tsx    · TenderScreen.test.tsx
│  └─ live-fill/   LiveFillScreen.tsx  · LiveFillProvider.tsx · LiveFillScreen.test.tsx (export en modale inclus)
│
├─ features/                     # modules autonomes ; API publique = index.ts
│  ├─ knowledge-base/    api.ts · DocumentTable · UploadDocuments · useDocuments
│  ├─ tender/            api.ts · TenderHeader · FormCard · SetupDialog · useTender
│  ├─ fill-session/      api.ts (SSE + PATCH) · useFillSession · fillEventsReducer · useUpdateField
│  ├─ review-queue/      ReviewQueue · FilterChips · FieldCard/{Auto,NotFound,Manual,
│  │                     Outdated,Conflict,Declaration} · useReviewKeyboard
│  ├─ document-preview/  DocumentPreview · renderers/{pdf,docx} · FieldOverlay · locator.ts
│  ├─ source-viewer/     api.ts · SourceView
│  └─ form-export/       api.ts · ExportDialog (résumé, champs vides, téléchargement)
│
├─ shared/
│  ├─ api/               client.ts (initialisation du client HTTP typé) · schema.gen.ts (généré)
│  ├─ ui/                composants shadcn, StatusBadge, tokens de couleur
│  ├─ lib/               utilitaires sans dépendance métier
│  ├─ utils/date.ts      seul point de manipulation des dates (règle ESLint), remplaçable par une lib
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

### Stack
Python 3.14 · FastAPI (SSE natif `fastapi.sse`) · SQLAlchemy 2.1 + psycopg 3 · Alembic (migrations) · PostgreSQL + pgvector · `fastembed` · SDK Anthropic (dans `llm/` uniquement) · PyMuPDF · python-docx · pytest · uv, ruff, pyright.

### Arborescence (modules métier)

```
backend/
├─ app/
│  ├─ main.py                 # FastAPI : routers ; au démarrage, migrations + seed (offre, 11 docs, 2 formulaires)
│  ├─ core/                   # config (pydantic-settings), db (engine, session, Base + TimestampMixin), erreurs
│  ├─ llm/                    # façade : Protocol LLM.generate_structured(prompt, schema)
│  │  ├─ anthropic_adapter.py
│  │  └─ fake_adapter.py      # rejoue des réponses enregistrées (tests, e2e)
│  └─ modules/
│     ├─ knowledge/           router · service · models
│     │  ├─ extraction/       pdf.py (PyMuPDF : texte + rectangles) · docx.py
│     │  ├─ chunking.py       passages = doc + page + rectangle + texte
│     │  └─ index.py          vecteurs (pgvector) + plein texte (tsvector), fusion RRF → retrieve()
│     ├─ tenders/             router · service · models
│     ├─ forms/               router · service · models
│     │  └─ parsing/          pdf_parser.py · docx_parser.py → FormSchema (pur)
│     ├─ filling/             router (lancer, SSE, PATCH champ) · service · models
│     │  ├─ job.py            orchestration des 5 phases, émet les événements
│     │  ├─ answer_engine.py  section → retrieve par champ → prompt → appel LLM
│     │  ├─ validator.py      vérification des citations et du format (pur)
│     │  └─ rules.py          type, groupe, ordre, compteurs, blocage d'export (pur)
│     └─ export/              router · pdf_exporter.py · docx_exporter.py (purs)
├─ migrations/                # Alembic
└─ tests/                     même arborescence que app/ + fixtures
```

**Règles de dépendance**
- Un module n'expose aux autres que son `service.py`.
- Seul `answer_engine` importe `llm/` ; seul `llm/` importe le SDK Anthropic.
- Les briques critiques sont **pures** (données en entrée, données en sortie, ni base ni réseau) : `parsing/`, `validator`, `rules`, `*_exporter`.

### Modèle de données (PostgreSQL)

Toutes les tables héritent d'un `TimestampMixin` : `created_at` (`timestamptz`, `server_default now()`) et `updated_at` (`timestamptz`, mis à jour à chaque modification par l'ORM).

| Table | Champs principaux |
|---|---|
| `tender` | titre, référence, autorité, échéance. Sert aussi de source « Tender details » |
| `document` | nom, format, pages, statut (`processing`/`indexed`/`error`), message d'erreur |
| `chunk` | document, page, rectangle, texte, `embedding vector(384)` (index HNSW), `tsv tsvector` (colonne générée, index GIN) |
| `form` | offre, fichier d'origine, format, statut (`not_started`/`in_review`/`ready`) |
| `field` | formulaire, section, ordre, libellé, nature (`text`/`number`/`date`/`yes_no`/`signature`), localisateur (JSONB) |
| `answer` | champ, valeur, candidats JSONB `[{value, quote, chunk_id, valid_until, valid_until_quote}]`, type (`auto`/`missing`/`manual`/`outdated`/`conflict`/`declaration`), `user_only` + raison, état, `resolved_by`, `resolved_at` |
| `fill_event` | formulaire, numéro de séquence, type (`phase`/`field`/`done`/`error`), données JSONB |

### Recherche hybride
- **Vecteurs** : `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions, local) → pgvector, distance cosinus.
- **Plein texte** : `tsvector` anglais + `ts_rank_cd`. Il ne s'agit pas d'un vrai BM25, mais c'est natif et suffisant à cette taille ; l'extension `pg_search` (BM25) reste une option si le rappel est insuffisant.
- **Fusion** : Reciprocal Rank Fusion des deux listes, top k par champ. Le plein texte rattrape les UID, numéros de police et noms propres ; les vecteurs rattrapent les reformulations.

### Remplissage
- Tâche asyncio dans le processus, une section à la fois. Chaque champ validé écrit son `answer` puis un `fill_event`.
- SSE : renvoie les événements depuis `Last-Event-ID`, puis attend les nouveaux (`asyncio.Queue`). Reprise possible après rechargement.
- **Appel LLM par section** : champs de la section, passages retrouvés par champ (top k, dédoublonnés), « Tender details ». Sortie contrainte par un outil Claude au schéma strict, température 0. Par champ : candidats avec citation, date de validité avec citation, `user_only` + raison, ou `not_found`.

### Validateur (pur)
- La citation doit se trouver dans le texte du passage (espaces et césures tolérés).
- La valeur doit figurer dans la citation après normalisation (nombres `100'000` = `100000`, dates, casse).
- Un Oui/Non n'est coché qu'avec une citation de preuve vérifiée.
- Échec → candidat rejeté ; plus aucun candidat → `not_found`.

### Règles (pures, dans cet ordre)
1. Signature ou cachet → jamais rempli.
2. `user_only` (classé par le LLM avec une raison) → `manual`, valeur pré-écrite possible (ville du siège, date du jour).
3. Au moins deux candidats valides aux valeurs normalisées différentes → `conflict`, le plus récent pré-sélectionné.
4. Date de validité dépassée → `outdated`.
5. `yes_no` avec preuve → `declaration` cochée ; sans preuve → `missing`.
6. Puis groupes, ordre de la file, compteurs et blocage d'export.

### Parsing et export
- **PDF** : parsing des suites de `…`/`.` avec PyMuPDF, libellé à gauche ou au-dessus, une section. Export : effacement des pointillés de la zone, texte dans le rectangle, police réduite si débordement.
- **DOCX** : python-docx, une section par tableau ; cellule libellé + cellule vide → champ ; colonnes Oui/Non → `yes_no`. Export : écriture dans la cellule avec le style du paragraphe, croix dans la bonne case Oui/Non.

### Tests back (pytest)
- **Parseurs** sur les vrais formulaires : `FormSchema` obtenu = schéma attendu, écrit à la main et relu.
- **Validateur et règles** : tests unitaires, un cas par critère générique.
- **Exporteurs** : réouverture du fichier exporté, valeurs aux bons endroits, reste identique à l'original (texte et structure).
- **API et job** avec `TestClient` + `FakeLLM` sur une base PostgreSQL de test (`formpilot_test`, créée et migrée par la fixture de session, tables vidées entre les tests) : séquence SSE, `PATCH` pendant le remplissage, reprise, blocage d'export.
- **Rappel de la recherche** (sans LLM) : pour chaque valeur de `GROUND_TRUTH.md`, le passage qui la contient doit être dans le top k. Protège contre les faux « introuvable ».

**Tests `slow`.** Les tests qui chargent le modèle d'embeddings (rappel de la recherche, ingestion réelle) sont marqués `@pytest.mark.slow` :
- exclus par défaut (`addopts = "-m 'not slow'"` dans `pyproject.toml`) ;
- lancés avec `make test-slow` (`pytest -m slow`) ou `make test-all` ;
- premier lancement : téléchargement du modèle (~100 Mo) dans `~/.cache/fastembed`, puis hors ligne ;
- les autres tests utilisent un embedder factice déterministe (vecteurs dérivés d'un hash du texte) pour ne jamais dépendre du modèle.
- Documenté aussi dans le README (étape 9).
