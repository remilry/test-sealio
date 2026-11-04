# Plan général — AI form filler

> Document vivant. Chaque étape y est cochée et détaillée au fur et à mesure.
> Contexte produit et priorités : voir `CLAUDE.md`. Échéance : jeudi 5 novembre.
> Statut : étapes 0 à 4.5 faites ; étape 5 découpée en 5a–5d, 5a et 5b mergées ; 5c (moteur IA back) implémentée sur sa branche, à valider. Parcours détaillé : `docs/USER_FLOW.md`. Les choix techniques marqués _proposition_ restent à confirmer à l'étape 3.

## 1. Ce qu'on a appris des deux formulaires

| | Annex 4 (DOCX) | Annex 7 (PDF) |
|---|---|---|
| Contenu | Questionnaire de ~45 champs : identité, forme juridique, capital, effectifs, assurances, offices fiscal/AVS/LPP, 17 questions Oui/Non, remarques, pièces jointes (extrait RC, extrait poursuites) | 1 page : projet, autorité adjudicatrice, identité du soumissionnaire, déclaration sanctions Ukraine (art. 29c), lieu/date, nom, signature |
| Structure technique | 7 tableaux Word, **aucun content control ni case à cocher** : les réponses vont dans des cellules vides à côté d'un libellé | **Pas de champs AcroForm** (PDF « à plat ») : les réponses sont des pointillés `……` à remplacer par du texte superposé |
| Difficulté d'export | Écrire dans la bonne cellule/run en conservant styles et mise en page | Calculer les coordonnées (x, y) de chaque zone, superposer le texte sans déborder |
| Difficulté IA | Champs factuels (UID, capital, assurance) **et** déclarations juridiques Oui/Non engageantes | Peu de faits, mais une déclaration légale à ne jamais « deviner » |

Conséquences :
- Il n'y a **pas de schéma de champs prêt à l'emploi** : la première brique est un _parseur_ qui produit une représentation commune (liste de champs : id, libellé, type, position dans le fichier source).
- Les questions Oui/Non sont des **déclarations engageantes** : cochées par l'IA seulement avec une preuve vérifiée et toujours visible, modifiables ; sans preuve, elles restent vides pour l'humain. Signature et cachet ne sont jamais remplis (décision 2026-11-03).
- Certains champs ne se trouvent dans aucun document (nom du projet, autorité adjudicatrice, lieu/date, signature) : ce sont des champs « saisie utilisateur ».

## 2. Principes directeurs (déduits de `CLAUDE.md`)

1. **Parcours utilisateur d'abord**, puis fiabilité IA, puis fidélité de l'export.
2. **Aucune réponse inventée** : chaque réponse = valeur + source (document, passage) + niveau de confiance, ou bien « non trouvé ».
3. **Humain dans la boucle** là où ça compte : l'IA remplit tout ce qu'elle peut prouver ; l'humain ne traite que les doutes (conflits, sources périmées) et les champs sans valeur, et peut tout modifier. Aucune règle propre à un formulaire : critères génériques uniquement (voir `docs/USER_FLOW.md` §4).
4. **Format d'origine** : DOCX ressorti en DOCX, PDF ressorti en PDF.
5. **Tests sur le critique** : parsing, validation des réponses, export.
6. Petits pas, un commit par pas, pas de fonctionnalité secondaire avant que le flux de bout en bout marche.

## 3. Étapes

Légende : ⬜ à faire · 🟦 en cours · ✅ fait. Chaque étape produit un livrable dans le repo.

### Étape 0 — Cadrage ✅
- Lire les formulaires, écrire ce plan, valider les décisions ouvertes (section 5).
- Livrable : `docs/PLAN.md` validé (2026-11-02).

