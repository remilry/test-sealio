# Plan général — AI form filler

> Document vivant. Chaque étape y est cochée et détaillée au fur et à mesure.
> Contexte produit et priorités : voir `CLAUDE.md`. Échéance : jeudi 5 novembre.
> Statut : étapes 0 à 2 validées. Parcours détaillé : `docs/USER_FLOW.md`. Les choix techniques marqués _proposition_ restent à confirmer à l'étape 3.

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

### Étape 3 — Architecture ⬜
- Choix de la stack, découpage en modules, modèle de données, contrats entre modules, stratégie de test. Pistes en section 6.
- Livrable : `docs/ARCHITECTURE.md` (+ décisions consignées).

### Principe : tranches verticales
Chaque étape à partir de la 4 livre une **fonctionnalité utilisable de bout en bout** : UI + API + logique + tests. Il n'y a plus d'étape « UI à la fin ». Chaque tranche se termine par :
- des tests unitaires sur le critique (parsing, validation, export) ;
- un test de bout en bout navigateur (Playwright) qui rejoue le parcours de la tranche sur les vrais formulaires ;
- une démo manuelle possible en une commande.

### Étape 4 — Walking skeleton (Annex 7 de bout en bout, sans IA) ⬜
- Repo git, outillage (lint, tests, lancement local en une commande).
- Parcours minimal complet : déposer l'Annex 7 (PDF) → champs détectés affichés → l'utilisateur les saisit à la main → export du PDF rempli → téléchargement.
- C'est volontairement la partie la plus risquée (parsing PDF à plat + superposition de texte) : on la valide en premier, avec l'UI en place dès le départ.
- Tests : parseur PDF (schéma attendu), export (texte au bon endroit, reste inchangé), e2e du parcours.

### Étape 5 — Base de connaissances + réponse IA sur l'Annex 7 ⬜ _(critique, testé)_
- UI : écran « base de connaissances » (documents de l'entreprise fictive, état d'ingestion) ; bouton « Remplir avec l'IA » ; chaque champ pré-rempli affiche sa **source** (document + passage) et un état (répondu / introuvable).
- Back : ingestion et recherche, réponse en sortie structurée, **validation stricte** (citation vérifiée mécaniquement, format du champ), `not_found` valide.
- Tests : validateur sans appel LLM, jeu de questions avec réponses attendues dont des « doit répondre introuvable », e2e du parcours.

### Étape 6 — Relecture et humain dans la boucle ⬜ _(testé)_
- UI : relecture champ par champ avec source visible/cliquable, édition, validation individuelle ou en lot, tri par priorité (introuvables, conflits, déclarations engageantes).
- Règles (voir `docs/USER_FLOW.md` §4) : export autorisé avec bandeau listant champs vides et doutes ; seule une déclaration Oui/Non sans réponse bloque l'export.
- Tests : règles de blocage, e2e « corriger une réponse puis exporter ».

### Étape 7 — Annex 4 (DOCX) de bout en bout ⬜ _(critique, testé)_
- Parsing des tableaux Word (libellés, cellules, types texte / Oui-Non / nombre), export dans les cellules en préservant la mise en page, avec la même UI que l'Annex 7.
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
- Fournisseur LLM final et disponibilité d'une clé API (étape 3/5).
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
