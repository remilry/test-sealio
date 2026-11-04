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
│ llm/            façade + adaptateurs (OpenAI, Fake)                   │
│ core/db         PostgreSQL + pgvector ; fichiers sur disque           │
└──────────────────────────────────────────────────────────────────────┘
data/ (ignoré par git) : uploads, exports. Seed au démarrage : tenant, offre, 2 formulaires. La base de connaissances n'est pas seedée : l'utilisateur y ajoute les documents (ceux de la démo sont dans `knowledge-base/documents/`)
```

| Sujet | Décision |
|---|---|
| Dépôt | Monorepo `frontend/` (pnpm) + `backend/` (uv), lancement `make dev`. Docker Compose uniquement pour PostgreSQL (image `pgvector/pgvector`) ; front et back tournent en local |
| Base de données | PostgreSQL + pgvector. Toutes les tables ont `created_at` et `updated_at` |
| Source de vérité | Le back : état des champs, fichiers, règles. Next.js = UI seule (pas de routes API) |
| Contrat | Modèles Pydantic → OpenAPI → `openapi-typescript` → types TS |
| Communication | REST + SSE (remplissage). Corrections utilisateur en `PATCH` pendant le flux ; `DELETE /forms/{id}/fill` abandonne le remplissage (réponses de l'utilisateur comprises) |
| Remplissage | Job asyncio côté back, événements persistés → SSE rejouable (rechargement), écrans de repli sur le même modèle |
| LLM | OpenAI `gpt-5-mini` (décision 2026-11-04, Claude auparavant) via une façade `llm/` (`generate_structured`) ; aucun autre module n'importe le SDK. **Un appel par section** du formulaire, lu en flux (`on_partial`) : événement SSE par champ, publié dès que le modèle l'a complet |
| Recherche | RAG hybride dans PostgreSQL : vecteurs (`fastembed` local + pgvector) + plein texte (`tsvector`), fusion des rangs (RRF). Passages = document + page + rectangle |
| Fiabilité | Le LLM renvoie toutes les valeurs candidates avec leurs citations exactes, ou rien. Le code vérifie chaque citation et chaque valeur, détecte les conflits (valeurs normalisées divergentes) et la péremption (date de validité renvoyée avec sa citation, comparée à aujourd'hui). Plus aucun candidat vérifié → `missing` |
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
│  ├─ knowledge-base/    knowledge-base.{api,queries}.ts · DocumentTable · UploadDocuments · useDocuments
│  ├─ tender/            tender.{api,queries}.ts (useTenders, useTender) · TenderHeader · FormList · SetupDialog
│  ├─ fill-session/      fill-session.{api,queries}.ts (useFormDetail, useFillState, useSaveAnswer ; SSE à l'étape 5) · SaveIndicator
│  ├─ review-queue/      ReviewQueue · FilterChips · FieldCard/{Auto,NotFound,Manual,
│  │                     Outdated,Conflict,Declaration} · useReviewKeyboard
│  ├─ document-preview/  DocumentPreview · renderers/{pdf,docx} · FieldOverlay · locator.ts
│  ├─ source-viewer/     source-viewer.{api,queries}.ts · SourceView
│  └─ form-export/       form-export.{api,queries}.ts · ExportDialog (résumé, champs vides, téléchargement)
│
├─ shared/
│  ├─ api/               client.ts (initialisation du client HTTP typé) · schema.gen.ts (généré)
│  ├─ ui/                composants shadcn, StatusBadge, tokens de couleur
│  ├─ components/        composants partagés hors shadcn (LoadStates : EmptyState, LoadError)
│  ├─ i18n/              next-intl : config (langues, fuseau), request.ts, messages/en.json (tous les textes)
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
4. Couche de données (skill `frontend-data-layer`) : chaque feature a son `[feature].api.ts` (types et appels HTTP) et son `[feature].queries.ts` (query keys et hooks `useXxx`, seuls à appeler TanStack Query) ; les composants n'utilisent que ces hooks (règle ESLint `no-restricted-imports`). `shared/api` ne contient que l'initialisation du client et les types générés.
5. `document-preview` est générique : il reçoit `{id, locator, value, tone}` et émet `onSelect(id)`.
6. Style (skill `frontend-code-style`) : early return dans les fonctions et composants, pas de ternaires imbriqués (`no-nested-ternary`) : sous-composant ou fonction nommée à la place.
7. Textes (skill `frontend-i18n`) : aucun texte en dur, tout passe par next-intl (`useTranslations`, messages dans `shared/i18n/messages`) ; règle ESLint `react/jsx-no-literals`. Anglais seulement pour l'instant.

### État
- **Données serveur** : cache TanStack Query (seule source côté front). Le flux SSE met à jour ce cache (`setQueryData`) ; les éditions partent en `PATCH` optimiste (« ✓ Saved »).
- **État d'interface** : local à l'écran. Sur *Live fill*, `LiveFillProvider` (Context limité à l'écran) porte `selectedFieldId`, le filtre et l'onglet Form/Source, partagés par la file et l'aperçu. Pas de store global.
- **Flux SSE** : lu avec `fetch` + `eventsource-parser` (pas d'`EventSource`, absent de Node / jsdom, et `Last-Event-ID` est géré à la main pour la reconnexion avec attente croissante). Chaque événement `answered` est appliqué au cache des réponses.
- **Progression** : fonction pure `fillProgress(phase, réponses reçues, temps écoulé, durée estimée)` ; le composant d'affichage garde un maximum atteint pour que la barre ne recule pas lors d'une reconnexion (le flux rejoue le run).
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
- **Playwright** : un seul test, le scénario principal, avec le vrai back en mode `FakeLLM`, dans un environnement dédié et propre à chaque lancement (base `formpilot_e2e` recréée, données vidées, ports 8100/3100, build `.next-e2e`) : jamais la base ni les serveurs de dev.

## 3. Architecture back

### Stack
Python 3.14 · FastAPI (SSE natif `fastapi.sse`) · SQLAlchemy 2.1 + psycopg 3 · Alembic (migrations) · PostgreSQL + pgvector · `fastembed` · SDK OpenAI (dans `llm/` uniquement) · PyMuPDF · python-docx · pytest · uv, ruff, pyright.

### Arborescence (modules métier)

```
backend/
├─ app/
│  ├─ main.py                 # FastAPI : routers ; au démarrage, migrations + seed (tenant, offre, 2 formulaires)
│  ├─ core/                   # config (pydantic-settings), db (engine, session, Base + TimestampMixin), erreurs
│  ├─ llm/                    # façade : Protocol LLM.generate_structured(LLMRequest) → modèle Pydantic
│  │  ├─ openai_adapter.py
│  │  └─ fake_adapter.py      # FakeLLM rejoue llm_recordings/<clé>.json (tests, e2e) · RecordingLLM
│  └─ modules/
│     ├─ knowledge/           router · service · models
│     │  ├─ extraction/       pdf.py (PyMuPDF : texte + rectangles) · docx.py
│     │  ├─ chunking.py       passages = doc + page + rectangle + texte
│     │  └─ index.py          vecteurs (pgvector) + plein texte (tsvector), fusion RRF → retrieve()
│     ├─ tenants/             service (dépendance `CurrentTenantId`) · models
│     ├─ tenders/             router · service · models
│     ├─ forms/               router · service · models
│     │  └─ parsing/          pdf_parser.py · docx_parser.py → FormSchema (pur)
│     ├─ filling/             router (lancer, SSE, PATCH champ) · service · models
│     │  ├─ job.py            orchestration des 5 phases, émet les événements
│     │  ├─ answer_engine.py  section → retrieve par champ → prompt → appel LLM
│     │  ├─ llm_schema.py     sortie structurée attendue du LLM
│     │  ├─ validator.py      vérification des citations et des valeurs (pur)
│     │  └─ rules.py          type de réponse ; groupe, ordre, blocage d'export à l'étape 6 (pur)
│     └─ export/              router · pdf_exporter.py · docx_exporter.py (purs)
├─ migrations/                # Alembic
└─ tests/                     même arborescence que app/ + fixtures
```

**Règles de dépendance**
- Un module n'expose aux autres que son `service.py`.
- Seul `answer_engine` (et le routeur, pour injecter le modèle) importe `llm/` ; seul `llm/` importe le SDK OpenAI.
- Les briques critiques sont **pures** (données en entrée, données en sortie, ni base ni réseau) : `parsing/`, `validator`, `rules`, `*_exporter`.

### Modèle de données (PostgreSQL)

Schéma actuel, généré depuis les modèles : [`DB_SCHEMA.md`](DB_SCHEMA.md) (`make db-schema` ; un test échoue s'il n'est pas à jour). Le tableau ci-dessous décrit aussi les tables à venir.

**Multi-tenant.** Les données de référence (offre, formulaires, champs détectés) viennent d'une source externe et sont partagées par tous les tenants (entreprises soumissionnaires). Ce qu'un tenant produit porte son `tenant_id`, directement ou via son remplissage : base de connaissances, `form_fill` et ses réponses. Plusieurs tenants remplissent le même formulaire ; dans un tenant, les collègues partagent le même remplissage. Sans connexion pour l'instant, chaque requête agit pour le tenant configuré (`FORMPILOT_CURRENT_TENANT`, seedé au démarrage) : la dépendance `CurrentTenantId` est le seul endroit à changer avec une vraie authentification.

Toutes les tables héritent d'un `TimestampMixin` : `created_at` (`timestamptz`, `server_default now()`) et `updated_at` (`timestamptz`, mis à jour à chaque modification par l'ORM).

| Table | Champs principaux |
|---|---|
| `tenant` | slug (unique), nom. L'entreprise soumissionnaire |
| `tender` | titre, référence, autorité, échéance. Sert aussi de source « Tender details » |
| `document` | tenant, nom, fichier, format, pages (nul pour un DOCX), statut (`processing`/`indexed`/`error`), message d'erreur, `indexed_at` |
| `chunk` | document, position, page, rectangle, texte (cité tel quel), contexte (titre du document + section, cherché mais jamais cité), `embedding vector(384)` (index HNSW), `tsv tsvector` (colonne générée sur contexte + texte, index GIN) |
| `form` | offre, fichier d'origine, format, pages. Partagé par tous les tenants |
| `field` | formulaire, section, ordre, libellé, nature (`text`/`number`/`date`/`yes_no`/`signature`), localisateur (JSONB) |
| `form_fill` | tenant, formulaire (unique ensemble), statut (`not_started`/`in_review`/`ready`), dernier remplissage IA (`ai_status` `running`/`done`/`failed`, `ai_started_at`, `ai_finished_at`). Créé à la première réponse ou au premier remplissage |
| `answer` | remplissage, champ (unique ensemble), valeur, candidats JSONB `[{value, citations: [{quote, document_name, document_id, chunk_id, page}], source_date, valid_until}]` (sélectionné en premier ; dates avec leur citation), type (`auto`/`missing`/`manual`/`outdated`/`conflict`/`declaration`, nul si jamais traité par l'IA), raison `user_only`, `needs_review`, `resolved_by`, `resolved_at` |
| `fill_event` | remplissage, id croissant (= id SSE), type (`phase`/`field`/`done`/`error`), données JSONB. Événements du dernier remplissage seulement |

### Recherche hybride
- **Vecteurs** : `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dimensions, local) → pgvector, distance cosinus.
- **Plein texte** : `tsvector` anglais + `ts_rank_cd`. Il ne s'agit pas d'un vrai BM25, mais c'est natif et suffisant à cette taille ; l'extension `pg_search` (BM25) reste une option si le rappel est insuffisant.
- **Fusion** : Reciprocal Rank Fusion des deux listes, top k par champ. Le plein texte rattrape les UID, numéros de police et noms propres ; les vecteurs rattrapent les reformulations.