### Étape 1 — Entreprise fictive et base de connaissances ✅ (validée)
- Inventer le soumissionnaire : une société suisse crédible dans les services de transformation digitale / IA (cohérent avec l'appel d'offres de l'Annex 4), fiche d'identité complète (raison sociale, UID, forme juridique, siège, capital, actionnariat, effectifs par catégorie, certifications, assurances, offices fiscal/AVS/LPP, contact).
- Produire des **documents réalistes**, dans des formats variés, c'est ce qui rend la démo crédible : extrait du registre du commerce, attestation d'assurance RC, plaquette de présentation, rapport annuel / comptes, certificats (ISO 27001…), règlement du personnel, etc.
- Y mettre volontairement des **pièges** pour tester la fiabilité : une info absente (→ « non trouvé »), deux documents contradictoires ou une donnée périmée (→ conflit signalé), une réponse Oui/Non non documentée (→ question à l'humain).
- Livrable : `knowledge-base/documents/` (11 documents PDF/DOCX, générés par `knowledge-base/generator/generate.py`) + `knowledge-base/GROUND_TRUTH.md` (valeurs attendues, statuts, pièges) servant de référence aux tests. Entreprise : **Alpenlogic AG**.

### Étape 2 — Parcours utilisateur ✅ (validée)
- Flux : Company knowledge → Tender (offre fictive avec les 2 formulaires) → Setup → **Live fill** (l'IA remplit sous les yeux de l'utilisateur, qui corrige en parallèle) → Export. *AI filling* + *Review* en repli technique.
- Livrable : `docs/USER_FLOW.md` + maquettes Claude Design `docs/design/Formpilot.dc.html`.

### Étape 3 — Architecture ✅ (validée)
- Choix de la stack, découpage en modules, modèle de données, contrats entre modules, stratégie de test. Pistes en section 6.
- Livrable : `docs/ARCHITECTURE.md` (+ décisions consignées).

### Principe : tranches verticales
Chaque étape à partir de la 4 livre une **fonctionnalité utilisable de bout en bout** : UI + API + logique + tests. Il n'y a plus d'étape « UI à la fin ». Chaque tranche se termine par :
- des tests unitaires sur le critique (parsing, validation, export) ;
- un test de bout en bout navigateur (Playwright) qui rejoue le parcours de la tranche sur les vrais formulaires ;
- une démo manuelle possible en une commande.

### Étape 4 — Socle + premier écran *Tender* (front + back) ✅
- Repo, outillage (lint, tests, `make dev` en une commande), Docker Compose PostgreSQL + pgvector, skills d'agent.
- L'offre et ses annexes sont déjà présentes : dans le produit elles viennent d'une source externe, ici seedées au démarrage depuis `forms/` (copie dans `data/`).
- Back : tables `tender` / `form`, API `GET /tenders`, `GET /tenders/{id}`, `GET /forms/{id}/file`.
- Front : barre latérale, écran *Tender* (en-tête, échéance au format suisse, cartes des formulaires avec format et statut) ; « Fill with AI » visible mais désactivé jusqu'à l'écran *Setup*. Utilitaires partagés : `shared/utils/date.ts`, `useHandleKeyDown`.
- Tests : API (pytest), écrans *Tender* / accueil / coquille (Vitest + MSW), scénario Playwright contre le vrai back.
- Mergé dans `main` le 2026-11-03.

### Étape 4.5 — Annex 7 de bout en bout, sans IA ✅
- Parcours : *Tender* → « Fill with AI » (ouvre l'écran de remplissage ; *Setup* viendra devant à l'étape 5) → champs détectés affichés sur l'aperçu → saisie à la main → *Export* (modale) → téléchargement du PDF rempli.
- **Parseur PDF générique** (`forms/parsing/pdf_parser.py`, pur) : pointillés `…`/`.` (libellé avant, à gauche sur la même ligne de base, ou au-dessus) et cases de tableau vides tracées par des filets (valeur à droite du libellé). Libellé « signature/stamp » → `signature`. Annex 7 : 10 champs dont 1 signature. Parsé à l'import (seed) : table `field` (localisateur JSONB : page, rectangle, ligne de base, taille de police, pointillés à effacer), `form.parsed_at` et `form.pages`. L'Annex 4 (DOCX) n'a pas encore de parseur : carte sans compteurs, « Fill with AI » désactivé.
- **Saisie** : table `answer` minimale (valeur, `resolved_by`, `resolved_at` ; colonnes IA à l'étape 5). `PATCH /forms/{id}/fields/{fieldId}` renvoie l'état complet (réponses + compteurs) ; 422 sur une signature ; le formulaire passe *In review* à la première valeur.
- **Export** (`export/pdf_exporter.py`, pur) : pointillés des champs remplis supprimés (redaction du texte seulement), valeur écrite sur la ligne de base du libellé, police réduite si elle déborde (plancher 5 pt). `GET /forms/{id}/export` (résumé : champs vides, à signer à la main) et `/export/file` (nom de fichier d'origine).
- **Front** : écran *Live fill* manuel (liste des champs, sauvegarde auto en quittant le champ ou sur Entrée, « ✓ Saved », compteur, aperçu `react-pdf` avec zones synchronisées, clavier ↑↓/j/k/Entrée) et *Export* en modale au-dessus du formulaire (bandeau champs vides, rappel signature, téléchargement PDF ; le résumé attend la sauvegarde en cours).
- Tests : parseur (schéma attendu de l'Annex 7 + PDF synthétiques), exporteur (valeurs dans leur rectangle, pointillés effacés seulement pour les champs remplis, reste de la page identique), API (pytest) ; écrans *Live fill* (export inclus) / *Tender* (Vitest, `react-pdf` remplacé par un stub) ; scénario Playwright jusqu'au téléchargement (vérifié aussi sur build de production).
- Limites connues : une valeur trop longue même à 5 pt déborde de sa zone ; le statut *Ready* n'est pas encore posé (étape 6).

### Étape 5 — Base de connaissances + réponse IA sur l'Annex 7 🟦 _(critique, testé)_
- UI : écran « base de connaissances » (documents de l'entreprise fictive, état d'ingestion) ; bouton « Remplir avec l'IA » ; chaque champ pré-rempli affiche sa **source** (document + passage) et un état (répondu / introuvable).
- Back : ingestion et recherche, réponse en sortie structurée, **validation stricte** (citation vérifiée mécaniquement, format du champ), `not_found` valide.
- Tests : validateur sans appel LLM, jeu de questions avec réponses attendues dont des « doit répondre introuvable », e2e du parcours.
- Découpée en 4 sous-étapes, chacune sur sa branche et validée avant la suivante (décision 2026-11-04).

#### 5a — Base de connaissances et recherche hybride ✅ (mergée le 2026-11-04)
- Back : module `knowledge`, tables `document` (tenant, nom, format, pages, statut `processing`/`indexed`/`error`, message d'erreur, `indexed_at`) et `chunk` (page, rectangle, texte, contexte, `embedding vector(384)` HNSW, `tsv` généré GIN).
- Extraction pure : PDF → blocs PyMuPDF avec page et rectangle ; DOCX → paragraphes (titres repérés) et lignes de tableau. Fichier illisible ou sans texte → statut `error` avec un message pour l'utilisateur.
- Découpage pur en passages : une page et une section par passage, ~800 caractères max, sans couper un bloc ; contexte = titre du document + titre de section (cherché, jamais cité).
- Embeddings : `fastembed` (`bge-small-en-v1.5`, cache `~/.cache/fastembed`) ; embedder factice déterministe (`FORMPILOT_EMBEDDER=hash`) pour les tests rapides.
- `search()` : vecteurs (cosinus) + plein texte (n'importe quel mot de la requête, `ts_rank_cd`), fusion RRF, filtrée par tenant et documents indexés.
- Seed : les 11 documents de `knowledge-base/documents/` indexés au démarrage (idempotent). _Retiré le 2026-11-04 : la base de connaissances démarre vide, voir le journal._ API `GET /knowledge`, `GET /knowledge/documents/{id}/file`.
- Front : écran *Company knowledge* (entreprise, nombre de documents, dernière indexation, tableau type / nom / pages / date d'ajout / statut, erreur affichée, téléchargement par ligne) ; clic sur un document → aperçu en modale (pages du PDF via `PdfViewer` de `document-preview`, bouton *Download* ; DOCX : message « pas encore d'aperçu » + téléchargement), entrée dans la barre latérale, carte *Company knowledge* sur l'écran *Tender* (nombre de documents, *Manage*).
- Tests : extraction et découpage (vrais documents + cas synthétiques), API, recherche (identifiant, tri, isolation des tenants), écran *Knowledge* et carte (Vitest), scénario Playwright étendu. Test `slow` de rappel avec le vrai modèle : pour chaque section des formulaires, les passages trouvés pour ses champs contiennent chaque valeur attendue de `GROUND_TRUTH.md` (mesure par section car l'IA répond section par section ; deux libellés seuls, « Legal form since » et « Main activity », ne trouvent pas leur passage en top 8).

#### 5b — Ajout et suppression de documents ✅ (mergée le 2026-11-04)
- Back : `POST /knowledge/documents` (multipart, plusieurs fichiers) → 202 avec les documents en `processing`, indexation en tâche de fond (`BackgroundTasks`, une transaction par document). Tout ou rien : un fichier non PDF/DOCX, vide ou de plus de 20 Mo refuse la requête (422, message pour l'utilisateur). Un fichier du même nom remplace le document existant (passages supprimés, réindexé, « ajouté » maintenant). Échec inattendu → `error` avec un message générique. Au démarrage, les documents restés `processing` (serveur arrêté) sont réindexés en arrière-plan. `DELETE /knowledge/documents/{id}` (204) supprime le document, ses passages (cascade) et son fichier ; un document supprimé pendant son indexation est ignoré.
- Front : bouton *Add documents* (sélecteur PDF/DOCX, plusieurs fichiers) ou glisser-déposer : zone de dépôt toujours visible en petits pointillés (« Drop PDF or Word documents here, or browse your files »), en dessous de la liste quand il y a des documents, à la place de l'écran vide sinon ; on peut aussi déposer n'importe où sous la barre du haut, la zone s'allume pendant le survol (« Release to add them »), seuls les fichiers réagissent (`FileDropArea` générique dans `shared/components`) ; les documents apparaissent aussitôt en tête en `Processing` (« Reading and indexing… »), la liste se rafraîchit chaque seconde tant qu'un document est en cours, puis `Indexed` ou `Error` avec la raison, sans recharger la page. Refus du back affiché tel quel (422), autre échec en mots simples, bandeau fermable. Corbeille par ligne → confirmation (« Delete {name}? », irréversible) → la ligne disparaît aussitôt, revient avec un bandeau si la suppression échoue.
- Tests : API d'ajout et de suppression (succès, plusieurs fichiers, illisible, remplacement, refus, taille, échec inattendu, reprise au démarrage, suppression, 404 / autre tenant, suppression pendant l'indexation) ; écran *Knowledge* (Processing → Indexed, → Error, plusieurs fichiers, refus, échec serveur, sélecteur, suppression : confirmer, annuler, échec ; glisser-déposer : zone sous la liste, zone = écran vide, dépôt, sortie sans dépôt, texte ignoré — seul usage permis de `fireEvent`, user-event ne sachant pas glisser des fichiers) ; e2e : ré-ajout d'un document existant sous son nom (remplacement, Processing → Indexed).
- Limite des tests front : sous jsdom + Vitest, un handler MSW ne peut pas lire un corps multipart construit avec des `File` jsdom (le fetch échoue) ; le handler vérifie donc le type de contenu, et les fichiers eux-mêmes sont vérifiés par les tests back et l'e2e.

#### 5c — Moteur de réponse IA (back) 🟦 (implémentée, en attente de validation et de l'enregistrement des vraies réponses)
- **Façade LLM** (`app/llm/`) : `generate_structured(LLMRequest[T]) -> T` (modèle Pydantic en sortie). Adaptateur **OpenAI** (`gpt-5-mini`, Responses API `responses.parse`, schéma strict, effort de raisonnement `low`, `store=False`) ; `FakeLLM` qui rejoue des réponses par **clé stable** (`<formulaire>--<section>`, pas le prompt, qui dépend de l'embedder) depuis `backend/llm_recordings/*.json` ; `RecordingLLM` + `scripts/record_llm.py` pour enregistrer les vraies réponses (base de dev, vrai modèle d'embeddings). Seul `app/llm/` importe le SDK `openai` ; le SDK Anthropic est retiré. Sans clé : 503 clair au lancement.
- **Moteur** (`filling/answer_engine.py`) : un appel par section ; pour chaque champ (hors signature et hors champs déjà fixés par l'utilisateur), recherche hybride top 8 sur son libellé, passages dédoublonnés et étiquetés `P1…`, « Tender details » (titre, référence, autorité, procédure, échéance) en `P1`. Le modèle renvoie par champ : candidats (valeur, une ou plusieurs citations exactes, date de la source et fin de validité avec citation), ou `user_only` + raison + valeur suggérée, ou rien.
- **Validateur** (pur) : citation cherchée dans le passage étiqueté puis dans les autres passages envoyés (lettres et chiffres seulement : casse, accents, espaces, ponctuation, césures tolérés) ; chaque mot et nombre significatif de la valeur doit figurer dans ses citations vérifiées (normalisation `100'000` = `100,000`, dates écrites de toutes les façons usuelles, accents) ; Oui/Non seulement avec citation de preuve ; une date n'est gardée que si sa citation l'énonce ; même valeur de plusieurs sources = un candidat avec toutes ses preuves.
- **Règles** (pures) : signature jamais remplie ; `user_only` → `manual` (valeur suggérée écrite, à revoir) ; ≥ 2 valeurs → `conflict`, la plus récente sélectionnée et placée en premier ; fin de validité dépassée → `outdated` ; Oui/Non prouvé → `declaration` cochée ; sinon `auto` ou `missing`. `needs_review` pour missing, manual, conflict, outdated.
- **Job** (`filling/job.py`, tâche de fond) : `POST /forms/{id}/fill` (202 ; 409 si déjà en cours ; 422 si le formulaire n'est pas lisible) ; 5 phases + un événement `field` par champ (`searching` puis `answered` avec la réponse et les compteurs), `done` ou `error`, persistés dans `fill_event` et commités un par un. `GET /forms/{id}/fill/events` (SSE) rejoue depuis `Last-Event-ID` puis lit la base toutes les 250 ms jusqu'à la fin du run. Une réponse fixée par l'utilisateur, avant ou pendant le remplissage, n'est jamais remplacée (upsert conditionnel). Au démarrage, un run resté `running` passe `failed` avec un message.
- Données : `answer` + `type`, `candidates` (JSONB), `user_only_reason`, `needs_review` ; `form_fill` + `ai_status` / `ai_started_at` / `ai_finished_at` ; table `fill_event`. `FillState` expose `ai_run` et `counts.doubts`.
- Tests : validateur (citations, valeurs composées, normalisation, Oui/Non, dates, fusion) et règles (un cas par règle) sans LLM ; API et job avec un `FakeLLM` scripté sur les vrais documents de démo (réponse sourcée, Tender details, introuvable, citation inventée rejetée, manuel, signature jamais envoyée, prompt, phases et événements, reprise `Last-Event-ID`, flux en direct, valeur utilisateur gardée avant et pendant, double lancement, échec du modèle, panne inattendue, interruption serveur, pas de clé) ; façade (rejeu, enregistrement).
- Reste à faire : enregistrer les vraies réponses de l'Annex 7 (`uv run python -m scripts.record_llm --add-demo-documents`, clé dans `backend/.env`), les relire, puis ajouter un test qui rejoue l'enregistrement réel.

#### 5d — Remplissage IA dans l'UI ⬜
- *Setup* (modale), *Live fill* en flux, source par champ (document, page, citation), état répondu / introuvable, e2e du parcours. Cartes Conflit / Périmé dans l'UI aux étapes 6–7.

### Étape 6 — Relecture et humain dans la boucle ⬜ _(testé)_
- UI : relecture champ par champ avec source visible/cliquable, édition, validation individuelle ou en lot, tri par priorité (introuvables, conflits, déclarations engageantes).
- Règles (voir `docs/USER_FLOW.md` §4) : export autorisé avec bandeau listant champs vides et doutes ; seule une déclaration Oui/Non sans réponse bloque l'export.
- Tests : règles de blocage, e2e « corriger une réponse puis exporter ».

### Étape 7 — Annex 4 (DOCX) de bout en bout ⬜ _(critique, testé)_
- Parsing des tableaux Word (libellés, cellules, types texte / Oui-Non / nombre), export dans les cellules en préservant la mise en page, avec la même UI que l'Annex 7.
- Aperçu des documents Word de la base de connaissances (`docx-preview`) dans la modale de *Company knowledge* et dans la vue *Source*.
- Cas difficiles de la base de connaissances : donnée absente, documents contradictoires, extrait périmé, déclarations Oui/Non non documentées.
- Tests : parseur (schéma attendu), export (réouverture du DOCX, valeurs aux bons endroits, reste intact, comparaison visuelle par rendu), e2e complet.

### Étape 8 — Durcissement ⬜
- Erreurs et cas limites (fichier illisible, API indisponible, formulaire inconnu), états de chargement, messages clairs.
- Évaluation de la qualité IA sur la vérité terrain : taux de bonnes réponses, de « introuvable » correct, zéro invention.

### Étape 9 — Livrables ⬜
- README : installation, lancement, choix techniques, limites connues, section **« Remaining features »**.
- Mise à jour de `CLAUDE.md` (état du projet).

### Si le temps le permet
- Réutilisation inter-formulaires (mémoriser les corrections), support d'autres formats, historique/versions, métriques de qualité.

## 4. Parcours utilisateur

Détaillé dans `docs/USER_FLOW.md` (validé le 2026-11-03).

## 5. Décisions prises et questions ouvertes

**Décidé (2026-11-02)**
- **Stack** : Next.js (front) + FastAPI (back, Python).
- **LLM** : Claude ou OpenAI, à trancher plus tard. Le code passe par une **façade** (interface unique, un adaptateur par fournisseur) pour changer de modèle par simple configuration.
- **Langue** : tout en anglais (UI, documents de la base, entreprise fictive).
- **Entreprise fictive** : PME IT/IA du canton de Zurich, ~40 employés.
- **Base de connaissances** : documents PDF et DOCX, générés par nous.
- **Ordre des étapes** : conservé pour l'instant, révisable.

**Encore ouvert (à traiter à l'étape concernée)**
- ~~Fournisseur LLM final~~ → Claude (2026-11-03), puis OpenAI `gpt-5-mini` (2026-11-04).
- Rigueur de la comparaison visuelle à l'export : seuil d'image ou vérification structurelle seulement (étape 4/7).

## 6. Pistes d'architecture (_propositions à discuter à l'étape 3_)

```
UI (relecture)  ──►  API locale
                      ├─ form-parser      DOCX/PDF → schéma de champs
                      ├─ knowledge-base   ingestion + index + retrieve()
                      ├─ answer-engine    retrieve + LLM + validation + règles « humain »
                      └─ exporter         schéma + réponses + fichier d'origine → fichier rempli
```

- **Séparation nette** : parseur, moteur de réponse et exporteur communiquent uniquement par des structures de données explicites (schéma de formulaire, réponse sourcée), donc testables isolément et sans appel LLM.
- **Façade LLM** : une interface (`generate_structured(prompt, schema)`) avec un adaptateur Claude et un adaptateur OpenAI, choisis par configuration ; aucun autre module n'importe un SDK fournisseur.
- **Persistance minimale** : fichiers + SQLite ou JSON local ; pas d'authentification.
- **Pipeline par champ** avec états (`pending → proposed → needs_review → approved`) pour que l'UI puisse tout afficher.
- **Fiabilité par construction** : sortie structurée du LLM, citation obligatoire, vérification mécanique de la citation, `not_found` comme réponse valide de premier rang.
- Bibliothèques candidates : `python-docx` (édition DOCX), `pdfplumber`/`PyMuPDF` (texte + coordonnées PDF, superposition).

## 7. Journal des décisions

| Date | Décision | Statut |
|---|---|---|
| 2026-11-02 | Plan général rédigé | validé |
| 2026-11-02 | Tranches verticales : UI + tests e2e dans chaque étape, walking skeleton sur l'Annex 7 d'abord | validé |
| 2026-11-02 | Stack Next.js + FastAPI ; façade LLM interchangeable (Claude/OpenAI à trancher) ; tout en anglais ; entreprise PME IT/IA zurichoise ~40 pers. ; base en PDF + DOCX | validé |
| 2026-11-02 | Entreprise fictive Alpenlogic AG validée ; assureur fictif « Limmat Versicherungen AG » (pas de vraie marque) ; 11 documents générés | validé |
| 2026-11-02 | Documents de la base rendus réalistes (papier à en-tête, références, pagination, tableaux, historiques, contenus hors sujet) ; distracteurs consignés dans GROUND_TRUTH.md | validé |
| 2026-11-02 | Étape 1 validée par l'utilisateur | validé |
| 2026-11-03 | Parcours basé sur les maquettes Claude Design ; écran principal *Live fill*, *AI filling* + *Review* en repli technique ; une offre fictive contenant les 2 formulaires | validé |
| 2026-11-03 | Déclarations Oui/Non cochées automatiquement quand une preuve est trouvée (preuve visible, modifiable) ; vides sinon | validé |
| 2026-11-03 | Export autorisé avec avertissement (champs vides, doutes) ; bloqué seulement par une déclaration sans réponse ; format d'origine uniquement | validé |
| 2026-11-03 | Aucune règle propre à un formulaire ou un champ : l'IA juge avec des critères génériques (preuve, conflit, péremption, champ réservé à l'utilisateur) | validé |
| 2026-11-03 | Remember answers, audit trail, résolution de conflit dans la base, sources « previous submissions » → Remaining features | validé |
| 2026-11-03 | Archi globale : monorepo `frontend/` (Next.js, client seul) + `backend/` (FastAPI, source de vérité), REST + SSE, types TS générés depuis l'OpenAPI, remplissage en job back avec événements persistés, SQLite + fichiers, `FakeLLM` pour des tests déterministes | validé |
| 2026-11-03 | LLM : Claude (via la façade) ; un appel par section du formulaire, événement SSE par champ | validé |
| 2026-11-03 | RAG (pour passer à l'échelle) : embeddings locaux (fastembed) + recherche hybride BM25/vecteurs dans SQLite (`sqlite-vec`) ; « introuvable » formulé honnêtement | validé |
| 2026-11-03 | Archi front : `app → screens → features → shared`, `api.ts` par feature, `shared/api` = init client + types générés, pas d'import entre features (par défaut), TanStack Query sans store global, `docx-preview` + `react-pdf` ; tests Vitest par écran (skill `screen-tests`) + 1 Playwright scénario principal | validé |
| 2026-11-03 | Archi back : modules métier (`knowledge`, `tenders`, `forms`, `filling`, `export`) + `llm/` ; briques critiques pures ; champs `user_only` classés par le LLM ; tests chargeant le modèle d'embeddings marqués `slow` | validé |
| 2026-11-03 | PostgreSQL + pgvector (remplace SQLite), recherche hybride conservée (pgvector + `tsvector`, fusion RRF) ; Docker Compose pour Postgres seulement ; `created_at` / `updated_at` sur toutes les tables | validé |
| 2026-11-03 | V1 sans extraction de faits à l'ingestion (coût) : *Company knowledge* liste les documents ; conflits et péremption détectés au remplissage (date de validité renvoyée par le LLM avec citation vérifiée) | validé |
| 2026-11-03 | Étape 4, setup front : Node 26 LTS (`.nvmrc`), pnpm 12, Next 16.4 (défauts create-next-app : Turbopack, Cache Components, AGENTS.md), shadcn/ui preset `base-nova` (Base UI), MSW 3 ; règles de modules vérifiées par `eslint-plugin-boundaries` ; skills `next-dev-loop`, `shadcn`, `vercel-react-best-practices`, `vercel-composition-patterns` + MCP `next-devtools` | validé |
| 2026-11-03 | Étape 4, setup back : Python 3.14 (3.15 bloqué par onnxruntime/fastembed), uv, FastAPI 0.162 avec SSE natif (pas de `sse-starlette`), SQLAlchemy 2.1, PostgreSQL 18 + pgvector 0.8.7 (`docker-compose.yml`), migrations Alembic au démarrage, base `formpilot_test` pour pytest ; SQLAlchemy et pyright conservés malgré le skill FastAPI (SQLModel, ty en bêta) ; skills `fastapi`, `uv`, `pydantic`, `supabase-postgres-best-practices` ; `make dev` lance db + back + front | validé |
| 2026-11-03 | Pas de dépôt des formulaires par l'utilisateur : l'offre et ses annexes viennent d'une source externe (seed au démarrage depuis `forms/`, copie dans `data/`) ; première page = *Tender* | validé |
| 2026-11-03 | Étape 4 recentrée sur le socle + premier écran *Tender* (front + back), mergée dans `main` ; parsing, saisie manuelle et export de l’Annex 7 déplacés en étape 4.5 | validé |
| 2026-11-03 | Étape 4.5 : « Fill with AI » ouvre directement l'écran de remplissage (Setup ajouté à l'étape 5) ; écran *Export* minimal dès cette étape ; dans les cases de tableau, la valeur s'écrit à droite du libellé | validé |
| 2026-11-03 | Étape 4.5 : parseur PDF générique (pointillés + cases vides), formulaires parsés à l'import, table `answer` minimale (étendue à l'étape 5), export par suppression des pointillés + texte sur la ligne de base | validé |
| 2026-11-04 | *Export* en modale au-dessus de *Live fill* au lieu d'une page (flux plus léger ; une page pourra revenir si nécessaire) | validé |
| 2026-11-04 | Multi-tenant anticipé : table `tenant` ; formulaires et champs partagés ; un `form_fill` par (tenant, formulaire) porte le statut et les réponses (les collègues d'un tenant partagent le même) ; tenant courant via la dépendance `CurrentTenantId` (tenant seedé tant qu'il n'y a pas d'authentification) ; données existantes migrées vers le tenant de démo | validé |
| 2026-11-04 | Schéma de la base généré depuis les modèles SQLAlchemy dans `docs/DB_SCHEMA.md` (Mermaid, `make db-schema`), un test vérifie qu'il est à jour | validé |
| 2026-11-04 | Étape 4.5 validée et mergée dans `main` | validé |
| 2026-11-04 | Étape 5 découpée en 5a (base de connaissances + recherche), 5b (upload), 5c (moteur IA back), 5d (UI de remplissage IA), une branche et une validation par sous-étape ; LLM Claude Sonnet 5.5, réponses réelles enregistrées pour le `FakeLLM` ; règles génériques pures dès 5c, cartes Conflit / Périmé plus tard | validé |
| 2026-11-04 | i18n front avec next-intl (sans routage par langue : locale fixe `en`, compatible Cache Components) ; tous les textes dans `shared/i18n/messages/en.json`, clés typées, pluriels ICU ; ESLint `react/jsx-no-literals` ; anglais seulement pour l'instant | validé |
| 2026-11-04 | 5a : passages d'une page et d'une section (~800 car.) avec contexte titre + section ; plein texte en « n'importe quel mot » ; rappel mesuré par section du formulaire ; cache du modèle dans `~/.cache/fastembed` | validé |
| 2026-11-04 | Documents de la base gardés tels quels, défauts compris (`&amp;` dans la plaquette, noms tirés des fichiers) : un cas réel en aura aussi | validé |
| 2026-11-04 | *Company knowledge* : clic sur un document = aperçu en modale (PDF), téléchargement toujours possible ; aperçu DOCX à l'étape 7 | validé |
| 2026-11-04 | Étape 5a validée et mergée dans `main` | validé |
| 2026-11-04 | 5b : ajout tout ou rien (PDF/DOCX, ≤ 20 Mo) ; même nom de fichier = remplacement du document ; indexation en tâche de fond, rafraîchissement de la liste chaque seconde tant qu'un document est `processing` ; reprise des documents `processing` au démarrage | validé |
| 2026-11-04 | Glisser-déposer de fichiers sur toute la page *Company knowledge* ; `fireEvent` autorisé dans les tests d'écran uniquement pour glisser des fichiers (skill `screen-tests`) | validé |
| 2026-11-04 | Suppression d'un document depuis *Company knowledge* (corbeille, confirmation, suppression définitive du fichier et des passages) ; zone de dépôt sous la liste | validé |
| 2026-11-04 | Étape 5b validée et mergée dans `main` | validé |
| 2026-11-04 | Plus de seed de la base de connaissances (ni au démarrage, ni pour la démo, ni pour l'e2e) : l'utilisateur ajoute les documents ; le scénario Playwright dépose les 11 documents de démo au début ; les tests back qui en ont besoin les ajoutent via une fixture | validé |
| 2026-11-04 | LLM : **OpenAI `gpt-5-mini`** au lieu de Claude (clé ajoutée par l'utilisateur dans `backend/.env`), toujours derrière la façade ; modèle configurable (`FORMPILOT_LLM_MODEL`) | validé |
| 2026-11-04 | 5c : un candidat peut avoir plusieurs citations, chaque mot et nombre significatif de la valeur doit figurer dans ses citations vérifiées (valeurs composées comme « Alpenlogic AG, company limited by shares (AG) ») | validé |
| 2026-11-04 | 5c : champ réservé à l'utilisateur = type `manual`, valeur suggérée écrite dans le formulaire (exportée si gardée) et signalée à revoir | validé |
| 2026-11-04 | 5c : un nouveau remplissage IA ne remplace jamais une valeur fixée par l'utilisateur (avant ou pendant le remplissage) ; le reste est recalculé | validé |
| 2026-11-04 | 5c : le LLM cite par texte exact, l'étiquette du passage n'est qu'un indice (citation cherchée dans tous les passages envoyés) ; enregistrements rejoués par clé formulaire + section ; date de la source par candidat (présélection du plus récent en conflit) ; SSE par lecture de la base toutes les 250 ms (pas d'`asyncio.Queue`) | proposé |
| 2026-11-04 | e2e dans un environnement dédié et propre : base `formpilot_e2e` supprimée et recréée à chaque lancement (script `scripts/reset_e2e.py`, refuse toute base dont le nom ne finit pas par `_e2e`), dossier `data-e2e/` vidé, back :8100 et front :3100 jamais réutilisés, build Next dans `.next-e2e` (le serveur de dev n'est pas touché) | validé |