### Remplissage
- Tâche de fond (`BackgroundTasks`, thread) dans le processus, une section à la fois. Chaque champ validé écrit son `answer` puis un `fill_event`, commité aussitôt. Les champs fixés par l'utilisateur ne sont pas redemandés, et l'upsert de l'IA ne remplace jamais une valeur de l'utilisateur, même enregistrée pendant le remplissage.
- SSE : renvoie les événements depuis `Last-Event-ID`, puis lit la base toutes les 250 ms jusqu'à la fin du run (plus simple qu'une `asyncio.Queue` entre threads, et identique après un rechargement). Un run resté `running` au démarrage du serveur passe `failed`.
- **Streaming** : la façade accepte `on_partial` (sortie partielle à chaque delta, dans l'ordre) ; l'adaptateur OpenAI lit le flux de la Responses API. Le moteur passe `on_field` : dès qu'un champ est complet dans la sortie partielle, il est validé, ses règles appliquées, son `answer` écrit et son événement émis, sans attendre la fin de la section ; ce qui reste à la fin est traité comme avant. `FakeLLM` rejoue les mêmes étapes en dormant d'après le bloc `timing` des enregistrements (`first_output_seconds`, `total_seconds`), selon `FORMPILOT_FAKE_LLM_LATENCY` (`recorded` par défaut, `none` dans les tests et l'e2e).
- **Abandon** : `DELETE /forms/{id}/fill` supprime les réponses et le run ; un run en cours s'en aperçoit (plus de `form_fill`) et s'arrête sans rien écrire. `POST /fill` répond 409 sur un formulaire commencé.
- **Appel LLM par section** : champs de la section, passages retrouvés par champ (top 8, dédoublonnés, étiquetés `P1…`), « Tender details ». Sortie structurée au schéma strict (`responses.parse`), effort de raisonnement bas. Par champ : candidats avec une ou plusieurs citations, date de la source et fin de validité avec citation, `user_only` + raison + valeur suggérée, ou rien.
- Enregistrement : `scripts/record_llm.py` rejoue le moteur avec le vrai modèle en flux et écrit `backend/llm_recordings/<formulaire>--<section>.json` (réponse + bloc `timing` mesuré), que `FakeLLM` rejoue (clé stable : le prompt dépend de l'embedder).

### Validateur (pur)
- La citation doit se trouver dans le texte d'un passage envoyé, l'étiqueté d'abord (seuls lettres et chiffres comparés : casse, accents, espaces, ponctuation et césures tolérés).
- Chaque mot et nombre significatif de la valeur doit figurer dans ses citations vérifiées après normalisation (nombres `100'000` = `100,000` = `100000`, dates, accents, casse) : une valeur peut combiner plusieurs citations.
- Un Oui/Non n'est coché qu'avec une citation de preuve vérifiée. Une date n'est gardée que si sa citation l'énonce.
- Échec → citation ou candidat rejeté ; plus aucun candidat → `missing`.

### Règles (pures, dans cet ordre)
1. Signature ou cachet → jamais rempli.
2. `user_only` (classé par le LLM avec une raison) → `manual`, valeur suggérée écrite (ville du siège, date du jour), à revoir.
3. Au moins deux candidats valides aux valeurs normalisées différentes → `conflict`, le plus récent pré-sélectionné.
4. Date de validité dépassée → `outdated`.
5. `yes_no` avec preuve → `declaration` cochée ; sans preuve → `missing`.
6. Une valeur → `auto` ; aucune → `missing`. Puis (étape 6) groupes, ordre de la file et blocage d'export.

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
